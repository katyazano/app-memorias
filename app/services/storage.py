"""Almacenamiento local de XML/PDF en ./data/storage/{obra_id}/.

Las rutas guardadas en la BD son relativas a DATA_DIR (con '/'), así la carpeta
./data se puede copiar o respaldar sin romper referencias.
"""
import re
import shutil
import time
import uuid as uuid_lib
from pathlib import Path
from typing import Optional

from app import config

STAGING_TTL_SECONDS = 24 * 3600


def _rel(path: Path) -> str:
    return path.relative_to(config.DATA_DIR).as_posix()


def abs_path(ruta_relativa: str) -> Path:
    """Resuelve una ruta relativa de la BD; impide salirse de DATA_DIR."""
    p = (config.DATA_DIR / ruta_relativa).resolve()
    if config.DATA_DIR not in p.parents and p != config.DATA_DIR:
        raise ValueError("Ruta fuera del directorio de datos.")
    return p


def obra_dir(obra_id: int) -> Path:
    d = config.STORAGE_DIR / str(obra_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_stem(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", name)


# ---------- staging: archivos subidos pendientes de confirmar ----------
def new_staging_dir() -> tuple[str, Path]:
    cleanup_staging()
    token = uuid_lib.uuid4().hex
    d = config.STAGING_DIR / token
    d.mkdir(parents=True, exist_ok=True)
    return token, d


def staging_dir(token: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise FileNotFoundError("Identificador de carga inválido.")
    d = config.STAGING_DIR / token
    if not d.is_dir():
        raise FileNotFoundError("La carga ya no existe (expiró o ya fue confirmada). Vuelve a subir los archivos.")
    return d


def cleanup_staging() -> None:
    if not config.STAGING_DIR.is_dir():
        return
    limite = time.time() - STAGING_TTL_SECONDS
    for d in config.STAGING_DIR.iterdir():
        try:
            if d.is_dir() and d.stat().st_mtime < limite:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def commit_staged_file(src: Path, obra_id: int, uuid: str, ext: str) -> str:
    """Mueve un archivo de staging a storage/{obra_id}/{UUID}.{ext}; devuelve ruta relativa."""
    extension = ext.lstrip(".")
    dest = obra_dir(obra_id) / f"{uuid}.{extension}"
    shutil.move(str(src), str(dest))
    return _rel(dest)


def delete_file(ruta_relativa: Optional[str]) -> None:
    if not ruta_relativa:
        return
    try:
        abs_path(ruta_relativa).unlink(missing_ok=True)
    except (ValueError, OSError):
        pass


def delete_obra_dir(obra_id: int) -> None:
    shutil.rmtree(config.STORAGE_DIR / str(obra_id), ignore_errors=True)
