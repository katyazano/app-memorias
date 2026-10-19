import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db
from app.models import Invoice, Payment, PaymentType, Project
from app.schemas import (
    CustomMemoryPayload,
    MemoryReportResponse,
    MemorySummary,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.number_to_words import numero_a_letras_mxn
from app.services.pdf_compiler import generate_memoria_pdf, render_memoria_html
from app.services.s3_service import generate_presigned_url

router = APIRouter(prefix="/projects", tags=["Proyectos / Projects"])

SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def _format_spanish_date(d: date) -> str:
    month_name = SPANISH_MONTHS.get(d.month, "")
    return f"{d.day} de {month_name} de {d.year}"


def _compile_memory_data(
    project: Project,
    start_date: date,
    end_date: date,
    memoria_number: str = "01",
    location: str = "Zapopan, Jalisco",
) -> Dict[str, Any]:
    """
    Agrupa los movimientos por categoría contable (Transferencias, Facturas/Efectivo, Rayas)
    y efectúa los cálculos financieros de honorarios (10%) e IVA (16%) idénticos a la plantilla oficial.
    """
    # 1. Separar pagos por categoría
    transferencias = [
        p for p in project.payments
        if p.payment_type in (PaymentType.BANK_TRANSFER, "bank_transfer", PaymentType.BANK_TRANSFER.value)
    ]
    rayas = [
        p for p in project.payments
        if p.payment_type in (PaymentType.PAYROLL, "payroll", PaymentType.PAYROLL.value)
    ]
    notas_efectivo = [
        p for p in project.payments
        if p.payment_type in (PaymentType.MANUAL_NOTE, "manual_note", PaymentType.MANUAL_NOTE.value)
    ]

    # Facturas y notas en efectivo se consolidan para la sección azul
    notas_facturas = list(project.invoices) + notas_efectivo

    # 1. Base Subtotals
    subtotal_transferencias = sum((p.amount for p in transferencias), Decimal("0.00"))
    subtotal_efectivo = sum((i.amount for i in project.invoices), Decimal("0.00")) + sum((p.amount for p in notas_efectivo), Decimal("0.00"))
    subtotal_rayas = sum((p.amount for p in rayas), Decimal("0.00"))

    # 2. Architectural Billing Logic
    honorarios = round((subtotal_transferencias + subtotal_efectivo + subtotal_rayas) * Decimal("0.10"), 2)
    subtotal_factura_arquitecto = subtotal_rayas + honorarios
    iva = round(subtotal_factura_arquitecto * Decimal("0.16"), 2)

    importe_factura_arquitecto = subtotal_factura_arquitecto + iva
    total_a_reembolsar = importe_factura_arquitecto + subtotal_efectivo
    gran_total_obra = subtotal_transferencias + total_a_reembolsar

    # 3. Expresión de montos en letras
    monto_honorarios_en_letras = numero_a_letras_mxn(importe_factura_arquitecto)
    monto_gran_total_en_letras = numero_a_letras_mxn(gran_total_obra)
    date_formatted = _format_spanish_date(end_date)

    # 4. Asignar URLs prefirmadas a facturas para enlaces S3
    for inv in project.invoices:
        if inv.pdf_s3_url and not inv.pdf_s3_url.startswith("http"):
            inv.pdf_s3_url = generate_presigned_url(inv.pdf_s3_url)

    summary = MemorySummary(
        subtotal_transferencias=subtotal_transferencias,
        subtotal_efectivo=subtotal_efectivo,
        subtotal_rayas=subtotal_rayas,
        honorarios=honorarios,
        subtotal_factura_arquitecto=subtotal_factura_arquitecto,
        iva=iva,
        importe_factura_arquitecto=importe_factura_arquitecto,
        total_a_reembolsar=total_a_reembolsar,
        gran_total_obra=gran_total_obra,
        monto_en_letras=monto_gran_total_en_letras,
        # Compatibilidad
        total_transferencias=subtotal_transferencias,
        total_notas_facturas=subtotal_efectivo,
        total_rayas=subtotal_rayas,
        total_gastos_directos=subtotal_transferencias + subtotal_efectivo + subtotal_rayas,
        total_honorarios=honorarios,
        subtotal_honorarios_rayas=subtotal_factura_arquitecto,
        iva_honorarios=iva,
        importe_honorarios_iva=importe_factura_arquitecto,
        gran_total=gran_total_obra,
        total_invoices_amount=sum((inv.amount for inv in project.invoices), Decimal("0.00")),
        total_payments_amount=sum((p.amount for p in project.payments), Decimal("0.00")),
        total_expenses=subtotal_transferencias + subtotal_efectivo + subtotal_rayas,
        invoices_count=len(project.invoices),
        payments_count=len(project.payments),
    )

    return {
        "project_id": project.id,
        "project_name": project.name,
        "client_name": project.client_name,
        "location": location,
        "memoria_number": memoria_number,
        "start_date": start_date,
        "end_date": end_date,
        "date_formatted": date_formatted,
        "summary": summary,
        "subtotal_transferencias": subtotal_transferencias,
        "subtotal_efectivo": subtotal_efectivo,
        "subtotal_rayas": subtotal_rayas,
        "honorarios": honorarios,
        "subtotal_factura_arquitecto": subtotal_factura_arquitecto,
        "iva": iva,
        "importe_factura_arquitecto": importe_factura_arquitecto,
        "total_a_reembolsar": total_a_reembolsar,
        "gran_total_obra": gran_total_obra,
        "transferencias": transferencias,
        "notas_facturas": notas_facturas,
        "rayas": rayas,
        "monto_honorarios_en_letras": monto_honorarios_en_letras,
        "monto_gran_total_en_letras": monto_gran_total_en_letras,
        "invoices": project.invoices,
        "payments": project.payments,
    }


# ==========================================
# 1. Endpoint: Resumen JSON de Memoria de Obra
# ==========================================
@router.get(
    "/{project_id}/memory",
    response_model=MemoryReportResponse,
    summary="Generar consolidado financiero de Memoria de Obra",
)
async def get_project_memory(
    project_id: uuid.UUID,
    start_date: date = Query(..., description="Fecha inicial del periodo (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Fecha final del periodo (YYYY-MM-DD)"),
    memoria_number: str = Query("01", description="Número consecutivo de memoria (ej. 01, 02)"),
    location: str = Query("Zapopan, Jalisco", description="Ubicación de la obra"),
    db: AsyncSession = Depends(get_db),
):
    """
    Agrega todas las facturas y los pagos correspondientes al proyecto dentro del
    rango de fechas especificado utilizando carga impaciente (eager loading).
    Calcula los subtotales de transferencias, notas y nómina, honorarios al 10% e IVA al 16%.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha inicial no puede ser posterior a la fecha final del periodo.",
        )

    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(
                Project.invoices.and_(
                    Invoice.date_issued >= start_date,
                    Invoice.date_issued <= end_date,
                )
            ).selectinload(Invoice.supplier),
            selectinload(
                Project.payments.and_(
                    Payment.date_paid >= start_date,
                    Payment.date_paid <= end_date,
                )
            ).selectinload(Payment.worker),
        )
    )

    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El proyecto con ID '{project_id}' no fue encontrado.",
        )

    data = _compile_memory_data(
        project=project,
        start_date=start_date,
        end_date=end_date,
        memoria_number=memoria_number,
        location=location,
    )

    return MemoryReportResponse(
        project_id=data["project_id"],
        project_name=data["project_name"],
        client_name=data["client_name"],
        location=data["location"],
        memoria_number=data["memoria_number"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        date_formatted=data["date_formatted"],
        summary=data["summary"],
        invoices=data["invoices"],
        payments=data["payments"],
    )


# ==========================================
# 2. Endpoint: Descarga de PDF de Memoria de Obra
# ==========================================
@router.get(
    "/{project_id}/memory/download",
    summary="Descargar el documento PDF compilado de la Memoria de Obra",
)
async def download_project_memory_pdf(
    project_id: uuid.UUID,
    start_date: date = Query(..., description="Fecha inicial del periodo (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Fecha final del periodo (YYYY-MM-DD)"),
    memoria_number: str = Query("01", description="Número consecutivo de memoria (ej. 01, 02)"),
    location: str = Query("Zapopan, Jalisco", description="Ubicación de la obra"),
    db: AsyncSession = Depends(get_db),
):
    """
    Genera el archivo binario PDF de la Memoria de Obra con diseño tipo Excel,
    formato horizontal Letter, paleta de colores oficial y cálculo de honorarios e IVA.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha inicial no puede ser posterior a la fecha final del periodo.",
        )

    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(
                Project.invoices.and_(
                    Invoice.date_issued >= start_date,
                    Invoice.date_issued <= end_date,
                )
            ).selectinload(Invoice.supplier),
            selectinload(
                Project.payments.and_(
                    Payment.date_paid >= start_date,
                    Payment.date_paid <= end_date,
                )
            ).selectinload(Payment.worker),
        )
    )

    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El proyecto con ID '{project_id}' no fue encontrado.",
        )

    data = _compile_memory_data(
        project=project,
        start_date=start_date,
        end_date=end_date,
        memoria_number=memoria_number,
        location=location,
    )

    pdf_bytes = generate_memoria_pdf(data)
    safe_project_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project.name)
    filename = f"Memoria_{memoria_number}_{safe_project_name}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


def _compile_custom_memory_data(
    project_id: uuid.UUID,
    project_name: str,
    client_name: str,
    payload: CustomMemoryPayload,
) -> Dict[str, Any]:
    """Compila datos para Jinja2 y PDF basados en una lista explícita de facturas y pagos seleccionados."""
    transferencias = [
        p for p in payload.payments
        if p.payment_type in (PaymentType.BANK_TRANSFER, "bank_transfer", PaymentType.BANK_TRANSFER.value)
    ]
    rayas = [
        p for p in payload.payments
        if p.payment_type in (PaymentType.PAYROLL, "payroll", PaymentType.PAYROLL.value)
    ]
    notas_efectivo = [
        p for p in payload.payments
        if p.payment_type in (PaymentType.MANUAL_NOTE, "manual_note", PaymentType.MANUAL_NOTE.value)
    ]

    notas_facturas = list(payload.invoices) + notas_efectivo

    subtotal_transferencias = sum((p.amount for p in transferencias), Decimal("0.00"))
    subtotal_efectivo = sum((i.amount for i in payload.invoices), Decimal("0.00")) + sum((p.amount for p in notas_efectivo), Decimal("0.00"))
    subtotal_rayas = sum((p.amount for p in rayas), Decimal("0.00"))

    honorarios = round((subtotal_transferencias + subtotal_efectivo + subtotal_rayas) * Decimal("0.10"), 2)
    subtotal_factura_arquitecto = subtotal_rayas + honorarios
    iva = round(subtotal_factura_arquitecto * Decimal("0.16"), 2)

    importe_factura_arquitecto = subtotal_factura_arquitecto + iva
    total_a_reembolsar = importe_factura_arquitecto + subtotal_efectivo
    gran_total_obra = subtotal_transferencias + total_a_reembolsar

    monto_honorarios_en_letras = numero_a_letras_mxn(importe_factura_arquitecto)
    monto_gran_total_en_letras = numero_a_letras_mxn(gran_total_obra)
    date_formatted = _format_spanish_date(payload.end_date)

    summary = MemorySummary(
        subtotal_transferencias=subtotal_transferencias,
        subtotal_efectivo=subtotal_efectivo,
        subtotal_rayas=subtotal_rayas,
        honorarios=honorarios,
        subtotal_factura_arquitecto=subtotal_factura_arquitecto,
        iva=iva,
        importe_factura_arquitecto=importe_factura_arquitecto,
        total_a_reembolsar=total_a_reembolsar,
        gran_total_obra=gran_total_obra,
        monto_en_letras=monto_gran_total_en_letras,
        total_transferencias=subtotal_transferencias,
        total_notas_facturas=subtotal_efectivo,
        total_rayas=subtotal_rayas,
        total_gastos_directos=subtotal_transferencias + subtotal_efectivo + subtotal_rayas,
        total_honorarios=honorarios,
        subtotal_honorarios_rayas=subtotal_factura_arquitecto,
        iva_honorarios=iva,
        importe_honorarios_iva=importe_factura_arquitecto,
        gran_total=gran_total_obra,
        total_invoices_amount=sum((inv.amount for inv in payload.invoices), Decimal("0.00")),
        total_payments_amount=sum((p.amount for p in payload.payments), Decimal("0.00")),
        total_expenses=subtotal_transferencias + subtotal_efectivo + subtotal_rayas,
        invoices_count=len(payload.invoices),
        payments_count=len(payload.payments),
    )

    return {
        "project_id": project_id,
        "project_name": project_name,
        "client_name": client_name,
        "location": payload.location,
        "memoria_number": payload.memoria_number,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "date_formatted": date_formatted,
        "summary": summary,
        "subtotal_transferencias": subtotal_transferencias,
        "subtotal_efectivo": subtotal_efectivo,
        "subtotal_rayas": subtotal_rayas,
        "honorarios": honorarios,
        "subtotal_factura_arquitecto": subtotal_factura_arquitecto,
        "iva": iva,
        "importe_factura_arquitecto": importe_factura_arquitecto,
        "total_a_reembolsar": total_a_reembolsar,
        "gran_total_obra": gran_total_obra,
        "transferencias": transferencias,
        "notas_facturas": notas_facturas,
        "rayas": rayas,
        "monto_honorarios_en_letras": monto_honorarios_en_letras,
        "monto_gran_total_en_letras": monto_gran_total_en_letras,
        "invoices": payload.invoices,
        "payments": payload.payments,
    }


@router.post(
    "/{project_id}/memory/compile",
    summary="Calcular resumen consolidado de memoria con selección personalizada",
)
async def compile_custom_memory(
    project_id: uuid.UUID,
    payload: CustomMemoryPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe la selección filtrada y personalizada de facturas y pagos (incluyendo externos de otras obras)
    y devuelve los totales financieros consolidados.
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El proyecto con ID '{project_id}' no fue encontrado.",
        )

    data = _compile_custom_memory_data(
        project_id=project.id,
        project_name=project.name,
        client_name=project.client_name,
        payload=payload,
    )
    return {
        "project_id": data["project_id"],
        "project_name": data["project_name"],
        "client_name": data["client_name"],
        "location": data["location"],
        "memoria_number": data["memoria_number"],
        "start_date": data["start_date"],
        "end_date": data["end_date"],
        "date_formatted": data["date_formatted"],
        "summary": data["summary"],
    }


@router.post(
    "/{project_id}/memory/download-custom",
    summary="Descargar PDF de memoria de obra con gastos seleccionados",
)
async def download_custom_memory_pdf(
    project_id: uuid.UUID,
    payload: CustomMemoryPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Genera el archivo binario PDF oficial de la Memoria de Obra conteniendo
    únicamente las facturas y pagos confirmados por el usuario.
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El proyecto con ID '{project_id}' no fue encontrado.",
        )

    data = _compile_custom_memory_data(
        project_id=project.id,
        project_name=project.name,
        client_name=project.client_name,
        payload=payload,
    )

    pdf_bytes = generate_memoria_pdf(data)
    safe_project_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project.name)
    filename = f"Memoria_{payload.memoria_number}_{safe_project_name}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ==========================================
# 3. CRUD Estándar de Proyectos
# ==========================================
@router.get(
    "/",
    response_model=List[ProjectResponse],
    summary="Listar todos los proyectos de obra",
)
async def list_projects(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Project)
        .offset(offset)
        .limit(limit)
        .order_by(Project.start_date.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo proyecto de obra",
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    project = Project(**payload.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Obtener información de un proyecto por ID",
)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado.",
        )
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Actualizar información del proyecto",
)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado para actualizar.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    await db.flush()
    await db.refresh(project)
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar proyecto",
)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado para eliminar.",
        )
    await db.delete(project)
