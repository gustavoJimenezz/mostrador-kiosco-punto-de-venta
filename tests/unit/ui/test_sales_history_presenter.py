"""Tests unitarios del SalesHistoryPresenter.

Verifica la lógica de presentación sin Qt — usa una vista fake.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import pytest

from src.domain.models.sale import PaymentMethod, Sale, SaleItem
from src.infrastructure.ui.presenters.sales_history_presenter import (
    SalesHistoryPresenter,
)


class FakeSalesHistoryView:
    """Vista fake que implementa ISalesHistoryView para tests."""

    def __init__(self) -> None:
        self.sales: list[Sale] = []
        self.detail: list[dict] = []
        self.daily_total: Decimal = Decimal("0")
        self.last_error: Optional[str] = None
        self.loading: bool = False

    def show_sales(self, sales: list[Sale]) -> None:
        self.sales = sales

    def show_sale_detail(self, items: list[dict]) -> None:
        self.detail = items

    def show_daily_total(self, total: Decimal) -> None:
        self.daily_total = total

    def show_error(self, message: str) -> None:
        self.last_error = message

    def show_loading(self, loading: bool) -> None:
        self.loading = loading


def _make_sale(total: Decimal = Decimal("1500.00")) -> Sale:
    item = SaleItem(product_id=1, quantity=1, price_at_sale=total)
    return Sale(
        payment_method=PaymentMethod.CASH,
        items=[item],
        timestamp=datetime(2026, 3, 23, 10, 0),
    )


class TestSalesHistoryPresenterOnSalesLoaded:
    def test_passes_sales_to_view(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)
        sales = [_make_sale(Decimal("1000.00")), _make_sale(Decimal("2000.00"))]

        presenter.on_sales_loaded(sales)

        assert view.sales == sales

    def test_computes_daily_total(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)
        sales = [_make_sale(Decimal("1000.00")), _make_sale(Decimal("2000.00"))]

        presenter.on_sales_loaded(sales)

        assert view.daily_total == Decimal("3000.00")

    def test_hides_loading_after_receiving_sales(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)

        presenter.on_sales_loaded([])

        assert view.loading is False

    def test_empty_sales_shows_zero_total(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)

        presenter.on_sales_loaded([])

        assert view.daily_total == Decimal("0")


class TestSalesHistoryPresenterGetSaleByRow:
    def test_returns_correct_sale(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)
        sales = [_make_sale(Decimal("100")), _make_sale(Decimal("200"))]
        presenter.on_sales_loaded(sales)

        assert presenter.get_sale_by_row(0) is sales[0]
        assert presenter.get_sale_by_row(1) is sales[1]

    def test_returns_none_for_invalid_row(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)
        presenter.on_sales_loaded([_make_sale()])

        assert presenter.get_sale_by_row(5) is None
        assert presenter.get_sale_by_row(-1) is None


class TestSalesHistoryPresenterDetailLoaded:
    def test_passes_items_to_view(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)
        items = [
            {"product_name": "Coca-Cola", "quantity": 2, "price_at_sale": Decimal("750"), "subtotal": Decimal("1500")}
        ]

        presenter.on_detail_loaded(items)

        assert view.detail == items


class TestSalesHistoryPresenterError:
    def test_error_hides_loading_and_shows_message(self):
        view = FakeSalesHistoryView()
        presenter = SalesHistoryPresenter(view)

        presenter.on_worker_error("Conexión fallida")

        assert view.loading is False
        assert view.last_error == "Conexión fallida"
