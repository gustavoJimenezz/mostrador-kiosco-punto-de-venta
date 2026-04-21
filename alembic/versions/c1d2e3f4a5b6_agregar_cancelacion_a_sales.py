"""agregar_cancelacion_a_sales

Agrega columnas is_cancelled y cancelled_at a la tabla sales para
soportar cancelación de ventas con restauración de stock (soft delete).

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-04-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sales") as batch_op:
        batch_op.add_column(
            sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("cancelled_at", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("is_cancelled")
