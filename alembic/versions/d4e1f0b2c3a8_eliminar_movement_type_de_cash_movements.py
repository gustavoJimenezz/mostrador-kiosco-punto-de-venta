"""Eliminar columna movement_type de cash_movements.

El tipo de movimiento (ingreso/egreso) ahora se determina por el signo del
monto: positivo = ingreso, negativo = egreso.

Revision ID: d4e1f0b2c3a8
Revises: b5e8f2a9c107
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "d4e1f0b2c3a8"
down_revision = "b5e8f2a9c107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Elimina la columna movement_type y convierte montos existentes a signo."""
    # Convertir egresos existentes a montos negativos antes de eliminar la columna
    op.execute(
        "UPDATE cash_movements SET amount = -ABS(amount) WHERE movement_type = 'EGRESO'"
    )
    op.drop_column("cash_movements", "movement_type")
    # El tipo enum en MariaDB se elimina implícitamente al no estar referenciado


def downgrade() -> None:
    """Restaura la columna movement_type y convierte montos negativos a EGRESO."""
    op.add_column(
        "cash_movements",
        sa.Column(
            "movement_type",
            sa.Enum("INGRESO", "EGRESO", name="movement_type_enum"),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE cash_movements SET movement_type = CASE WHEN amount >= 0 THEN 'INGRESO' ELSE 'EGRESO' END"
    )
    op.execute(
        "UPDATE cash_movements SET amount = ABS(amount) WHERE movement_type = 'EGRESO'"
    )
    op.alter_column("cash_movements", "movement_type", nullable=False)
