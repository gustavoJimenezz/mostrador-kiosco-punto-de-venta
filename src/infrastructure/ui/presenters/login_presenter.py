"""Presenter para la pantalla de login (selección de usuario + PIN)."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

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
        cash_close_repo: Repositorio de arqueos (opcional). Si se provee,
            permite verificar si hay sesión de caja abierta y abrirla al
            autenticarse cuando es necesario.
    """

    def __init__(
        self,
        authenticate_use_case: AuthenticateUser,
        user_repository: UserRepository,
        cash_close_repo=None,
    ) -> None:
        self._authenticate = authenticate_use_case
        self._user_repo = user_repository
        self._cash_close_repo = cash_close_repo
        self._view = None

    def set_view(self, view) -> None:
        """Inyecta la vista LoginWindow.

        Args:
            view: Instancia de LoginWindow.
        """
        self._view = view

    def needs_opening_amount(self) -> bool:
        """Retorna True si no hay sesión de caja abierta.

        Se usa para mostrar el campo de monto inicial en el login cuando la
        caja aún no fue abierta en el día. Retorna False ante cualquier error
        de DB para no bloquear el acceso.

        Returns:
            True si se debe pedir el monto inicial al cajero.
        """
        if self._cash_close_repo is None:
            return False
        try:
            return self._cash_close_repo.get_open() is None
        except Exception:
            return False

    def get_active_users(self) -> list[User]:
        """Retorna la lista de usuarios activos para mostrar en la UI.

        Returns:
            Lista de usuarios activos ordenados por nombre.
        """
        return self._user_repo.get_all_active()

    def on_pin_submitted(
        self,
        user_id: int,
        pin: str,
        opening_amount: Optional[Decimal] = None,
    ) -> bool:
        """Verifica el PIN y, si es correcto, inicia la sesión.

        Si se provee ``opening_amount`` y hay un repositorio de caja
        configurado, abre la sesión de caja de forma síncrona antes de
        retornar. Esto permite que la caja quede abierta justo después del
        login sin necesidad de pasar por la vista F10.

        Args:
            user_id: ID del usuario seleccionado en la pantalla de login.
            pin: PIN ingresado en texto plano.
            opening_amount: Monto inicial de caja. Solo se usa cuando
                ``needs_opening_amount()`` es True.

        Returns:
            True si la autenticación fue exitosa, False en caso contrario.
        """
        try:
            user = self._authenticate.execute(user_id, pin)
            AppSession.login(user)
            if opening_amount is not None and self._cash_close_repo is not None:
                from src.application.use_cases.get_or_open_cash_close import (
                    GetOrOpenCashClose,
                )
                GetOrOpenCashClose(self._cash_close_repo).execute(
                    opening_amount=opening_amount
                )
            return True
        except AuthenticationError as exc:
            if self._view:
                self._view.show_error(str(exc))
            return False
