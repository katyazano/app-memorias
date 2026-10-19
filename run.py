"""Script para iniciar el backend con un solo comando: python run.py"""
import socket
import sys
import uvicorn
from app import config


def obtener_version_esquema() -> str:
    """Obtiene la versión actual de la migración en la base de datos."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.migration import MigrationContext
        from app.database import engine

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            if not current_rev:
                return "Sin migraciones aplicadas (vacía)"

            ini_path = config.BASE_DIR / "alembic.ini"
            alembic_cfg = Config(str(ini_path))
            alembic_cfg.set_main_option("script_location", str(config.BASE_DIR / "migrations"))
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            head_rev = script_dir.get_current_head()

            if current_rev == head_rev:
                return f"{current_rev} (actualizado a HEAD)"
            return f"{current_rev} (HEAD disponible: {head_rev})"
    except Exception as e:
        return f"Desconocida ({e})"


def verificar_puerto_disponible(host: str, port: int) -> bool:
    """Verifica si el puerto local está libre para escuchar."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
        except OSError:
            return False


if __name__ == "__main__":
    config.ensure_dirs()

    # 1. Verificar versión del esquema de base de datos
    version_esquema = obtener_version_esquema()
    print("=" * 60)
    print("           MEMORIAS DE GASTOS - INICIO DE BACKEND")
    print("=" * 60)
    print(f"[*] Base de datos:    {config.DB_PATH}")
    print(f"[*] Versión esquema:  {version_esquema}")

    # 2. Verificar disponibilidad del puerto
    puerto_libre = verificar_puerto_disponible(config.HOST, config.PORT)
    if not puerto_libre:
        print("!" * 60)
        print(f"[ALERTA] El puerto {config.PORT} ya está ocupado por otro proceso.")
        print(f"         Si ya tienes una instancia anterior ejecutándose, ciérrala antes")
        print(f"         o cambia PORT en la configuración.")
        print("!" * 60)
        sys.exit(1)

    print(f"[*] Servidor listo en: http://{config.HOST}:{config.PORT}")
    print(f"[*] Documentación:    http://{config.HOST}:{config.PORT}/docs")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
