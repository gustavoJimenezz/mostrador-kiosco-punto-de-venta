"""Tests unitarios del CashPresenter.

Verifica la lógica de presentación sin Qt — usa una vista fake.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import pytest

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement, MovementType
from src.infrastructure.ui.presenters.cash_presenter import CashPresenter


class FakeCashView:
    """Vista fake que implementa ICashView para tests."""

    def __init__(self) -> None:
        self.session_open: Optional[CashClose] = None
        self.session_closed_called: bool = False
        self.sales_summary: tuple = (Decimal("0"), Decimal("0"), Decimal("0"))
        self.movements: list[CashMovement] = []
        self.close_result: Optional[Decimal] = None
        self.last_error: Optional[str] = None
        self.last_success: Optional[str] = None

    def show_session_open(self, cash_close: CashClose) -> None:
        self.session_open = cash_close
        self.session_closed_called = False

    def show_session_closed(self) -> None:
        self.session_open = None
        self.session_closed_called = True

    def show_sales_summary(self, cash, debit, transfer) -> None:
        self.sales_summary = (cash, debit, transfer)

    def show_movements(self, movements: list[CashMovement]) -> None:
        self.movements = movements

    def show_close_result(self, difference: Optional[Decimal]) -> None:
        self.close_result = difference

    def show_error(self, message: str) -> None:
        self.last_error = message

    def show_success(self, message: str) -> None:
        self.last_success = message


def _make_cash_close(id: int = 1) -> CashClose:
    cc = CashClose(
        opened_at=datetime(2026, 3, 23, 8, 0),
        opening_amount=Decimal("5000.00"),
    )
    cc.id = id
    return cc


class TestCashPresenterOnStateLoaded:
    def test_shows_session_open_when_cash_close_exists(self):
        view = FakeCashView()
        presenter = CashPresenter(view)
        cc = _make_cash_close()

        presenter.on_state_loaded({
            "cash_close": cc,
            "movements": [],
            "sales_totals": {},
        })

        assert view.session_open is cc
        assert not view.session_closed_called

    def test_shows_session_closed_when_no_cash_close(self):
        view = FakeCashView()
        presenter = CashPresenter(view)

        presenter.on_state_loaded({
            "cash_close": None,
            "movements": [],
            "sales_totals": {},
        })

        assert view.session_closed_called

    def test_populates_sales_summary(self):
        view = FakeCashView()
        presenter = CashPresenter(view)

        presenter.on_state_loaded({
            "cash_close": None,
            "movements": [],
            "sales_totals": {
                "EFECTIVO": Decimal("10000.00"),
                "DEBITO": Decimal("3500.00"),
            },
        })

        cash, debit, transfer = view.sales_summary
        assert cash == Decimal("10000.00")
        assert debit == Decimal("3500.00")
        assert transfer == Decimal("0")


class TestCashPresenterValidations:
    def test_open_session_negative_amount_shows_error(self):
        view = FakeCashView()
        presenter = CashPresenter(view)

        result = presenter.on_open_session_requested(Decimal("-1"))

        assert result is False
        assert view.last_error is not None

    def test_close_session_no_active_close_shows_error(self):
        view = FakeCashView()
        presenter = CashPresenter(view)

        result = presenter.on_close_session_requested(Decimal("1000"))

        assert result is False
        assert view.last_error is not None

    def test_add_movement_empty_description_shows_error(self):
        view = FakeCashView()
        presenter = CashPresenter(view)
        cc = _make_cash_close()
        presenter.on_state_loaded({"cash_close": cc, "movements": [], "sales_totals": {}})

        result = presenter.on_add_movement_requested(Decimal("100"), "")

        assert result is False
        assert view.last_error is not None

    def test_add_movement_zero_amount_shows_error(self):
        view = FakeCashView()
        presenter = CashPresenter(view)
        cc = _make_cash_close()
        presenter.on_state_loaded({"cash_close": cc, "movements": [], "sales_totals": {}})

        result = presenter.on_add_movement_requested(Decimal("0"), "Pago")

        assert result is False


class TestCashPresenterCallbacks:
    def test_on_session_opened_updates_view(self):
        view = FakeCashView()
        presenter = CashPresenter(view)
        cc = _make_cash_close()

        presenter.on_session_opened(cc)

        assert view.session_open is cc
        assert view.last_success is not None

    def test_on_session_closed_with_surplus_shows_surplus(self):
        view = FakeCashView()
        presenter = CashPresenter(view)
        cc = CashClose(
            opened_at=datetime(2026, 3, 23, 8, 0),
            opening_amount=Decimal("5000.00"),
            closed_at=datetime(2026, 3, 23, 20, 0),
            closing_amount=Decimal("5100.00"),
        )

        presenter.on_session_closed(cc)

        assert view.session_closed_called
        assert "Sobrante" in (view.last_success or "")

    def test_on_movement_added_appends_to_list(self):
        view = FakeCashView()
        presenter = CashPresenter(view)
        cc = _make_cash_close()
        presenter.on_state_loaded({"cash_close": cc, "movements": [], "sales_totals": {}})

        mov = CashMovement(
            cash_close_id=1,
            amount=Decimal("200.00"),
            movement_type=MovementType.INCOME,
            description="Test",
            created_at=datetime.now(),
            id=1,
        )
        presenter.on_movement_added(mov)

        assert len(view.movements) == 1
        assert view.movements[0] is mov
