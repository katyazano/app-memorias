"""Configuración 100% local: SQLite + archivos en disco (sin servicios externos)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _resolve_data_dir() -> Path:
    raw = os.getenv("APP_DATA_DIR", "data")
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


DATA_DIR: Path = _resolve_data_dir()
STORAGE_DIR: Path = DATA_DIR / "storage"
STAGING_DIR: Path = STORAGE_DIR / "_staging"
DB_PATH: Path = DATA_DIR / "app.db"
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

_raw_host = os.getenv("APP_HOST", "127.0.0.1").strip()
# Seguridad: Asegurar que el servidor escuche ÚNICAMENTE en interfaz local (127.0.0.1) y jamás en 0.0.0.0
if _raw_host not in ("127.0.0.1", "localhost"):
    _raw_host = "127.0.0.1"
HOST: str = _raw_host
PORT: int = int(os.getenv("APP_PORT", "8000"))
APP_VERSION: str = "2.0.0-20261017.3"


def ensure_dirs() -> None:
    """Crea ./data y ./data/storage si no existen."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
