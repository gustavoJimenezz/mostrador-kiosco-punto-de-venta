"""Agregar tabla categories y FK en products.category_id.

Crea la tabla ``categories`` y establece la FK desde ``products.category_id``
hacia ``categories.id`` con ``ON DELETE SET NULL`` para no romper productos
existentes si se elimina una categoría.

Revision ID: 3f2a1b4c8d90
Revises: 1bafd69c0714
Create Date: 2026-03-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3f2a1b4c8d90"
down_revision: Union[str, Sequence[str], None] = "1bafd69c0714"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea tabla categories y agrega FK en products.category_id."""
    from sqlalchemy import inspect as sa_inspect

    bind = op.get_bind()
    existing_tables = sa_inspect(bind).get_table_names()

    # ------------------------------------------------------------------
    # categories — tabla de categorías (debe existir antes de la FK)
    # Idempotente: si ya existe (ej. por una migración parcial previa),
    # se omite la creación sin error.
    # ------------------------------------------------------------------
    if "categories" not in existing_tables:
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.UniqueConstraint("name", name="uq_categories_name"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("ix_categories_name", "categories", ["name"])

    # ------------------------------------------------------------------
    # products.category_id — agregar FK hacia categories.id
    # SQLite no soporta ADD CONSTRAINT sobre tablas existentes; la FK
    # se omite en SQLite y queda enforced por PRAGMA foreign_keys=ON
    # definido en el engine (create_sqlite_engine). En MariaDB se agrega
    # normalmente.
    # ------------------------------------------------------------------
    if bind.dialect.name != "sqlite":
        existing_fks = [
            fk["name"]
            for fk in sa_inspect(bind).get_foreign_keys("products")
        ]
        if "fk_products_category_id" not in existing_fks:
            op.create_foreign_key(
                "fk_products_category_id",
                "products",
                "categories",
                ["category_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    """Elimina FK de products y la tabla categories."""
    op.drop_constraint("fk_products_category_id", "products", type_="foreignkey")
    op.drop_table("categories")
