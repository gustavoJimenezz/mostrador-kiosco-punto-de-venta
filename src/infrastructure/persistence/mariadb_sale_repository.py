"""Adaptador de infraestructura: persistencia atómica de ventas en MariaDB.

Implementa el puerto SaleRepository usando SQLAlchemy Core SQL (no ORM),
dado que Sale y SaleItem no tienen mapeo imperativo en mappings.py.

Garantiza que INSERT sales + INSERT sale_items + UPDATE stock ocurran
en una sola transacción. Si falla cualquier paso, hace rollback completo.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.domain.models.sale import Sale
from src.infrastructure.persistence.tables import (
    products_table,
    sale_items_table,
    sales_table,
)


class MariadbSaleRepository:
    """Implementación MariaDB de SaleRepository (transacción atómica).

    Usa SQLAlchemy Core (INSERT/UPDATE explícitos) en lugar de ORM para
    las tablas sales y sale_items, que no tienen mapeo imperativo.

    El descuento de stock se ejecuta dentro de la misma transacción
    para cumplir la regla de atomicidad del negocio.

    Args:
        session: Sesión SQLAlchemy activa. El repositorio gestiona
                 commit/rollback de la transacción de venta.

    Examples:
        >>> repo = MariadbSaleRepository(session)
        >>> saved_sale = repo.save(sale)
    """

    def __init__(self, session: Session) -> None:
        """Inicializa el repositorio con la sesión SQLAlchemy.

        Args:
            session: Sesión activa. No debe tener transacciones pendientes.
        """
        self._session = session

    def save(self, sale: Sale) -> Sale:
        """Persiste la venta y descuenta el stock de forma atómica.

        Operaciones dentro de la transacción (en orden):
        1. INSERT en ``sales`` (cabecera con UUID, total, método de pago).
        2. INSERT en ``sale_items`` por cada ítem (price_at_sale inmutable).
        3. UPDATE ``products.stock`` decrementando la cantidad vendida.
        4. COMMIT.

        Si cualquier paso falla, se ejecuta ROLLBACK completo.

        Args:
            sale: Entidad Sale con sus ítems completamente formados.
                  Cada SaleItem requiere ``product_id``, ``quantity``
                  y ``price_at_sale`` ya asignados.

        Returns:
            Sale persistida (la misma entidad recibida, sin mutación).

        Raises:
            Exception: Propaga el error original tras ejecutar rollback.
        """
        try:
            self._session.execute(
                sales_table.insert().values(
                    id=str(sale.id),
                    timestamp=sale.timestamp,
                    total_amount=sale.total_amount.amount,
                    payment_method=sale.payment_method.value,
                    cash_close_id=sale.cash_close_id,
                )
            )

            for item in sale.items:
                self._session.execute(
                    sale_items_table.insert().values(
                        sale_id=str(sale.id),
                        product_id=item.product_id,
                        quantity=item.quantity,
                        price_at_sale=item.price_at_sale,
                    )
                )
                self._session.execute(
                    products_table.update()
                    .where(products_table.c.id == item.product_id)
                    .values(stock=products_table.c.stock - item.quantity)
                )

            self._session.commit()
            return sale

        except Exception:
            self._session.rollback()
            raise
