import os
import sys
import tempfile
from pathlib import Path

import pytest

# Los tests nunca deben tocar ./data real.
_TMP = tempfile.mkdtemp(prefix="memorias_tests_")
os.environ["APP_DATA_DIR"] = _TMP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.database import Base, engine
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def init_test_env():
    config.ensure_dirs()
    Base.metadata.create_all(bind=engine)
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(str(config.ALEMBIC_INI))
        alembic_cfg.set_main_option("script_location", str(config.MIGRATIONS_DIR))
        alembic_cfg.set_main_option("sqlalchemy.url", config.DATABASE_URL)
        command.stamp(alembic_cfg, "head")
    except Exception:
        pass
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
