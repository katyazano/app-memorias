"""Configuración 100% local: SQLite + archivos en disco (sin servicios externos).
Soporta modo desarrollo y modo empaquetado (PyInstaller / sys.frozen).
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

APP_VERSION: str = "2.0.0+20261020.0356"

IS_FROZEN: bool = getattr(sys, "frozen", False)

# Directorio de recursos de solo lectura (código, frontend/dist, templates, migraciones, alembic.ini)
if IS_FROZEN:
    # PyInstaller extrae recursos en sys._MEIPASS
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent

BASE_DIR: Path = BUNDLE_DIR
FRONTEND_DIST_DIR: Path = BUNDLE_DIR / "frontend" / "dist"
MIGRATIONS_DIR: Path = BUNDLE_DIR / "migrations"
ALEMBIC_INI: Path = BUNDLE_DIR / "alembic.ini"

# Cargar .env únicamente si existe (modo desarrollo o pruebas)
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Directorios de datos escribibles (SQLite, comprobantes XML/PDF, respaldos, logs)
if IS_FROZEN:
    # En modo empaquetado, todo dato escribible vive en %LOCALAPPDATA%\MemoriasGastos\
    local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    BASE_WRITABLE_DIR: Path = Path(local_appdata).resolve() / "MemoriasGastos"
    DATA_DIR: Path = BASE_WRITABLE_DIR / "data"
    STORAGE_DIR: Path = BASE_WRITABLE_DIR / "storage"
    STAGING_DIR: Path = STORAGE_DIR / "_staging"
    LOGS_DIR: Path = BASE_WRITABLE_DIR / "logs"
    BACKUPS_DEFAULT_DIR: Path = BASE_WRITABLE_DIR / "respaldos"
    DB_PATH: Path = DATA_DIR / "app.db"
else:
    # En modo desarrollo, conserva el comportamiento relativo en ./data o APP_DATA_DIR
    raw_data_dir = os.getenv("APP_DATA_DIR", "data")
    p_data = Path(raw_data_dir)
    if not p_data.is_absolute():
        p_data = BASE_DIR / p_data
    DATA_DIR = p_data.resolve()
    BASE_WRITABLE_DIR = DATA_DIR.parent
    STORAGE_DIR = DATA_DIR / "storage"
    STAGING_DIR = STORAGE_DIR / "_staging"
    LOGS_DIR = DATA_DIR / "logs"
    BACKUPS_DEFAULT_DIR = DATA_DIR / "respaldos"
    DB_PATH = DATA_DIR / "app.db"

DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

_raw_host = os.getenv("APP_HOST", "127.0.0.1").strip()
# Seguridad: Asegurar que el servidor escuche ÚNICAMENTE en interfaz local (127.0.0.1) y jamás en 0.0.0.0
if _raw_host not in ("127.0.0.1", "localhost"):
    _raw_host = "127.0.0.1"
HOST: str = _raw_host
PORT: int = int(os.getenv("APP_PORT", "8000"))


def ensure_dirs() -> None:
    """Crea directorios necesarios para datos, storage, staging, logs y respaldos."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
