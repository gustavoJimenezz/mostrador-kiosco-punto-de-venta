"""Agregar tabla cash_movements para movimientos manuales de caja.

Crea la tabla ``cash_movements`` para registrar ingresos y egresos
manuales dentro de una sesión de arqueo (``cash_closes``).
Permite cuadrar el efectivo al cierre considerando movimientos que
no provienen de ventas (pago a proveedores, retiro de caja, etc.).

Revision ID: b5e8f2a9c107
Revises: 3f2a1b4c8d90
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "b5e8f2a9c107"
down_revision = "3f2a1b4c8d90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla cash_movements con FK a cash_closes."""
    from sqlalchemy import inspect as sa_inspect

    bind = op.get_bind()
    if "cash_movements" not in sa_inspect(bind).get_table_names():
        op.create_table(
            "cash_movements",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "cash_close_id",
                sa.Integer(),
                sa.ForeignKey("cash_closes.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "movement_type",
                sa.Enum("INGRESO", "EGRESO", name="movement_type_enum"),
                nullable=False,
            ),
            sa.Column(
                "description",
                sa.String(250),
                nullable=False,
                server_default="",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
        )
        op.create_index(
            "ix_cash_movements_cash_close_id",
            "cash_movements",
            ["cash_close_id"],
        )


def downgrade() -> None:
    """Elimina la tabla cash_movements y su tipo enum."""
    op.drop_index("ix_cash_movements_cash_close_id", table_name="cash_movements")
    op.drop_table("cash_movements")
    # Eliminar el tipo enum en MariaDB (no aplica en MySQL < 5.7, sin efecto)
    sa.Enum(name="movement_type_enum").drop(op.get_bind(), checkfirst=True)
