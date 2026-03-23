"""Tests unitarios del StockInjectPresenter (MVP).

No requieren PySide6 instalado. El StockInjectPresenter es Python puro y se
testea con una FakeStockInjectView que implementa IStockInjectView en memoria.

Casos cubiertos:
- Barcode encontrado con qty válida → retorna (product, qty).
- Barcode encontrado con qty=0 → retorna None, muestra error.
- Barcode no encontrado → show_status con is_error=True.
- Búsqueda vacía → show_status con is_error=True.
- Un resultado → inyección automática (retorna tupla).
- Múltiples resultados → show_search_results llamado, retorna None.
- Selección de lista con qty válida → retorna (product, qty).
- Stock inyectado → add_or_update_injected_row + clear_search + show_status con qty.
- Error de worker → show_status con is_error=True.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import pytest

from src.domain.models.product import Product
from src.infrastructure.ui.presenters.stock_inject_presenter import (
    IStockInjectView,
    StockInjectPresenter,
)


# ---------------------------------------------------------------------------
# FakeView
# ---------------------------------------------------------------------------


class FakeStockInjectView:
    """Vista falsa que registra todas las llamadas del presenter."""

    def __init__(self) -> None:
        self.search_results: list[Product] = []
        self.status_messages: list[tuple[str, bool]] = []
        self.injected_rows: list[Product] = []
        self._quantity: int = 1
        self.clear_search_called: int = 0

    def show_search_results(self, products: list[Product]) -> None:
        self.search_results = list(products)

    def show_status(self, message: str, is_error: bool = False) -> None:
        self.status_messages.append((message, is_error))

    def add_or_update_injected_row(self, product: Product) -> None:
        self.injected_rows.append(product)

    def get_quantity(self) -> int:
        return self._quantity

    def clear_search(self) -> None:
        self.clear_search_called += 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(name: str = "Producto Test", stock: int = 10, pid: int = 1) -> Product:
    return Product(
        id=pid,
        barcode="7790000000001",
        name=name,
        current_cost=Decimal("100.00"),
        margin_percent=Decimal("30.00"),
        stock=stock,
    )


@pytest.fixture
def view() -> FakeStockInjectView:
    return FakeStockInjectView()


@pytest.fixture
def presenter(view: FakeStockInjectView) -> StockInjectPresenter:
    return StockInjectPresenter(view=view)


# ---------------------------------------------------------------------------
# Tests: on_barcode_found
# ---------------------------------------------------------------------------


class TestOnBarcodeFound:
    def test_qty_valida_retorna_tupla(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 5
        product = _make_product()
        result = presenter.on_barcode_found(product)

        assert result is not None
        returned_product, qty = result
        assert returned_product is product
        assert qty == 5

    def test_qty_cero_retorna_none_y_muestra_error(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 0
        result = presenter.on_barcode_found(_make_product())

        assert result is None
        assert any(is_error for _, is_error in view.status_messages)

    def test_guarda_last_injected_qty(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 7
        presenter.on_barcode_found(_make_product())
        assert presenter._last_injected_qty == 7


class TestOnBarcodeNotFound:
    def test_muestra_error_con_barcode(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        presenter.on_barcode_not_found("7791234567890")

        assert len(view.status_messages) == 1
        message, is_error = view.status_messages[0]
        assert is_error is True
        assert "7791234567890" in message


# ---------------------------------------------------------------------------
# Tests: on_search_results_ready
# ---------------------------------------------------------------------------


class TestOnSearchResultsReady:
    def test_lista_vacia_muestra_error(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        result = presenter.on_search_results_ready([])

        assert result is None
        assert any(is_error for _, is_error in view.status_messages)

    def test_un_resultado_retorna_tupla_automaticamente(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 3
        product = _make_product()
        result = presenter.on_search_results_ready([product])

        assert result is not None
        returned_product, qty = result
        assert returned_product is product
        assert qty == 3
        # No se llamó show_search_results
        assert len(view.search_results) == 0

    def test_multiples_resultados_muestra_lista_y_retorna_none(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        products = [_make_product("A", pid=1), _make_product("B", pid=2)]
        result = presenter.on_search_results_ready(products)

        assert result is None
        assert len(view.search_results) == 2

    def test_un_resultado_con_qty_invalida_retorna_none(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 0
        result = presenter.on_search_results_ready([_make_product()])

        assert result is None
        assert any(is_error for _, is_error in view.status_messages)


# ---------------------------------------------------------------------------
# Tests: on_product_selected_from_list
# ---------------------------------------------------------------------------


class TestOnProductSelectedFromList:
    def test_qty_valida_retorna_tupla(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 10
        product = _make_product()
        result = presenter.on_product_selected_from_list(product)

        assert result is not None
        assert result == (product, 10)

    def test_qty_invalida_retorna_none(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 0
        result = presenter.on_product_selected_from_list(_make_product())

        assert result is None


# ---------------------------------------------------------------------------
# Tests: on_stock_injected
# ---------------------------------------------------------------------------


class TestOnStockInjected:
    def test_agrega_fila_y_limpia_busqueda(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        product = _make_product(stock=15)
        presenter.on_stock_injected(product)

        assert len(view.injected_rows) == 1
        assert view.injected_rows[0] is product
        assert view.clear_search_called == 1

    def test_mensaje_incluye_nombre_qty_y_stock(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        view._quantity = 4
        presenter.on_barcode_found(_make_product())  # registra last_injected_qty=4

        product = _make_product(name="Pepsi 500ml", stock=24)
        presenter.on_stock_injected(product)

        last_msg, is_error = view.status_messages[-1]
        assert is_error is False
        assert "Pepsi 500ml" in last_msg
        assert "4" in last_msg
        assert "24" in last_msg


# ---------------------------------------------------------------------------
# Tests: on_worker_error
# ---------------------------------------------------------------------------


class TestOnWorkerError:
    def test_muestra_error(
        self, presenter: StockInjectPresenter, view: FakeStockInjectView
    ) -> None:
        presenter.on_worker_error("Stock insuficiente: disponible=2, requerido=5")

        assert len(view.status_messages) == 1
        message, is_error = view.status_messages[0]
        assert is_error is True
        assert "Stock insuficiente" in message
