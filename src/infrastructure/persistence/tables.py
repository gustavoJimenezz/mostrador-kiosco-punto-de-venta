"""Definición del esquema de base de datos usando SQLAlchemy Core.

Todas las tablas se definen aquí como objetos ``Table``. El mapeo imperativo
entre estas tablas y las entidades de dominio vive en ``mappings.py``.

Referencia del esquema: doc/aspectos-tecnicos.md (sección "Diseño de Base de Datos").
"""

from __future__ import annotations

from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
)

from src.domain.models.sale import PaymentMethod
from src.domain.models.user import UserRole

metadata = MetaData()

# ---------------------------------------------------------------------------
# users — Operadores del sistema POS (autenticación por PIN)
# ---------------------------------------------------------------------------
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column(
        "role",
        SAEnum(
            UserRole,
            values_callable=lambda x: [e.value for e in x],
            name="user_role_enum",
        ),
        nullable=False,
    ),
    # Hash bcrypt de 60 caracteres. Nunca almacenar el PIN en texto plano.
    Column("pin_hash", String(60), nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="1"),
)

# ---------------------------------------------------------------------------
# categories — Categorías de productos (ej: Golosinas, Bebidas)
# ---------------------------------------------------------------------------
categories_table = Table(
    "categories",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
    Index("ix_categories_name", "name"),
)

# ---------------------------------------------------------------------------
# products — Catálogo de productos del kiosco
# ---------------------------------------------------------------------------
products_table = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("barcode", String(50), nullable=False, unique=True),
    Column("name", String(250), nullable=False),
    Column("current_cost", Numeric(12, 2), nullable=False),
    Column("margin_percent", Numeric(15, 4), nullable=False),
    Column("stock", Integer, nullable=False, server_default="0"),
    Column("min_stock", Integer, nullable=False, server_default="0"),
    Column(
        "category_id",
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # Índice explícito en barcode para búsqueda O(log n) por EAN-13.
    # El FullText index en 'name' se agrega en la migración Alembic con DDL
    # específico de MariaDB: CREATE FULLTEXT INDEX ix_products_name ON products(name)
    Index("ix_products_barcode", "barcode"),
)

# ---------------------------------------------------------------------------
# cash_closes — Arqueo de caja diario
# ---------------------------------------------------------------------------
cash_closes_table = Table(
    "cash_closes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("opened_at", DateTime, nullable=False),
    Column("closed_at", DateTime, nullable=True),
    Column("opening_amount", Numeric(12, 2), nullable=False),
    Column("closing_amount", Numeric(12, 2), nullable=True),
    Column("total_sales_cash", Numeric(12, 2), nullable=False, server_default="0.00"),
    Column("total_sales_debit", Numeric(12, 2), nullable=False, server_default="0.00"),
    Column(
        "total_sales_transfer", Numeric(12, 2), nullable=False, server_default="0.00"
    ),
    Column("gross_profit_estimate", Numeric(12, 2), nullable=True),
    Column("total_cost_estimate", Numeric(12, 2), nullable=True),
)

# ---------------------------------------------------------------------------
# sales — Cabecera de venta
#
# Nota: la columna total_amount se persiste como snapshot para consultas
# analíticas (ej: suma del día sin cargar ítems). El dominio la calcula
# dinámicamente desde sale_items; el repositorio la materializa al guardar.
# ---------------------------------------------------------------------------
sales_table = Table(
    "sales",
    metadata,
    Column("id", CHAR(36), primary_key=True),  # UUID almacenado como string
    Column("timestamp", DateTime, nullable=False),
    Column("total_amount", Numeric(12, 2), nullable=False),
    Column(
        "payment_method",
        SAEnum(*[e.value for e in PaymentMethod], name="payment_method_enum"),
        nullable=False,
    ),
    Column(
        "cash_close_id",
        Integer,
        ForeignKey("cash_closes.id", ondelete="SET NULL"),
        nullable=True,
    ),
)

# ---------------------------------------------------------------------------
# sale_items — Ítems de venta (price_at_sale es inmutable)
# ---------------------------------------------------------------------------
sale_items_table = Table(
    "sale_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "sale_id",
        CHAR(36),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "product_id",
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("quantity", Integer, nullable=False),
    # Crítico: precio en el momento exacto de la venta. Nunca se recalcula.
    Column("price_at_sale", Numeric(12, 2), nullable=False),
)

# ---------------------------------------------------------------------------
# cash_movements — Movimientos manuales de caja (ingresos/egresos)
# ---------------------------------------------------------------------------
cash_movements_table = Table(
    "cash_movements",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "cash_close_id",
        Integer,
        ForeignKey("cash_closes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("description", String(250), nullable=False, server_default=""),
    Column("created_at", DateTime, nullable=False),
    Index("ix_cash_movements_cash_close_id", "cash_close_id"),
)

# ---------------------------------------------------------------------------
# price_history — Historial de cambios de costo (radar de inflación)
# ---------------------------------------------------------------------------
price_history_table = Table(
    "price_history",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "product_id",
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("old_cost", Numeric(12, 2), nullable=False),
    Column("new_cost", Numeric(12, 2), nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Index("ix_price_history_product_id", "product_id"),
)
