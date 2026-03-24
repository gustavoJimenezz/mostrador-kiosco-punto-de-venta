"""Presenter del historial de ventas (patrón MVP).

Lógica de presentación para la vista de historial (F2).
Sin dependencias de PySide6: Python puro, completamente testeable.

Responsabilidades:
- Recibir la lista de ventas del worker y notificar a la vista.
- Calcular el total del día para mostrar en el resumen.
- Delegar la carga del detalle de una venta al worker correspondiente.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from src.domain.models.sale import Sale


@runtime_checkable
class ISalesHistoryView(Protocol):
    """Interfaz que la vista de historial de ventas debe implementar."""

    def show_sales(self, sales: list[Sale]) -> None:
        """Muestra la lista de ventas en la tabla de historial."""
        ...

    def show_sale_detail(self, items: list[dict]) -> None:
        """Muestra el detalle de ítems de la venta seleccionada."""
        ...

    def show_daily_total(self, total: Decimal) -> None:
        """Muestra el total del día en el label de resumen."""
        ...

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error en la barra de estado."""
        ...

    def show_loading(self, loading: bool) -> None:
        """Muestra u oculta el indicador de carga."""
        ...


class SalesHistoryPresenter:
    """Presenter para la vista de historial de ventas (F2).

    Args:
        view: Instancia que implementa ISalesHistoryView.

    Examples:
        >>> presenter = SalesHistoryPresenter(view)
        >>> presenter.on_sales_loaded([sale1, sale2])
    """

    def __init__(self, view: ISalesHistoryView) -> None:
        self._view = view
        self._sales: list[Sale] = []

    # ------------------------------------------------------------------
    # Callbacks de workers
    # ------------------------------------------------------------------

    def on_sales_loaded(self, sales: list[Sale]) -> None:
        """Callback: recibe la lista de ventas desde LoadSalesWorker.

        Calcula el total del día sumando ``total_amount`` de cada venta
        (ya persistido como snapshot en la DB).

        Args:
            sales: Lista de Sale sin ítems cargados.
        """
        self._sales = sales
        self._view.show_loading(False)
        self._view.show_sales(sales)

        total = sum(
            (s.total_amount.amount for s in sales),
            Decimal("0"),
        )
        self._view.show_daily_total(total)

    def on_detail_loaded(self, items: list[dict]) -> None:
        """Callback: recibe el detalle de ítems desde LoadSaleDetailWorker.

        Args:
            items: Lista de dicts con claves product_name, quantity,
                   price_at_sale, subtotal.
        """
        self._view.show_sale_detail(items)

    def on_worker_error(self, message: str) -> None:
        """Callback: error en cualquier worker del historial.

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

    def get_sale_by_row(self, row: int) -> Optional[Sale]:
        """Retorna la venta correspondiente a la fila seleccionada.

        Args:
            row: Índice de fila en la tabla de ventas.

        Returns:
            Sale correspondiente, o None si el índice está fuera de rango.
        """
        if 0 <= row < len(self._sales):
            return self._sales[row]
        return None
