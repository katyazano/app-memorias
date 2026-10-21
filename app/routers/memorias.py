import logging
import re
import unicodedata
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Memoria, Obra
from app.schemas import MemoriaGuardar, MemoriaOut, PreviewIn, PreviewOut
from app.services.excel_service import generar_excel_memoria
from app.services.memoria_service import (
    cerrar_memoria,
    generar_preview,
    guardar_memoria,
    memoria_a_out,
    reabrir_memoria,
)
from app.services.pdf_service import (
    GeneracionPdfError,
    NavegadorNoEncontradoError,
    generar_pdf_memoria,
)

logger = logging.getLogger("app.memorias")
router = APIRouter(tags=["Memorias"])


@router.get("/memorias/verificar-folio")
def verificar_folio_factura(
    folio: str,
    excluir_memoria_id: int = None,
    db: Session = Depends(get_db),
):
    query = db.query(Memoria).filter(Memoria.folio_factura_arquitecto == folio.strip())
    if excluir_memoria_id:
        query = query.filter(Memoria.id != excluir_memoria_id)
    existente = query.first()
    if existente:
        obra_nom = existente.obra.nombre if existente.obra else f"Obra #{existente.obra_id}"
        return {
            "usado": True,
            "memoria_id": existente.id,
            "memoria_numero": existente.numero,
            "obra_nombre": obra_nom,
            "estado": existente.estado.value,
        }
    return {"usado": False}


@router.post("/obras/{obra_id}/memorias/preview", response_model=PreviewOut)
def previsualizar_memoria(
    obra_id: int,
    data: PreviewIn,
    db: Session = Depends(get_db),
):
    return generar_preview(
        db=db,
        obra_id=obra_id,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        fecha_emision=data.fecha_emision,
        ciudad=data.ciudad,
        gastos_extra_ids=data.gastos_extra_ids,
        rayas_extra_ids=data.rayas_extra_ids,
        numero=data.numero,
        porcentaje_honorarios=data.porcentaje_honorarios,
        seleccion=data.seleccion,
    )


@router.post("/memorias", response_model=MemoriaOut, status_code=status.HTTP_201_CREATED)
def crear_borrador_memoria(
    data: MemoriaGuardar,
    db: Session = Depends(get_db),
):
    memoria = guardar_memoria(db=db, data=data)
    return memoria_a_out(memoria)


@router.put("/memorias/{memoria_id}", response_model=MemoriaOut)
def actualizar_borrador_memoria(
    memoria_id: int,
    data: MemoriaGuardar,
    db: Session = Depends(get_db),
):
    memoria = guardar_memoria(db=db, data=data, memoria_id=memoria_id)
    return memoria_a_out(memoria)


@router.get("/memorias/{memoria_id}", response_model=MemoriaOut)
def obtener_memoria(memoria_id: int, db: Session = Depends(get_db)):
    memoria = db.query(Memoria).filter(Memoria.id == memoria_id).first()
    if not memoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoria no encontrada.")
    return memoria_a_out(memoria)


@router.post("/memorias/{memoria_id}/cerrar", response_model=MemoriaOut)
def cerrar_memoria_endpoint(memoria_id: int, db: Session = Depends(get_db)):
    memoria = cerrar_memoria(db=db, memoria_id=memoria_id)
    return memoria_a_out(memoria)


@router.post("/memorias/{memoria_id}/reabrir", response_model=MemoriaOut)
def reabrir_memoria_endpoint(memoria_id: int, db: Session = Depends(get_db)):
    memoria = reabrir_memoria(db=db, memoria_id=memoria_id)
    return memoria_a_out(memoria)


@router.get("/memorias/{memoria_id}/pdf")
def exportar_memoria_pdf(
    memoria_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    memoria = db.query(Memoria).filter(Memoria.id == memoria_id).first()
    if not memoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoria no encontrada.")
    obra = memoria.obra
    if not obra:
        obra = db.query(Obra).filter(Obra.id == memoria.obra_id).first()

    obra_nombre = (obra.nombre if obra else f"OBRA {memoria.obra_id}").strip()
    nombre_archivo = f"MEMORIA {memoria.numero:02d} - {obra_nombre}.pdf"
    nombre_archivo_limpio = re.sub(r'[\\/*?:"<>|]', "", nombre_archivo)

    base_url = str(request.base_url).rstrip("/")
    if "testserver" in base_url:
        import os
        base_url = os.environ.get("TEST_SERVER_URL", "http://127.0.0.1:8000")
    try:
        pdf_bytes = generar_pdf_memoria(memoria_id=memoria_id, base_url=base_url)
    except NavegadorNoEncontradoError as e:
        logger.error(f"Navegador no encontrado para PDF de memoria {memoria_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "mensaje": (
                    "No se encontró Microsoft Edge ni Google Chrome en el sistema para generar el PDF automáticamente. "
                    "Puedes abrir la versión imprimible y usar Ctrl + P para Guardar como PDF."
                ),
                "codigo": "navegador_no_encontrado",
                "rutas_probadas": e.rutas_probadas,
                "memoria_id": memoria_id,
            },
        )
    except GeneracionPdfError as e:
        logger.error(
            f"Fallo al ejecutar navegador ({e.navegador}) para PDF de memoria {memoria_id}: "
            f"salida={e.codigo_salida}, stderr={e.stderr}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "mensaje": f"El navegador se encontró ({e.navegador}) pero falló al generar el PDF: {e.detalle}",
                "codigo": "error_generacion_pdf",
                "navegador": e.navegador,
                "codigo_salida": e.codigo_salida,
                "stderr": e.stderr,
                "memoria_id": memoria_id,
            },
        )
    except RuntimeError as e:
        logger.error(f"Error de runtime al generar PDF para memoria {memoria_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "mensaje": f"Error al generar PDF con el navegador: {e}",
                "codigo": "error_runtime_pdf",
                "memoria_id": memoria_id,
            },
        )
    except Exception as e:
        logger.exception(f"Error inesperado al generar PDF para memoria {memoria_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "mensaje": f"Error inesperado al generar PDF: {e}",
                "codigo": "error_inesperado_pdf",
                "memoria_id": memoria_id,
            },
        )

    nombre_ascii = unicodedata.normalize("NFKD", nombre_archivo_limpio).encode("ascii", "ignore").decode("ascii")
    nombre_encoded = quote(nombre_archivo_limpio)
    content_disp_pdf = f'attachment; filename="{nombre_ascii}"; filename*=UTF-8\'\'{nombre_encoded}'

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disp_pdf,
            "X-PDF-Generation-Method": "edge-cli-no-header-footer",
            "Access-Control-Expose-Headers": "Content-Disposition, X-PDF-Generation-Method",
        },
    )


@router.get("/memorias/{memoria_id}/xlsx")
def exportar_memoria_xlsx(
    memoria_id: int,
    db: Session = Depends(get_db),
):
    memoria = db.query(Memoria).filter(Memoria.id == memoria_id).first()
    if not memoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoria no encontrada.")
    obra = memoria.obra
    if not obra:
        obra = db.query(Obra).filter(Obra.id == memoria.obra_id).first()

    obra_nombre = (obra.nombre if obra else f"OBRA {memoria.obra_id}").strip()
    nombre_archivo = f"MEMORIA {memoria.numero:02d} - {obra_nombre}.xlsx"
    nombre_archivo_limpio = re.sub(r'[\\/*?:"<>|]', "", nombre_archivo)

    try:
        excel_bytes = generar_excel_memoria(memoria=memoria, obra=obra)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar archivo Excel: {e}",
        )

    nombre_ascii = unicodedata.normalize("NFKD", nombre_archivo_limpio).encode("ascii", "ignore").decode("ascii")
    nombre_encoded = quote(nombre_archivo_limpio)
    content_disp_xlsx = f'attachment; filename="{nombre_ascii}"; filename*=UTF-8\'\'{nombre_encoded}'

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": content_disp_xlsx,
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
