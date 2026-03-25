"""Adaptador de infraestructura: persistencia atómica de ventas en MariaDB.

Implementa el puerto SaleRepository usando SQLAlchemy Core SQL (no ORM),
dado que Sale y SaleItem no tienen mapeo imperativo en mappings.py.

Garantiza que INSERT sales + INSERT sale_items + UPDATE stock ocurran
en una sola transacción. Si falla cualquier paso, hace rollback completo.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domain.models.sale import PaymentMethod, Sale, SaleItem
from src.infrastructure.persistence.tables import (
    cash_closes_table,
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

            if sale.cash_close_id is not None:
                if sale.payment_method == PaymentMethod.CASH:
                    col = cash_closes_table.c.total_sales_cash
                elif sale.payment_method == PaymentMethod.DEBIT:
                    col = cash_closes_table.c.total_sales_debit
                else:
                    col = cash_closes_table.c.total_sales_transfer
                self._session.execute(
                    cash_closes_table.update()
                    .where(cash_closes_table.c.id == sale.cash_close_id)
                    .values({col.key: col + sale.total_amount.amount})
                )

            self._session.commit()
            return sale

        except Exception:
            self._session.rollback()
            raise

    # ------------------------------------------------------------------
    # SaleQueryRepository — consultas de historial y reportes
    # ------------------------------------------------------------------

    def list_by_date_range(self, start: datetime, end: datetime) -> list[Sale]:
        """Lista ventas en el rango ``[start, end)`` sin cargar sus ítems.

        Retorna entidades ``Sale`` con ``items=[]`` para eficiencia.
        Los ítems se obtienen bajo demanda con ``get_sale_items_with_names``.

        Args:
            start: Fecha/hora de inicio (inclusivo).
            end: Fecha/hora de fin (exclusivo).

        Returns:
            Lista de Sale ordenada por ``timestamp`` descendente.
        """
        rows = self._session.execute(
            sales_table.select()
            .where(sales_table.c.timestamp >= start)
            .where(sales_table.c.timestamp < end)
            .order_by(sales_table.c.timestamp.desc())
        ).fetchall()

        return [
            Sale(
                payment_method=PaymentMethod(row.payment_method),
                items=[],
                timestamp=row.timestamp,
                cash_close_id=row.cash_close_id,
                id=UUID(row.id),
                total_snapshot=Decimal(str(row.total_amount)),
            )
            for row in rows
        ]

    def get_daily_totals(self, day: date) -> dict[str, Decimal]:
        """Retorna totales de ventas del día agrupados por método de pago.

        Args:
            day: Fecha a consultar.

        Returns:
            Diccionario ``{payment_method_value: total_amount}``.
        """
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())

        rows = self._session.execute(
            select(
                sales_table.c.payment_method,
                func.sum(sales_table.c.total_amount).label("total"),
            )
            .where(sales_table.c.timestamp.between(start, end))
            .group_by(sales_table.c.payment_method)
        ).fetchall()

        return {row.payment_method: Decimal(str(row.total)) for row in rows}

    def get_sale_items_with_names(self, sale_id: UUID) -> list[dict]:
        """Carga los ítems de una venta con el nombre del producto.

        Realiza un JOIN entre ``sale_items`` y ``products`` para obtener
        el nombre vigente del producto (ON DELETE RESTRICT garantiza
        que el producto existe mientras haya ítems asociados).

        Args:
            sale_id: UUID de la venta.

        Returns:
            Lista de dicts con claves:
            ``product_name``, ``quantity``, ``price_at_sale``, ``subtotal``.
        """
        rows = self._session.execute(
            select(
                products_table.c.name.label("product_name"),
                sale_items_table.c.quantity,
                sale_items_table.c.price_at_sale,
            )
            .join(
                products_table,
                sale_items_table.c.product_id == products_table.c.id,
            )
            .where(sale_items_table.c.sale_id == str(sale_id))
            .order_by(sale_items_table.c.id)
        ).fetchall()

        return [
            {
                "product_name": row.product_name,
                "quantity": row.quantity,
                "price_at_sale": Decimal(str(row.price_at_sale)),
                "subtotal": Decimal(str(row.price_at_sale)) * row.quantity,
            }
            for row in rows
        ]
