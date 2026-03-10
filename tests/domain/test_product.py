"""Tests unitarios para la entidad Product."""

import pytest
from decimal import Decimal

from src.domain.models.product import Product
from src.domain.models.price import Price


def make_product(**kwargs) -> Product:
    """Factory helper para crear productos de prueba con valores por defecto."""
    defaults = dict(
        barcode="7790895000115",
        name="Alfajor Jorgito",
        current_cost=Decimal("250.00"),
        margin_percent=Decimal("35.00"),
    )
    defaults.update(kwargs)
    return Product(**defaults)


class TestProductConstruction:

    def test_create_basic_product(self):
        p = make_product()
        assert p.barcode == "7790895000115"
        assert p.name == "Alfajor Jorgito"

    def test_default_stock_is_zero(self):
        p = make_product()
        assert p.stock == 0

    def test_default_id_is_none(self):
        p = make_product()
        assert p.id is None

    def test_empty_barcode_raises(self):
        with pytest.raises(ValueError, match="código de barras"):
            make_product(barcode="")

    def test_whitespace_barcode_raises(self):
        with pytest.raises(ValueError, match="código de barras"):
            make_product(barcode="   ")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="nombre"):
            make_product(name="")

    def test_negative_cost_raises(self):
        with pytest.raises(ValueError, match="costo"):
            make_product(current_cost=Decimal("-1.00"))

    def test_negative_margin_raises(self):
        with pytest.raises(ValueError, match="margen"):
            make_product(margin_percent=Decimal("-0.01"))

    def test_negative_stock_raises(self):
        with pytest.raises(ValueError, match="stock"):
            make_product(stock=-1)

    def test_negative_min_stock_raises(self):
        with pytest.raises(ValueError, match="mínimo"):
            make_product(min_stock=-1)


class TestProductCurrentPrice:

    def test_price_calculation(self):
        """Costo 250 + 35% margen = 337.50."""
        p = make_product(current_cost=Decimal("250.00"), margin_percent=Decimal("35.00"))
        assert p.current_price.amount == Decimal("337.50")

    def test_price_with_zero_margin(self):
        p = make_product(current_cost=Decimal("100.00"), margin_percent=Decimal("0"))
        assert p.current_price.amount == Decimal("100.00")

    def test_price_returns_price_instance(self):
        p = make_product()
        assert isinstance(p.current_price, Price)

    def test_price_recalculates_after_cost_update(self):
        p = make_product(current_cost=Decimal("100.00"), margin_percent=Decimal("50.00"))
        p.update_cost(Decimal("200.00"))
        assert p.current_price.amount == Decimal("300.00")


class TestProductStockAlerts:

    def test_is_low_stock_true(self):
        p = make_product(stock=2, min_stock=5)
        assert p.is_low_stock is True

    def test_is_low_stock_false(self):
        p = make_product(stock=10, min_stock=5)
        assert p.is_low_stock is False

    def test_is_low_stock_at_min(self):
        """Exactamente en el mínimo también es nivel crítico."""
        p = make_product(stock=5, min_stock=5)
        assert p.is_low_stock is True


class TestProductStockOperations:

    def test_decrement_stock(self):
        p = make_product(stock=10)
        p.decrement_stock(3)
        assert p.stock == 7

    def test_decrement_stock_to_zero(self):
        p = make_product(stock=5)
        p.decrement_stock(5)
        assert p.stock == 0

    def test_decrement_stock_insufficient_raises(self):
        p = make_product(stock=2)
        with pytest.raises(ValueError, match="insuficiente"):
            p.decrement_stock(3)

    def test_decrement_stock_zero_quantity_raises(self):
        p = make_product(stock=10)
        with pytest.raises(ValueError, match="positiva"):
            p.decrement_stock(0)

    def test_decrement_stock_negative_quantity_raises(self):
        p = make_product(stock=10)
        with pytest.raises(ValueError, match="positiva"):
            p.decrement_stock(-1)

    def test_increment_stock(self):
        p = make_product(stock=5)
        p.increment_stock(10)
        assert p.stock == 15

    def test_increment_stock_zero_raises(self):
        p = make_product(stock=5)
        with pytest.raises(ValueError, match="positiva"):
            p.increment_stock(0)

    def test_increment_stock_negative_raises(self):
        p = make_product(stock=5)
        with pytest.raises(ValueError, match="positiva"):
            p.increment_stock(-5)


class TestProductCostAndMarginUpdates:

    def test_update_cost(self):
        p = make_product(current_cost=Decimal("100.00"))
        p.update_cost(Decimal("150.00"))
        assert p.current_cost == Decimal("150.00")

    def test_update_cost_negative_raises(self):
        p = make_product()
        with pytest.raises(ValueError, match="negativo"):
            p.update_cost(Decimal("-10.00"))

    def test_update_cost_to_zero_allowed(self):
        p = make_product()
        p.update_cost(Decimal("0"))
        assert p.current_cost == Decimal("0")

    def test_update_margin(self):
        p = make_product(margin_percent=Decimal("35.00"))
        p.update_margin(Decimal("50.00"))
        assert p.margin_percent == Decimal("50.00")

    def test_update_margin_negative_raises(self):
        p = make_product()
        with pytest.raises(ValueError, match="negativo"):
            p.update_margin(Decimal("-5.00"))

    def test_update_margin_to_zero_allowed(self):
        p = make_product()
        p.update_margin(Decimal("0"))
        assert p.margin_percent == Decimal("0")
