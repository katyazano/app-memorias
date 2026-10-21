"""Lanzador principal y punto de entrada único de Memorias de Gastos.

Funcionalidades:
1. Control de instancia única mediante Named Mutex en Windows.
2. Selección de puerto disponible (8000 o siguiente libre).
3. Escritura de registros (logs) en %LOCALAPPDATA%\\MemoriasGastos\\logs\\app.log.
4. Apertura automática del navegador predeterminado.
5. Apagado controlado e integración con el monitor de inactividad (heartbeat).
"""
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from app import config

# Configurar directorios base antes de cualquier inicialización
config.ensure_dirs()

# ----------------------------------------------------
# 1. Configuración de Registro (Logging)
# ----------------------------------------------------
log_file = config.LOGS_DIR / "app.log"
log_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s (pid %(process)d): %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler = RotatingFileHandler(
    filename=str(log_file),
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)

# Si hay consola disponible (ej. MemoriasGastos-Debug.exe o consola interactiva)
if sys.stderr and not sys.stderr.closed:
    try:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
    except Exception:
        pass

logger = logging.getLogger("launcher")
logger.info(f"=== Iniciando Memorias de Gastos v{config.APP_VERSION} (Frozen={config.IS_FROZEN}) ===")
logger.info(f"Directorio de recursos: {config.BUNDLE_DIR}")
logger.info(f"Directorio de datos escribibles: {config.DATA_DIR}")

# ----------------------------------------------------
# 2. Control de Instancia Única (Named Mutex en Windows)
# ----------------------------------------------------
MUTEX_NAME = os.environ.get("MEMORIAS_MUTEX_NAME", "Local\\MemoriasGastos_SingleInstance_Mutex_v2")
h_mutex = None
url_file = config.DATA_DIR.parent / "app.url"

if sys.platform == "win32":
    try:
        kernel32 = ctypes.windll.kernel32
        h_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            logger.info("Otra instancia de la aplicación ya se encuentra en ejecución.")
            url_a_abrir = "http://127.0.0.1:8000"
            if url_file.exists():
                try:
                    url_a_abrir = url_file.read_text("utf-8").strip() or url_a_abrir
                except Exception as e:
                    logger.warning(f"No se pudo leer app.url: {e}")

            logger.info(f"Abriendo navegador en la instancia activa: {url_a_abrir}")
            webbrowser.open(url_a_abrir)
            sys.exit(0)
    except Exception as e:
        logger.warning(f"No se pudo verificar Mutex de instancia única: {e}")


# ----------------------------------------------------
# 3. Detección y Selección de Puerto
# ----------------------------------------------------
def obtener_puerto_disponible(puerto_preferido: int = 8000) -> int:
    """Intenta usar el puerto preferido; si está ocupado, encuentra uno libre."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", puerto_preferido))
            return puerto_preferido
        except OSError:
            logger.info(f"Puerto preferido {puerto_preferido} ocupado. Buscando puerto alternativo...")

    for p in range(8001, 8100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = obtener_puerto_disponible(config.PORT)
    url = f"http://127.0.0.1:{port}"
    logger.info(f"Servidor configurado en {url}")

    # Guardar URL activa para instancias subsecuentes
    try:
        url_file.write_text(url, encoding="utf-8")
    except Exception as e:
        logger.warning(f"No se pudo escribir archivo app.url: {e}")

    # Importar FastAPI app
    from app.main import app
    import uvicorn
    from app.services.lifecycle_service import set_shutdown_callback

    server_config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_config=None,
        access_log=False,
        timeout_keep_alive=30,
    )
    server = uvicorn.Server(config=server_config)

    # Registrar callback para que el endpoint de apagado o inactividad detenga uvicorn
    set_shutdown_callback(lambda: setattr(server, "should_exit", True))

    # Hilo para abrir navegador web en cuanto /health responda
    def _abrir_navegador_cuando_listo():
        for _ in range(40):
            time.sleep(0.25)
            if getattr(server, "should_exit", False):
                return
            try:
                import urllib.request
                req = urllib.request.Request(f"{url}/health")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass

        if not getattr(server, "should_exit", False):
            if os.environ.get("MEMORIAS_NO_BROWSER") != "1":
                logger.info(f"Abriendo navegador web en {url}")
                webbrowser.open(url)

    threading.Thread(target=_abrir_navegador_cuando_listo, daemon=True, name="BrowserLauncher").start()

    try:
        server.run()
    finally:
        logger.info("Servidor detenido. Limpiando recursos...")
        try:
            if url_file.exists():
                url_file.unlink()
        except Exception:
            pass
        if h_mutex and sys.platform == "win32":
            try:
                kernel32.CloseHandle(h_mutex)
            except Exception:
                pass
        logger.info("=== Aplicación cerrada correctamente ===")


if __name__ == "__main__":
    main()
