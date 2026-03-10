"""Domain Service PriceCalculator.

Centraliza la lógica de cálculo de precios y márgenes para el kiosco.
Opera sobre Value Objects Price y tipos Decimal para garantizar precisión monetaria.
Sin estado. Sin dependencias externas.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from src.domain.models.price import Price


class PriceCalculator:
    """Servicio de dominio para cálculos de precios y márgenes en ARS.

    Sin estado: todos los métodos son estáticos o de clase.
    Usa Decimal con ROUND_HALF_UP en todos los cálculos.

    Examples:
        >>> from decimal import Decimal
        >>> cost = Price("250.00")
        >>> PriceCalculator.calculate_sale_price(cost, Decimal("35.00")).amount
        Decimal('337.50')
    """

    @staticmethod
    def calculate_sale_price(cost: Price, margin_percent: Decimal) -> Price:
        """Calcula el precio de venta dado el costo y el margen porcentual.

        Fórmula: precio_venta = costo × (1 + margen / 100)

        Args:
            cost: Costo de compra del producto.
            margin_percent: Porcentaje de margen de ganancia (ej: Decimal("35.00")).

        Returns:
            Price con el precio de venta calculado y redondeado.

        Raises:
            ValueError: Si el margen es negativo.

        Examples:
            >>> PriceCalculator.calculate_sale_price(Price("100.00"), Decimal("50.00")).amount
            Decimal('150.00')
        """
        if margin_percent < Decimal("0"):
            raise ValueError(
                f"El margen no puede ser negativo: {margin_percent}"
            )
        return cost.apply_margin(margin_percent)

    @staticmethod
    def calculate_margin_percent(cost: Price, sale_price: Price) -> Decimal:
        """Calcula el margen porcentual a partir del costo y el precio de venta.

        Fórmula: margen = (precio_venta / costo - 1) × 100

        Args:
            cost: Costo de compra del producto.
            sale_price: Precio de venta del producto.

        Returns:
            Porcentaje de margen redondeado a 2 decimales.

        Raises:
            ValueError: Si el costo es cero o si el precio de venta es menor al costo.

        Examples:
            >>> PriceCalculator.calculate_margin_percent(Price("100.00"), Price("135.00"))
            Decimal('35.00')
        """
        if cost.is_zero():
            raise ValueError(
                "No se puede calcular el margen con costo igual a cero."
            )
        if sale_price < cost:
            raise ValueError(
                f"El precio de venta ({sale_price.amount}) no puede ser menor al costo ({cost.amount})."
            )
        margin = (sale_price.amount / cost.amount - Decimal("1")) * Decimal("100")
        return margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def apply_bulk_increase(cost: Price, increase_percent: Decimal) -> Price:
        """Aplica un aumento porcentual al costo (útil para listas masivas de proveedores).

        Args:
            cost: Costo actual del producto.
            increase_percent: Porcentaje de aumento (ej: Decimal("15") para +15%).

        Returns:
            Nuevo Price con el costo actualizado.

        Raises:
            ValueError: Si el porcentaje de aumento es negativo.

        Examples:
            >>> PriceCalculator.apply_bulk_increase(Price("200.00"), Decimal("15")).amount
            Decimal('230.00')
        """
        if increase_percent < Decimal("0"):
            raise ValueError(
                f"El porcentaje de aumento no puede ser negativo: {increase_percent}"
            )
        return cost.percentage_increase(increase_percent)

    @staticmethod
    def calculate_cost_to_achieve_price(
        target_sale_price: Price, margin_percent: Decimal
    ) -> Price:
        """Calcula el costo máximo para lograr un precio de venta objetivo con un margen dado.

        Útil para determinar el costo límite al negociar con proveedores.
        Fórmula: costo_max = precio_venta / (1 + margen / 100)

        Args:
            target_sale_price: Precio de venta objetivo.
            margin_percent: Margen de ganancia deseado.

        Returns:
            Price con el costo máximo tolerable.

        Raises:
            ValueError: Si el margen es negativo o el precio objetivo es cero.

        Examples:
            >>> PriceCalculator.calculate_cost_to_achieve_price(Price("337.50"), Decimal("35.00")).amount
            Decimal('250.00')
        """
        if margin_percent < Decimal("0"):
            raise ValueError(
                f"El margen no puede ser negativo: {margin_percent}"
            )
        if target_sale_price.is_zero():
            raise ValueError("El precio de venta objetivo no puede ser cero.")
        divisor = Decimal("1") + margin_percent / Decimal("100")
        return Price(target_sale_price.amount / divisor)
