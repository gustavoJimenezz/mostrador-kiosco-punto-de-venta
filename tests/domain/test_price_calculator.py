"""Tests unitarios para el Domain Service PriceCalculator.

Cubre todos los métodos estáticos con énfasis en casos límite
y corrección del redondeo ROUND_HALF_UP.
"""

import pytest
from decimal import Decimal

from src.domain.models.price import Price
from src.domain.services.price_calculator import PriceCalculator


class TestCalculateSalePrice:

    def test_35_percent_margin_on_250(self):
        """Caso referencia del documento: 250 + 35% = 337.50."""
        result = PriceCalculator.calculate_sale_price(Price("250.00"), Decimal("35.00"))
        assert result.amount == Decimal("337.50")

    def test_50_percent_margin_on_100(self):
        result = PriceCalculator.calculate_sale_price(Price("100.00"), Decimal("50.00"))
        assert result.amount == Decimal("150.00")

    def test_zero_margin(self):
        result = PriceCalculator.calculate_sale_price(Price("200.00"), Decimal("0"))
        assert result.amount == Decimal("200.00")

    def test_100_percent_margin_doubles_price(self):
        result = PriceCalculator.calculate_sale_price(Price("100.00"), Decimal("100"))
        assert result.amount == Decimal("200.00")

    def test_returns_price_instance(self):
        result = PriceCalculator.calculate_sale_price(Price("100.00"), Decimal("20"))
        assert isinstance(result, Price)

    def test_negative_margin_raises(self):
        with pytest.raises(ValueError, match="negativo"):
            PriceCalculator.calculate_sale_price(Price("100.00"), Decimal("-1"))

    def test_rounding_applied(self):
        """Costo 33.00 + 15% = 37.95 (exacto, sin redondeo extra)."""
        result = PriceCalculator.calculate_sale_price(Price("33.00"), Decimal("15"))
        assert result.amount == Decimal("37.95")

    def test_small_margin_rounding(self):
        """Verifica ROUND_HALF_UP: 99.995 → 100.00."""
        result = PriceCalculator.calculate_sale_price(Price("99.995"), Decimal("0"))
        assert result.amount == Decimal("100.00")


class TestCalculateMarginPercent:

    def test_35_percent_from_250_to_337_50(self):
        margin = PriceCalculator.calculate_margin_percent(
            Price("250.00"), Price("337.50")
        )
        assert margin == Decimal("35.00")

    def test_50_percent_margin(self):
        margin = PriceCalculator.calculate_margin_percent(
            Price("100.00"), Price("150.00")
        )
        assert margin == Decimal("50.00")

    def test_zero_margin(self):
        margin = PriceCalculator.calculate_margin_percent(
            Price("100.00"), Price("100.00")
        )
        assert margin == Decimal("0.00")

    def test_zero_cost_raises(self):
        with pytest.raises(ValueError, match="cero"):
            PriceCalculator.calculate_margin_percent(Price("0"), Price("100.00"))

    def test_sale_price_below_cost_raises(self):
        with pytest.raises(ValueError, match="menor al costo"):
            PriceCalculator.calculate_margin_percent(Price("100.00"), Price("90.00"))

    def test_result_is_decimal(self):
        result = PriceCalculator.calculate_margin_percent(
            Price("100.00"), Price("135.00")
        )
        assert isinstance(result, Decimal)

    def test_rounds_to_two_decimals(self):
        """200 → 300 = 50.00% exacto."""
        margin = PriceCalculator.calculate_margin_percent(
            Price("200.00"), Price("300.00")
        )
        assert margin == Decimal("50.00")

    def test_non_integer_margin(self):
        """100 → 133.33 ≈ 33.33%."""
        margin = PriceCalculator.calculate_margin_percent(
            Price("100.00"), Price("133.33")
        )
        assert margin == Decimal("33.33")


class TestApplyBulkIncrease:

    def test_15_percent_increase_on_200(self):
        """Caso referencia: 200 + 15% = 230."""
        result = PriceCalculator.apply_bulk_increase(Price("200.00"), Decimal("15"))
        assert result.amount == Decimal("230.00")

    def test_zero_increase(self):
        result = PriceCalculator.apply_bulk_increase(Price("200.00"), Decimal("0"))
        assert result.amount == Decimal("200.00")

    def test_100_percent_increase(self):
        result = PriceCalculator.apply_bulk_increase(Price("100.00"), Decimal("100"))
        assert result.amount == Decimal("200.00")

    def test_negative_increase_raises(self):
        with pytest.raises(ValueError, match="negativo"):
            PriceCalculator.apply_bulk_increase(Price("200.00"), Decimal("-1"))

    def test_returns_price_instance(self):
        result = PriceCalculator.apply_bulk_increase(Price("100.00"), Decimal("10"))
        assert isinstance(result, Price)

    def test_rounding_applied_correctly(self):
        """100 + 33% = 133.00."""
        result = PriceCalculator.apply_bulk_increase(Price("100.00"), Decimal("33"))
        assert result.amount == Decimal("133.00")


class TestCalculateCostToAchievePrice:

    def test_reverse_calculate_cost(self):
        """337.50 / 1.35 = 250.00."""
        result = PriceCalculator.calculate_cost_to_achieve_price(
            Price("337.50"), Decimal("35.00")
        )
        assert result.amount == Decimal("250.00")

    def test_150_at_50_percent_margin(self):
        """150 / 1.50 = 100.00."""
        result = PriceCalculator.calculate_cost_to_achieve_price(
            Price("150.00"), Decimal("50.00")
        )
        assert result.amount == Decimal("100.00")

    def test_zero_margin_returns_same_price(self):
        result = PriceCalculator.calculate_cost_to_achieve_price(
            Price("200.00"), Decimal("0")
        )
        assert result.amount == Decimal("200.00")

    def test_negative_margin_raises(self):
        with pytest.raises(ValueError, match="negativo"):
            PriceCalculator.calculate_cost_to_achieve_price(
                Price("100.00"), Decimal("-5")
            )

    def test_zero_target_price_raises(self):
        with pytest.raises(ValueError, match="cero"):
            PriceCalculator.calculate_cost_to_achieve_price(
                Price("0"), Decimal("35")
            )

    def test_returns_price_instance(self):
        result = PriceCalculator.calculate_cost_to_achieve_price(
            Price("100.00"), Decimal("25")
        )
        assert isinstance(result, Price)
