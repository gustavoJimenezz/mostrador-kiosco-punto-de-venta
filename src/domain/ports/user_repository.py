"""Puerto de persistencia para la entidad User."""

from __future__ import annotations

from typing import Optional, Protocol

from src.domain.models.user import User


class UserRepository(Protocol):
    """Define el contrato de persistencia para usuarios del POS."""

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Retorna un usuario por su ID, o None si no existe.

        Args:
            user_id: ID del usuario a buscar.

        Returns:
            El User encontrado, o None.
        """
        ...

    def get_all_active(self) -> list[User]:
        """Retorna todos los usuarios con is_active=True, ordenados por nombre.

        Returns:
            Lista de usuarios activos.
        """
        ...

    def get_all_admins(self) -> list[User]:
        """Retorna todos los usuarios con rol ADMIN y is_active=True.

        Returns:
            Lista de usuarios administradores activos.
        """
        ...

    def save(self, user: User) -> User:
        """Persiste un usuario nuevo o actualiza uno existente.

        Args:
            user: Entidad User a persistir.

        Returns:
            El User con el id asignado por la DB.
        """
        ...
