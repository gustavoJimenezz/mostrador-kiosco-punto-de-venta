"""Presenter para la pantalla de login (selección de usuario + PIN)."""

from __future__ import annotations

from src.application.use_cases.authenticate_user import (
    AuthenticateUser,
    AuthenticationError,
)
from src.domain.models.user import User
from src.domain.ports.user_repository import UserRepository
from src.infrastructure.ui.session import AppSession


class LoginPresenter:
    """Maneja la lógica de autenticación para la LoginWindow.

    Args:
        authenticate_use_case: Caso de uso de autenticación.
        user_repository: Repositorio para obtener la lista de usuarios activos.
    """

    def __init__(
        self,
        authenticate_use_case: AuthenticateUser,
        user_repository: UserRepository,
    ) -> None:
        self._authenticate = authenticate_use_case
        self._user_repo = user_repository
        self._view = None

    def set_view(self, view) -> None:
        """Inyecta la vista LoginWindow.

        Args:
            view: Instancia de LoginWindow.
        """
        self._view = view

    def get_active_users(self) -> list[User]:
        """Retorna la lista de usuarios activos para mostrar en la UI.

        Returns:
            Lista de usuarios activos ordenados por nombre.
        """
        return self._user_repo.get_all_active()

    def on_pin_submitted(self, user_id: int, pin: str) -> bool:
        """Verifica el PIN y, si es correcto, inicia la sesión.

        Args:
            user_id: ID del usuario seleccionado en la pantalla de login.
            pin: PIN ingresado en texto plano.

        Returns:
            True si la autenticación fue exitosa, False en caso contrario.
        """
        try:
            user = self._authenticate.execute(user_id, pin)
            AppSession.login(user)
            return True
        except AuthenticationError as exc:
            if self._view:
                self._view.show_error(str(exc))
            return False
