"""Router para endpoints del sistema (heartbeat, apagado controlado y apertura de registros)."""
import logging
import os
import sys
from fastapi import APIRouter
from app import config
from app.services.lifecycle_service import registrar_heartbeat, solicitar_apagado

logger = logging.getLogger("app.sistema")
router = APIRouter(prefix="/sistema", tags=["Sistema"])


@router.post("/heartbeat")
def heartbeat_endpoint():
    """Recibe la señal de vida periódica enviada por el frontend mientras la pestaña está abierta."""
    t = registrar_heartbeat()
    return {"status": "ok", "timestamp": t}


@router.post("/apagar")
def apagar_endpoint():
    """Solicita el apagado del servidor local tras confirmación del usuario en la interfaz."""
    solicitar_apagado()
    return {"status": "ok", "mensaje": "El servidor se está apagando. Puedes cerrar esta ventana."}


@router.post("/abrir-logs")
def abrir_logs_endpoint():
    """Abre la carpeta de registros del sistema en el explorador de Windows."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = str(config.LOGS_DIR)
    if sys.platform == "win32":
        try:
            os.startfile(ruta)
            return {"status": "ok", "ruta": ruta}
        except Exception as e:
            logger.error(f"Error al abrir carpeta de logs: {e}", exc_info=True)
            return {"status": "error", "mensaje": str(e), "ruta": ruta}
    return {"status": "ok", "ruta": ruta}

