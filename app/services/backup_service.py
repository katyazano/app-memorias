"""Servicio de respaldos automáticos, rotación a 10 copias, restauración y restablecimiento seguro."""
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app import config
from app.models import Configuracion

logger = logging.getLogger(__name__)

CLAVE_CARPETA_RESPALDOS = "carpeta_respaldos"
CLAVE_ULTIMO_RESPALDO_DIARIO = "ultimo_respaldo_diario_fecha"
MAX_RESPALDOS_CONSERVADOS = 10


def format_tamano_bytes(b: int) -> str:
    """Formatea bytes en formato legible (B, KB, MB, GB)."""
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    return f"{b / (1024 * 1024 * 1024):.1f} GB"


def get_carpeta_respaldos_default() -> Path:
    """Retorna la carpeta de respaldos por defecto."""
    p = config.BACKUPS_DEFAULT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_backup_dir(db: Optional[Session] = None) -> Path:
    """Obtiene la carpeta configurada para almacenar respaldos.
    Si no existe o no tiene permisos de escritura, hace fallback seguro a data/respaldos.
    """
    ruta_custom: Optional[str] = None
    if db:
        try:
            conf = db.query(Configuracion).filter(Configuracion.clave == CLAVE_CARPETA_RESPALDOS).first()
            if conf and conf.valor and conf.valor.strip():
                ruta_custom = conf.valor.strip()
        except Exception as e:
            logger.warning(f"No se pudo consultar carpeta de respaldos de BD: {e}")

    if ruta_custom:
        try:
            p = Path(ruta_custom)
            p.mkdir(parents=True, exist_ok=True)
            # Prueba de escritura
            test_f = p / ".test_write"
            test_f.write_text("ok", encoding="utf-8")
            test_f.unlink()
            return p
        except Exception as e:
            logger.warning(f"La carpeta configurada '{ruta_custom}' no es accesible ({e}). Usando ruta por defecto.")

    return get_carpeta_respaldos_default()


def rotar_respaldos(carpeta: Path, max_copias: int = MAX_RESPALDOS_CONSERVADOS) -> List[str]:
    """Conserva únicamente los últimos max_copias archivos .zip de respaldo, eliminando los más antiguos."""
    eliminados = []
    try:
        if not carpeta.exists():
            return eliminados

        archivos = [
            f for f in carpeta.iterdir()
            if f.is_file() and f.suffix.lower() == ".zip" and f.name.startswith("respaldo_")
        ]
        # Ordenar por fecha de modificación descendente (más nuevos primero)
        archivos.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        if len(archivos) > max_copias:
            sobrantes = archivos[max_copias:]
            for s in sobrantes:
                try:
                    s.unlink()
                    eliminados.append(s.name)
                    logger.info(f"Respaldo antiguo eliminado por rotación: {s.name}")
                except Exception as e:
                    logger.error(f"No se pudo eliminar respaldo antiguo {s.name}: {e}")
    except Exception as e:
        logger.error(f"Error durante rotación de respaldos: {e}")
    return eliminados


def crear_respaldo_seguro(db: Optional[Session] = None, origen: str = "manual") -> Tuple[Path, str]:
    """Genera una copia de seguridad segura de app.db (SQLite backup API) y la carpeta storage,
    la guarda en la carpeta configurada y ejecuta rotación a los últimos 10 respaldos.
    """
    carpeta = get_backup_dir(db)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"respaldo_{origen}_{timestamp}.zip"
    destino_zip = carpeta / nombre_archivo

    temp_db_path = None
    try:
        # 1. Copia segura de SQLite (online backup API, seguro contra WAL)
        if config.DB_PATH.exists():
            temp_db_fd, temp_db_path_str = tempfile.mkstemp(suffix="_backup.db")
            os.close(temp_db_fd)
            temp_db_path = Path(temp_db_path_str)

            src_conn = sqlite3.connect(str(config.DB_PATH))
            dst_conn = sqlite3.connect(str(temp_db_path))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

        # 2. Empaquetar en ZIP
        with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            if temp_db_path and temp_db_path.exists():
                zf.write(temp_db_path, arcname="data/app.db")

            if config.STORAGE_DIR.exists():
                for root, _, files in os.walk(config.STORAGE_DIR):
                    for f in files:
                        full_p = Path(root) / f
                        if "_staging" in full_p.parts:
                            continue
                        try:
                            rel_p = full_p.relative_to(config.STORAGE_DIR)
                            zf.write(full_p, arcname=f"storage/{rel_p.as_posix()}")
                        except Exception as e:
                            logger.warning(f"No se pudo empaquetar archivo {full_p}: {e}")

        logger.info(f"Respaldo generado exitosamente: {destino_zip}")

        # 3. Rotar a últimas 10 copias
        rotar_respaldos(carpeta, MAX_RESPALDOS_CONSERVADOS)

        return destino_zip, nombre_archivo
    finally:
        if temp_db_path and temp_db_path.exists():
            try:
                temp_db_path.unlink()
            except Exception:
                pass


def listar_respaldos(db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """Lista todos los respaldos .zip disponibles en la carpeta configurada."""
    carpeta = get_backup_dir(db)
    respaldos = []
    if not carpeta.exists():
        return respaldos

    for f in carpeta.iterdir():
        if f.is_file() and f.suffix.lower() == ".zip" and f.name.startswith("respaldo_"):
            try:
                st = f.stat()
                mtime = datetime.fromtimestamp(st.st_mtime)
                # Deducir origen del nombre: respaldo_{origen}_{timestamp}.zip
                partes = f.stem.split("_")
                origen = partes[1] if len(partes) >= 3 else "general"

                respaldos.append({
                    "nombre": f.name,
                    "ruta": str(f.resolve()),
                    "tamano_bytes": st.st_size,
                    "tamano_formateado": format_tamano_bytes(st.st_size),
                    "fecha_creacion": mtime.strftime("%d/%m/%Y %H:%M:%S"),
                    "fecha_creacion_iso": mtime.isoformat(),
                    "origen": origen,
                })
            except Exception as e:
                logger.warning(f"Error leyendo info de respaldo {f.name}: {e}")

    # Ordenar más recientes primero
    respaldos.sort(key=lambda x: x["fecha_creacion_iso"], reverse=True)
    return respaldos


def validar_archivo_respaldo(zip_path: Path) -> Tuple[bool, str]:
    """Verifica la integridad de un archivo .zip de respaldo:
    1. Que sea un ZIP válido y legible.
    2. Que contenga data/app.db.
    3. Que la base de datos interna pase PRAGMA integrity_check.
    """
    if not zip_path.exists():
        return False, f"El archivo '{zip_path.name}' no existe."

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            nombres = zf.namelist()
            if "data/app.db" not in nombres and "app.db" not in nombres:
                return False, "El archivo de respaldo no contiene la base de datos 'data/app.db'."

            # Extraer temporalmente la BD para revisar integridad SQLite
            db_entry = "data/app.db" if "data/app.db" in nombres else "app.db"
            with tempfile.TemporaryDirectory() as tmp_dir:
                extracted_db = zf.extract(db_entry, path=tmp_dir)
                conn = sqlite3.connect(extracted_db)
                try:
                    cur = conn.cursor()
                    cur.execute("PRAGMA integrity_check;")
                    res = cur.fetchone()
                    if not res or res[0] != "ok":
                        return False, f"La base de datos contiene errores de integridad: {res}"
                finally:
                    conn.close()

        return True, "Respaldo válido y verificado."
    except zipfile.BadZipFile:
        return False, "El archivo no es un formato ZIP válido o está dañado."
    except Exception as e:
        return False, f"Error validando archivo de respaldo: {e}"


def restaurar_respaldo(db: Session, nombre_archivo: str) -> Dict[str, Any]:
    """Restaura la base de datos y archivos de comprobantes desde un respaldo .zip:
    1. Valida el respaldo.
    2. Crea automáticamente un respaldo de seguridad previo: respaldo_pre_restauracion_...
    3. Sobrescribe data/app.db y data/storage.
    4. Ejecuta migraciones para asegurar coherencia.
    """
    carpeta = get_backup_dir(db)
    zip_path = carpeta / nombre_archivo
    valido, mensaje = validar_archivo_respaldo(zip_path)
    if not valido:
        raise ValueError(mensaje)

    # 1. Respaldo preventivo obligatorio antes de tocar los datos
    pre_rest_path, pre_rest_nombre = crear_respaldo_seguro(db, origen="pre_restauracion")

    # 2. Desconectar SQLAlchemy engine temporalmente
    from app.database import engine
    engine.dispose()

    # 3. Extraer archivos restaurados
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            arc_name = member.filename
            if arc_name.startswith("storage/"):
                rel_path = arc_name[len("storage/"):]
                if not rel_path:
                    continue
                target_path = config.STORAGE_DIR / rel_path
            elif arc_name.startswith("data/storage/"):
                rel_path = arc_name[len("data/storage/"):]
                if not rel_path:
                    continue
                target_path = config.STORAGE_DIR / rel_path
            elif arc_name in ("data/app.db", "app.db"):
                target_path = config.DB_PATH
            elif arc_name.startswith("data/"):
                rel_path = arc_name[len("data/"):]
                if not rel_path:
                    continue
                target_path = config.DATA_DIR / rel_path
            else:
                continue

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)

    # 4. Asegurar directorios y aplicar migraciones pendientes si las hubiera
    from app.main import aplicar_migraciones
    aplicar_migraciones()

    logger.info(f"Restauración completada con éxito desde {nombre_archivo}")
    return {
        "status": "ok",
        "mensaje": f"Restauración completada con éxito desde '{nombre_archivo}'.",
        "respaldo_previo": pre_rest_nombre,
    }


def restablecer_datos_vacios(db: Session) -> Dict[str, Any]:
    """Elimina todas las obras de prueba, facturas, rayas, gastos y comprobantes,
    dejando el sistema en limpio para cargar obras reales.
    Crea OBLIGATORIAMENTE un respaldo previo antes de borrar.
    """
    # 1. Respaldo previo obligatorio
    pre_resp_path, pre_resp_nombre = crear_respaldo_seguro(db, origen="pre_restablecer")

    # 2. Borrar registros de la base de datos en orden seguro de llaves foráneas
    from app.models import (
        Memoria,
        Anticipo,
        Gasto,
        Factura,
        PagoRaya,
        Trabajador,
        Proveedor,
        Obra,
    )

    db.query(Memoria).delete(synchronize_session=False)
    db.query(Anticipo).delete(synchronize_session=False)
    db.query(Gasto).delete(synchronize_session=False)
    db.query(Factura).delete(synchronize_session=False)
    db.query(PagoRaya).delete(synchronize_session=False)
    db.query(Trabajador).delete(synchronize_session=False)
    db.query(Proveedor).delete(synchronize_session=False)
    db.query(Obra).delete(synchronize_session=False)

    # Resetear correlativo de folio a 0
    conf_folio = db.query(Configuracion).filter(Configuracion.clave == "ultimo_folio_factura_arquitecto").first()
    if conf_folio:
        conf_folio.valor = "0"
    else:
        db.add(Configuracion(clave="ultimo_folio_factura_arquitecto", valor="0"))

    db.commit()

    # 3. Limpiar almacenamiento de archivos (storage) conservando la estructura base
    if config.STORAGE_DIR.exists():
        for item in config.STORAGE_DIR.iterdir():
            if item.name == "_staging":
                continue
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                logger.warning(f"No se pudo limpiar archivo de storage {item}: {e}")

    config.ensure_dirs()
    logger.info("Sistema restablecido a datos vacíos exitosamente.")

    return {
        "status": "ok",
        "mensaje": "El sistema ha sido restablecido a datos vacíos exitosamente. Listo para obras reales.",
        "respaldo_previo": pre_resp_nombre,
    }


def verificar_respaldo_diario(db: Session) -> bool:
    """Verifica si hoy ya se ejecutó el respaldo automático diario.
    Si no se ha realizado hoy, lo genera de inmediato y registra la fecha.
    """
    hoy_str = date.today().isoformat()
    try:
        conf = db.query(Configuracion).filter(Configuracion.clave == CLAVE_ULTIMO_RESPALDO_DIARIO).first()
        if conf and conf.valor == hoy_str:
            return False  # Ya se ejecutó hoy

        # Generar respaldo diario
        crear_respaldo_seguro(db, origen="diario")

        if not conf:
            conf = Configuracion(clave=CLAVE_ULTIMO_RESPALDO_DIARIO, valor=hoy_str)
            db.add(conf)
        else:
            conf.valor = hoy_str
        db.commit()
        logger.info(f"Respaldo diario automático realizado para la fecha {hoy_str}")
        return True
    except Exception as e:
        logger.error(f"Error ejecutando verificación de respaldo diario: {e}")
        return False
