"""Caso de uso: obtener el arqueo abierto o abrir uno nuevo.

Si ya existe un arqueo abierto, lo retorna sin modificarlo.
Si no hay ninguno, crea uno nuevo con el monto inicial indicado.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.domain.models.cash_close import CashClose
from src.domain.ports.cash_repository import CashCloseRepository


class GetOrOpenCashClose:
    """Retorna el arqueo actualmente abierto, o abre uno nuevo.

    Garantiza que siempre exista exactamente un arqueo abierto.
    Si ya hay uno, lo retorna. Si no, crea uno con el ``opening_amount``
    provisto (por defecto 0).

    Args:
        cash_repo: Repositorio de arqueos de caja.

    Examples:
        >>> uc = GetOrOpenCashClose(repo)
        >>> close = uc.execute(opening_amount=Decimal("5000.00"))
        >>> close.is_open
        True
    """

    def __init__(self, cash_repo: CashCloseRepository) -> None:
        self._cash_repo = cash_repo

    def execute(self, opening_amount: Decimal = Decimal("0.00")) -> CashClose:
        """Retorna el arqueo abierto o crea uno nuevo.

        Args:
            opening_amount: Fondo inicial de caja, solo usado si se crea
                            un arqueo nuevo. Ignorado si ya hay uno abierto.

        Returns:
            CashClose con ``is_open == True``.

        Raises:
            ValueError: Si ``opening_amount`` es negativo.
        """
        existing = self._cash_repo.get_open()
        if existing is not None:
            return existing

        new_close = CashClose(
            opened_at=datetime.now(),
            opening_amount=opening_amount,
        )
        return self._cash_repo.save(new_close)
