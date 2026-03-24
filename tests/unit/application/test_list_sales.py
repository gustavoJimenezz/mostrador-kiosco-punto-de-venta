"""Tests unitarios del caso de uso ListSales.

No requiere base de datos — usa un repositorio en memoria.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.use_cases.list_sales import ListSales
from src.domain.models.sale import PaymentMethod, Sale, SaleItem


class InMemorySaleQueryRepository:
    """Repositorio de consulta en memoria para tests de ListSales."""

    def __init__(self, sales: list[Sale] | None = None) -> None:
        self._sales = sales or []

    def list_by_date_range(self, start: datetime, end: datetime) -> list[Sale]:
        return [
            s for s in self._sales if start <= s.timestamp < end
        ]

    def get_daily_totals(self, day) -> dict:
        return {}


def _make_sale(
    timestamp: datetime,
    amount: Decimal = Decimal("1000.00"),
) -> Sale:
    item = SaleItem(product_id=1, quantity=1, price_at_sale=amount)
    return Sale(
        payment_method=PaymentMethod.CASH,
        items=[item],
        timestamp=timestamp,
    )


class TestListSales:
    def test_returns_sales_in_range(self):
        sales = [
            _make_sale(datetime(2026, 3, 23, 9, 0)),
            _make_sale(datetime(2026, 3, 23, 14, 0)),
            _make_sale(datetime(2026, 3, 24, 9, 0)),  # fuera del rango
        ]
        repo = InMemorySaleQueryRepository(sales)
        uc = ListSales(repo)

        start = datetime(2026, 3, 23, 0, 0)
        end = datetime(2026, 3, 24, 0, 0)
        result = uc.execute(start, end)

        assert len(result) == 2

    def test_returns_empty_when_no_sales(self):
        repo = InMemorySaleQueryRepository([])
        uc = ListSales(repo)

        result = uc.execute(
            start=datetime(2026, 3, 23, 0, 0),
            end=datetime(2026, 3, 24, 0, 0),
        )

        assert result == []

    def test_raises_when_start_after_end(self):
        repo = InMemorySaleQueryRepository([])
        uc = ListSales(repo)

        with pytest.raises(ValueError, match="anterior al fin"):
            uc.execute(
                start=datetime(2026, 3, 24, 0, 0),
                end=datetime(2026, 3, 23, 0, 0),
            )

    def test_raises_when_start_equals_end(self):
        repo = InMemorySaleQueryRepository([])
        uc = ListSales(repo)

        with pytest.raises(ValueError):
            ts = datetime(2026, 3, 23, 12, 0)
            uc.execute(start=ts, end=ts)
