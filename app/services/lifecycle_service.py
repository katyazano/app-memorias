"""Servicio de ciclo de vida del backend: monitoreo de inactividad por heartbeat y apagado controlado."""
import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("app.lifecycle")

INACTIVITY_TIMEOUT_SECONDS = 300  # 5 minutos sin latidos
STARTUP_GRACE_PERIOD_SECONDS = 180  # 3 minutos de gracia inicial tras el arranque

_startup_time = time.time()
_last_heartbeat = time.time()
_shutdown_requested = False
_monitor_thread: Optional[threading.Thread] = None
_shutdown_callback: Optional[Callable[[], None]] = None


def set_shutdown_callback(cb: Callable[[], None]) -> None:
    """Registra una función callback a invocar cuando se deba apagar el servidor."""
    global _shutdown_callback
    _shutdown_callback = cb


def registrar_heartbeat() -> float:
    """Actualiza la marca de tiempo del último latido recibido desde el frontend."""
    global _last_heartbeat
    _last_heartbeat = time.time()
    return _last_heartbeat


def solicitar_apagado() -> None:
    """Solicita el apagado controlado del servidor."""
    global _shutdown_requested
    _shutdown_requested = True
    logger.info("Solicitud explícita de apagado recibida.")

    def _do_shutdown():
        time.sleep(0.5)
        if _shutdown_callback:
            try:
                _shutdown_callback()
                return
            except Exception as e:
                logger.error(f"Error en callback de apagado: {e}")
        # Si no hay callback o falló, salida limpia
        os._exit(0)

    threading.Thread(target=_do_shutdown, daemon=True).start()


def _monitor_loop() -> None:
    """Bucle en segundo plano que vigila la inactividad del frontend."""
    logger.info("Monitor de inactividad iniciado (cierre automático tras 5 min sin pestañas abiertas).")
    while not _shutdown_requested:
        time.sleep(15)
        ahora = time.time()
        # Verificar tiempo de gracia de arranque
        if ahora - _startup_time < STARTUP_GRACE_PERIOD_SECONDS:
            continue

        inactividad = ahora - _last_heartbeat
        if inactividad > INACTIVITY_TIMEOUT_SECONDS:
            logger.info(
                f"Inactividad detectada: {int(inactividad)} segundos sin latidos del frontend. "
                "Cerrando el servidor automáticamente para liberar recursos..."
            )
            solicitar_apagado()
            break


def iniciar_monitor_inactividad() -> None:
    """Arranca el hilo de monitoreo en segundo plano si no está corriendo."""
    global _monitor_thread, _startup_time, _last_heartbeat
    _startup_time = time.time()
    _last_heartbeat = time.time()
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True, name="HeartbeatMonitor")
        _monitor_thread.start()
