"""Tests unitarios del ProductPresenter (MVP).

No requieren PySide6 ni base de datos. El ProductPresenter es Python puro
y se testea con una FakeProductManagementView en memoria.

Cubre:
- Lógica recíproca Margen → Precio Final (Caso A)
- Lógica recíproca Precio Final → Margen (Caso B)
- Guards: costo cero, strings inválidos
- Validación de formulario y construcción de Product
- Flujo de callbacks de workers
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import pytest

from src.domain.models.category import Category
from src.domain.models.product import Product
from src.infrastructure.ui.presenters.product_presenter import ProductPresenter


# ---------------------------------------------------------------------------
# FakeProductManagementView
# ---------------------------------------------------------------------------


class FakeProductManagementView:
    """Vista falsa que registra todas las llamadas del presenter."""

    def __init__(self) -> None:
        self.product_list: list[Product] = []
        self.form_product: Optional[Product] = None
        self.form_categories: list[Category] = []
        self.form_cleared: bool = False
        self.final_price_display: Optional[Decimal] = None
        self.margin_display: Optional[Decimal] = None
        self.status_message: str = ""
        self.status_is_error: bool = False
        self.delete_confirmation_return: bool = True
        self.save_button_enabled: bool = True
        self.delete_button_enabled: bool = False
        self._form_data: dict = {
            "barcode": "",
            "name": "",
            "category_id": None,
            "stock": "0",
            "min_stock": "0",
            "cost": "0",
            "margin": 0.0,
            "final_price": "0",
        }

    def show_product_list(self, products: list[Product]) -> None:
        self.product_list = list(products)

    def show_product_in_form(self, product: Product, categories: list[Category]) -> None:
        self.form_product = product
        self.form_categories = list(categories)

    def clear_form(self) -> None:
        self.form_cleared = True
        self.form_product = None

    def set_final_price_display(self, price: Decimal) -> None:
        self.final_price_display = price

    def set_margin_display(self, margin: Decimal) -> None:
        self.margin_display = margin

    def show_status(self, message: str, is_error: bool = False) -> None:
        self.status_message = message
        self.status_is_error = is_error

    def show_delete_confirmation(self, product_name: str) -> bool:
        return self.delete_confirmation_return

    def set_save_button_enabled(self, enabled: bool) -> None:
        self.save_button_enabled = enabled

    def set_delete_button_enabled(self, enabled: bool) -> None:
        self.delete_button_enabled = enabled

    def get_form_data(self) -> dict:
        return dict(self._form_data)

    def set_form_data(self, **kwargs) -> None:
        """Helper de test para configurar datos del formulario."""
        self._form_data.update(kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def view() -> FakeProductManagementView:
    return FakeProductManagementView()


@pytest.fixture
def presenter(view: FakeProductManagementView) -> ProductPresenter:
    return ProductPresenter(view=view)


def _make_product(**kwargs) -> Product:
    defaults = {
        "barcode": "7790895000115",
        "name": "Alfajor Jorgito",
        "current_cost": Decimal("1000"),
        "margin_percent": Decimal("35"),
        "stock": 10,
        "min_stock": 2,
    }
    defaults.update(kwargs)
    return Product(**defaults)


# ---------------------------------------------------------------------------
# Lógica recíproca: Margen → Precio Final (Caso A)
# ---------------------------------------------------------------------------


def test_margin_changed_calculates_final_price(presenter, view):
    """cost=1000, margin=35 → price=1350.00."""
    presenter._current_cost = Decimal("1000")
    presenter.on_margin_changed("35")
    assert view.final_price_display == Decimal("1350.00")


def test_margin_zero_equals_cost(presenter, view):
    """margin=0 → price=cost."""
    presenter._current_cost = Decimal("500")
    presenter.on_margin_changed("0")
    assert view.final_price_display == Decimal("500.00")


def test_margin_changed_uses_round_half_up(presenter, view):
    """cost=100, margin=33.333 → price=133.33 (ROUND_HALF_UP)."""
    presenter._current_cost = Decimal("100")
    presenter.on_margin_changed("33.333")
    assert view.final_price_display == Decimal("133.33")


def test_cost_zero_does_not_crash(presenter, view):
    """Si cost=0, on_margin_changed no debe lanzar excepción ni actualizar precio."""
    presenter._current_cost = Decimal("0")
    presenter.on_margin_changed("35")
    assert view.final_price_display is None


def test_cost_changed_updates_internal_cost_and_recalculates(presenter, view):
    """on_cost_changed actualiza _current_cost y recalcula precio con margen del form."""
    view.set_form_data(margin=20.0)
    presenter.on_cost_changed("1000")
    assert presenter._current_cost == Decimal("1000")
    assert view.final_price_display == Decimal("1200.00")


# ---------------------------------------------------------------------------
# Lógica recíproca: Precio Final → Margen (Caso B)
# ---------------------------------------------------------------------------


def test_final_price_changed_calculates_margin(presenter, view):
    """cost=1000, price=1350 → margin=35.00."""
    presenter._current_cost = Decimal("1000")
    presenter.on_final_price_changed("1350")
    assert view.margin_display == Decimal("35.00")


def test_final_price_when_cost_zero_does_not_update_margin(presenter, view):
    """Si cost=0, on_final_price_changed no debe actualizar el margen."""
    presenter._current_cost = Decimal("0")
    presenter.on_final_price_changed("1350")
    assert view.margin_display is None


def test_final_price_with_invalid_string_does_not_crash(presenter, view):
    """Un string no numérico no debe lanzar excepción."""
    presenter._current_cost = Decimal("1000")
    presenter.on_final_price_changed("no_es_numero")
    assert view.margin_display is None


def test_final_price_negative_does_not_update_margin(presenter, view):
    """Un precio negativo no debe actualizar el margen."""
    presenter._current_cost = Decimal("1000")
    presenter.on_final_price_changed("-100")
    assert view.margin_display is None


# ---------------------------------------------------------------------------
# Validación de formulario y construcción de Product
# ---------------------------------------------------------------------------


def test_save_with_empty_barcode_shows_error(presenter, view):
    """Si el barcode está vacío, on_save_requested retorna None y muestra error."""
    view.set_form_data(barcode="", name="Alfajor", cost="100", margin=30.0)
    result = presenter.on_save_requested()
    assert result is None
    assert view.status_is_error is True
    assert "barras" in view.status_message.lower()


def test_save_with_empty_name_shows_error(presenter, view):
    """Si el nombre está vacío, retorna None y muestra error."""
    view.set_form_data(barcode="123456789", name="", cost="100", margin=30.0)
    result = presenter.on_save_requested()
    assert result is None
    assert view.status_is_error is True


def test_save_with_negative_cost_shows_error(presenter, view):
    """Si el costo es negativo, retorna None y muestra error."""
    view.set_form_data(barcode="123456789", name="Producto", cost="-10", margin=30.0)
    result = presenter.on_save_requested()
    assert result is None
    assert view.status_is_error is True


def test_save_with_valid_data_returns_product(presenter, view):
    """Datos válidos → retorna un Product correctamente construido."""
    view.set_form_data(
        barcode="7790895000115",
        name="Alfajor Jorgito",
        cost="250",
        margin=35.0,
        stock="10",
        min_stock="2",
        category_id=None,
    )
    result = presenter.on_save_requested()
    assert result is not None
    assert isinstance(result, Product)
    assert result.barcode == "7790895000115"
    assert result.current_cost == Decimal("250")
    assert result.margin_percent == Decimal("35.0")


def test_save_valid_preserves_selected_product_id(presenter, view):
    """Si hay un producto seleccionado, el Product retornado conserva su ID."""
    presenter._selected_product = _make_product(id=42)
    view.set_form_data(
        barcode="7790895000115",
        name="Alfajor",
        cost="200",
        margin=30.0,
        stock="5",
        min_stock="1",
    )
    result = presenter.on_save_requested()
    assert result is not None
    assert result.id == 42


# ---------------------------------------------------------------------------
# Flujo de nuevos productos y selección
# ---------------------------------------------------------------------------


def test_new_product_clears_selection(presenter, view):
    """on_new_product_requested limpia _selected_product y llama clear_form."""
    presenter._selected_product = _make_product(id=1)
    presenter.on_new_product_requested()
    assert presenter._selected_product is None
    assert view.form_cleared is True


def test_new_product_disables_delete_button(presenter, view):
    presenter.on_new_product_requested()
    assert view.delete_button_enabled is False


# ---------------------------------------------------------------------------
# Callbacks de workers
# ---------------------------------------------------------------------------


def test_on_products_loaded_delegates_to_view(presenter, view):
    """on_products_loaded llama view.show_product_list con la lista."""
    products = [_make_product(barcode="111"), _make_product(barcode="222")]
    presenter.on_products_loaded(products)
    assert view.product_list == products


def test_on_products_loaded_shows_count_in_status(presenter, view):
    products = [_make_product(barcode="111")]
    presenter.on_products_loaded(products)
    assert "1" in view.status_message


def test_on_product_fetched_updates_selected(presenter, view):
    """on_product_fetched actualiza _selected_product y llama show_product_in_form."""
    product = _make_product(id=7)
    categories = [Category(name="Golosinas", id=1)]
    presenter.on_product_fetched({"product": product, "categories": categories})
    assert presenter._selected_product is product
    assert view.form_product is product
    assert view.form_categories == categories


def test_on_product_fetched_enables_delete_button(presenter, view):
    product = _make_product(id=7)
    presenter.on_product_fetched({"product": product, "categories": []})
    assert view.delete_button_enabled is True


def test_on_product_fetched_none_shows_error(presenter, view):
    """Si product es None, muestra error."""
    presenter.on_product_fetched({"product": None, "categories": []})
    assert view.status_is_error is True


def test_on_save_completed_updates_selected_product(presenter, view):
    """on_save_completed actualiza _selected_product y muestra mensaje de éxito."""
    product = _make_product(id=5)
    presenter.on_save_completed(product)
    assert presenter._selected_product is product
    assert view.status_is_error is False
    assert "guardado" in view.status_message.lower()


def test_on_delete_completed_clears_form(presenter, view):
    """on_delete_completed limpia la selección y el formulario."""
    presenter._selected_product = _make_product(id=3)
    presenter.on_delete_completed()
    assert presenter._selected_product is None
    assert view.form_cleared is True
    assert view.delete_button_enabled is False


def test_on_worker_error_shows_error_status(presenter, view):
    presenter.on_worker_error("Conexión perdida")
    assert view.status_is_error is True
    assert "Conexión perdida" in view.status_message


# ---------------------------------------------------------------------------
# Flujo de eliminación
# ---------------------------------------------------------------------------


def test_delete_when_confirmation_false_returns_false(presenter, view):
    """Si el usuario no confirma, on_delete_requested retorna False."""
    presenter._selected_product = _make_product(id=1)
    view.delete_confirmation_return = False
    result = presenter.on_delete_requested()
    assert result is False


def test_delete_when_no_product_selected_shows_error(presenter, view):
    """Si no hay producto seleccionado, muestra error y retorna False."""
    presenter._selected_product = None
    result = presenter.on_delete_requested()
    assert result is False
    assert view.status_is_error is True
