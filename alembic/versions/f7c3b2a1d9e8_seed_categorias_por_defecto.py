"""seed_categorias_por_defecto

Revision ID: f7c3b2a1d9e8
Revises: a303e5c85524
Create Date: 2026-03-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7c3b2a1d9e8'
down_revision: Union[str, Sequence[str], None] = 'a303e5c85524'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIAS_POR_DEFECTO = [
    "Cigarrillos",
    "Golosinas",
    "Bebidas",
    "Galletas",
    "Despensa",
    "Snacks",
]


def upgrade() -> None:
    """Inserta las categorías por defecto. Usa INSERT OR IGNORE / INSERT IGNORE para idempotencia."""
    placeholders = ", ".join(f"('{nombre}')" for nombre in CATEGORIAS_POR_DEFECTO)
    # SQLite usa "INSERT OR IGNORE", MariaDB usa "INSERT IGNORE".
    ignore_keyword = "OR IGNORE" if op.get_bind().dialect.name == "sqlite" else "IGNORE"
    op.execute(sa.text(f"INSERT {ignore_keyword} INTO categories (name) VALUES {placeholders}"))


def downgrade() -> None:
    """Elimina las categorías por defecto insertadas en este seed."""
    nombres_quoted = ", ".join(f"'{nombre}'" for nombre in CATEGORIAS_POR_DEFECTO)
    op.execute(sa.text(f"DELETE FROM categories WHERE name IN ({nombres_quoted})"))
