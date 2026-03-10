"""Mapeo imperativo (classical mapping) de entidades de dominio con SQLAlchemy 2.0.

Vincula las clases Python del dominio con las tablas definidas en ``tables.py``
sin que el dominio importe nada de SQLAlchemy. El mapeo se aplica externamente,
preservando la pureza de las entidades de dominio.

Entidades mapeadas en este módulo:
- ``Product`` → ``products_table``
- ``CashClose`` → ``cash_closes_table``

``Sale`` y ``SaleItem`` se persisten mediante Core SQL en los casos de uso
(ver future ticket ProcessSale) dado que ``Sale.total_amount`` es un ``@property``
calculado y ``SaleItem`` no expone ``sale_id`` como atributo de dominio.
"""

from __future__ import annotations

from sqlalchemy.orm import registry

from src.domain.models.cash_close import CashClose
from src.domain.models.product import Product
from .tables import cash_closes_table, products_table

mapper_registry = registry()

_mappings_configured: bool = False


def configure_mappings() -> None:
    """Aplica el mapeo imperativo entre entidades de dominio y tablas de DB.

    Debe invocarse UNA sola vez al arrancar la aplicación (en ``main.py``,
    antes de crear cualquier repositorio). Es idempotente: llamadas repetidas
    son ignoradas con seguridad.

    Note:
        SQLAlchemy instrumenta los atributos de las clases de dominio tras
        esta llamada. Los atributos existentes (``Product.barcode``, etc.)
        se convierten en ``InstrumentedAttribute``, habilitando las queries
        ORM (``select(Product).where(Product.barcode == "...")``).

    Examples:
        >>> from src.infrastructure.persistence.mappings import configure_mappings
        >>> configure_mappings()  # llamar una sola vez en main.py
    """
    global _mappings_configured
    if _mappings_configured:
        return

    # Product: mapeo directo columna↔atributo por coincidencia de nombres.
    # SQLAlchemy asigna 'id' tras flush/commit (autoincrement).
    mapper_registry.map_imperatively(
        Product,
        products_table,
    )

    # CashClose: ídem. Todos los atributos coinciden con las columnas de la tabla.
    mapper_registry.map_imperatively(
        CashClose,
        cash_closes_table,
    )

    _mappings_configured = True
