"""Entidad de dominio CashMovement (Movimiento de caja).

Registra cada movimiento manual de efectivo dentro de una sesión de caja:
ingresos (ej: fondo de inicio, cobros fuera del sistema) y egresos
(ej: pago a proveedores, retiro de efectivo).

Las ventas generan su propio rastro en ``sales``. Los movimientos manuales
se registran aquí para el cuadre del arqueo diario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class MovementType(str, Enum):
    """Tipo de movimiento de caja.

    Attributes:
        INCOME: Ingreso de efectivo (aumenta el saldo).
        EXPENSE: Egreso de efectivo (disminuye el saldo).
    """

    INCOME = "INGRESO"
    EXPENSE = "EGRESO"


@dataclass
class CashMovement:
    """Movimiento manual de efectivo dentro de un arqueo de caja.

    Se usa para registrar ingresos o egresos que no provienen de una venta
    directa, como pagos a proveedores, reposición de cambio o retiros.

    Attributes:
        cash_close_id: FK al arqueo de caja al que pertenece este movimiento.
        amount: Monto del movimiento (siempre positivo; el tipo indica dirección).
        movement_type: INGRESO o EGRESO.
        description: Texto libre que describe el movimiento.
        created_at: Momento exacto del registro.
        id: PK asignada por la DB (None antes de persistir).

    Examples:
        >>> from decimal import Decimal
        >>> from datetime import datetime
        >>> m = CashMovement(
        ...     cash_close_id=1,
        ...     amount=Decimal("5000.00"),
        ...     movement_type=MovementType.INCOME,
        ...     description="Fondo de cambio inicial",
        ...     created_at=datetime.now(),
        ... )
        >>> m.movement_type
        <MovementType.INCOME: 'INGRESO'>
    """

    cash_close_id: int
    amount: Decimal
    movement_type: MovementType
    description: str
    created_at: datetime
    id: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Valida invariantes del movimiento.

        Raises:
            ValueError: Si el monto es negativo o la descripción está vacía.
        """
        if self.amount <= Decimal("0"):
            raise ValueError(
                f"El monto del movimiento debe ser mayor a cero: {self.amount}"
            )
        if not self.description.strip():
            raise ValueError("La descripción del movimiento no puede estar vacía.")
