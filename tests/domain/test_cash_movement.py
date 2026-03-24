"""Tests unitarios del dominio: CashMovement.

Cubre validaciones de invariantes, tipos y comportamiento básico.
No requiere base de datos.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.cash_movement import CashMovement, MovementType


def _make(
    amount: Decimal = Decimal("1000.00"),
    movement_type: MovementType = MovementType.INCOME,
    description: str = "Fondo inicial",
) -> CashMovement:
    return CashMovement(
        cash_close_id=1,
        amount=amount,
        movement_type=movement_type,
        description=description,
        created_at=datetime(2026, 3, 23, 9, 0),
    )


class TestCashMovementCreation:
    def test_income_movement_created(self):
        mov = _make(movement_type=MovementType.INCOME)
        assert mov.movement_type == MovementType.INCOME
        assert mov.movement_type.value == "INGRESO"

    def test_expense_movement_created(self):
        mov = _make(movement_type=MovementType.EXPENSE)
        assert mov.movement_type == MovementType.EXPENSE
        assert mov.movement_type.value == "EGRESO"

    def test_id_defaults_to_none(self):
        mov = _make()
        assert mov.id is None

    def test_amount_stored_correctly(self):
        mov = _make(amount=Decimal("2500.50"))
        assert mov.amount == Decimal("2500.50")


class TestCashMovementValidations:
    def test_zero_amount_raises(self):
        with pytest.raises(ValueError, match="mayor a cero"):
            _make(amount=Decimal("0"))

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="mayor a cero"):
            _make(amount=Decimal("-100"))

    def test_empty_description_raises(self):
        with pytest.raises(ValueError, match="descripción"):
            _make(description="")

    def test_whitespace_description_raises(self):
        with pytest.raises(ValueError, match="descripción"):
            _make(description="   ")


class TestMovementType:
    def test_income_is_str(self):
        assert MovementType.INCOME == "INGRESO"

    def test_expense_is_str(self):
        assert MovementType.EXPENSE == "EGRESO"

    def test_from_string(self):
        assert MovementType("INGRESO") is MovementType.INCOME
        assert MovementType("EGRESO") is MovementType.EXPENSE
