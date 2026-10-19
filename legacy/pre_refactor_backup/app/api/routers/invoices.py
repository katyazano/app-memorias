import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db
from app.models import Invoice, Project, Supplier
from app.schemas import InvoiceCreate, InvoiceResponse, InvoiceUpdate
from app.services.parser_service import extract_invoice_data as extract_pdf_data
from app.services.s3_service import generate_presigned_url, upload_file_to_s3
from app.services.xml_parser import extract_cfdi_xml

router = APIRouter(prefix="/invoices", tags=["Facturas / Invoices"])


def attach_presigned_url_to_invoice(invoice: Invoice) -> Invoice:
    """Convierte la clave de S3 almacenada en la base de datos en una URL prefirmada temporal."""
    if invoice.pdf_s3_url and not invoice.pdf_s3_url.startswith("http"):
        invoice.pdf_s3_url = generate_presigned_url(invoice.pdf_s3_url)
    return invoice


# =========================================================================
# 1. Endpoint: Subir y Extraer Facturas (Dual Workflow: XML + PDF Pair)
# =========================================================================
@router.post(
    "/upload",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Subir y extraer facturas (emparejando archivos XML y PDF en lote)",
)
async def upload_and_parse_invoices(
    files: List[UploadFile] = File(..., description="Archivos XML y PDF de las facturas"),
):
    """
    Flujo de extracción de alta precisión:
    1. Agrupa los archivos subidos por nombre base (ej. 'factura_01.xml' y 'factura_01.pdf').
    2. Si hay archivo XML, extrae los datos fiscales con precisión exacta (CFDI 4.0/3.3).
    3. Si hay archivo PDF, lo sube a AWS S3 privado y genera una URL prefirmada de visualización.
    4. Si solo se sube PDF, utiliza el extractor PDF de respaldo.
    5. Retorna la lista de diccionarios combinados para revisión en el frontend (sin guardar aún en BD).
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe subir al menos un archivo (XML o PDF).",
        )

    # 1. Agrupar archivos por su nombre base (sin extensión)
    # Ejemplo: 'INV_1001.xml' y 'INV_1001.pdf' comparten la clave 'inv_1001'
    file_groups: Dict[str, Dict[str, UploadFile]] = {}

    for file_item in files:
        filename = file_item.filename or "archivo"
        base_name, ext = os.path.splitext(filename)
        ext_clean = ext.lower().replace(".", "")
        group_key = base_name.strip().lower()

        if group_key not in file_groups:
            file_groups[group_key] = {}
        
        file_groups[group_key][ext_clean] = file_item

    parsed_results: List[Dict[str, Any]] = []

    for group_key, group_files in file_groups.items():
        xml_file = group_files.get("xml")
        pdf_file = group_files.get("pdf")

        # Variables de salida
        parsed_data: Dict[str, Any] = {}
        s3_object_key: str = ""
        presigned_view_url: Optional[str] = None
        source_filename: str = ""

        # --- A. Procesar PDF si está presente (Subida a S3) ---
        if pdf_file:
            source_filename = pdf_file.filename
            pdf_bytes = await pdf_file.read()
            if pdf_bytes:
                # Subir PDF a S3 de forma no bloqueante
                s3_object_key = await run_in_threadpool(
                    upload_file_to_s3,
                    pdf_bytes,
                    pdf_file.filename,
                )
                presigned_view_url = await run_in_threadpool(
                    generate_presigned_url,
                    s3_object_key,
                    3600,
                )

        # --- B. Extraer datos (Prioridad: XML exacto, Fallback: PDF) ---
        if xml_file:
            source_filename = source_filename or xml_file.filename
            xml_bytes = await xml_file.read()
            if xml_bytes:
                parsed_data = extract_cfdi_xml(xml_bytes)
        elif pdf_file and pdf_bytes:
            # Fallback: Solo subió PDF sin XML
            parsed_data = extract_pdf_data(file_bytes=pdf_bytes, filename=pdf_file.filename)

        if not parsed_data:
            continue

        # Normalizar comprobante/folio
        comprobante_val = (
            parsed_data.get("comprobante")
            or parsed_data.get("invoice_number")
            or f"CFDI-{uuid.uuid4().hex[:8].upper()}"
        )

        # Normalizar fecha evitando "None"
        fecha_raw = parsed_data.get("fecha") or parsed_data.get("date_issued")
        if not fecha_raw or str(fecha_raw).strip().lower() in ("none", "null", "", "nat"):
            fecha_str = str(date.today())
        else:
            fecha_str = str(fecha_raw).split("T")[0][:10]

        # Normalizar importe
        importe_raw = parsed_data.get("importe") if parsed_data.get("importe") is not None else parsed_data.get("amount")
        try:
            importe_num = float(importe_raw or 0.0)
        except (ValueError, TypeError):
            importe_num = 0.0

        # Normalizar concepto
        concepto_raw = parsed_data.get("concepto") or parsed_data.get("concept") or "Materiales / Servicios"
        if isinstance(concepto_raw, list):
            concepto_raw = ", ".join(str(x) for x in concepto_raw if x)
        concepto_str = str(concepto_raw)[:255]
        proveedor_raw = (
            parsed_data.get("proveedor")
            or parsed_data.get("supplier_name")
            or "PROVEEDOR GENERAL"
        )

        parsed_results.append({
            "comprobante": str(comprobante_val),
            "fecha": fecha_str,
            "importe": importe_num,
            "concepto": concepto_str,
            "proveedor": str(proveedor_raw),
            "s3_object_key": s3_object_key,
            "pdf_s3_url": presigned_view_url or s3_object_key,
            "is_parsed_automatically": True,
            "filename": source_filename,
            "has_xml": bool(xml_file),
            "has_pdf": bool(pdf_file),
        })

    if not parsed_results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo extraer información válida de los archivos subidos. Verifique que sean archivos XML CFDI o PDF válidos.",
        )

    return parsed_results


# =========================================================================
# 2. Endpoint: Guardado Masivo (Bulk Insert)
# =========================================================================
@router.post(
    "/bulk",
    response_model=List[InvoiceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Guardar lote de facturas validadas en una sola transacción",
)
async def create_invoices_bulk(
    invoices_data: List[InvoiceCreate],
    db: AsyncSession = Depends(get_db),
):
    """
    Guarda múltiples facturas validadas en la base de datos en una sola transacción atómica,
    resolviendo o dando de alta proveedores por su nombre de forma automática.
    """
    if not invoices_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista de facturas a guardar no puede estar vacía.",
        )

    project_ids = {inv.project_id for inv in invoices_data}
    for p_id in project_ids:
        project = await db.get(Project, p_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El proyecto con ID '{p_id}' no existe en el sistema.",
            )

    db_invoices: List[Invoice] = []
    # Caché local de proveedores en esta transacción para evitar duplicados
    supplier_cache: Dict[str, uuid.UUID] = {}

    for inv_schema in invoices_data:
        sup_id = inv_schema.supplier_id

        # Si no viene supplier_id, buscar o crear por supplier_name (proveedor)
        if not sup_id:
            s_name = (inv_schema.supplier_name or "PROVEEDOR GENERAL").strip()
            s_key = s_name.lower()
            if s_key in supplier_cache:
                sup_id = supplier_cache[s_key]
            else:
                stmt_s = select(Supplier).where(Supplier.name.ilike(s_name))
                res_s = await db.execute(stmt_s)
                existing_s = res_s.scalars().first()
                if existing_s:
                    sup_id = existing_s.id
                else:
                    new_s = Supplier(
                        name=s_name,
                        material_category="Materiales / Servicios",
                    )
                    db.add(new_s)
                    await db.flush()
                    await db.refresh(new_s)
                    sup_id = new_s.id
                supplier_cache[s_key] = sup_id

        db_inv = Invoice(
            project_id=inv_schema.project_id,
            supplier_id=sup_id,
            invoice_number=inv_schema.invoice_number,
            concept=inv_schema.concept,
            amount=inv_schema.amount,
            pdf_s3_url=inv_schema.pdf_s3_url,
            date_issued=inv_schema.date_issued,
            is_parsed_automatically=inv_schema.is_parsed_automatically,
        )
        db_invoices.append(db_inv)

    db.add_all(db_invoices)
    await db.flush()

    stmt = (
        select(Invoice)
        .where(Invoice.id.in_([inv.id for inv in db_invoices]))
        .options(selectinload(Invoice.supplier))
    )
    result = await db.execute(stmt)
    invoices = result.scalars().all()
    return [attach_presigned_url_to_invoice(inv) for inv in invoices]


# =========================================================================
# 3. CRUD Estándar para Facturas
# =========================================================================
@router.get(
    "/",
    response_model=List[InvoiceResponse],
    summary="Listar facturas registradas con URLs prefirmadas",
)
async def list_invoices(
    project_id: Optional[uuid.UUID] = None,
    supplier_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.supplier))
        .offset(offset)
        .limit(limit)
        .order_by(Invoice.date_issued.desc())
    )
    if project_id:
        stmt = stmt.where(Invoice.project_id == project_id)
    if supplier_id:
        stmt = stmt.where(Invoice.supplier_id == supplier_id)

    result = await db.execute(stmt)
    invoices = result.scalars().all()
    return [attach_presigned_url_to_invoice(inv) for inv in invoices]


@router.post(
    "/",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar factura individual manualmente",
)
async def create_invoice(
    payload: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, payload.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El proyecto con ID '{payload.project_id}' no fue encontrado.",
        )

    supplier = await db.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El proveedor con ID '{payload.supplier_id}' no fue encontrado.",
        )

    db_invoice = Invoice(**payload.model_dump())
    db.add(db_invoice)
    await db.flush()
    await db.refresh(db_invoice, attribute_names=["supplier"])
    return attach_presigned_url_to_invoice(db_invoice)


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Obtener detalle de factura por ID",
)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.supplier))
    )
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada.",
        )
    return attach_presigned_url_to_invoice(invoice)


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Actualizar campos de una factura",
)
async def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada para actualizar.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    await db.flush()
    await db.refresh(invoice, attribute_names=["supplier"])
    return attach_presigned_url_to_invoice(invoice)


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar factura",
)
async def delete_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada para eliminar.",
        )
    await db.delete(invoice)
