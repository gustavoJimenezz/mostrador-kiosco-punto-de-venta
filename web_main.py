"""Entry point del POS Web (v2.0).

Reemplaza ``src/main.py`` (PySide6) como punto de entrada de la aplicación.
Configura logging, carga variables de entorno y lanza uvicorn.

Uso:
    poetry run python3 web_main.py
    DATABASE_URL=sqlite:///./dev.db poetry run python3 web_main.py
    POS_LOG_LEVEL=DEBUG poetry run python3 web_main.py
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv


def _setup_logging() -> Path:
    """Configura logging con rotación diaria.

    Escribe en ``~/.local/share/kiosco-pos/pos.log`` con rotación que
    conserva los últimos 7 días. El nivel se controla con ``POS_LOG_LEVEL``
    (default: ``INFO``).

    Returns:
        Ruta al archivo de log activo.
    """
    log_dir = Path.home() / ".local" / "share" / "kiosco-pos"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "pos.log"

    level = getattr(logging, os.environ.get("POS_LOG_LEVEL", "INFO").upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path,
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stderr_handler)

    # Silenciar logs verbosos de librerías externas
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return log_path


def main() -> None:
    """Inicia el servidor uvicorn con la app FastAPI."""
    load_dotenv()
    log_path = _setup_logging()

    logging.getLogger(__name__).info(
        "POS Web iniciando. Log: %s | PID: %d", log_path, os.getpid()
    )

    host = os.environ.get("POS_HOST", "127.0.0.1")
    port = int(os.environ.get("POS_PORT", "8000"))
    reload = os.environ.get("POS_RELOAD", "false").lower() == "true"

    uvicorn.run(
        "src.infrastructure.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        workers=1,          # SQLite con StaticPool requiere exactamente 1 worker
        reload=reload,      # activar con POS_RELOAD=true en desarrollo
        log_config=None,    # usamos nuestro propio logging configurado arriba
    )


if __name__ == "__main__":
    main()
