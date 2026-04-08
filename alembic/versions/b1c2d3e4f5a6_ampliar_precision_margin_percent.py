"""ampliar_precision_margin_percent

Amplía margin_percent de Numeric(5,2) a Numeric(15,4) para que la
lógica recíproca precio→margen round-tripee exactamente al centavo.

Con 2 decimales el error máximo en precio era ±$0.04 por cada $1000 de costo.
Con 4 decimales el error queda por debajo de $0.001.

Revision ID: b1c2d3e4f5a6
Revises: f7c3b2a1d9e8
Create Date: 2026-04-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'f7c3b2a1d9e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Amplía la precisión de margin_percent a 4 decimales."""
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column(
            "margin_percent",
            type_=sa.Numeric(15, 4),
            existing_type=sa.Numeric(5, 2),
            nullable=False,
        )


def downgrade() -> None:
    """Revierte margin_percent a 2 decimales (puede truncar datos)."""
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column(
            "margin_percent",
            type_=sa.Numeric(5, 2),
            existing_type=sa.Numeric(15, 4),
            nullable=False,
        )
