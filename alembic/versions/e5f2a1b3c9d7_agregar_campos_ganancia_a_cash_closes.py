"""Agregar columnas de ganancia estimada a cash_closes.

Persiste la ganancia bruta estimada y el costo de mercadería vendida
al momento del cierre de caja, calculados sobre el costo actual de
los productos (aproximación válida para informes de rentabilidad).

Revision ID: e5f2a1b3c9d7
Revises: d4e1f0b2c3a8
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "e5f2a1b3c9d7"
down_revision = "d4e1f0b2c3a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Agrega gross_profit_estimate y total_cost_estimate a cash_closes."""
    op.add_column(
        "cash_closes",
        sa.Column("gross_profit_estimate", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "cash_closes",
        sa.Column("total_cost_estimate", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    """Elimina las columnas de ganancia estimada."""
    op.drop_column("cash_closes", "total_cost_estimate")
    op.drop_column("cash_closes", "gross_profit_estimate")
