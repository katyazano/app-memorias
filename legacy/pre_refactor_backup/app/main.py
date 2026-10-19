from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.invoices import router as invoices_router
from app.api.routers.payments import router as payments_router
from app.api.routers.projects import router as projects_router
from app.api.routers.suppliers import router as suppliers_router
from app.api.routers.workers import router as workers_router
from app.database import Base, async_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor de ciclo de vida para inicialización de base de datos y cierre ordenado de conexiones."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await async_engine.dispose()


app = FastAPI(
    title="Plataforma de Gestión de Obras y Memoria de Gastos",
    description="API RESTful asíncrona para control de obras, facturación de proveedores CFDI 4.0, nómina y generación de Memorias de Obra.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuración de CORS para desarrollo local y frontend Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de enrutadores modulares
app.include_router(projects_router)
app.include_router(invoices_router)
app.include_router(payments_router)
app.include_router(suppliers_router)
app.include_router(workers_router)


@app.get("/health", tags=["Salud del Sistema / Health"])
async def health_check():
    """Verificación de estado y disponibilidad del servidor API."""
    return {
        "status": "healthy",
        "service": "construction-pm-api",
        "message": "Servicio de gestión de obra operando correctamente.",
    }
