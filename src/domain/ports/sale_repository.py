"""Puerto de salida: contrato de persistencia atómica para ventas.

Define la interfaz que el adaptador MariaDB debe implementar para
persistir ventas garantizando atomicidad: INSERT sale + sale_items
+ UPDATE stock en una sola transacción.

El dominio solo conoce este Protocol; nunca importa SQLAlchemy ni MariaDB.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models.sale import Sale


@runtime_checkable
class SaleRepository(Protocol):
    """Puerto de salida para persistencia atómica de ventas.

    La implementación garantiza que INSERT de sale, sale_items y
    UPDATE de stock ocurran en una sola transacción DB.

    Examples:
        >>> class MockSaleRepo:
        ...     def save(self, sale: Sale) -> Sale: ...
        >>> isinstance(MockSaleRepo(), SaleRepository)
        True
    """

    def save(self, sale: Sale) -> Sale:
        """Persiste la venta (sale + sale_items) y descuenta el stock.

        La atomicidad es responsabilidad del adaptador de infraestructura.

        Args:
            sale: Entidad Sale con sus ítems completamente formados
                  (product_id, quantity, price_at_sale ya asignados).

        Returns:
            Sale persistida con IDs asignados por la DB.

        Raises:
            Exception: Si la transacción falla. El adaptador debe hacer rollback.
        """
        ...
