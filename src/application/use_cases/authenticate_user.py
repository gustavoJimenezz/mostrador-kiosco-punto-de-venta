"""Caso de uso: autenticar un usuario con su PIN."""

from __future__ import annotations

import bcrypt

from src.domain.models.user import User
from src.domain.ports.user_repository import UserRepository


class AuthenticationError(Exception):
    """Se lanza cuando el PIN es incorrecto o el usuario no existe/está inactivo."""


class AuthenticateUser:
    """Verifica el PIN de un usuario y retorna la entidad autenticada.

    Args:
        user_repository: Repositorio de usuarios.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._repo = user_repository

    def execute(self, user_id: int, pin: str) -> User:
        """Autentica al usuario verificando el hash bcrypt del PIN.

        Args:
            user_id: ID del usuario que intenta ingresar.
            pin: PIN en texto plano ingresado por el usuario.

        Returns:
            El User autenticado.

        Raises:
            AuthenticationError: Si el usuario no existe, está inactivo
                o el PIN es incorrecto.
        """
        user = self._repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Usuario no encontrado o inactivo.")
        if not bcrypt.checkpw(pin.encode("utf-8"), user.pin_hash.encode("utf-8")):
            raise AuthenticationError("PIN incorrecto.")
        return user
