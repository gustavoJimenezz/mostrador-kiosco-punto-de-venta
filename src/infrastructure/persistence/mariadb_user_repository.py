"""Repositorio MariaDB para la entidad User."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.models.user import User


class MariadbUserRepository:
    """Implementación MariaDB del puerto UserRepository.

    Args:
        session: Sesión SQLAlchemy activa.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Retorna un usuario por su ID, o None si no existe.

        Args:
            user_id: ID del usuario a buscar.

        Returns:
            El User encontrado, o None.
        """
        return self._session.get(User, user_id)

    def get_all_active(self) -> list[User]:
        """Retorna todos los usuarios activos, ordenados por nombre.

        Returns:
            Lista de usuarios con is_active=True.
        """
        stmt = select(User).where(User.is_active.is_(True)).order_by(User.name)
        return list(self._session.scalars(stmt).all())

    def get_all_admins(self) -> list[User]:
        """Retorna todos los usuarios ADMIN activos.

        Returns:
            Lista de administradores con is_active=True.
        """
        from src.infrastructure.persistence.tables import users_table
        from sqlalchemy import text as sa_text

        rows = self._session.execute(
            sa_text(
                "SELECT id FROM users WHERE role = 'admin' AND is_active = 1"
            )
        ).fetchall()
        admin_ids = [row[0] for row in rows]
        return [u for u in (self._session.get(User, uid) for uid in admin_ids) if u]

    def save(self, user: User) -> User:
        """Persiste un usuario nuevo o actualiza uno existente.

        Args:
            user: Entidad User a persistir.

        Returns:
            El User con el id asignado tras el commit.
        """
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user
