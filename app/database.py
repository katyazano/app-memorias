from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos."""


def make_engine(url: str = config.DATABASE_URL) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


engine: Engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: una sesión por petición; commit si no hubo error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
