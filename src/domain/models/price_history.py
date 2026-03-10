"""Entidad de dominio PriceHistory.

Registro inmutable de cambios de costo de un producto.
Vital para analizar rentabilidad histórica ante la inflación en Argentina.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from .price import Price


@dataclass(frozen=True)
class PriceHistory:
    """Registro inmutable de un cambio de costo de un producto.

    Attributes:
        product_id: FK al producto afectado.
        old_cost: Costo anterior al cambio.
        new_cost: Costo nuevo tras el aumento/reducción.
        updated_at: Momento exacto del cambio de precio.
        id: PK asignada por la DB (None antes de persistir).

    Examples:
        >>> from datetime import datetime
        >>> from decimal import Decimal
        >>> ph = PriceHistory(product_id=1, old_cost=Decimal("200.00"), new_cost=Decimal("250.00"), updated_at=datetime.now())
        >>> ph.increase_percent
        Decimal('25.00')
    """

    product_id: int
    old_cost: Decimal
    new_cost: Decimal
    updated_at: datetime
    id: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Valida invariantes del registro.

        Raises:
            ValueError: Si algún campo es inválido.
        """
        if self.old_cost < Decimal("0"):
            raise ValueError(
                f"El costo anterior no puede ser negativo: {self.old_cost}"
            )
        if self.new_cost < Decimal("0"):
            raise ValueError(
                f"El nuevo costo no puede ser negativo: {self.new_cost}"
            )
        if self.old_cost == Decimal("0") and self.new_cost > Decimal("0"):
            # Primer registro de costo: válido
            pass

    @property
    def increase_percent(self) -> Optional[Decimal]:
        """Calcula el porcentaje de variación del costo.

        Returns:
            Porcentaje de aumento/reducción redondeado a 2 decimales,
            o None si el costo anterior era cero.
        """
        if self.old_cost == Decimal("0"):
            return None
        variation = (self.new_cost - self.old_cost) / self.old_cost * Decimal("100")
        from decimal import ROUND_HALF_UP
        return variation.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def old_sale_price(self) -> Price:
        """Precio de venta anterior (solo referencial, sin margen almacenado).

        Returns:
            Price basado en el costo anterior.
        """
        return Price(self.old_cost)

    @property
    def new_sale_price(self) -> Price:
        """Precio de venta nuevo (solo referencial, sin margen almacenado).

        Returns:
            Price basado en el nuevo costo.
        """
        return Price(self.new_cost)
