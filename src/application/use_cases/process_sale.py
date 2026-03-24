"""Caso de uso: procesar una venta de forma atómica.

Regla crítica de negocio: descuento de stock + registro de venta ocurren
en una sola transacción DB. O todo, o nada.

El caso de uso valida las reglas de negocio (stock suficiente, carrito no
vacío) y delega la persistencia atómica al SaleRepository.
"""

from __future__ import annotations

from typing import Optional

from src.domain.models.product import Product
from src.domain.models.sale import PaymentMethod, Sale, SaleItem
from src.domain.ports.product_repository import ProductRepository
from src.domain.ports.sale_repository import SaleRepository


class ProcessSale:
    """Caso de uso: crea y persiste una venta de forma atómica.

    Responsabilidades:
        - Validar que el carrito no esté vacío.
        - Validar stock suficiente para cada ítem.
        - Construir las entidades Sale y SaleItem con price_at_sale correcto
          (snapshot del precio actual, inmutable tras la venta).
        - Delegar la persistencia atómica al SaleRepository.

    Args:
        sale_repo: Puerto de persistencia de ventas (atómico).
        product_repo: Puerto de acceso a productos (para validaciones futuras).

    Examples:
        >>> uc = ProcessSale(sale_repo, product_repo)
        >>> sale = uc.execute(cart, PaymentMethod.CASH)
        >>> sale.total_amount.amount
        Decimal('337.50')
    """

    def __init__(
        self,
        sale_repo: SaleRepository,
        product_repo: ProductRepository,
    ) -> None:
        """Inicializa el caso de uso con los repositorios inyectados.

        Args:
            sale_repo: Implementación de SaleRepository (transacción atómica).
            product_repo: Implementación de ProductRepository.
        """
        self._sale_repo = sale_repo
        self._product_repo = product_repo

    def execute(
        self,
        cart: dict[int, tuple[Product, int]],
        payment_method: PaymentMethod,
        cash_close_id: Optional[int] = None,
    ) -> Sale:
        """Procesa y persiste una venta completa.

        El price_at_sale de cada SaleItem se toma del precio de venta
        calculado en el momento de la llamada (product.current_price).
        Este valor es inmutable: nunca se recalcula retroactivamente.

        Args:
            cart: Diccionario ``{product_id: (Product, quantity)}`` con
                  los ítems a vender.
            payment_method: Método de pago seleccionado por el cajero.
            cash_close_id: ID del arqueo de caja activo. Si se provee,
                la venta queda vinculada a la sesión para el detalle de caja.

        Returns:
            Sale persistida con los ítems y price_at_sale registrado.

        Raises:
            ValueError: Si el carrito está vacío o hay stock insuficiente
                        para algún producto.
        """
        if not cart:
            raise ValueError("No se puede procesar una venta con carrito vacío.")

        for product, quantity in cart.values():
            if product.stock < quantity:
                raise ValueError(
                    f"Stock insuficiente para '{product.name}': "
                    f"disponible={product.stock}, requerido={quantity}"
                )

        items = [
            SaleItem(
                product_id=product.id,
                quantity=quantity,
                price_at_sale=product.current_price.amount,
            )
            for product, quantity in cart.values()
        ]

        sale = Sale(
            payment_method=payment_method,
            items=items,
            cash_close_id=cash_close_id,
        )
        return self._sale_repo.save(sale)
