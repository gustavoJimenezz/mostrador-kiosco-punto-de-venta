"""Caso de uso: verificar PIN de administrador para desbloquear funciones."""

from __future__ import annotations

import bcrypt

from src.domain.ports.user_repository import UserRepository


class ElevateToAdmin:
    """Verifica que el PIN ingresado corresponde a algún usuario ADMIN activo.

    No requiere seleccionar un usuario específico: basta con que el PIN
    coincida con cualquier administrador. Esto permite que cualquier admin
    desbloquee las funciones de configuración sin identificarse primero.

    Args:
        user_repository: Repositorio de usuarios.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._repo = user_repository

    def execute(self, pin: str) -> bool:
        """Verifica el PIN contra todos los administradores activos.

        Args:
            pin: PIN en texto plano ingresado en el diálogo de acceso.

        Returns:
            True si el PIN coincide con algún administrador activo.
        """
        admins = self._repo.get_all_admins()
        pin_bytes = pin.encode("utf-8")
        return any(
            bcrypt.checkpw(pin_bytes, admin.pin_hash.encode("utf-8"))
            for admin in admins
        )
