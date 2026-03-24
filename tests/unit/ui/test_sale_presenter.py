"""Tests unitarios del SalePresenter (MVP).

No requieren PySide6 instalado. El SalePresenter es Python puro y se
testea con una FakeView que implementa ISaleView en memoria.

Cubre todos los criterios de aceptación del Ticket 3.1:
- Agregar producto al carrito por barcode.
- Incrementar cantidad al escanear el mismo barcode dos veces.
- Búsqueda por nombre con resultados vacíos.
- Total de venta actualizado en tiempo real.
- F1 limpia el carrito.
- Confirmar venta vacía muestra error.
- Confirmar venta retorna PaymentMethod para que MainWindow lance el worker.
- Venta completada limpia el carrito.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock

import pytest

from src.domain.models.price import Price
from src.domain.models.product import Product
from src.domain.models.sale import PaymentMethod, Sale, SaleItem
from src.infrastructure.ui.presenters.sale_presenter import ISaleView, SalePresenter


# ---------------------------------------------------------------------------
# FakeView: implementación mínima de ISaleView para tests
# ---------------------------------------------------------------------------


class FakeView:
    """Vista falsa que registra todas las llamadas del presenter.

    Permite verificar en los tests qué métodos fueron invocados y con qué
    argumentos, sin necesidad de Qt.
    """

    def __init__(self) -> None:
        self.cart_items: dict[int, tuple[Product, int]] = {}
        self.last_total: Optional[Price] = None
        self.search_results: list[Product] = []
        self.errors: list[str] = []
        self.sale_confirmed: Optional[Sale] = None
        self.change_dialog_return: bool = True
        self.last_change_dialog_total: Optional[Price] = None

    def show_product_in_cart(self, product: Product, quantity: int) -> None:
        self.cart_items[product.id] = (product, quantity)

    def update_total(self, total: Price) -> None:
        self.last_total = total

    def show_search_results(self, products: list[Product]) -> None:
        self.search_results = products

    def clear_cart_display(self) -> None:
        self.cart_items.clear()

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def show_stock_error(self, message: str) -> None:
        self.errors.append(message)

    def show_sale_confirmed(self, sale: Sale) -> None:
        self.sale_confirmed = sale

    def show_change_dialog(self, total: Price) -> bool:
        self.last_change_dialog_total = total
        return self.change_dialog_return


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(
    barcode: str = "7790001000001",
    name: str = "Alfajor Jorgito",
    cost: str = "250.00",
    margin: str = "35.00",
    stock: int = 50,
    product_id: int = 1,
) -> Product:
    """Crea un Product de prueba con ID asignado."""
    p = Product(
        barcode=barcode,
        name=name,
        current_cost=Decimal(cost),
        margin_percent=Decimal(margin),
        stock=stock,
    )
    p.id = product_id
    return p


def _make_sale(product: Product) -> Sale:
    """Crea un Sale mock que simula una venta exitosa."""
    item = SaleItem(
        product_id=product.id,
        quantity=1,
        price_at_sale=product.current_price.amount,
    )
    sale = Sale(payment_method=PaymentMethod.CASH, items=[item])
    return sale


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def view() -> FakeView:
    return FakeView()


@pytest.fixture
def presenter(view: FakeView) -> SalePresenter:
    return SalePresenter(view=view)


@pytest.fixture
def product() -> Product:
    return _make_product()


# ---------------------------------------------------------------------------
# Tests: gestión del carrito
# ---------------------------------------------------------------------------


class TestCartManagement:
    def test_barcode_found_adds_product_to_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)

        assert product.id in presenter.get_cart()
        assert presenter.get_cart()[product.id][1] == 1

    def test_barcode_found_calls_show_product_in_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)

        assert product.id in view.cart_items
        assert view.cart_items[product.id][1] == 1

    def test_duplicate_barcode_increments_quantity(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_barcode_found(product)

        assert presenter.get_cart()[product.id][1] == 2
        assert view.cart_items[product.id][1] == 2

    def test_two_different_products_added_to_cart(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        p1 = _make_product(barcode="001", name="Producto A", product_id=1)
        p2 = _make_product(barcode="002", name="Producto B", product_id=2)

        presenter.on_barcode_found(p1)
        presenter.on_barcode_found(p2)

        assert len(presenter.get_cart()) == 2

    def test_product_selected_from_list_adds_to_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_product_selected_from_list(product)

        assert product.id in presenter.get_cart()
        assert presenter.get_cart()[product.id][1] == 1

    def test_product_selected_increments_if_already_in_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_product_selected_from_list(product)

        assert presenter.get_cart()[product.id][1] == 2

    def test_new_sale_clears_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_new_sale()

        assert len(presenter.get_cart()) == 0
        assert len(view.cart_items) == 0

    def test_new_sale_resets_total_to_zero(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_new_sale()

        assert view.last_total.amount == Decimal("0.00")

    def test_get_cart_returns_defensive_copy(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        cart_copy = presenter.get_cart()
        cart_copy.clear()

        assert len(presenter.get_cart()) == 1


# ---------------------------------------------------------------------------
# Tests: cálculo del total
# ---------------------------------------------------------------------------


class TestTotalCalculation:
    def test_total_correct_for_single_item(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(cost="250.00", margin="35.00")
        presenter.on_barcode_found(product)

        assert view.last_total == product.current_price

    def test_total_correct_for_two_units_same_product(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(cost="250.00", margin="35.00")
        presenter.on_barcode_found(product)
        presenter.on_barcode_found(product)

        assert view.last_total == product.current_price * 2

    def test_total_two_different_products(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        p1 = _make_product(barcode="001", cost="100.00", margin="0.00", product_id=1)
        p2 = _make_product(barcode="002", cost="200.00", margin="0.00", product_id=2)

        presenter.on_barcode_found(p1)
        presenter.on_barcode_found(p2)

        assert view.last_total == Price("300.00")

    def test_quantity_change_updates_total(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(cost="100.00", margin="0.00")
        presenter.on_barcode_found(product)
        presenter.on_quantity_changed(product.id, 3)

        assert view.last_total == Price("300.00")

    def test_quantity_zero_removes_item_from_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_quantity_changed(product.id, 0)

        assert product.id not in presenter.get_cart()

    def test_get_total_empty_cart_is_zero(
        self, presenter: SalePresenter
    ) -> None:
        assert presenter.get_total() == Price("0")


# ---------------------------------------------------------------------------
# Tests: manejo de errores
# ---------------------------------------------------------------------------


class TestErrors:
    def test_barcode_not_found_shows_error(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        presenter.on_barcode_not_found("7790000000000")

        assert len(view.errors) == 1
        assert "7790000000000" in view.errors[0]

    def test_confirm_sale_empty_cart_shows_error(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        result = presenter.on_confirm_sale_requested()

        assert result is None
        assert len(view.errors) == 1
        assert "vacío" in view.errors[0].lower()

    def test_product_without_id_shows_error_and_not_added(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product_no_id = Product(
            barcode="001",
            name="Sin ID",
            current_cost=Decimal("100"),
            margin_percent=Decimal("0"),
        )
        presenter.on_barcode_found(product_no_id)

        assert len(view.errors) == 1
        assert len(presenter.get_cart()) == 0

    def test_search_error_shows_error(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        presenter.on_search_error("Connection refused")

        assert len(view.errors) == 1
        assert "Connection refused" in view.errors[0]

    def test_search_no_results_shows_error(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        presenter.on_search_results_ready([])

        assert len(view.errors) == 1

    def test_sale_error_shows_error_and_preserves_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_sale_error("Stock insuficiente para 'Alfajor Jorgito'")

        assert len(view.errors) == 1
        assert "Stock insuficiente" in view.errors[0]
        assert len(presenter.get_cart()) == 1


# ---------------------------------------------------------------------------
# Tests: flujo de confirmación de venta
# ---------------------------------------------------------------------------


class TestConfirmSale:
    def test_confirm_sale_returns_payment_method(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        result = presenter.on_confirm_sale_requested()

        assert result == PaymentMethod.CASH

    def test_confirm_sale_returns_none_when_dialog_cancelled(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        view.change_dialog_return = False
        presenter.on_barcode_found(product)
        result = presenter.on_confirm_sale_requested()

        assert result is None

    def test_sale_completed_clears_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        sale = _make_sale(product)

        presenter.on_sale_completed(sale)

        assert len(presenter.get_cart()) == 0
        assert len(view.cart_items) == 0

    def test_sale_completed_notifies_view(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        sale = _make_sale(product)

        presenter.on_sale_completed(sale)

        assert view.sale_confirmed == sale

    def test_sale_completed_resets_total(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        sale = _make_sale(product)

        presenter.on_sale_completed(sale)

        assert view.last_total.amount == Decimal("0.00")


# ---------------------------------------------------------------------------
# Tests: búsqueda por nombre
# ---------------------------------------------------------------------------


class TestSearchByName:
    def test_search_results_passed_to_view(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        products = [
            _make_product(barcode="001", name="Coca Cola", product_id=1),
            _make_product(barcode="002", name="Coca Cola Zero", product_id=2),
        ]
        presenter.on_search_results_ready(products)

        assert view.search_results == products

    def test_cash_close_shows_stub_message(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        presenter.on_cash_close()

        assert len(view.errors) == 1


# ---------------------------------------------------------------------------
# Tests: flujo F12 — pago en efectivo con ChangeDialog
# ---------------------------------------------------------------------------


class TestCashPayment:
    def test_cash_payment_empty_cart_shows_error_returns_none(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        result = presenter.on_cash_payment_requested()

        assert result is None
        assert len(view.errors) == 1
        assert "vacío" in view.errors[0].lower()

    def test_cash_payment_confirmed_returns_cash_method(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        view.change_dialog_return = True
        presenter.on_barcode_found(product)

        result = presenter.on_cash_payment_requested()

        assert result == PaymentMethod.CASH

    def test_cash_payment_cancelled_returns_none(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        view.change_dialog_return = False
        presenter.on_barcode_found(product)

        result = presenter.on_cash_payment_requested()

        assert result is None

    def test_cash_payment_passes_correct_total_to_dialog(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        p1 = _make_product(barcode="001", cost="100.00", margin="0.00", product_id=1)
        p2 = _make_product(barcode="002", cost="200.00", margin="0.00", product_id=2)
        presenter.on_barcode_found(p1)
        presenter.on_barcode_found(p2)

        presenter.on_cash_payment_requested()

        assert view.last_change_dialog_total == Price("300.00")


# ---------------------------------------------------------------------------
# Tests: eliminar ítem individual del carrito (Supr)
# ---------------------------------------------------------------------------


class TestRemoveCartItem:
    def test_remove_existing_item_clears_it_from_presenter_cart(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_remove_selected_item(product.id)

        assert product.id not in presenter.get_cart()

    def test_remove_existing_item_clears_it_from_view(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_remove_selected_item(product.id)

        assert product.id not in view.cart_items

    def test_remove_last_item_leaves_cart_empty(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_remove_selected_item(product.id)

        assert len(presenter.get_cart()) == 0
        assert len(view.cart_items) == 0

    def test_remove_item_updates_total_to_zero(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_remove_selected_item(product.id)

        assert view.last_total.amount == Decimal("0.00")

    def test_remove_one_of_two_items_leaves_other_intact(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        p1 = _make_product(barcode="001", name="Producto A", product_id=1)
        p2 = _make_product(barcode="002", name="Producto B", product_id=2)
        presenter.on_barcode_found(p1)
        presenter.on_barcode_found(p2)

        presenter.on_remove_selected_item(p1.id)

        assert p1.id not in presenter.get_cart()
        assert p2.id in presenter.get_cart()

    def test_remove_one_of_two_items_recalculates_total(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        p1 = _make_product(barcode="001", cost="100.00", margin="0.00", product_id=1)
        p2 = _make_product(barcode="002", cost="200.00", margin="0.00", product_id=2)
        presenter.on_barcode_found(p1)
        presenter.on_barcode_found(p2)

        presenter.on_remove_selected_item(p1.id)

        assert view.last_total == Price("200.00")

    def test_remove_nonexistent_product_id_is_noop(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_remove_selected_item(9999)

        assert len(presenter.get_cart()) == 1
        assert len(view.errors) == 0

    def test_remove_item_with_multiple_units_removes_entirely(
        self, presenter: SalePresenter, view: FakeView, product: Product
    ) -> None:
        presenter.on_barcode_found(product)
        presenter.on_barcode_found(product)
        presenter.on_barcode_found(product)
        assert presenter.get_cart()[product.id][1] == 3

        presenter.on_remove_selected_item(product.id)

        assert product.id not in presenter.get_cart()


# ---------------------------------------------------------------------------
# Tests: validación de stock al agregar al carrito
# ---------------------------------------------------------------------------


class TestStockValidation:
    def test_product_with_zero_stock_not_added_to_cart(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(stock=0)
        presenter.on_barcode_found(product)

        assert product.id not in presenter.get_cart()
        assert len(view.errors) == 1

    def test_product_with_zero_stock_shows_error_message(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(name="Galletitas", stock=0)
        presenter.on_barcode_found(product)

        assert "Galletitas" in view.errors[0]
        assert "stock" in view.errors[0].lower()

    def test_exceeding_stock_on_barcode_scan_shows_error(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(stock=2)
        presenter.on_barcode_found(product)
        presenter.on_barcode_found(product)
        # cantidad == stock, siguiente debe fallar
        presenter.on_barcode_found(product)

        assert presenter.get_cart()[product.id][1] == 2
        assert len(view.errors) == 1

    def test_exceeding_stock_on_barcode_scan_error_mentions_product(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(name="Agua 500ml", stock=1)
        presenter.on_barcode_found(product)
        presenter.on_barcode_found(product)

        assert "Agua 500ml" in view.errors[0]

    def test_quantity_change_above_stock_shows_error_and_does_not_update(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(stock=3)
        presenter.on_barcode_found(product)
        presenter.on_quantity_changed(product.id, 5)

        assert presenter.get_cart()[product.id][1] == 1
        assert len(view.errors) == 1

    def test_quantity_change_equal_to_stock_is_allowed(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(stock=3)
        presenter.on_barcode_found(product)
        presenter.on_quantity_changed(product.id, 3)

        assert presenter.get_cart()[product.id][1] == 3
        assert len(view.errors) == 0

    def test_product_selected_from_list_with_zero_stock_blocked(
        self, presenter: SalePresenter, view: FakeView
    ) -> None:
        product = _make_product(stock=0)
        presenter.on_product_selected_from_list(product)

        assert product.id not in presenter.get_cart()
        assert len(view.errors) == 1
