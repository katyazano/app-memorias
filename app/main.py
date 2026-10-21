"""Punto de entrada principal de la aplicación FastAPI."""
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

from alembic import command
from alembic.config import Config
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.routers import (
    anticipos,
    configuracion,
    facturas,
    gastos,
    memorias,
    obras,
    proveedores,
    rayas,
    sistema,
    trabajadores,
)

logger = logging.getLogger("app")
SERVER_START_TIME = datetime.now()


def obtener_version_esquema() -> str:
    """Obtiene la versión actual de la migración de Alembic en la base de datos."""
    try:
        from alembic.script import ScriptDirectory
        from alembic.migration import MigrationContext
        from app.database import engine

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            if not current_rev:
                return "Sin migraciones aplicadas (vacía)"

            ini_path = config.ALEMBIC_INI
            alembic_cfg = Config(str(ini_path))
            alembic_cfg.set_main_option("script_location", str(config.MIGRATIONS_DIR))
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            head_rev = script_dir.get_current_head()

            if current_rev == head_rev:
                return f"{current_rev} (actualizado a HEAD)"
            return f"{current_rev} (HEAD disponible: {head_rev})"
    except Exception as e:
        return f"Desconocida ({e})"


def aplicar_migraciones():
    """Ejecuta las migraciones pendientes de Alembic hacia head.
    Antes de migrar, realiza un respaldo de seguridad automático de app.db si existe.
    """
    if config.DB_PATH.exists() and config.DB_PATH.stat().st_size > 0:
        try:
            from app.services.backup_service import crear_respaldo_seguro
            crear_respaldo_seguro(origen="pre_migracion")
            logger.info("Respaldo preventivo automático realizado antes de aplicar migraciones.")
        except Exception as e:
            logger.warning(f"No se pudo generar respaldo pre-migración: {e}")

    try:
        ini_path = config.ALEMBIC_INI
        alembic_cfg = Config(str(ini_path))
        alembic_cfg.set_main_option("script_location", str(config.MIGRATIONS_DIR))
        alembic_cfg.set_main_option("sqlalchemy.url", config.DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        logger.info("Migraciones de base de datos aplicadas correctamente.")
    except Exception as e:
        logger.error(f"Error al aplicar migraciones: {e}")
        # Si la base de datos ya fue inicializada o en tests, no bloquear si ya está en head
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicio: crear directorios y aplicar migraciones
    config.ensure_dirs()
    aplicar_migraciones()
    # Verificación de respaldo automático diario
    try:
        from app.database import SessionLocal
        from app.services.backup_service import verificar_respaldo_diario
        with SessionLocal() as db:
            verificar_respaldo_diario(db)
    except Exception as e:
        logger.error(f"Error al verificar respaldo diario en arranque: {e}")

    # Iniciar monitor de latidos (heartbeat) para apagado automático por inactividad
    try:
        from app.services.lifecycle_service import iniciar_monitor_inactividad
        iniciar_monitor_inactividad()
    except Exception as e:
        logger.error(f"Error al iniciar monitor de inactividad: {e}")

    yield
    # Cierre


app = FastAPI(
    title="Memorias de Gastos API",
    description="Backend 100% local en SQLite para gestión de obras, facturas CFDI, pagos y memorias de gastos.",
    version="2.0.0",
    lifespan=lifespan,
)

# Permitir CORS para desarrollo de cliente frontend (React Vite / Next / etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar frontend compilado (dist) si existe
dist_dir = config.FRONTEND_DIST_DIR
dist_assets = dist_dir / "assets"
dist_index = dist_dir / "index.html"

if dist_assets.exists():
    app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")

# Incluir routers bajo prefijo /api (para llamadas directas desde frontend en producción)
api_router = APIRouter(prefix="/api")
api_router.include_router(obras.router)
api_router.include_router(proveedores.router)
api_router.include_router(trabajadores.router)
api_router.include_router(anticipos.router)
api_router.include_router(rayas.router)
api_router.include_router(gastos.router)
api_router.include_router(facturas.router)
api_router.include_router(memorias.router)
api_router.include_router(configuracion.router)
api_router.include_router(sistema.router)
app.include_router(api_router)

# Incluir routers sin prefijo para retrocompatibilidad con tests existentes
app.include_router(obras.router)
app.include_router(proveedores.router)
app.include_router(trabajadores.router)
app.include_router(anticipos.router)
app.include_router(rayas.router)
app.include_router(gastos.router)
app.include_router(facturas.router)
app.include_router(memorias.router)
app.include_router(configuracion.router)
app.include_router(sistema.router)


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"Error 500 no controlado en {request.method} {request.url.path}: {exc}\n{tb}")
    msg = (
        "No se pudo guardar la factura. Los detalles técnicos se guardaron en el registro."
        if "facturas/confirmar" in request.url.path
        else "Ocurrió un error inesperado en el servidor. Los detalles técnicos se guardaron en el registro."
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": msg,
            "mensaje": msg,
            "detalles_tecnicos": tb,
        },
    )


@app.middleware("http")
async def spa_middleware(request: Request, call_next):
    path = request.url.path
    if (
        path.startswith("/api")
        or path.startswith("/assets")
        or path in ("/docs", "/redoc", "/openapi.json", "/health")
        or path.endswith("/pdf")
        or path.endswith("/xlsx")
        or path.endswith(".zip")
    ):
        return await call_next(request)

    # Si se pide HTML desde navegador web o Playwright
    accept = request.headers.get("accept", "")
    if "text/html" in accept and dist_index.exists():
        target = dist_dir / path.lstrip("/")
        if target.is_file():
            return FileResponse(target)
        return FileResponse(dist_index)

    response = await call_next(request)
    if response.status_code == 404 and dist_index.exists() and not path.startswith("/api") and not path.endswith(".zip"):
        target = dist_dir / path.lstrip("/")
        if target.is_file():
            return FileResponse(target)
        return FileResponse(dist_index)
    return response


@app.get("/memorias/{memoria_id}/imprimir", include_in_schema=False)
def servir_imprimir_html(memoria_id: int):
    if dist_index.exists():
        return FileResponse(dist_index)
    raise HTTPException(status_code=404, detail="Frontend compilado no encontrado. Ejecuta 'npm run build'.")


@app.get("/", include_in_schema=False)
def servir_raiz():
    if dist_index.exists():
        return FileResponse(dist_index)
    return {"status": "ok", "app": "memorias-backend"}


@app.get("/health", tags=["Salud"])
@app.get("/api/health", tags=["Salud"])
def health_check():
    return {
        "status": "ok",
        "app": "memorias-backend",
        "database": "sqlite",
        "version_build": {
            "arranque": SERVER_START_TIME.strftime("%d/%m/%Y %H:%M:%S"),
            "arranque_iso": SERVER_START_TIME.isoformat(),
            "esquema": obtener_version_esquema(),
            "version_codigo": config.APP_VERSION,
        },
    }

