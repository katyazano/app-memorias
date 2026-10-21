"""Router para Configuración clave/valor."""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Configuracion
from app.schemas import (
    ConfiguracionOut,
    ConfiguracionUpdate,
    RespaldosInfoOut,
    RespaldoItem,
    RestaurarRespaldoRequest,
    RestablecerDatosRequest,
)

router = APIRouter(prefix="/configuracion", tags=["Configuración"])


@router.get("/{clave}", response_model=ConfiguracionOut)
def obtener_configuracion(clave: str, db: Session = Depends(get_db)):
    conf = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if not conf:
        if clave == "ultimo_folio_factura_arquitecto":
            return ConfiguracionOut(clave=clave, valor="0")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Configuración '{clave}' no encontrada.")
    return ConfiguracionOut(clave=conf.clave, valor=conf.valor)


@router.put("/{clave}", response_model=ConfiguracionOut)
def guardar_configuracion(clave: str, data: ConfiguracionUpdate, db: Session = Depends(get_db)):
    val = data.valor.strip()
    if clave == "ultimo_folio_factura_arquitecto":
        try:
            val_int = int(val)
            if val_int < 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El valor de 'ultimo_folio_factura_arquitecto' debe ser un número entero no negativo.",
            )

    if clave == "carpeta_respaldos" and val:
        try:
            p = Path(val)
            p.mkdir(parents=True, exist_ok=True)
            test_f = p / ".test_write"
            test_f.write_text("ok", encoding="utf-8")
            test_f.unlink()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La carpeta '{val}' no es válida o no tiene permisos de escritura: {e}",
            )

    conf = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if not conf:
        conf = Configuracion(clave=clave, valor=val)
        db.add(conf)
    else:
        conf.valor = val

    db.flush()
    return ConfiguracionOut(clave=conf.clave, valor=conf.valor)


@router.get("/sistema/respaldos", response_model=RespaldosInfoOut)
def listar_respaldos_endpoint(db: Session = Depends(get_db)):
    """Lista las últimas copias de respaldo disponibles en la carpeta configurada."""
    from app.services.backup_service import get_backup_dir, listar_respaldos, CLAVE_CARPETA_RESPALDOS

    conf_dir = db.query(Configuracion).filter(Configuracion.clave == CLAVE_CARPETA_RESPALDOS).first()
    carpeta_configurada = conf_dir.valor if conf_dir and conf_dir.valor else None
    actual = get_backup_dir(db)
    items = listar_respaldos(db)
    return RespaldosInfoOut(
        carpeta_actual=str(actual.resolve()),
        carpeta_configurada=carpeta_configurada,
        respaldos=[RespaldoItem(**item) for item in items],
    )


@router.post("/sistema/respaldos/generar")
def generar_respaldo_manual(db: Session = Depends(get_db)):
    """Genera manualmente una copia de seguridad en la carpeta configurada y rota a 10 copias."""
    from app.services.backup_service import crear_respaldo_seguro
    try:
        path, nombre = crear_respaldo_seguro(db, origen="manual")
        return {
            "status": "ok",
            "mensaje": f"Respaldo generado exitosamente: {nombre}",
            "nombre": nombre,
            "ruta": str(path.resolve()),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar respaldo: {e}",
        )


@router.post("/sistema/respaldos/restaurar")
def restaurar_respaldo_endpoint(data: RestaurarRespaldoRequest, db: Session = Depends(get_db)):
    """Restaura los datos desde un archivo .zip existente en la carpeta de respaldos.
    Realiza una validación previa y genera un respaldo de seguridad antes de aplicar los cambios.
    """
    from app.services.backup_service import restaurar_respaldo
    try:
        res = restaurar_respaldo(db, data.nombre_archivo)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la restauración del respaldo: {e}",
        )


@router.get("/sistema/respaldos/descargar/{nombre_archivo}")
def descargar_archivo_respaldo(nombre_archivo: str, db: Session = Depends(get_db)):
    """Descarga un archivo .zip de respaldo específico."""
    from fastapi.responses import FileResponse
    from app.services.backup_service import get_backup_dir
    import re

    # Validar nombre para evitar Directory Traversal
    if not re.match(r"^respaldo_[a-zA-Z0-9_\-]+\.zip$", nombre_archivo):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de archivo de respaldo no válido.")

    carpeta = get_backup_dir(db)
    archivo = (carpeta / nombre_archivo).resolve()

    # Asegurar que esté dentro de la carpeta
    if not str(archivo).startswith(str(carpeta.resolve())):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado al archivo solicitado.")

    if not archivo.exists() or not archivo.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo de respaldo no existe.")

    return FileResponse(
        path=archivo,
        filename=nombre_archivo,
        media_type="application/zip",
    )


@router.post("/sistema/restablecer-datos-vacios")
def restablecer_datos_vacios_endpoint(data: RestablecerDatosRequest, db: Session = Depends(get_db)):
    """Elimina todas las obras de prueba, facturas, rayas, gastos y archivos de storage.
    Requiere confirmación explícita con el texto exacto 'BORRAR TODO'.
    Crea automáticamente un respaldo de seguridad antes de proceder.
    """
    if data.confirmacion.strip() != "BORRAR TODO":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debe escribir exactamente 'BORRAR TODO' para confirmar el restablecimiento.",
        )

    from app.services.backup_service import restablecer_datos_vacios
    try:
        res = restablecer_datos_vacios(db)
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al restablecer datos del sistema: {e}",
        )


@router.get("/sistema/respaldo")
def descargar_respaldo():
    """Genera y descarga un archivo .zip que contiene la base de datos app.db
    (copiada de forma segura mediante sqlite3 backup API) y la carpeta de storage."""
    import io
    import sqlite3
    import tempfile
    import zipfile
    from datetime import datetime
    from fastapi.responses import Response
    from app.config import DATA_DIR, DB_PATH, STORAGE_DIR

    zip_buffer = io.BytesIO()
    temp_db_path = None

    try:
        # 1. Copia segura de SQLite mediante backup API (WAL safe)
        if DB_PATH.exists():
            temp_db_fd, temp_db_path_str = tempfile.mkstemp(suffix="_backup.db")
            os.close(temp_db_fd)
            temp_db_path = Path(temp_db_path_str)

            src_conn = sqlite3.connect(str(DB_PATH))
            dst_conn = sqlite3.connect(str(temp_db_path))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            if temp_db_path and temp_db_path.exists():
                zip_file.write(temp_db_path, arcname="data/app.db")

            # 2. Agregar archivos de storage
            if STORAGE_DIR.exists():
                for root, _, files in os.walk(STORAGE_DIR):
                    for f in files:
                        full_p = Path(root) / f
                        # Omitir temporales de staging
                        if "_staging" in full_p.parts:
                            continue
                        rel_p = full_p.relative_to(STORAGE_DIR)
                        zip_file.write(full_p, arcname=f"storage/{rel_p.as_posix()}")
    finally:
        if temp_db_path and temp_db_path.exists():
            try:
                temp_db_path.unlink()
            except Exception:
                pass

    zip_buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"respaldo_memorias_{timestamp}.zip"

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

