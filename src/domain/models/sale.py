"""Entidades de dominio Sale y SaleItem.

Una Sale es la cabecera de una transacción de venta.
Cada SaleItem representa un producto vendido con el precio fijo
al momento de la transacción (price_at_sale).

Regla crítica: price_at_sale es inmutable una vez registrado.
Nunca se recalcula retroactivamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from .price import Price


class PaymentMethod(str, Enum):
    """Métodos de pago aceptados en el kiosco.

    Attributes:
        CASH: Efectivo.
        DEBIT: Tarjeta de débito.
        TRANSFER: Transferencia bancaria (Mercado Pago, etc.).
    """

    CASH = "EFECTIVO"
    DEBIT = "DEBITO"
    TRANSFER = "TRANSFERENCIA"


@dataclass(frozen=True)
class SaleItem:
    """Línea de detalle de una venta.

    Attributes:
        product_id: FK al producto vendido.
        quantity: Cantidad de unidades vendidas.
        price_at_sale: Precio unitario al momento de la venta (inmutable).
        id: PK asignada por la DB (None antes de persistir).

    Examples:
        >>> item = SaleItem(product_id=1, quantity=3, price_at_sale=Decimal("337.50"))
        >>> item.subtotal.amount
        Decimal('1012.50')
    """

    product_id: int
    quantity: int
    price_at_sale: Decimal
    id: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Valida invariantes del ítem.

        Raises:
            ValueError: Si la cantidad o el precio son inválidos.
        """
        if self.quantity <= 0:
            raise ValueError(
                f"La cantidad debe ser mayor a cero: {self.quantity}"
            )
        if self.price_at_sale < Decimal("0"):
            raise ValueError(
                f"El precio al momento de venta no puede ser negativo: {self.price_at_sale}"
            )

    @property
    def subtotal(self) -> Price:
        """Calcula el subtotal del ítem (precio_unitario × cantidad).

        Returns:
            Price con el subtotal del ítem.
        """
        return Price(self.price_at_sale) * self.quantity


@dataclass
class Sale:
    """Cabecera de una transacción de venta.

    Attributes:
        payment_method: Método de pago utilizado.
        items: Lista de ítems vendidos (al menos uno requerido).
        timestamp: Momento de la venta (por defecto: ahora).
        cash_close_id: FK al arqueo de caja del día (None hasta el cierre).
        id: UUID de la venta (generado automáticamente).

    Examples:
        >>> item = SaleItem(product_id=1, quantity=2, price_at_sale=Decimal("337.50"))
        >>> sale = Sale(payment_method=PaymentMethod.CASH, items=[item])
        >>> sale.total_amount.amount
        Decimal('675.00')
    """

    payment_method: PaymentMethod
    items: list[SaleItem] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    cash_close_id: Optional[int] = None
    id: UUID = field(default_factory=uuid4, compare=False)

    def __post_init__(self) -> None:
        """Valida que la venta tenga al menos un ítem.

        Raises:
            ValueError: Si la lista de ítems está vacía.
        """
        if not self.items:
            raise ValueError("Una venta debe contener al menos un ítem.")

    @property
    def total_amount(self) -> Price:
        """Calcula el total de la venta sumando todos los subtotales.

        Returns:
            Price con el monto total de la venta.
        """
        total = Price("0")
        for item in self.items:
            total = total + item.subtotal
        return total

    @property
    def item_count(self) -> int:
        """Retorna la cantidad total de unidades vendidas.

        Returns:
            Suma de cantidades de todos los ítems.
        """
        return sum(item.quantity for item in self.items)

    def add_item(self, item: SaleItem) -> None:
        """Agrega un ítem a la venta.

        Args:
            item: SaleItem a agregar.

        Raises:
            ValueError: Si el ítem es inválido.
        """
        self.items.append(item)
