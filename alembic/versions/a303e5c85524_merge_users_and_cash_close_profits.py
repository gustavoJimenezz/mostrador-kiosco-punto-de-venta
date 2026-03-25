"""merge_users_and_cash_close_profits

Revision ID: a303e5c85524
Revises: c9d8e7f6a5b4, e5f2a1b3c9d7
Create Date: 2026-03-24 21:44:15.510891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a303e5c85524'
down_revision: Union[str, Sequence[str], None] = ('c9d8e7f6a5b4', 'e5f2a1b3c9d7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
