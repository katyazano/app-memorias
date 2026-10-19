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
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
