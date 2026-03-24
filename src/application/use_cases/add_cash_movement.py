"""Caso de uso: registrar un movimiento manual de caja.

Permite al cajero ingresar o egresar efectivo manualmente dentro de
una sesión de caja abierta (ej: pago a proveedor, reposición de cambio).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.domain.models.cash_movement import CashMovement, MovementType
from src.domain.ports.cash_repository import CashMovementRepository


class AddCashMovement:
    """Registra un movimiento manual (ingreso o egreso) en el arqueo activo.

    Args:
        movement_repo: Repositorio de movimientos de caja.

    Examples:
        >>> uc = AddCashMovement(repo)
        >>> mov = uc.execute(
        ...     cash_close_id=1,
        ...     amount=Decimal("2000.00"),
        ...     movement_type=MovementType.EXPENSE,
        ...     description="Pago a proveedor",
        ... )
        >>> mov.movement_type
        <MovementType.EXPENSE: 'EGRESO'>
    """

    def __init__(self, movement_repo: CashMovementRepository) -> None:
        self._movement_repo = movement_repo

    def execute(
        self,
        cash_close_id: int,
        amount: Decimal,
        movement_type: MovementType,
        description: str,
    ) -> CashMovement:
        """Persiste el movimiento manual en el arqueo de caja indicado.

        Args:
            cash_close_id: ID del arqueo de caja donde registrar el movimiento.
            amount: Monto del movimiento (debe ser mayor a cero).
            movement_type: INGRESO o EGRESO.
            description: Texto descriptivo del movimiento (requerido).

        Returns:
            CashMovement persistido con ``id`` asignado.

        Raises:
            ValueError: Si el monto es <= 0 o la descripción está vacía.
        """
        movement = CashMovement(
            cash_close_id=cash_close_id,
            amount=amount,
            movement_type=movement_type,
            description=description.strip(),
            created_at=datetime.now(),
        )
        return self._movement_repo.save(movement)
