"""Presenter del historial de cierres de caja (patrón MVP).

Lógica de presentación para la vista de historial de arqueos (solo ADMIN).
Sin dependencias de PySide6: Python puro, completamente testeable.

Responsabilidades:
- Recibir la lista de CashClose del worker y notificar a la vista.
- Delegar validaciones de rango de fechas al caso de uso.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models.cash_close import CashClose


@runtime_checkable
class ICashHistoryView(Protocol):
    """Interfaz que la vista de historial de arqueos debe implementar."""

    def show_closes(self, closes: list[CashClose]) -> None:
        """Muestra la lista de arqueos en la tabla."""
        ...

    def show_loading(self, loading: bool) -> None:
        """Muestra u oculta el indicador de carga."""
        ...

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error."""
        ...


class CashHistoryPresenter:
    """Presenter para la vista de historial de arqueos de caja.

    Args:
        view: Instancia que implementa ICashHistoryView.

    Examples:
        >>> presenter = CashHistoryPresenter(view)
        >>> presenter.on_closes_loaded([close1, close2])
    """

    def __init__(self, view: ICashHistoryView) -> None:
        self._view = view
        self._closes: list[CashClose] = []

    # ------------------------------------------------------------------
    # Callbacks de workers
    # ------------------------------------------------------------------

    def on_closes_loaded(self, closes: list[CashClose]) -> None:
        """Callback: recibe la lista de arqueos desde LoadCashHistoryWorker.

        Args:
            closes: Lista de CashClose del rango consultado.
        """
        self._closes = closes
        self._view.show_loading(False)
        self._view.show_closes(closes)

    def on_worker_error(self, message: str) -> None:
        """Callback: error en el worker de historial.

        Args:
            message: Descripción del error.
        """
        self._view.show_loading(False)
        self._view.show_error(message)

    # ------------------------------------------------------------------
    # Acciones de la vista
    # ------------------------------------------------------------------

    def on_search_requested(self) -> None:
        """Notifica que el usuario inició una búsqueda (muestra spinner)."""
        self._view.show_loading(True)
