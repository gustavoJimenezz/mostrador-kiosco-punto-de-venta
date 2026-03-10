"""Tests unitarios para la entidad CashClose (Arqueo de Caja)."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.domain.models.cash_close import CashClose
from src.domain.models.price import Price


def make_cash_close(**kwargs) -> CashClose:
    defaults = dict(
        opened_at=datetime(2026, 3, 10, 8, 0, 0),
        opening_amount=Decimal("5000.00"),
    )
    defaults.update(kwargs)
    return CashClose(**defaults)


class TestCashCloseConstruction:

    def test_create_open_cash_close(self):
        cc = make_cash_close()
        assert cc.is_open is True
        assert cc.closed_at is None
        assert cc.closing_amount is None

    def test_default_sales_totals_are_zero(self):
        cc = make_cash_close()
        assert cc.total_sales_cash == Decimal("0.00")
        assert cc.total_sales_debit == Decimal("0.00")
        assert cc.total_sales_transfer == Decimal("0.00")

    def test_negative_opening_amount_raises(self):
        with pytest.raises(ValueError, match="apertura"):
            make_cash_close(opening_amount=Decimal("-1.00"))

    def test_negative_closing_amount_raises(self):
        with pytest.raises(ValueError, match="cierre"):
            make_cash_close(
                closed_at=datetime(2026, 3, 10, 20, 0),
                closing_amount=Decimal("-1.00"),
            )

    def test_closed_at_without_closing_amount_raises(self):
        with pytest.raises(ValueError, match="monto de cierre"):
            make_cash_close(
                closed_at=datetime(2026, 3, 10, 20, 0),
                closing_amount=None,
            )

    def test_close_before_open_raises(self):
        opened = datetime(2026, 3, 10, 8, 0)
        with pytest.raises(ValueError, match="anterior"):
            make_cash_close(
                opened_at=opened,
                closed_at=opened - timedelta(hours=1),
                closing_amount=Decimal("5000.00"),
            )


class TestCashCloseTotals:

    def test_total_sales_sums_all_methods(self):
        cc = make_cash_close(
            total_sales_cash=Decimal("10000.00"),
            total_sales_debit=Decimal("5000.00"),
            total_sales_transfer=Decimal("2500.00"),
        )
        assert cc.total_sales.amount == Decimal("17500.00")

    def test_total_sales_returns_price(self):
        cc = make_cash_close()
        assert isinstance(cc.total_sales, Price)

    def test_expected_cash(self):
        cc = make_cash_close(
            opening_amount=Decimal("5000.00"),
            total_sales_cash=Decimal("10000.00"),
        )
        assert cc.expected_cash.amount == Decimal("15000.00")

    def test_expected_cash_returns_price(self):
        cc = make_cash_close()
        assert isinstance(cc.expected_cash, Price)

    def test_cash_difference_none_when_open(self):
        cc = make_cash_close()
        assert cc.cash_difference is None

    def test_cash_difference_zero_when_exact(self):
        cc = CashClose(
            opened_at=datetime(2026, 3, 10, 8, 0),
            opening_amount=Decimal("5000.00"),
            total_sales_cash=Decimal("10000.00"),
            closed_at=datetime(2026, 3, 10, 20, 0),
            closing_amount=Decimal("15000.00"),
        )
        assert cc.cash_difference == Decimal("0.00")

    def test_cash_difference_positive_surplus(self):
        cc = CashClose(
            opened_at=datetime(2026, 3, 10, 8, 0),
            opening_amount=Decimal("5000.00"),
            total_sales_cash=Decimal("10000.00"),
            closed_at=datetime(2026, 3, 10, 20, 0),
            closing_amount=Decimal("15200.00"),
        )
        assert cc.cash_difference == Decimal("200.00")

    def test_cash_difference_negative_shortage(self):
        cc = CashClose(
            opened_at=datetime(2026, 3, 10, 8, 0),
            opening_amount=Decimal("5000.00"),
            total_sales_cash=Decimal("10000.00"),
            closed_at=datetime(2026, 3, 10, 20, 0),
            closing_amount=Decimal("14800.00"),
        )
        assert cc.cash_difference == Decimal("-200.00")


class TestCashCloseOperations:

    def test_close_cash_close(self):
        cc = make_cash_close()
        close_time = datetime(2026, 3, 10, 20, 0)
        cc.close(close_time, Decimal("15000.00"))
        assert cc.is_open is False
        assert cc.closed_at == close_time
        assert cc.closing_amount == Decimal("15000.00")

    def test_close_already_closed_raises(self):
        cc = make_cash_close()
        cc.close(datetime(2026, 3, 10, 20, 0), Decimal("5000.00"))
        with pytest.raises(ValueError, match="ya fue cerrado"):
            cc.close(datetime(2026, 3, 10, 21, 0), Decimal("5000.00"))

    def test_close_with_negative_amount_raises(self):
        cc = make_cash_close()
        with pytest.raises(ValueError, match="negativo"):
            cc.close(datetime(2026, 3, 10, 20, 0), Decimal("-100.00"))

    def test_close_before_open_raises(self):
        opened = datetime(2026, 3, 10, 8, 0)
        cc = make_cash_close(opened_at=opened)
        with pytest.raises(ValueError, match="anterior"):
            cc.close(opened - timedelta(hours=1), Decimal("5000.00"))

    def test_register_sale_cash(self):
        cc = make_cash_close()
        cc.register_sale(cash_amount=Decimal("1000.00"))
        assert cc.total_sales_cash == Decimal("1000.00")

    def test_register_sale_debit(self):
        cc = make_cash_close()
        cc.register_sale(debit_amount=Decimal("500.00"))
        assert cc.total_sales_debit == Decimal("500.00")

    def test_register_sale_transfer(self):
        cc = make_cash_close()
        cc.register_sale(transfer_amount=Decimal("750.00"))
        assert cc.total_sales_transfer == Decimal("750.00")

    def test_register_multiple_sales_accumulates(self):
        cc = make_cash_close()
        cc.register_sale(cash_amount=Decimal("1000.00"))
        cc.register_sale(cash_amount=Decimal("500.00"))
        assert cc.total_sales_cash == Decimal("1500.00")

    def test_register_sale_on_closed_raises(self):
        cc = make_cash_close()
        cc.close(datetime(2026, 3, 10, 20, 0), Decimal("5000.00"))
        with pytest.raises(ValueError, match="cerrada"):
            cc.register_sale(cash_amount=Decimal("100.00"))

    def test_register_sale_negative_cash_raises(self):
        cc = make_cash_close()
        with pytest.raises(ValueError, match="negativos"):
            cc.register_sale(cash_amount=Decimal("-100.00"))

    def test_register_sale_negative_debit_raises(self):
        cc = make_cash_close()
        with pytest.raises(ValueError, match="negativos"):
            cc.register_sale(debit_amount=Decimal("-50.00"))

    def test_register_sale_negative_transfer_raises(self):
        cc = make_cash_close()
        with pytest.raises(ValueError, match="negativos"):
            cc.register_sale(transfer_amount=Decimal("-25.00"))
