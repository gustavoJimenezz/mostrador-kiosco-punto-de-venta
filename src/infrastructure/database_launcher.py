"""Orquestador del proceso MariaDB para el bundle portable del POS.

Responsabilidades:
    1. Detectar si ``mysqld.exe`` ya está corriendo en el sistema.
    2. Si no lo está (y el binario existe en ``vendor/``), iniciarlo de forma
       silenciosa usando ``subprocess.Popen`` con ``CREATE_NO_WINDOW``.
    3. Realizar un health check de hasta ``HEALTH_CHECK_RETRIES`` intentos de
       conexión SQLAlchemy antes de permitir que la UI arranque.

Este módulo **no importa nada del dominio**. Es infraestructura pura cuyo
único consumidor es ``main.py``, que lo invoca antes de instanciar
``QApplication``.

Comportamiento por entorno:
    - **Windows (bundle):** inicia ``mysqld.exe`` desde ``vendor/mariadb/bin/``
      si el proceso no está activo.
    - **Linux / desarrollo:** si el binario no existe, omite el inicio y va
      directo al health check asumiendo que MariaDB ya corre externamente.
"""

from __future__ import annotations

import configparser
import logging
import subprocess
import time
from pathlib import Path

import psutil
import sqlalchemy

logger = logging.getLogger(__name__)

MYSQLD_PROCESS_NAME = "mysqld.exe"
HEALTH_CHECK_RETRIES = 3
HEALTH_CHECK_DELAY_SEC = 2.0
HEALTH_CHECK_TIMEOUT_SEC = 10.0


def launch_mariadb(
    vendor_path: Path,
    config_path: Path,
    connection_url: str | None = None,
) -> bool:
    """Punto de entrada principal del orquestador.

    Verifica si MariaDB está corriendo; lo inicia si es necesario; y realiza
    un health check antes de retornar.

    Args:
        vendor_path: Ruta al directorio raíz del bundle MariaDB portable
            (p. ej. ``Path("vendor/mariadb")``). Debe contener
            ``bin/mysqld.exe`` en entornos Windows.
        config_path: Ruta al archivo ``database.ini`` con los parámetros de
            conexión (sección ``[database]``).
        connection_url: URL de conexión SQLAlchemy. Si es ``None``, se
            construye a partir de ``config_path``.

    Returns:
        ``True`` si la conexión a MariaDB está disponible; ``False`` si los
        ``HEALTH_CHECK_RETRIES`` intentos fallaron.
    """
    config = _read_config(config_path)
    port: int = config.getint("database", "port", fallback=3306)

    if connection_url is None:
        connection_url = _build_connection_url(config)

    mysqld_bin = vendor_path / "bin" / MYSQLD_PROCESS_NAME

    if mysqld_bin.exists():
        if not _is_mysqld_running():
            logger.info("mysqld.exe no detectado — iniciando proceso...")
            _start_mysqld(mysqld_bin, port)
        else:
            logger.info("mysqld.exe ya está en ejecución.")
    else:
        logger.info(
            "Binario mysqld.exe no encontrado en '%s'. "
            "Asumiendo MariaDB externo (entorno de desarrollo).",
            mysqld_bin,
        )

    return _health_check(connection_url, HEALTH_CHECK_RETRIES, HEALTH_CHECK_DELAY_SEC)


# ---------------------------------------------------------------------------
# Funciones privadas
# ---------------------------------------------------------------------------


def _read_config(config_path: Path) -> configparser.ConfigParser:
    """Lee y retorna el ``ConfigParser`` desde ``config_path``.

    Args:
        config_path: Ruta al archivo ``.ini``.

    Returns:
        Instancia de ``ConfigParser`` con los valores del archivo.
    """
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def _build_connection_url(config: configparser.ConfigParser) -> str:
    """Construye la URL de conexión SQLAlchemy desde ``config``.

    Args:
        config: ``ConfigParser`` con sección ``[database]``.

    Returns:
        URL con formato ``mysql+pymysql://user:password@host:port/database``.
    """
    section = config["database"] if "database" in config else {}
    host = section.get("host", "localhost")
    port = section.get("port", "3306")
    user = section.get("user", "root")
    password = section.get("password", "")
    database = section.get("database", "kiosco_pos")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def _is_mysqld_running() -> bool:
    """Verifica si existe al menos un proceso ``mysqld.exe`` activo.

    Usa ``psutil.process_iter`` para enumerar los procesos del sistema.

    Returns:
        ``True`` si el proceso está corriendo; ``False`` en caso contrario.
    """
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] == MYSQLD_PROCESS_NAME:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _start_mysqld(mysqld_bin: Path, port: int) -> None:
    """Inicia ``mysqld.exe`` en background de forma silenciosa.

    Usa ``CREATE_NO_WINDOW`` para que la ventana de consola no sea visible
    durante la ejecución normal del kiosco.

    Args:
        mysqld_bin: Ruta completa al ejecutable ``mysqld.exe``.
        port: Puerto TCP en el que MariaDB escuchará conexiones.
    """
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [str(mysqld_bin), f"--port={port}", "--console"],
        creationflags=creation_flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("mysqld.exe iniciado en puerto %d.", port)


def _health_check(
    connection_url: str,
    retries: int,
    delay: float,
) -> bool:
    """Intenta conectar a MariaDB hasta ``retries`` veces.

    Usa un engine SQLAlchemy con ``NullPool`` para evitar conexiones
    persistentes durante el chequeo de arranque.

    Args:
        connection_url: URL de conexión SQLAlchemy.
        retries: Número máximo de intentos de conexión.
        delay: Segundos de espera entre intentos.

    Returns:
        ``True`` si la conexión fue exitosa en algún intento; ``False`` si
        todos los intentos fallaron.
    """
    engine = sqlalchemy.create_engine(
        connection_url,
        poolclass=sqlalchemy.pool.NullPool,
    )

    for attempt in range(1, retries + 1):
        try:
            with engine.connect():
                logger.info("Health check exitoso en intento %d/%d.", attempt, retries)
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Health check intento %d/%d falló: %s", attempt, retries, exc
            )
            if attempt < retries:
                time.sleep(delay)

    engine.dispose()
    return False
