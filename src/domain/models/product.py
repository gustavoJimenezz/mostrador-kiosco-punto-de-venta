"""Entidad de dominio Product.

Representa un producto del catálogo del kiosco. Es Python puro,
sin dependencias de SQLAlchemy ni de ningún framework externo.
El mapeo ORM se realiza de forma imperativa en infrastructure/persistence/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .price import Price


@dataclass
class Product:
    """Entidad que representa un producto en el catálogo del kiosco.

    Attributes:
        id: Identificador único (asignado por la DB; None antes de persistir).
        barcode: Código EAN-13 u otro código de barras del producto.
        name: Nombre descriptivo del producto.
        current_cost: Último costo de compra al proveedor en ARS.
        margin_percent: Porcentaje de ganancia aplicado al costo (ej: 35.00).
        stock: Cantidad actual en inventario.
        min_stock: Umbral mínimo para alerta de stock crítico.
        category_id: FK a la tabla de categorías (opcional).

    Examples:
        >>> p = Product(barcode="7790895000115", name="Alfajor Jorgito", current_cost=Decimal("250.00"), margin_percent=Decimal("35.00"))
        >>> p.current_price.amount
        Decimal('337.50')
    """

    barcode: str
    name: str
    current_cost: Decimal
    margin_percent: Decimal = Decimal("30")
    stock: int = 0
    min_stock: int = 0
    category_id: Optional[int] = None
    id: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Valida invariantes de la entidad tras la inicialización.

        Raises:
            ValueError: Si algún campo viola las reglas de negocio.
        """
        if not self.barcode or not self.barcode.strip():
            raise ValueError("El código de barras no puede estar vacío.")
        if not self.name or not self.name.strip():
            raise ValueError("El nombre del producto no puede estar vacío.")
        if self.current_cost < Decimal("0"):
            raise ValueError(
                f"El costo no puede ser negativo: {self.current_cost}"
            )
        if self.margin_percent < Decimal("0"):
            raise ValueError(
                f"El margen no puede ser negativo: {self.margin_percent}"
            )
        if self.stock < 0:
            raise ValueError(f"El stock no puede ser negativo: {self.stock}")
        if self.min_stock < 0:
            raise ValueError(
                f"El stock mínimo no puede ser negativo: {self.min_stock}"
            )

    @property
    def current_price(self) -> Price:
        """Calcula el precio de venta actual basado en costo y margen.

        Returns:
            Price con el precio de venta calculado.
        """
        return Price(self.current_cost).apply_margin(self.margin_percent)

    @property
    def is_low_stock(self) -> bool:
        """Indica si el stock actual está en nivel crítico.

        Returns:
            True si el stock actual es menor o igual al stock mínimo.
        """
        return self.stock <= self.min_stock

    def update_cost(self, new_cost: Decimal) -> None:
        """Actualiza el costo del producto.

        Este método NO registra el historial; esa responsabilidad
        recae en el caso de uso correspondiente (UpdateProductCost).

        Args:
            new_cost: Nuevo costo de compra en ARS.

        Raises:
            ValueError: Si el nuevo costo es negativo.
        """
        if new_cost < Decimal("0"):
            raise ValueError(f"El costo no puede ser negativo: {new_cost}")
        self.current_cost = new_cost

    def update_margin(self, new_margin: Decimal) -> None:
        """Actualiza el margen de ganancia del producto.

        Args:
            new_margin: Nuevo porcentaje de margen (ej: Decimal("40.00")).

        Raises:
            ValueError: Si el nuevo margen es negativo.
        """
        if new_margin < Decimal("0"):
            raise ValueError(f"El margen no puede ser negativo: {new_margin}")
        self.margin_percent = new_margin

    def decrement_stock(self, quantity: int) -> None:
        """Descuenta stock tras una venta.

        Args:
            quantity: Cantidad a descontar.

        Raises:
            ValueError: Si la cantidad es inválida o el stock sería negativo.
        """
        if quantity <= 0:
            raise ValueError(
                f"La cantidad a descontar debe ser positiva: {quantity}"
            )
        if self.stock < quantity:
            raise ValueError(
                f"Stock insuficiente: disponible={self.stock}, requerido={quantity}"
            )
        self.stock -= quantity

    def increment_stock(self, quantity: int) -> None:
        """Incrementa stock tras una compra o ajuste.

        Args:
            quantity: Cantidad a agregar.

        Raises:
            ValueError: Si la cantidad es inválida.
        """
        if quantity <= 0:
            raise ValueError(
                f"La cantidad a incrementar debe ser positiva: {quantity}"
            )
        self.stock += quantity
