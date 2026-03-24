"""Implementaciones en memoria de los repositorios de caja para tests unitarios.

No requieren base de datos. Cumplen los contratos de los puertos
``CashCloseRepository`` y ``CashMovementRepository``.
"""

from __future__ import annotations

from typing import Optional

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement


class InMemoryCashCloseRepository:
    """Repositorio en memoria de arqueos de caja.

    Almacena arqueos en una lista. Simula el comportamiento de
    ``get_open()`` retornando el primer arqueo sin ``closed_at``.

    Examples:
        >>> repo = InMemoryCashCloseRepository()
        >>> from datetime import datetime
        >>> from decimal import Decimal
        >>> cc = CashClose(opened_at=datetime.now(), opening_amount=Decimal("0"))
        >>> saved = repo.save(cc)
        >>> repo.get_open() is saved
        True
    """

    def __init__(self) -> None:
        self._closes: list[CashClose] = []
        self._next_id: int = 1
        self.fail_with: Exception | None = None

    def get_open(self) -> Optional[CashClose]:
        """Retorna el primer arqueo con ``closed_at=None``."""
        for cc in self._closes:
            if cc.closed_at is None:
                return cc
        return None

    def save(self, cash_close: CashClose) -> CashClose:
        """Persiste el arqueo en memoria, asignando ID si no tiene uno.

        Raises:
            Exception: Si ``fail_with`` está configurado.
        """
        if self.fail_with is not None:
            raise self.fail_with
        if cash_close.id is None:
            cash_close.id = self._next_id
            self._next_id += 1
            self._closes.append(cash_close)
        return cash_close


class InMemoryCashMovementRepository:
    """Repositorio en memoria de movimientos manuales de caja.

    Examples:
        >>> repo = InMemoryCashMovementRepository()
        >>> len(repo.list_by_cash_close(1))
        0
    """

    def __init__(self) -> None:
        self._movements: list[CashMovement] = []
        self._next_id: int = 1
        self.fail_with: Exception | None = None

    def save(self, movement: CashMovement) -> CashMovement:
        """Persiste el movimiento en memoria.

        Raises:
            Exception: Si ``fail_with`` está configurado.
        """
        if self.fail_with is not None:
            raise self.fail_with
        if movement.id is None:
            movement.id = self._next_id
            self._next_id += 1
        self._movements.append(movement)
        return movement

    def list_by_cash_close(self, cash_close_id: int) -> list[CashMovement]:
        """Retorna los movimientos del arqueo indicado, ordenados por ``created_at``."""
        return sorted(
            [m for m in self._movements if m.cash_close_id == cash_close_id],
            key=lambda m: m.created_at,
        )
