"""Tests unitarios para la entidad PriceHistory."""

import pytest
from datetime import datetime
from decimal import Decimal

from src.domain.models.price_history import PriceHistory
from src.domain.models.price import Price


def make_history(**kwargs) -> PriceHistory:
    defaults = dict(
        product_id=1,
        old_cost=Decimal("200.00"),
        new_cost=Decimal("250.00"),
        updated_at=datetime(2026, 3, 10, 10, 0),
    )
    defaults.update(kwargs)
    return PriceHistory(**defaults)


class TestPriceHistoryConstruction:

    def test_create_valid_record(self):
        ph = make_history()
        assert ph.product_id == 1
        assert ph.old_cost == Decimal("200.00")
        assert ph.new_cost == Decimal("250.00")

    def test_default_id_is_none(self):
        ph = make_history()
        assert ph.id is None

    def test_negative_old_cost_raises(self):
        with pytest.raises(ValueError, match="anterior"):
            make_history(old_cost=Decimal("-1.00"))

    def test_negative_new_cost_raises(self):
        with pytest.raises(ValueError, match="nuevo costo"):
            make_history(new_cost=Decimal("-1.00"))

    def test_old_cost_zero_allowed(self):
        """Primer registro de precio: costo anterior era 0."""
        ph = make_history(old_cost=Decimal("0"), new_cost=Decimal("100.00"))
        assert ph.old_cost == Decimal("0")

    def test_is_immutable(self):
        ph = make_history()
        with pytest.raises(Exception):
            ph.new_cost = Decimal("300.00")


class TestPriceHistoryCalculations:

    def test_increase_percent_25(self):
        """De 200 a 250 = 25% de aumento."""
        ph = make_history(old_cost=Decimal("200.00"), new_cost=Decimal("250.00"))
        assert ph.increase_percent == Decimal("25.00")

    def test_increase_percent_negative_reduction(self):
        """De 200 a 150 = -25% (reducción de precio)."""
        ph = make_history(old_cost=Decimal("200.00"), new_cost=Decimal("150.00"))
        assert ph.increase_percent == Decimal("-25.00")

    def test_increase_percent_zero_old_cost_returns_none(self):
        ph = make_history(old_cost=Decimal("0"), new_cost=Decimal("100.00"))
        assert ph.increase_percent is None

    def test_increase_percent_rounds_correctly(self):
        """De 300 a 400 = 33.33%."""
        ph = make_history(old_cost=Decimal("300.00"), new_cost=Decimal("400.00"))
        assert ph.increase_percent == Decimal("33.33")

    def test_old_sale_price_returns_price(self):
        ph = make_history()
        assert isinstance(ph.old_sale_price, Price)
        assert ph.old_sale_price.amount == Decimal("200.00")

    def test_new_sale_price_returns_price(self):
        ph = make_history()
        assert isinstance(ph.new_sale_price, Price)
        assert ph.new_sale_price.amount == Decimal("250.00")
