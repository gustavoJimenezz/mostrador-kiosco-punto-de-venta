"""Tests unitarios del CashPresenter.

Verifica la lógica de presentación sin Qt — usa una vista fake.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import pytest

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement
from src.infrastructure.ui.presenters.cash_presenter import CashPresenter


class FakeCashView:
    """Vista fake que implementa ICashView para tests."""

    def __init__(self) -> None:
        self.session_open: Optional[CashClose] = None
        self.session_closed_called: bool = False
        self.sales_summary: tuple = (Decimal("0"), Decimal("0"), Decimal("0"))
        self.movements_total: Decimal = Decimal("0")
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

    def show_movements_total(self, total: Decimal) -> None:
        self.movements_total = total

    def show_close_result(self, difference: Optional[Decimal]) -> None:
        self.close_result = difference

    def show_error(self, message: str) -> None:
        self.last_error = message

    def show_success(self, message: str) -> None:
        self.last_success = message


class FakeCashMovementsView:
    """Vista fake que implementa ICashMovementsView para tests."""

    def __init__(self) -> None:
        self.session_open: Optional[CashClose] = None
        self.session_closed_called: bool = False
        self.movements: list[CashMovement] = []
        self.last_error: Optional[str] = None
        self.last_success: Optional[str] = None

    def show_session_open(self, cash_close: CashClose) -> None:
        self.session_open = cash_close
        self.session_closed_called = False

    def show_session_closed(self) -> None:
        self.session_open = None
        self.session_closed_called = True

    def show_movements(self, movements: list[CashMovement]) -> None:
        self.movements = list(movements)

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

    def test_on_movement_added_updates_movements_view(self):
        view = FakeCashView()
        mov_view = FakeCashMovementsView()
        presenter = CashPresenter(view)
        presenter.set_movements_view(mov_view)
        cc = _make_cash_close()
        presenter.on_state_loaded({"cash_close": cc, "movements": [], "sales_totals": {}})

        mov = CashMovement(
            cash_close_id=1,
            amount=Decimal("200.00"),
            description="Test",
            created_at=datetime.now(),
            id=1,
        )
        presenter.on_movement_added(mov)

        assert len(mov_view.movements) == 1
        assert mov_view.movements[0] is mov

    def test_on_movement_added_updates_total_in_close_view(self):
        view = FakeCashView()
        presenter = CashPresenter(view)
        cc = _make_cash_close()
        presenter.on_state_loaded({"cash_close": cc, "movements": [], "sales_totals": {}})

        mov = CashMovement(
            cash_close_id=1,
            amount=Decimal("200.00"),
            description="Test",
            created_at=datetime.now(),
            id=1,
        )
        presenter.on_movement_added(mov)

        assert view.movements_total == Decimal("200.00")


class TestCashPresenterActiveCloseId:
    def test_returns_none_initially(self) -> None:
        """Sin cargar estado, el ID activo es None."""
        presenter = CashPresenter(FakeCashView())
        assert presenter.get_active_cash_close_id() is None

    def test_returns_id_after_state_loaded_with_open_session(self) -> None:
        """on_state_loaded con sesión abierta debe fijar el ID activo."""
        presenter = CashPresenter(FakeCashView())
        cc = _make_cash_close(id=5)
        presenter.on_state_loaded({"cash_close": cc, "movements": [], "sales_totals": {}})
        assert presenter.get_active_cash_close_id() == 5

    def test_returns_none_after_state_loaded_without_session(self) -> None:
        """on_state_loaded sin sesión abierta debe dejar el ID en None."""
        presenter = CashPresenter(FakeCashView())
        presenter.on_state_loaded({"cash_close": None, "movements": [], "sales_totals": {}})
        assert presenter.get_active_cash_close_id() is None

    def test_returns_id_after_session_opened(self) -> None:
        """on_session_opened debe fijar el ID activo (ruta 'Abrir caja')."""
        presenter = CashPresenter(FakeCashView())
        cc = _make_cash_close(id=99)
        presenter.on_session_opened(cc)
        assert presenter.get_active_cash_close_id() == 99

    def test_returns_none_after_session_closed(self) -> None:
        """on_session_closed debe limpiar el ID activo."""
        from src.domain.models.cash_close import CashClose

        presenter = CashPresenter(FakeCashView())
        cc = _make_cash_close(id=1)
        presenter.on_state_loaded({"cash_close": cc, "movements": [], "sales_totals": {}})
        closed_cc = CashClose(
            opened_at=datetime(2026, 3, 24, 8, 0),
            opening_amount=Decimal("5000.00"),
            closed_at=datetime(2026, 3, 24, 20, 0),
            closing_amount=Decimal("15000.00"),
        )
        presenter.on_session_closed(closed_cc)
        assert presenter.get_active_cash_close_id() is None

    def test_sales_summary_reads_totals_from_state_dict(self) -> None:
        """El presenter muestra correctamente los totales del dict de estado."""
        view = FakeCashView()
        presenter = CashPresenter(view)
        presenter.on_state_loaded({
            "cash_close": _make_cash_close(id=1),
            "movements": [],
            "sales_totals": {
                "EFECTIVO": Decimal("12500.00"),
                "DEBITO": Decimal("3200.00"),
                "TRANSFERENCIA": Decimal("0.00"),
            },
        })
        cash, debit, transfer = view.sales_summary
        assert cash == Decimal("12500.00")
        assert debit == Decimal("3200.00")
        assert transfer == Decimal("0.00")
