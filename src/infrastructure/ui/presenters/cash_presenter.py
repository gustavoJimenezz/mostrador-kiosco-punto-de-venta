"""Presenter del arqueo de caja (patrón MVP).

Lógica de presentación para la vista de cierre de caja (F10).
Sin dependencias de PySide6: Python puro, completamente testeable.

Responsabilidades:
- Calcular el resumen del día (ventas por método, movimientos, saldo esperado).
- Coordinar apertura/cierre de sesión y registro de movimientos.
- Notificar a la vista qué mostrar en cada estado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement


@runtime_checkable
class ICashView(Protocol):
    """Interfaz que la vista de arqueo de caja debe implementar."""

    def show_session_open(self, cash_close: CashClose) -> None:
        """Muestra el estado de sesión abierta con sus datos."""
        ...

    def show_session_closed(self) -> None:
        """Muestra el estado de sesión cerrada (sin arqueo activo)."""
        ...

    def show_sales_summary(
        self,
        cash: Decimal,
        debit: Decimal,
        transfer: Decimal,
    ) -> None:
        """Actualiza los labels de totales de ventas del día."""
        ...

    def show_movements(self, movements: list[CashMovement]) -> None:
        """Actualiza la tabla de movimientos manuales."""
        ...

    def show_close_result(self, difference: Optional[Decimal]) -> None:
        """Muestra el resultado del cierre: diferencia contada vs esperada."""
        ...

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error en la barra de estado."""
        ...

    def show_success(self, message: str) -> None:
        """Muestra un mensaje de éxito en la barra de estado."""
        ...


class CashPresenter:
    """Presenter para la vista de arqueo de caja (F10).

    Gestiona el estado de la sesión de caja activa y coordina
    las acciones del cajero con la vista.

    Args:
        view: Instancia que implementa ICashView.

    Examples:
        >>> presenter = CashPresenter(view)
        >>> presenter.on_state_loaded({"cash_close": None, "movements": [], "sales_totals": {}})
    """

    def __init__(self, view: ICashView) -> None:
        self._view = view
        self._active_close: Optional[CashClose] = None
        self._movements: list[CashMovement] = []
        self._sales_totals: dict[str, Decimal] = {}

    # ------------------------------------------------------------------
    # Callbacks de workers
    # ------------------------------------------------------------------

    def on_state_loaded(self, state: dict) -> None:
        """Callback: recibe el estado completo del arqueo desde LoadCashStateWorker.

        Args:
            state: Diccionario con ``cash_close``, ``movements``, ``sales_totals``.
        """
        self._active_close = state.get("cash_close")
        self._movements = state.get("movements", [])
        self._sales_totals = state.get("sales_totals", {})

        if self._active_close:
            self._view.show_session_open(self._active_close)
        else:
            self._view.show_session_closed()

        cash = self._sales_totals.get("EFECTIVO", Decimal("0"))
        debit = self._sales_totals.get("DEBITO", Decimal("0"))
        transfer = self._sales_totals.get("TRANSFERENCIA", Decimal("0"))
        self._view.show_sales_summary(cash, debit, transfer)
        self._view.show_movements(self._movements)

    def on_session_opened(self, cash_close: CashClose) -> None:
        """Callback: sesión abierta exitosamente.

        Args:
            cash_close: Arqueo de caja recién creado o ya existente.
        """
        self._active_close = cash_close
        self._view.show_session_open(cash_close)
        self._view.show_success("Caja abierta correctamente.")

    def on_session_closed(self, cash_close: CashClose) -> None:
        """Callback: sesión cerrada exitosamente.

        Args:
            cash_close: Arqueo de caja recién cerrado.
        """
        self._active_close = None
        difference = cash_close.cash_difference
        self._view.show_close_result(difference)
        self._view.show_session_closed()

        if difference is not None:
            if difference >= Decimal("0"):
                msg = f"Caja cerrada. Sobrante: ${difference:,.2f}"
            else:
                msg = f"Caja cerrada. Faltante: ${abs(difference):,.2f}"
            self._view.show_success(msg)

    def on_movement_added(self, movement: CashMovement) -> None:
        """Callback: movimiento manual registrado exitosamente.

        Args:
            movement: CashMovement persistido.
        """
        self._movements.append(movement)
        self._view.show_movements(self._movements)
        tipo = "Ingreso" if movement.is_income else "Egreso"
        self._view.show_success(
            f"{tipo} registrado: ${abs(movement.amount):,.2f} — {movement.description}"
        )

    def on_worker_error(self, message: str) -> None:
        """Callback: error en cualquier worker de caja.

        Args:
            message: Descripción del error.
        """
        self._view.show_error(message)

    # ------------------------------------------------------------------
    # Acciones del cajero (validaciones de UI)
    # ------------------------------------------------------------------

    def on_open_session_requested(self, opening_amount: Decimal) -> bool:
        """Valida el monto inicial antes de lanzar el worker de apertura.

        Args:
            opening_amount: Monto ingresado por el cajero.

        Returns:
            True si la validación pasa y se debe lanzar el worker.
        """
        if opening_amount < Decimal("0"):
            self._view.show_error("El monto inicial no puede ser negativo.")
            return False
        return True

    def on_close_session_requested(self, closing_amount: Decimal) -> bool:
        """Valida el monto contado antes de lanzar el worker de cierre.

        Args:
            closing_amount: Monto físico contado por el cajero.

        Returns:
            True si la validación pasa y se debe lanzar el worker.
        """
        if self._active_close is None:
            self._view.show_error("No hay ninguna sesión de caja abierta.")
            return False
        if closing_amount < Decimal("0"):
            self._view.show_error("El monto contado no puede ser negativo.")
            return False
        return True

    def on_add_movement_requested(
        self,
        amount: Decimal,
        description: str,
    ) -> bool:
        """Valida los datos del movimiento antes de lanzar el worker.

        Args:
            amount: Monto del movimiento.
            description: Descripción ingresada por el cajero.

        Returns:
            True si la validación pasa y se debe lanzar el worker.
        """
        if self._active_close is None:
            self._view.show_error("No hay ninguna sesión de caja abierta.")
            return False
        if amount == Decimal("0"):
            self._view.show_error("El monto del movimiento no puede ser cero.")
            return False
        if not description.strip():
            self._view.show_error("La descripción del movimiento es obligatoria.")
            return False
        return True

    def get_active_cash_close_id(self) -> Optional[int]:
        """Retorna el ID del arqueo activo, o None si no hay ninguno.

        Returns:
            ID del CashClose abierto, o None.
        """
        return self._active_close.id if self._active_close else None
