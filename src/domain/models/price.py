"""Value Object Price para aritmética monetaria en ARS.

Encapsula Decimal con ROUND_HALF_UP para evitar descuadre de caja
por acumulación de errores de punto flotante.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Union

_QUANTIZE_ARS = Decimal("0.01")

MonetaryInput = Union[Decimal, str, int]


def _to_decimal(value: MonetaryInput) -> Decimal:
    """Convierte un valor monetario a Decimal.

    Args:
        value: Valor numérico como Decimal, str o int.

    Returns:
        Instancia de Decimal.

    Raises:
        TypeError: Si el tipo no es soportado.
        ValueError: Si el string no representa un número válido.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"Tipo no soportado para Price: {type(value)!r}")


@dataclass(frozen=True)
class Price:
    """Value Object que representa un precio o monto en ARS.

    Inmutable. Toda operación retorna una nueva instancia.
    El redondeo siempre aplica ROUND_HALF_UP con dos decimales.

    Attributes:
        amount: Monto en pesos argentinos, redondeado a 2 decimales.

    Examples:
        >>> p = Price("100.005")
        >>> p.amount
        Decimal('100.01')
        >>> (Price("50.00") + Price("25.50")).amount
        Decimal('75.50')
    """

    amount: Decimal

    def __init__(self, amount: MonetaryInput) -> None:
        """Inicializa el Price redondeando al centavo más cercano (ROUND_HALF_UP).

        Args:
            amount: Monto como Decimal, str o int.

        Raises:
            TypeError: Si el tipo no es soportado.
            ValueError: Si el valor es negativo o no numérico.
        """
        raw = _to_decimal(amount)
        if raw < Decimal("0"):
            raise ValueError(f"El precio no puede ser negativo: {raw}")
        rounded = raw.quantize(_QUANTIZE_ARS, rounding=ROUND_HALF_UP)
        # frozen=True requiere object.__setattr__ para asignar en __init__
        object.__setattr__(self, "amount", rounded)

    # ------------------------------------------------------------------
    # Aritmética
    # ------------------------------------------------------------------

    def __add__(self, other: Price) -> Price:
        """Suma dos precios.

        Args:
            other: Price a sumar.

        Returns:
            Nuevo Price con la suma.
        """
        if not isinstance(other, Price):
            return NotImplemented
        return Price(self.amount + other.amount)

    def __sub__(self, other: Price) -> Price:
        """Resta dos precios.

        Args:
            other: Price a restar.

        Returns:
            Nuevo Price con la diferencia.

        Raises:
            ValueError: Si el resultado es negativo.
        """
        if not isinstance(other, Price):
            return NotImplemented
        return Price(self.amount - other.amount)

    def __mul__(self, factor: Union[Decimal, int]) -> Price:
        """Multiplica el precio por un factor numérico.

        Args:
            factor: Multiplicador (Decimal o int).

        Returns:
            Nuevo Price con el resultado.
        """
        if not isinstance(factor, (Decimal, int)):
            return NotImplemented
        return Price(self.amount * Decimal(factor))

    def __rmul__(self, factor: Union[Decimal, int]) -> Price:
        """Soporta factor * Price.

        Args:
            factor: Multiplicador (Decimal o int).

        Returns:
            Nuevo Price con el resultado.
        """
        return self.__mul__(factor)

    def __truediv__(self, divisor: Union[Decimal, int]) -> Price:
        """Divide el precio por un divisor numérico.

        Args:
            divisor: Divisor (Decimal o int).

        Returns:
            Nuevo Price con el cociente.

        Raises:
            ZeroDivisionError: Si el divisor es cero.
        """
        if not isinstance(divisor, (Decimal, int)):
            return NotImplemented
        return Price(self.amount / Decimal(divisor))

    # ------------------------------------------------------------------
    # Comparación
    # ------------------------------------------------------------------

    def __lt__(self, other: Price) -> bool:
        if not isinstance(other, Price):
            return NotImplemented
        return self.amount < other.amount

    def __le__(self, other: Price) -> bool:
        if not isinstance(other, Price):
            return NotImplemented
        return self.amount <= other.amount

    def __gt__(self, other: Price) -> bool:
        if not isinstance(other, Price):
            return NotImplemented
        return self.amount > other.amount

    def __ge__(self, other: Price) -> bool:
        if not isinstance(other, Price):
            return NotImplemented
        return self.amount >= other.amount

    # ------------------------------------------------------------------
    # Representación
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"Price('{self.amount}')"

    def __str__(self) -> str:
        return f"ARS {self.amount:,.2f}"

    # ------------------------------------------------------------------
    # Helpers de negocio
    # ------------------------------------------------------------------

    def apply_margin(self, margin_percent: Decimal) -> Price:
        """Calcula el precio de venta aplicando un margen porcentual sobre el costo.

        Fórmula: precio_venta = costo * (1 + margen / 100)

        Args:
            margin_percent: Porcentaje de margen (ej: Decimal("35.00") para 35%).

        Returns:
            Nuevo Price con el precio de venta calculado.

        Raises:
            ValueError: Si el margen es negativo.
        """
        if margin_percent < Decimal("0"):
            raise ValueError(f"El margen no puede ser negativo: {margin_percent}")
        factor = Decimal("1") + margin_percent / Decimal("100")
        return Price(self.amount * factor)

    def percentage_increase(self, percent: Decimal) -> Price:
        """Aplica un aumento porcentual al precio.

        Args:
            percent: Porcentaje de aumento (ej: Decimal("15") para +15%).

        Returns:
            Nuevo Price con el aumento aplicado.
        """
        factor = Decimal("1") + percent / Decimal("100")
        return Price(self.amount * factor)

    def is_zero(self) -> bool:
        """Retorna True si el monto es cero.

        Returns:
            bool indicando si el precio es cero.
        """
        return self.amount == Decimal("0.00")
