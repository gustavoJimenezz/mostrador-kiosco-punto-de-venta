"""Crear tablas iniciales del sistema POS.

Crea las 5 tablas del esquema:
- products: catálogo de productos con índice en barcode y FullText en name
- cash_closes: arqueo de caja diario
- sales: cabecera de ventas (UUID como PK CHAR(36))
- sale_items: detalle de venta con price_at_sale inmutable
- price_history: historial de cambios de costo (radar de inflación ARS)

Revision ID: 1bafd69c0714
Revises:
Create Date: 2026-03-10
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "1bafd69c0714"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea todas las tablas con sus índices y restricciones."""

    # ------------------------------------------------------------------
    # cash_closes — sin FK salientes; se crea primero
    # ------------------------------------------------------------------
    op.create_table(
        "cash_closes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("opening_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("closing_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "total_sales_cash",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "total_sales_debit",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "total_sales_transfer",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ------------------------------------------------------------------
    # products — índice B-Tree en barcode + FullText en name
    # ------------------------------------------------------------------
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("barcode", sa.String(50), nullable=False),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("current_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("margin_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("barcode", name="uq_products_barcode"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_products_barcode", "products", ["barcode"])
    # FullText index para búsqueda fuzzy por nombre (meta: < 50ms con 5,000 registros).
    # DDL explícito porque SQLAlchemy Core no abstrae CREATE FULLTEXT INDEX.
    op.execute("CREATE FULLTEXT INDEX ix_products_name_fulltext ON products(name)")

    # ------------------------------------------------------------------
    # sales — UUID almacenado como CHAR(36)
    # ------------------------------------------------------------------
    op.create_table(
        "sales",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum("EFECTIVO", "DEBITO", "TRANSFERENCIA", name="payment_method_enum"),
            nullable=False,
        ),
        sa.Column(
            "cash_close_id",
            sa.Integer(),
            sa.ForeignKey("cash_closes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_sales_timestamp", "sales", ["timestamp"])
    op.create_index("ix_sales_cash_close_id", "sales", ["cash_close_id"])

    # ------------------------------------------------------------------
    # sale_items — price_at_sale inmutable; CASCADE al borrar la venta
    # ------------------------------------------------------------------
    op.create_table(
        "sale_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "sale_id",
            sa.CHAR(36),
            sa.ForeignKey("sales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price_at_sale", sa.Numeric(12, 2), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])

    # ------------------------------------------------------------------
    # price_history — registro inmutable de cambios de costo
    # ------------------------------------------------------------------
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_price_history_product_id", "price_history", ["product_id"])


def downgrade() -> None:
    """Elimina todas las tablas en orden inverso (respetando FKs)."""
    op.drop_table("price_history")
    op.drop_table("sale_items")
    op.drop_table("sales")
    op.drop_table("products")
    op.drop_table("cash_closes")
