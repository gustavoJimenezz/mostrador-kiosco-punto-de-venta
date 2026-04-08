"""Configuración del motor de base de datos SQLAlchemy para MariaDB.

Centraliza la creación del Engine y la fábrica de sesiones.
No importa nada del dominio; es infraestructura pura.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool


def create_mariadb_engine(connection_url: str, echo: bool = False) -> Engine:
    """Crea un Engine SQLAlchemy optimizado para MariaDB en entorno local.

    Args:
        connection_url: URL de conexión MariaDB con driver PyMySQL. Formato:
            ``mysql+pymysql://user:password@host:port/database?charset=utf8mb4``
        echo: Si True, loguea todas las sentencias SQL generadas. Solo para
            desarrollo; nunca activar en producción.

    Returns:
        Engine configurado con pool de conexiones.

    Note:
        - ``pool_pre_ping=True``: verifica la salud de la conexión antes de
          entregarla al llamador. Previene errores silenciosos en kioscos que
          quedan inactivos varias horas (conexiones muertas por timeout del server).
        - ``pool_recycle=3600``: descarta y recrea conexiones cada hora para
          evitar el error "MySQL server has gone away".
        - ``pool_size=5``: suficiente para una terminal POS de una sola caja.
          Aumentar si se implementa multi-terminal en la misma instancia.
    """
    return create_engine(
        connection_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=echo,
    )


def create_sqlite_engine(db_path: Path, echo: bool = False) -> Engine:
    """Crea un Engine SQLAlchemy optimizado para SQLite en entorno local (kiosco).

    Diseñado para un único proceso con un solo worker uvicorn. Activa WAL
    y foreign keys automáticamente en cada nueva conexión.

    Args:
        db_path: Ruta al archivo ``.db``. Se crea si no existe.
        echo: Si True, loguea todas las sentencias SQL. Solo para desarrollo.

    Returns:
        Engine configurado con ``StaticPool`` (una sola conexión persistente).

    Note:
        - ``StaticPool``: reutiliza la misma conexión en todos los threads.
          Correcto para un servidor de un solo worker (uvicorn ``--workers 1``).
        - ``check_same_thread=False``: necesario para SQLite con FastAPI/uvicorn,
          donde la sesión puede crearse en un thread y usarse en otro.
        - WAL activado via evento ``connect`` para permitir lecturas concurrentes
          mientras hay una escritura en curso.
        - ``foreign_keys=ON`` porque SQLite no los activa por defecto.
    """
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=echo,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Crea la fábrica de sesiones SQLAlchemy vinculada al engine dado.

    Args:
        engine: Engine configurado con ``create_mariadb_engine``.

    Returns:
        ``sessionmaker`` configurado. Usar como context manager::

            SessionFactory = create_session_factory(engine)
            with SessionFactory() as session:
                repo = MariadbProductRepository(session)
                product = repo.get_by_barcode("7790895000115")
                session.commit()

    Note:
        - ``autoflush=False``: evita flushes automáticos inesperados durante la
          construcción de objetos en los casos de uso.
        - ``autocommit=False``: el commit es responsabilidad explícita del
          llamador (principio de Unidad de Trabajo).
    """
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
