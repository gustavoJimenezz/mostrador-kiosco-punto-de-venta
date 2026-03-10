"""Tests unitarios para el Value Object Price.

Cubre: construcción, redondeo ROUND_HALF_UP, aritmética,
comparación, helpers de negocio y casos de borde/error.
"""

import pytest
from decimal import Decimal

from src.domain.models.price import Price


class TestPriceConstruction:
    """Tests de construcción e inicialización."""

    def test_create_from_decimal(self):
        p = Price(Decimal("100.00"))
        assert p.amount == Decimal("100.00")

    def test_create_from_string(self):
        p = Price("250.50")
        assert p.amount == Decimal("250.50")

    def test_create_from_int(self):
        p = Price(500)
        assert p.amount == Decimal("500.00")

    def test_create_zero(self):
        p = Price("0")
        assert p.amount == Decimal("0.00")

    def test_rounds_half_up(self):
        """0.005 debe redondearse a 0.01 con ROUND_HALF_UP."""
        p = Price("0.005")
        assert p.amount == Decimal("0.01")

    def test_rounds_half_up_large(self):
        """100.005 → 100.01."""
        p = Price("100.005")
        assert p.amount == Decimal("100.01")

    def test_rounds_down_when_below_half(self):
        """100.004 → 100.00."""
        p = Price("100.004")
        assert p.amount == Decimal("100.00")

    def test_negative_raises_value_error(self):
        with pytest.raises(ValueError, match="negativo"):
            Price("-0.01")

    def test_unsupported_type_raises_type_error(self):
        with pytest.raises(TypeError):
            Price(3.14)  # float no soportado

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(Exception):
            Price("no_es_un_numero")

    def test_is_immutable(self):
        p = Price("100.00")
        with pytest.raises(Exception):
            p.amount = Decimal("200.00")


class TestPriceArithmetic:
    """Tests de operaciones aritméticas."""

    def test_add_two_prices(self):
        result = Price("100.00") + Price("50.00")
        assert result.amount == Decimal("150.00")

    def test_add_preserves_rounding(self):
        result = Price("33.33") + Price("33.34")
        assert result.amount == Decimal("66.67")

    def test_subtract_prices(self):
        result = Price("100.00") - Price("30.00")
        assert result.amount == Decimal("70.00")

    def test_subtract_to_zero(self):
        result = Price("100.00") - Price("100.00")
        assert result.amount == Decimal("0.00")

    def test_subtract_resulting_negative_raises(self):
        with pytest.raises(ValueError, match="negativo"):
            Price("50.00") - Price("100.00")

    def test_multiply_by_int(self):
        result = Price("100.00") * 3
        assert result.amount == Decimal("300.00")

    def test_multiply_by_decimal(self):
        result = Price("100.00") * Decimal("1.5")
        assert result.amount == Decimal("150.00")

    def test_rmul_by_int(self):
        result = 3 * Price("100.00")
        assert result.amount == Decimal("300.00")

    def test_multiply_with_rounding(self):
        """337.50 * 3 = 1012.50."""
        result = Price("337.50") * 3
        assert result.amount == Decimal("1012.50")

    def test_divide_by_int(self):
        result = Price("300.00") / 3
        assert result.amount == Decimal("100.00")

    def test_divide_by_decimal(self):
        result = Price("150.00") / Decimal("2")
        assert result.amount == Decimal("75.00")

    def test_divide_by_zero_raises(self):
        with pytest.raises(Exception):
            Price("100.00") / 0

    def test_add_non_price_returns_not_implemented(self):
        result = Price("100.00").__add__(42)
        assert result is NotImplemented

    def test_sub_non_price_returns_not_implemented(self):
        result = Price("100.00").__sub__(42)
        assert result is NotImplemented

    def test_mul_float_returns_not_implemented(self):
        result = Price("100.00").__mul__(1.5)
        assert result is NotImplemented

    def test_div_float_returns_not_implemented(self):
        result = Price("100.00").__truediv__(1.5)
        assert result is NotImplemented


class TestPriceComparison:
    """Tests de operaciones de comparación."""

    def test_equal_prices(self):
        assert Price("100.00") == Price("100.00")

    def test_not_equal_prices(self):
        assert Price("100.00") != Price("200.00")

    def test_less_than(self):
        assert Price("50.00") < Price("100.00")

    def test_less_than_or_equal(self):
        assert Price("100.00") <= Price("100.00")
        assert Price("50.00") <= Price("100.00")

    def test_greater_than(self):
        assert Price("100.00") > Price("50.00")

    def test_greater_than_or_equal(self):
        assert Price("100.00") >= Price("100.00")
        assert Price("200.00") >= Price("100.00")

    def test_lt_non_price_returns_not_implemented(self):
        result = Price("100.00").__lt__(42)
        assert result is NotImplemented

    def test_le_non_price_returns_not_implemented(self):
        result = Price("100.00").__le__(42)
        assert result is NotImplemented

    def test_gt_non_price_returns_not_implemented(self):
        result = Price("100.00").__gt__(42)
        assert result is NotImplemented

    def test_ge_non_price_returns_not_implemented(self):
        result = Price("100.00").__ge__(42)
        assert result is NotImplemented


class TestPriceRepresentation:
    """Tests de representación string."""

    def test_repr(self):
        assert repr(Price("100.00")) == "Price('100.00')"

    def test_str(self):
        p = Price("1234.56")
        assert str(p) == "ARS 1,234.56"

    def test_str_zero(self):
        assert str(Price("0")) == "ARS 0.00"


class TestPriceBusinessHelpers:
    """Tests de métodos de negocio."""

    def test_apply_margin_35_percent(self):
        """Costo 250.00 + 35% = 337.50."""
        price = Price("250.00").apply_margin(Decimal("35.00"))
        assert price.amount == Decimal("337.50")

    def test_apply_margin_zero(self):
        """0% de margen no cambia el precio."""
        price = Price("100.00").apply_margin(Decimal("0"))
        assert price.amount == Decimal("100.00")

    def test_apply_margin_100_percent(self):
        """100% de margen duplica el precio."""
        price = Price("100.00").apply_margin(Decimal("100"))
        assert price.amount == Decimal("200.00")

    def test_apply_margin_negative_raises(self):
        with pytest.raises(ValueError, match="negativo"):
            Price("100.00").apply_margin(Decimal("-1"))

    def test_apply_margin_rounds_correctly(self):
        """Costo 33.00 + 15% = 37.95."""
        price = Price("33.00").apply_margin(Decimal("15"))
        assert price.amount == Decimal("37.95")

    def test_percentage_increase(self):
        """Precio 200.00 + 15% = 230.00."""
        price = Price("200.00").percentage_increase(Decimal("15"))
        assert price.amount == Decimal("230.00")

    def test_percentage_increase_rounds(self):
        """Precio 100.00 + 33% = 133.00."""
        price = Price("100.00").percentage_increase(Decimal("33"))
        assert price.amount == Decimal("133.00")

    def test_is_zero_true(self):
        assert Price("0").is_zero() is True

    def test_is_zero_false(self):
        assert Price("0.01").is_zero() is False
