"""Agregar tabla users para autenticación de operadores del POS.

Crea la tabla ``users`` con roles ADMIN/OPERATOR e inserta un usuario
administrador por defecto con PIN "1234" (cambiar tras el primer uso).

Revision ID: c9d8e7f6a5b4
Revises: b5e8f2a9c107
Create Date: 2026-03-23
"""

from __future__ import annotations

import bcrypt
import sqlalchemy as sa
from alembic import op

revision = "c9d8e7f6a5b4"
down_revision = "b5e8f2a9c107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla users e inserta el admin por defecto."""
    from sqlalchemy import inspect as sa_inspect

    bind = op.get_bind()
    if "users" not in sa_inspect(bind).get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column(
                "role",
                sa.Enum("admin", "operator", name="user_role_enum"),
                nullable=False,
            ),
            # bcrypt genera hashes de exactamente 60 caracteres.
            sa.Column("pin_hash", sa.String(60), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
        )

    # Usuario ADMIN por defecto. PIN: 1234 — cambiar tras el primer uso.
    # Idempotente: solo inserta si no existe ningún admin.
    result = bind.execute(sa.text("SELECT COUNT(*) FROM users WHERE role = 'admin'"))
    if result.scalar() == 0:
        pin_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode("utf-8")
        op.execute(
            sa.text(
                "INSERT INTO users (name, role, pin_hash, is_active) "
                "VALUES ('Administrador', 'admin', :pin_hash, 1)"
            ).bindparams(pin_hash=pin_hash)
        )


def downgrade() -> None:
    """Elimina la tabla users y su tipo enum."""
    op.drop_table("users")
    sa.Enum(name="user_role_enum").drop(op.get_bind(), checkfirst=True)
