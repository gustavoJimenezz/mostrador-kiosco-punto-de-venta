from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Importamos el metadata de nuestro esquema para habilitar autogenerate.
# Alembic compara este metadata contra el estado actual de la DB para
# generar migraciones automáticas con `alembic revision --autogenerate`.
from src.infrastructure.persistence.tables import metadata as target_metadata

import os 
from dotenv import load_dotenv # <--- Añadido

# Cargar variables de entorno desde el archivo .env
load_dotenv()

config = context.config

# --- LÓGICA PARA SOBRESCRIBIR LA URL CON EL .ENV ---
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
# ---------------------------------------------------


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline' (sin conexión activa a la DB).

    Útil para generar scripts SQL que luego se aplican manualmente.
    """
    url = config.get_main_option("sqlalchemy.url")
    is_sqlite = (url or "").startswith("sqlite")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        # render_as_batch requerido para SQLite: emula ALTER TABLE con recreación de tabla.
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online' (con conexión activa a la DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # render_as_batch requerido para SQLite: emula ALTER TABLE con recreación de tabla.
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
