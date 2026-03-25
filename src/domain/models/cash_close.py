"""Entidad de dominio CashClose (Arqueo de Caja).

Representa el cierre diario de caja del kiosco.
Agrupa todas las ventas del día y permite calcular
la diferencia entre el efectivo esperado y el real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from .price import Price


@dataclass
class CashClose:
    """Arqueo de caja diario del kiosco.

    Attributes:
        opened_at: Momento en que se abrió la caja.
        opening_amount: Monto inicial en caja al abrir (fondo de cambio).
        closed_at: Momento del cierre (None si la caja sigue abierta).
        closing_amount: Dinero contado físicamente al cierre (None si abierta).
        total_sales_cash: Total de ventas en efectivo durante el día.
        total_sales_debit: Total de ventas con débito durante el día.
        total_sales_transfer: Total de ventas por transferencia durante el día.
        id: PK asignada por la DB (None antes de persistir).

    Examples:
        >>> from datetime import datetime
        >>> from decimal import Decimal
        >>> cc = CashClose(opened_at=datetime.now(), opening_amount=Decimal("5000.00"))
        >>> cc.is_open
        True
    """

    opened_at: datetime
    opening_amount: Decimal
    closed_at: Optional[datetime] = None
    closing_amount: Optional[Decimal] = None
    total_sales_cash: Decimal = field(default=Decimal("0.00"))
    total_sales_debit: Decimal = field(default=Decimal("0.00"))
    total_sales_transfer: Decimal = field(default=Decimal("0.00"))
    gross_profit_estimate: Optional[Decimal] = field(default=None, compare=False)
    total_cost_estimate: Optional[Decimal] = field(default=None, compare=False)
    id: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Valida invariantes del arqueo.

        Raises:
            ValueError: Si los montos son negativos o el cierre es inconsistente.
        """
        if self.opening_amount < Decimal("0"):
            raise ValueError(
                f"El monto de apertura no puede ser negativo: {self.opening_amount}"
            )
        if self.closing_amount is not None and self.closing_amount < Decimal("0"):
            raise ValueError(
                f"El monto de cierre no puede ser negativo: {self.closing_amount}"
            )
        if self.closed_at is not None and self.closing_amount is None:
            raise ValueError(
                "Si se registra la hora de cierre, se debe indicar el monto de cierre."
            )
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError(
                "La hora de cierre no puede ser anterior a la de apertura."
            )

    @property
    def is_open(self) -> bool:
        """Indica si la caja está abierta.

        Returns:
            True si la caja no ha sido cerrada.
        """
        return self.closed_at is None

    @property
    def total_sales(self) -> Price:
        """Total de ventas del día sumando todos los métodos de pago.

        Returns:
            Price con el total de ventas del día.
        """
        return Price(
            self.total_sales_cash + self.total_sales_debit + self.total_sales_transfer
        )

    @property
    def expected_cash(self) -> Price:
        """Efectivo esperado en caja (apertura + ventas en efectivo).

        Returns:
            Price con el monto esperado en billetes.
        """
        return Price(self.opening_amount + self.total_sales_cash)

    @property
    def cash_difference(self) -> Optional[Decimal]:
        """Diferencia entre el efectivo contado y el esperado.

        Solo disponible si la caja fue cerrada.

        Returns:
            Diferencia en ARS (positivo: sobrante, negativo: faltante),
            o None si la caja está abierta.
        """
        if self.closing_amount is None:
            return None
        from decimal import ROUND_HALF_UP
        diff = self.closing_amount - self.expected_cash.amount
        return diff.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def close(self, closed_at: datetime, closing_amount: Decimal) -> None:
        """Cierra el arqueo de caja.

        Args:
            closed_at: Momento del cierre.
            closing_amount: Monto contado físicamente al cierre.

        Raises:
            ValueError: Si la caja ya está cerrada o los parámetros son inválidos.
        """
        if not self.is_open:
            raise ValueError("El arqueo de caja ya fue cerrado.")
        if closing_amount < Decimal("0"):
            raise ValueError(
                f"El monto de cierre no puede ser negativo: {closing_amount}"
            )
        if closed_at < self.opened_at:
            raise ValueError(
                "La hora de cierre no puede ser anterior a la de apertura."
            )
        self.closed_at = closed_at
        self.closing_amount = closing_amount

    def register_sale(
        self,
        cash_amount: Decimal = Decimal("0"),
        debit_amount: Decimal = Decimal("0"),
        transfer_amount: Decimal = Decimal("0"),
    ) -> None:
        """Acumula los montos de una venta al arqueo.

        Args:
            cash_amount: Monto en efectivo de la venta.
            debit_amount: Monto en débito de la venta.
            transfer_amount: Monto en transferencia de la venta.

        Raises:
            ValueError: Si la caja está cerrada o los montos son negativos.
        """
        if not self.is_open:
            raise ValueError("No se pueden registrar ventas en una caja cerrada.")
        if cash_amount < Decimal("0") or debit_amount < Decimal("0") or transfer_amount < Decimal("0"):
            raise ValueError("Los montos de venta no pueden ser negativos.")
        self.total_sales_cash += cash_amount
        self.total_sales_debit += debit_amount
        self.total_sales_transfer += transfer_amount
