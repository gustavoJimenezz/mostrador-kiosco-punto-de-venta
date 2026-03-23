"""Tests unitarios del StockEditPresenter (MVP).

No requieren PySide6 instalado. El StockEditPresenter es Python puro y se
testea con una FakeStockEditView que implementa IStockEditView en memoria.

Casos cubiertos:
- Barcode encontrado → show_product_form llamado con el producto.
- Confirmar con qty=5 increment → retorna (product, "increment", 5).
- Confirmar con qty=0 → retorna None, muestra error.
- Stock actualizado → add_or_update_edited_row + reset_form llamados.
- Un solo resultado en búsqueda → show_product_form directo (sin lista).
- Múltiples resultados → show_search_results llamado.
- Barcode no encontrado → show_status con is_error=True.
- Sin producto seleccionado al confirmar → retorna None y muestra error.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import pytest

from src.domain.models.product import Product
from src.infrastructure.ui.presenters.stock_edit_presenter import (
    IStockEditView,
    StockEditPresenter,
)


# ---------------------------------------------------------------------------
# FakeView
# ---------------------------------------------------------------------------


class FakeStockEditView:
    """Vista falsa que registra todas las llamadas del presenter."""

    def __init__(self) -> None:
        self.search_results: list[Product] = []
        self.shown_product: Optional[Product] = None
        self.status_messages: list[tuple[str, bool]] = []
        self.edited_rows: list[Product] = []
        self._operation: str = "increment"
        self._quantity: int = 1
        self.reset_called: int = 0

    def show_search_results(self, products: list[Product]) -> None:
        self.search_results = list(products)

    def show_product_form(self, product: Product) -> None:
        self.shown_product = product

    def show_status(self, message: str, is_error: bool = False) -> None:
        self.status_messages.append((message, is_error))

    def add_or_update_edited_row(self, product: Product) -> None:
        self.edited_rows.append(product)

    def get_operation(self) -> str:
        return self._operation

    def get_quantity(self) -> int:
        return self._quantity

    def reset_form(self) -> None:
        self.reset_called += 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_product(
    name: str = "Producto Test",
    stock: int = 10,
    product_id: int = 1,
) -> Product:
    return Product(
        id=product_id,
        barcode="7790000000001",
        name=name,
        current_cost=Decimal("100.00"),
        margin_percent=Decimal("30.00"),
        stock=stock,
    )


@pytest.fixture
def view() -> FakeStockEditView:
    return FakeStockEditView()


@pytest.fixture
def presenter(view: FakeStockEditView) -> StockEditPresenter:
    return StockEditPresenter(view=view)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOnBarcodeFound:
    def test_guarda_producto_seleccionado_y_muestra_formulario(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        product = _make_product()
        presenter.on_barcode_found(product)

        assert view.shown_product is product
        assert presenter._selected_product is product

    def test_barcode_no_encontrado_muestra_error(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        presenter.on_barcode_not_found("7790000099999")

        assert len(view.status_messages) == 1
        message, is_error = view.status_messages[0]
        assert is_error is True
        assert "7790000099999" in message


class TestOnSearchResultsReady:
    def test_lista_vacia_muestra_error(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        presenter.on_search_results_ready([])

        assert len(view.status_messages) == 1
        assert view.status_messages[0][1] is True  # is_error

    def test_un_resultado_va_directo_al_formulario(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        product = _make_product()
        presenter.on_search_results_ready([product])

        assert view.shown_product is product
        assert len(view.search_results) == 0  # no se llamó show_search_results

    def test_multiples_resultados_muestra_lista(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        products = [_make_product("A", product_id=1), _make_product("B", product_id=2)]
        presenter.on_search_results_ready(products)

        assert len(view.search_results) == 2
        assert view.shown_product is None  # no se fue directo al form


class TestOnConfirmStockEditRequested:
    def test_sin_producto_seleccionado_retorna_none(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        view._quantity = 5
        result = presenter.on_confirm_stock_edit_requested()

        assert result is None
        assert any(is_error for _, is_error in view.status_messages)

    def test_cantidad_cero_retorna_none(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        presenter._selected_product = _make_product()
        view._quantity = 0

        result = presenter.on_confirm_stock_edit_requested()

        assert result is None
        assert any(is_error for _, is_error in view.status_messages)

    def test_increment_valido_retorna_tupla(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        product = _make_product()
        presenter._selected_product = product
        view._operation = "increment"
        view._quantity = 5

        result = presenter.on_confirm_stock_edit_requested()

        assert result is not None
        returned_product, operation, qty = result
        assert returned_product is product
        assert operation == "increment"
        assert qty == 5

    def test_decrement_valido_retorna_tupla(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        product = _make_product()
        presenter._selected_product = product
        view._operation = "decrement"
        view._quantity = 3

        result = presenter.on_confirm_stock_edit_requested()

        assert result is not None
        _, operation, qty = result
        assert operation == "decrement"
        assert qty == 3


class TestOnStockUpdated:
    def test_agrega_fila_en_tabla_y_resetea_form(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        product = _make_product(stock=15)
        presenter.on_stock_updated(product)

        assert len(view.edited_rows) == 1
        assert view.edited_rows[0] is product
        assert view.reset_called == 1

    def test_muestra_mensaje_con_nombre_y_stock(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        product = _make_product(name="Coca Cola", stock=20)
        presenter.on_stock_updated(product)

        assert len(view.status_messages) == 1
        message, is_error = view.status_messages[0]
        assert is_error is False
        assert "Coca Cola" in message
        assert "20" in message


class TestOnWorkerError:
    def test_muestra_error(
        self, presenter: StockEditPresenter, view: FakeStockEditView
    ) -> None:
        presenter.on_worker_error("Conexión fallida")

        assert len(view.status_messages) == 1
        message, is_error = view.status_messages[0]
        assert is_error is True
        assert "Conexión fallida" in message
