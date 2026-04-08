"""FastAPI application factory para el POS web (v2.0).

Crea y configura la aplicación FastAPI con:
- Lifespan: configure_mappings, engine SQLite, alembic migrate
- SessionMiddleware para autenticación por cookie
- CORS para desarrollo con Vite (:5173)
- Todos los routers registrados bajo /api/
- Archivos estáticos del bundle React (frontend/dist/)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.infrastructure.persistence.database import (
    create_mariadb_engine,
    create_session_factory,
    create_sqlite_engine,
)
from src.infrastructure.persistence.mappings import configure_mappings
from src.infrastructure.web.routers import admin, auth, cash, import_, pos

logger = logging.getLogger(__name__)

_DEFAULT_SQLITE_PATH = Path.home() / ".local" / "share" / "kiosco-pos" / "pos.db"


def _run_alembic_migrations(database_url: str) -> None:
    """Ejecuta ``alembic upgrade head`` programáticamente al arrancar."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")
    logger.info("Migraciones Alembic aplicadas correctamente.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler: inicializa la DB al arrancar, limpia al apagar."""
    database_url = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{_DEFAULT_SQLITE_PATH}",
    )

    logger.info("DATABASE_URL: %s", database_url)

    # Asegurar que el directorio de la DB existe (solo para SQLite)
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_sqlite_engine(db_path)
    else:
        engine = create_mariadb_engine(database_url)

    # Aplicar migraciones antes de aceptar requests
    try:
        _run_alembic_migrations(database_url)
    except Exception:
        logger.exception("Error al ejecutar migraciones Alembic. Continuando de todos modos.")

    configure_mappings()
    session_factory = create_session_factory(engine)

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.database_url = database_url

    logger.info("POS Web listo en http://localhost:8000")
    yield

    # Shutdown: cerrar el engine limpiamente
    engine.dispose()
    logger.info("Engine de base de datos cerrado.")


def create_app() -> FastAPI:
    """Factory que crea y configura la aplicación FastAPI.

    Returns:
        FastAPI app lista para ser ejecutada por uvicorn.
    """
    app = FastAPI(
        title="Kiosco POS",
        version="2.0.0",
        description="Sistema POS para kioscos — API REST",
        lifespan=lifespan,
        # Deshabilitar docs en producción si se quiere; dejarlos habilitados es útil
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # --- Middlewares --------------------------------------------------------
    secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    app.add_middleware(SessionMiddleware, secret_key=secret_key, max_age=86400)

    # CORS: permitir Vite dev server en desarrollo (:5173)
    # En producción el frontend se sirve desde el mismo origen, CORS no es necesario
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ------------------------------------------------------------
    app.include_router(auth.router)
    app.include_router(pos.router)
    app.include_router(cash.router)
    app.include_router(admin.router)
    app.include_router(import_.router)

    # --- Static files (bundle React) ----------------------------------------
    # En desarrollo: Vite sirve el frontend en :5173 con proxy a /api → :8000
    # En producción: el bundle generado por `npm run build` se monta aquí
    frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
        logger.info("Sirviendo frontend desde %s", frontend_dist)
    else:
        logger.warning(
            "frontend/dist/ no encontrado. "
            "Ejecutá `cd frontend && npm run build` para generar el bundle React."
        )

    return app
