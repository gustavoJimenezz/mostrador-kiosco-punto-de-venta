"""Tests unitarios de los casos de uso de arqueo de caja.

Cubre: GetOrOpenCashClose, CloseCashClose, AddCashMovement.
No requiere base de datos — usa repositorios en memoria.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from src.application.use_cases.add_cash_movement import AddCashMovement
from src.application.use_cases.close_cash_close import CloseCashClose
from src.application.use_cases.get_or_open_cash_close import GetOrOpenCashClose
from src.domain.models.cash_close import CashClose
from tests.unit.domain.mocks.in_memory_cash_repository import (
    InMemoryCashCloseRepository,
    InMemoryCashMovementRepository,
)


# ---------------------------------------------------------------------------
# GetOrOpenCashClose
# ---------------------------------------------------------------------------

class TestGetOrOpenCashClose:
    def test_creates_new_session_when_none_exists(self):
        repo = InMemoryCashCloseRepository()
        uc = GetOrOpenCashClose(repo)

        result = uc.execute(opening_amount=Decimal("5000.00"))

        assert result.is_open
        assert result.opening_amount == Decimal("5000.00")
        assert result.id is not None

    def test_returns_existing_open_session(self):
        repo = InMemoryCashCloseRepository()
        existing = CashClose(
            opened_at=datetime(2026, 3, 23, 8, 0),
            opening_amount=Decimal("3000.00"),
        )
        repo.save(existing)
        uc = GetOrOpenCashClose(repo)

        result = uc.execute(opening_amount=Decimal("9999.00"))

        assert result is existing
        assert result.opening_amount == Decimal("3000.00")  # no sobreescribe

    def test_default_opening_amount_is_zero(self):
        repo = InMemoryCashCloseRepository()
        uc = GetOrOpenCashClose(repo)

        result = uc.execute()

        assert result.opening_amount == Decimal("0.00")

    def test_negative_opening_amount_raises(self):
        repo = InMemoryCashCloseRepository()
        uc = GetOrOpenCashClose(repo)

        with pytest.raises(ValueError):
            uc.execute(opening_amount=Decimal("-100"))


# ---------------------------------------------------------------------------
# CloseCashClose
# ---------------------------------------------------------------------------

class TestCloseCashClose:
    def test_closes_open_session(self):
        repo = InMemoryCashCloseRepository()
        cc = CashClose(
            opened_at=datetime(2026, 3, 23, 8, 0),
            opening_amount=Decimal("5000.00"),
        )
        repo.save(cc)
        uc = CloseCashClose(repo)

        result = uc.execute(closing_amount=Decimal("15000.00"))

        assert not result.is_open
        assert result.closing_amount == Decimal("15000.00")

    def test_raises_when_no_open_session(self):
        repo = InMemoryCashCloseRepository()
        uc = CloseCashClose(repo)

        with pytest.raises(ValueError, match="No hay ningún arqueo"):
            uc.execute(closing_amount=Decimal("1000.00"))

    def test_negative_closing_amount_raises(self):
        repo = InMemoryCashCloseRepository()
        cc = CashClose(
            opened_at=datetime(2026, 3, 23, 8, 0),
            opening_amount=Decimal("5000.00"),
        )
        repo.save(cc)
        uc = CloseCashClose(repo)

        with pytest.raises(ValueError):
            uc.execute(closing_amount=Decimal("-1"))


# ---------------------------------------------------------------------------
# AddCashMovement
# ---------------------------------------------------------------------------

class TestAddCashMovement:
    def test_income_movement_persisted(self):
        repo = InMemoryCashMovementRepository()
        uc = AddCashMovement(repo)

        mov = uc.execute(
            cash_close_id=1,
            amount=Decimal("2000.00"),
            description="Reposición de cambio",
        )

        assert mov.id is not None
        assert mov.is_income is True
        assert mov.amount == Decimal("2000.00")

    def test_expense_movement_persisted(self):
        repo = InMemoryCashMovementRepository()
        uc = AddCashMovement(repo)

        mov = uc.execute(
            cash_close_id=1,
            amount=Decimal("-500.00"),
            description="Pago a proveedor",
        )

        assert mov.is_income is False

    def test_description_stripped_whitespace(self):
        repo = InMemoryCashMovementRepository()
        uc = AddCashMovement(repo)

        mov = uc.execute(
            cash_close_id=1,
            amount=Decimal("100.00"),
            description="  Descripción con espacios  ",
        )

        assert mov.description == "Descripción con espacios"

    def test_zero_amount_raises(self):
        repo = InMemoryCashMovementRepository()
        uc = AddCashMovement(repo)

        with pytest.raises(ValueError):
            uc.execute(
                cash_close_id=1,
                amount=Decimal("0"),
                description="Test",
            )

    def test_empty_description_raises(self):
        repo = InMemoryCashMovementRepository()
        uc = AddCashMovement(repo)

        with pytest.raises(ValueError):
            uc.execute(
                cash_close_id=1,
                amount=Decimal("100.00"),
                description="",
            )
