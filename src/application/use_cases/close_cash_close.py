"""Caso de uso: cerrar el arqueo de caja activo.

Registra la hora de cierre y el monto físico contado por el cajero.
Solo puede cerrarse el arqueo que está actualmente abierto.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.domain.models.cash_close import CashClose
from src.domain.ports.cash_repository import CashCloseRepository


class CloseCashClose:
    """Cierra el arqueo de caja actualmente abierto.

    Args:
        cash_repo: Repositorio de arqueos de caja.

    Examples:
        >>> uc = CloseCashClose(repo)
        >>> closed = uc.execute(closing_amount=Decimal("15000.00"))
        >>> closed.is_open
        False
    """

    def __init__(self, cash_repo: CashCloseRepository) -> None:
        self._cash_repo = cash_repo

    def execute(self, closing_amount: Decimal) -> CashClose:
        """Cierra el arqueo abierto registrando el monto físico contado.

        Args:
            closing_amount: Dinero contado físicamente al cerrar la caja.

        Returns:
            CashClose cerrado y persistido.

        Raises:
            ValueError: Si no hay ningún arqueo abierto o el monto es negativo.
        """
        cash_close = self._cash_repo.get_open()
        if cash_close is None:
            raise ValueError("No hay ningún arqueo de caja abierto para cerrar.")

        cash_close.close(
            closed_at=datetime.now(),
            closing_amount=closing_amount,
        )
        return self._cash_repo.save(cash_close)
