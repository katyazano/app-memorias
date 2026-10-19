"""Router para recepción, parseo, revisión, confirmación y descarga de facturas (CFDI XML + PDF)."""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Factura, Gasto, Obra, OrigenGasto, Proveedor
from app.routers.gastos import gasto_a_out
from app.schemas import (
    DuplicadoInfo,
    ErrorArchivo,
    FacturaConfirmarItem,
    FacturaLeida,
    FacturasConfirmar,
    GastoOut,
    ProveedorSugerido,
    SugeridoGasto,
    UploadFacturasOut,
)
from app.services.parser_service import extract_text_from_pdf_bytes
from app.services.storage import abs_path, commit_staged_file, new_staging_dir, staging_dir
from app.services.xml_parser import CfdiParseError, extract_cfdi_xml

router = APIRouter(tags=["Facturas"])

UUID_REGEX = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


@router.post("/obras/{obra_id}/facturas", response_model=UploadFacturasOut)
async def subir_facturas(
    obra_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    # 1. Separar archivos por tipo
    xml_files: List[Tuple[str, bytes]] = []
    pdf_files: List[Tuple[str, bytes]] = []

    for f in files:
        nombre = f.filename or "archivo"
        contenido = await f.read()
        nombre_lower = nombre.lower()
        if nombre_lower.endswith(".xml"):
            xml_files.append((nombre, contenido))
        elif nombre_lower.endswith(".pdf"):
            pdf_files.append((nombre, contenido))
        else:
            # Archivo ignorado o no soportado
            pass

    # Indexar PDFs por nombre base (stem) y por UUIDs encontrados en su texto
    pdfs_por_stem: Dict[str, Tuple[str, bytes]] = {}
    pdfs_por_uuid: Dict[str, Tuple[str, bytes]] = {}

    for pdf_nombre, pdf_bytes in pdf_files:
        stem = Path(pdf_nombre).stem.lower().strip()
        pdfs_por_stem[stem] = (pdf_nombre, pdf_bytes)

        # Buscar UUID en texto del PDF
        try:
            texto = extract_text_from_pdf_bytes(pdf_bytes)
            encontrados = UUID_REGEX.findall(texto)
            for u in encontrados:
                pdfs_por_uuid[u.lower()] = (pdf_nombre, pdf_bytes)
        except Exception:
            pass

    items: List[FacturaLeida] = []
    errores: List[ErrorArchivo] = []
    uuids_en_este_lote: set = set()
    pdfs_usados: set = set()

    for xml_nombre, xml_bytes in xml_files:
        # A) Parsear XML
        try:
            cfdi = extract_cfdi_xml(xml_bytes)
        except CfdiParseError as e:
            errores.append(
                ErrorArchivo(
                    archivo=xml_nombre,
                    codigo="xml_invalido",
                    detalle=str(e),
                )
            )
            continue
        except Exception as e:
            errores.append(
                ErrorArchivo(
                    archivo=xml_nombre,
                    codigo="error_lectura",
                    detalle=f"Error inesperado al leer XML: {str(e)}",
                )
            )
            continue

        # B) Validar duplicado dentro del mismo lote
        if cfdi.uuid in uuids_en_este_lote:
            errores.append(
                ErrorArchivo(
                    archivo=xml_nombre,
                    codigo="uuid_duplicado_lote",
                    detalle=f"El UUID {cfdi.uuid} está repetido dentro de los archivos subidos.",
                )
            )
            continue

        # C) Validar duplicado contra la BD
        factura_existente = db.query(Factura).filter(Factura.uuid == cfdi.uuid).first()
        if factura_existente:
            gasto_existente = factura_existente.gasto
            obra_existente = gasto_existente.obra if gasto_existente else None
            duplicado = DuplicadoInfo(
                gasto_id=gasto_existente.id if gasto_existente else 0,
                obra_id=obra_existente.id if obra_existente else 0,
                obra_nombre=obra_existente.nombre if obra_existente else "Desconocida",
                fecha=gasto_existente.fecha if gasto_existente else cfdi.fecha,
            )
            errores.append(
                ErrorArchivo(
                    archivo=xml_nombre,
                    codigo="uuid_duplicado",
                    detalle=f"La factura con UUID {cfdi.uuid} ya está registrada en la obra '{duplicado.obra_nombre}'.",
                    duplicado_de=duplicado,
                )
            )
            continue

        uuids_en_este_lote.add(cfdi.uuid)

        # D) Asociar PDF por stem o por UUID
        xml_stem = Path(xml_nombre).stem.lower().strip()
        matched_pdf: Optional[Tuple[str, bytes]] = None
        if xml_stem in pdfs_por_stem:
            matched_pdf = pdfs_por_stem[xml_stem]
        elif cfdi.uuid.lower() in pdfs_por_uuid:
            matched_pdf = pdfs_por_uuid[cfdi.uuid.lower()]

        # E) Guardar en carpeta temporal de staging
        token, s_path = new_staging_dir()
        xml_dest = s_path / "factura.xml"
        xml_dest.write_bytes(xml_bytes)

        pdf_dest_nombre: Optional[str] = None
        if matched_pdf:
            p_nombre, p_bytes = matched_pdf
            pdf_dest = s_path / "factura.pdf"
            pdf_dest.write_bytes(p_bytes)
            pdf_dest_nombre = p_nombre
            pdfs_usados.add(p_nombre)

        # F) Información sugerida de proveedor y gasto
        prov_existente = db.query(Proveedor).filter(Proveedor.rfc == cfdi.rfc_emisor).first()
        prov_sugerido = ProveedorSugerido(
            rfc=cfdi.rfc_emisor,
            razon_social=cfdi.nombre_emisor,
            existente_id=prov_existente.id if prov_existente else None,
            alias=prov_existente.alias if prov_existente else None,
        )

        sug_gasto = SugeridoGasto(
            fecha=cfdi.fecha,
            concepto_resumido=cfdi.concepto_sugerido,
            comprobante=cfdi.comprobante,
            metodo_pago=cfdi.metodo_pago_sugerido,
            proveedor_alias=prov_existente.alias if prov_existente else None,
            requiere_decision_metodo_pago=cfdi.requiere_decision_metodo_pago,
        )

        items.append(
            FacturaLeida(
                staging_id=token,
                archivo_xml=xml_nombre,
                archivo_pdf=pdf_dest_nombre,
                datos=cfdi.to_dict(),
                proveedor=prov_sugerido,
                sugerido=sug_gasto,
                requiere_decision_metodo_pago=cfdi.requiere_decision_metodo_pago,
            )
        )

    # Revisar si quedaron PDFs huérfanos sin XML asociado
    for pdf_nombre, _ in pdf_files:
        if pdf_nombre not in pdfs_usados:
            errores.append(
                ErrorArchivo(
                    archivo=pdf_nombre,
                    codigo="pdf_sin_xml",
                    detalle="No se encontró un archivo XML correspondiente para este PDF.",
                )
            )

    # Si no hubo items válidos y todos los errores fueron por duplicado, responder 409
    if not items and errores and all(e.codigo in ("uuid_duplicado", "uuid_duplicado_lote") for e in errores):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Todas las facturas subidas ya están registradas en el sistema.",
        )

    return UploadFacturasOut(items=items, errores=errores)


@router.post("/obras/{obra_id}/facturas/confirmar", response_model=List[GastoOut], status_code=status.HTTP_201_CREATED)
def confirmar_facturas(
    obra_id: int,
    data: FacturasConfirmar,
    db: Session = Depends(get_db),
):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    gastos_creados: List[Gasto] = []

    for item in data.items:
        try:
            s_path = staging_dir(item.staging_id)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"La carga temporal {item.staging_id} no existe o expiró. Por favor vuelve a subir el archivo.",
            )

        staged_xml = s_path / "factura.xml"
        if not staged_xml.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se encontró el archivo XML en el almacenamiento temporal.",
            )

        # Re-parsear el XML como única fuente de verdad
        try:
            cfdi = extract_cfdi_xml(staged_xml.read_bytes())
        except CfdiParseError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error al verificar XML en staging: {str(e)}",
            )

        # Verificar unicidad de UUID
        existente = db.query(Factura).filter(Factura.uuid == cfdi.uuid).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "codigo": "factura_duplicada",
                    "uuid": cfdi.uuid,
                    "obra_id": existente.gasto.obra_id if existente.gasto else 0,
                    "obra_nombre": existente.gasto.obra.nombre if (existente.gasto and existente.gasto.obra) else "",
                    "fecha": existente.gasto.fecha.isoformat() if existente.gasto else "",
                    "mensaje": f"La factura con UUID {cfdi.uuid} ya fue registrada previamente.",
                },
            )

        # Proveedor: buscar o crear
        prov = db.query(Proveedor).filter(Proveedor.rfc == cfdi.rfc_emisor).first()
        if not prov:
            razon = item.proveedor_razon_social.strip() if item.proveedor_razon_social else cfdi.nombre_emisor
            alias = item.proveedor_alias.strip() if item.proveedor_alias else None
            prov = Proveedor(rfc=cfdi.rfc_emisor, razon_social=razon, alias=alias)
            db.add(prov)
            db.flush()
        else:
            if item.proveedor_alias is not None:
                prov.alias = item.proveedor_alias.strip() if item.proveedor_alias else None
            if item.proveedor_razon_social:
                prov.razon_social = item.proveedor_razon_social.strip()
            db.flush()

        # Validar método de pago obligatorio
        if not item.metodo_pago:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Debe seleccionar un método de pago para la factura.",
            )

        # Crear Gasto
        fecha_gasto = item.fecha or cfdi.fecha
        concepto_gasto = (item.concepto_resumido.strip() if item.concepto_resumido else "") or cfdi.concepto_sugerido
        comprobante_gasto = (item.comprobante.strip() if item.comprobante else "") or cfdi.comprobante

        gasto = Gasto(
            obra_id=obra_id,
            fecha=fecha_gasto,
            proveedor_id=prov.id,
            concepto_resumido=concepto_gasto,
            comprobante=comprobante_gasto,
            tipo_comprobante="FACTURA",
            importe=cfdi.total,  # Total exacto del CFDI
            metodo_pago=item.metodo_pago,
            origen=OrigenGasto.XML,
        )
        db.add(gasto)
        db.flush()

        # Mover archivos de staging a almacenamiento permanente
        staged_pdf = s_path / "factura.pdf"
        rel_xml = commit_staged_file(staged_xml, obra_id, cfdi.uuid, "xml")
        rel_pdf = None
        if staged_pdf.exists():
            rel_pdf = commit_staged_file(staged_pdf, obra_id, cfdi.uuid, "pdf")

        # Limpiar directorio de staging de este item
        try:
            import shutil
            shutil.rmtree(s_path, ignore_errors=True)
        except Exception:
            pass

        # Crear registro de Factura
        factura = Factura(
            gasto_id=gasto.id,
            uuid=cfdi.uuid,
            serie=cfdi.serie,
            folio=cfdi.folio,
            subtotal=cfdi.subtotal,
            total=cfdi.total,
            rfc_emisor=cfdi.rfc_emisor,
            forma_pago_sat=cfdi.forma_pago,
            metodo_pago_sat=cfdi.metodo_pago_sat,
            ruta_xml=rel_xml,
            ruta_pdf=rel_pdf,
        )
        db.add(factura)
        db.flush()

        gastos_creados.append(gasto)

    return [gasto_a_out(g) for g in gastos_creados]


@router.get("/facturas/{gasto_id}/archivo/{tipo}")
def descargar_archivo_factura(gasto_id: int, tipo: str, db: Session = Depends(get_db)):
    if tipo not in ("xml", "pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo inválido. Debe ser 'xml' o 'pdf'.",
        )

    g = db.query(Gasto).filter(Gasto.id == gasto_id).first()
    if not g or not g.factura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada.")

    ruta_rel = g.factura.ruta_xml if tipo == "xml" else g.factura.ruta_pdf
    if not ruta_rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay archivo {tipo.upper()} asociado a esta factura.",
        )

    try:
        path = abs_path(ruta_rel)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ruta de archivo inválida.")

    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo no existe en disco.")

    media_type = "application/xml" if tipo == "xml" else "application/pdf"
    return FileResponse(path=path, media_type=media_type, filename=path.name)
