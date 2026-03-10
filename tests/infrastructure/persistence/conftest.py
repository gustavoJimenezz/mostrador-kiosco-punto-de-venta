"""Fixtures de pytest para tests de infraestructura de persistencia.

Los fixtures de integración (engine, session, populated_products) requieren
una DB MariaDB real accesible via la variable de entorno POS_TEST_DB_URL.
Si la variable no está definida, los tests de integración se saltan
automáticamente con pytest.skip().
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from src.domain.models.product import Product
from src.infrastructure.persistence.database import (
    create_mariadb_engine,
    create_session_factory,
)
from src.infrastructure.persistence.mappings import configure_mappings
from src.infrastructure.persistence.tables import metadata, products_table

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
_DB_URL_ENV = "POS_TEST_DB_URL"
_SKIP_REASON = (
    f"Requiere DB MariaDB real. "
    f"Definir {_DB_URL_ENV}=mysql+pymysql://user:pass@host/db_test"
)

_PRODUCT_BRANDS = [
    "Coca Cola", "Pepsi", "Sprite", "Fanta", "7Up",
    "Manaos", "Cunnington", "La Salamandra", "Terma", "Gatorade",
    "Alfajor Jorgito", "Alfajor Havanna", "Alfajor Milka",
    "Galletitas Oreo", "Galletitas Chocolinas", "Galletitas Melba",
    "Papas Lays", "Papas Pringles", "Papas Pehuamar",
    "Caramelos Fini", "Chicles Beldent",
]


# ---------------------------------------------------------------------------
# Fixtures de sesión de test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_url() -> str:
    """Retorna la URL de conexión a la DB de test o hace skip del test.

    Returns:
        String con la URL de conexión MariaDB para tests de integración.
    """
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(_SKIP_REASON)
    return url


@pytest.fixture(scope="session")
def engine(db_url: str):
    """Crea el Engine SQLAlchemy para la DB de test.

    Configura los mappings imperativos y crea/destruye las tablas
    una sola vez para toda la sesión de pytest.

    Args:
        db_url: URL de conexión MariaDB provista por el fixture db_url.

    Yields:
        Engine SQLAlchemy configurado.
    """
    configure_mappings()
    eng = create_mariadb_engine(db_url, echo=False)

    metadata.create_all(eng)
    with eng.connect() as conn:
        conn.execute(
            text(
                "CREATE FULLTEXT INDEX IF NOT EXISTS ix_products_name_fulltext "
                "ON products(name)"
            )
        )
        conn.commit()

    yield eng

    metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine):
    """Crea la fábrica de sesiones para la DB de test.

    Args:
        engine: Engine del fixture engine.

    Returns:
        sessionmaker vinculada al engine de test.
    """
    return create_session_factory(engine)


@pytest.fixture
def db_session(session_factory):
    """Provee una sesión con rollback automático al finalizar el test.

    Usa SAVEPOINT para aislar cada test sin truncar tablas entre runs.

    Args:
        session_factory: Fábrica de sesiones del fixture session_factory.

    Yields:
        Session SQLAlchemy lista para usar en el test.
    """
    with session_factory() as session:
        session.begin_nested()  # SAVEPOINT
        yield session
        session.rollback()


@pytest.fixture(scope="session")
def populated_products(engine, session_factory):
    """Inserta 5,000 productos con nombres realistas en la DB de test.

    Usa scope=session para insertar los datos solo una vez por run de pytest.
    Verifica el count antes de insertar para soportar reruns sin teardown.

    Args:
        engine: Engine del fixture engine.
        session_factory: Fábrica de sesiones.

    Returns:
        int: Cantidad de productos en la tabla (5000).
    """
    with session_factory() as session:
        count = session.execute(
            select(func.count()).select_from(products_table)
        ).scalar()

        if count and count >= 5000:
            session.commit()
            return count

        products = []
        for i in range(5000):
            brand = _PRODUCT_BRANDS[i % len(_PRODUCT_BRANDS)]
            variant = i // len(_PRODUCT_BRANDS)
            products.append(
                Product(
                    barcode=f"{i:013d}",
                    name=f"{brand} {variant + 1:03d}ml",
                    current_cost=Decimal("100.00") + Decimal(str(i % 500)),
                    margin_percent=Decimal("35.00"),
                    stock=10,
                )
            )

        batch_size = 500
        for start in range(0, len(products), batch_size):
            for p in products[start : start + batch_size]:
                session.add(p)
            session.flush()

        session.commit()

    return 5000
