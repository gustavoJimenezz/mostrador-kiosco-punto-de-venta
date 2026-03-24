"""Sesión de usuario activa durante la vida de la aplicación POS."""

from __future__ import annotations

from typing import Optional

from src.domain.models.user import User, UserRole


class AppSession:
    """Almacena el usuario autenticado en memoria durante la ejecución.

    No persiste entre reinicios: la sesión finaliza al cerrar el programa.
    Implementado como clase de métodos de clase (singleton sin instancia).

    Note:
        La autenticación la gestiona ``AuthenticateUser``. Esta clase solo
        mantiene la referencia al usuario ya verificado.
    """

    _current_user: Optional[User] = None

    @classmethod
    def login(cls, user: User) -> None:
        """Guarda al usuario autenticado en la sesión activa.

        Args:
            user: Usuario ya verificado por AuthenticateUser.
        """
        cls._current_user = user

    @classmethod
    def logout(cls) -> None:
        """Limpia la sesión activa."""
        cls._current_user = None

    @classmethod
    def current_user(cls) -> Optional[User]:
        """Retorna el usuario activo, o None si no hay sesión.

        Returns:
            El User autenticado, o None.
        """
        return cls._current_user

    @classmethod
    def is_admin(cls) -> bool:
        """Retorna True si el usuario activo tiene rol ADMIN.

        Maneja tanto ``UserRole.ADMIN`` (enum) como ``"admin"`` (string
        devuelto por SQLAlchemy cuando el mapeo es con enum de strings).

        Returns:
            True solo si hay sesión activa con rol ADMIN.
        """
        if cls._current_user is None:
            return False
        role = cls._current_user.role
        return role == UserRole.ADMIN or role == UserRole.ADMIN.value

    @classmethod
    def is_authenticated(cls) -> bool:
        """Retorna True si hay un usuario activo en sesión.

        Returns:
            True si hay sesión activa.
        """
        return cls._current_user is not None
