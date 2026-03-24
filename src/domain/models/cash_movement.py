"""Entidad de dominio CashMovement (Movimiento de caja).

Registra cada movimiento manual de efectivo dentro de una sesión de caja.
Ingresos se expresan con monto positivo, egresos con monto negativo.

Las ventas generan su propio rastro en ``sales``. Los movimientos manuales
se registran aquí para el cuadre del arqueo diario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class CashMovement:
    """Movimiento manual de efectivo dentro de un arqueo de caja.

    Se usa para registrar ingresos o egresos que no provienen de una venta
    directa, como pagos a proveedores, reposición de cambio o retiros.

    El signo del monto determina la dirección:
    - Positivo: ingreso (aumenta el saldo).
    - Negativo: egreso (disminuye el saldo).

    Attributes:
        cash_close_id: FK al arqueo de caja al que pertenece este movimiento.
        amount: Monto del movimiento (positivo = ingreso, negativo = egreso).
        description: Texto libre que describe el movimiento.
        created_at: Momento exacto del registro.
        id: PK asignada por la DB (None antes de persistir).

    Examples:
        >>> from decimal import Decimal
        >>> from datetime import datetime
        >>> ingreso = CashMovement(
        ...     cash_close_id=1,
        ...     amount=Decimal("5000.00"),
        ...     description="Fondo de cambio inicial",
        ...     created_at=datetime.now(),
        ... )
        >>> egreso = CashMovement(
        ...     cash_close_id=1,
        ...     amount=Decimal("-2000.00"),
        ...     description="Pago a proveedor",
        ...     created_at=datetime.now(),
        ... )
    """

    cash_close_id: int
    amount: Decimal
    description: str
    created_at: datetime
    id: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Valida invariantes del movimiento.

        Raises:
            ValueError: Si el monto es cero o la descripción está vacía.
        """
        if self.amount == Decimal("0"):
            raise ValueError("El monto del movimiento no puede ser cero.")
        if not self.description.strip():
            raise ValueError("La descripción del movimiento no puede estar vacía.")

    @property
    def is_income(self) -> bool:
        """Retorna True si el movimiento es un ingreso (monto positivo)."""
        return self.amount > Decimal("0")
