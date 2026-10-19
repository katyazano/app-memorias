from alembic import context
from sqlalchemy import create_engine, pool

from app import config, models  # noqa: F401  (registra los modelos en Base.metadata)
from app.database import Base

target_metadata = Base.metadata


def _url() -> str:
    # Permite que el código (o las pruebas) inyecten otra URL.
    return context.config.get_main_option("sqlalchemy.url") or config.DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        user_module_prefix="app.types.",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.ensure_dirs()
    connectable = create_engine(_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite: ALTER TABLE vía copia de tabla
            user_module_prefix="app.types.",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
