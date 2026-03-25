"""Adaptador de infraestructura: persistencia de arqueo de caja en MariaDB.

Implementa los puertos ``CashCloseRepository`` y ``CashMovementRepository``.
- ``CashClose`` se gestiona vía ORM (mapeo imperativo en ``mappings.py``).
- ``CashMovement`` se persiste vía Core SQL (no tiene mapeo ORM).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement
from src.infrastructure.persistence.tables import (
    cash_movements_table,
    products_table,
    sale_items_table,
    sales_table,
)


class MariadbCashRepository:
    """Repositorio MariaDB para arqueos de caja y movimientos manuales.

    Implementa ``CashCloseRepository`` y ``CashMovementRepository`` en una
    sola clase para compartir la sesión de DB en operaciones coordinadas.

    ``CashClose`` usa ORM (gracias al mapeo imperativo en ``mappings.py``).
    ``CashMovement`` usa Core SQL (mapeo imperativo no definido para esta entidad).

    Args:
        session: Sesión SQLAlchemy activa.

    Examples:
        >>> repo = MariadbCashRepository(session)
        >>> close = repo.get_open()
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # CashCloseRepository
    # ------------------------------------------------------------------

    def get_open(self) -> Optional[CashClose]:
        """Retorna el arqueo abierto actualmente (``closed_at IS NULL``).

        Returns:
            CashClose con ``closed_at=None``, o None si no existe ninguno.
        """
        return (
            self._session.query(CashClose)
            .filter(CashClose.closed_at == None)  # noqa: E711
            .order_by(CashClose.opened_at.desc())
            .first()
        )

    def save(self, cash_close: CashClose) -> CashClose:
        """Persiste (INSERT o UPDATE) el arqueo de caja.

        Si ``cash_close.id`` es None, realiza INSERT y asigna el id generado.
        Si ya tiene id, realiza UPDATE del registro existente.

        Args:
            cash_close: Entidad a persistir.

        Returns:
            La misma instancia con ``id`` asignado.
        """
        self._session.add(cash_close)
        self._session.commit()
        return cash_close

    # ------------------------------------------------------------------
    # CashMovementRepository
    # ------------------------------------------------------------------

    def save_movement(self, movement: CashMovement) -> CashMovement:
        """Persiste un movimiento manual de caja.

        Args:
            movement: Entidad CashMovement a insertar.

        Returns:
            CashMovement con ``id`` asignado por la DB.
        """
        result = self._session.execute(
            cash_movements_table.insert().values(
                cash_close_id=movement.cash_close_id,
                amount=movement.amount,
                description=movement.description,
                created_at=movement.created_at,
            )
        )
        self._session.commit()
        movement.id = result.lastrowid
        return movement

    def list_movements(self, cash_close_id: int) -> list[CashMovement]:
        """Lista todos los movimientos de un arqueo de caja.

        Args:
            cash_close_id: ID del arqueo a consultar.

        Returns:
            Lista de CashMovement ordenada por ``created_at`` ascendente.
        """
        rows = self._session.execute(
            cash_movements_table.select()
            .where(cash_movements_table.c.cash_close_id == cash_close_id)
            .order_by(cash_movements_table.c.created_at)
        ).fetchall()

        return [
            CashMovement(
                id=row.id,
                cash_close_id=row.cash_close_id,
                amount=row.amount,
                description=row.description,
                created_at=row.created_at,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Puerto CashMovementRepository — alias para compatibilidad con Protocol
    # ------------------------------------------------------------------

    def save(self, obj):  # type: ignore[override]
        """Delegación: persiste CashClose o CashMovement según el tipo.

        Satisface tanto ``CashCloseRepository`` como ``CashMovementRepository``.

        Args:
            obj: Instancia de CashClose o CashMovement a persistir.

        Returns:
            La misma instancia con ``id`` asignado.

        Raises:
            TypeError: Si el tipo no es CashClose ni CashMovement.
        """
        if isinstance(obj, CashClose):
            return self._save_cash_close(obj)
        if isinstance(obj, CashMovement):
            return self.save_movement(obj)
        raise TypeError(f"Tipo no soportado por save(): {type(obj)}")

    def _save_cash_close(self, cash_close: CashClose) -> CashClose:
        self._session.add(cash_close)
        self._session.commit()
        self._session.refresh(cash_close)
        return cash_close

    def list_by_cash_close(self, cash_close_id: int) -> list[CashMovement]:
        """Alias de ``list_movements`` para satisfacer ``CashMovementRepository``."""
        return self.list_movements(cash_close_id)

    def list_by_date_range(self, start: date, end: date) -> list[CashClose]:
        """Lista los arqueos cuya apertura cae dentro del rango de fechas.

        Args:
            start: Fecha de inicio (inclusivo).
            end: Fecha de fin (inclusivo).

        Returns:
            Lista de CashClose ordenada por ``opened_at`` descendente.
        """
        dt_start = datetime.combine(start, datetime.min.time())
        dt_end = datetime.combine(end, datetime.max.time())
        return (
            self._session.query(CashClose)
            .filter(CashClose.opened_at.between(dt_start, dt_end))
            .order_by(CashClose.opened_at.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Reporting: totales de ventas del día (sin pre-acumulación)
    # ------------------------------------------------------------------

    def get_sales_totals_for_session(self, cash_close_id: int) -> dict[str, Decimal]:
        """Computa los totales de ventas agrupados por método de pago para un arqueo.

        Filtra la tabla ``sales`` por ``cash_close_id`` para obtener únicamente
        las ventas vinculadas a la sesión activa, no al día completo.

        Args:
            cash_close_id: ID del arqueo de caja a consultar.

        Returns:
            Diccionario ``{payment_method_value: total_amount}``. Solo incluye
            métodos con al menos una venta. Ejemplo::

                {"EFECTIVO": Decimal("12500.00"), "DEBITO": Decimal("3200.00")}
        """
        from sqlalchemy import func, select

        rows = self._session.execute(
            select(
                sales_table.c.payment_method,
                func.sum(sales_table.c.total_amount).label("total"),
            )
            .where(sales_table.c.cash_close_id == cash_close_id)
            .group_by(sales_table.c.payment_method)
        ).fetchall()

        return {row.payment_method: Decimal(str(row.total)) for row in rows}

    def get_profit_data_for_session(self, cash_close_id: int) -> dict:
        """Calcula ganancia bruta estimada para un arqueo de caja.

        Realiza JOIN entre sales → sale_items → products filtrando por
        ``cash_close_id``. El costo se toma de ``products.current_cost``
        (valor actual, aproximación aceptable para kioscos).

        Args:
            cash_close_id: ID del arqueo de caja a analizar.

        Returns:
            Diccionario con claves:
            ``total_revenue``, ``total_cost_estimate``, ``gross_profit``,
            ``margin_percent``, ``total_sales_count``.
        """
        from decimal import ROUND_HALF_UP
        from sqlalchemy import func, select

        row = self._session.execute(
            select(
                func.coalesce(
                    func.sum(sale_items_table.c.price_at_sale * sale_items_table.c.quantity),
                    0,
                ).label("total_revenue"),
                func.coalesce(
                    func.sum(products_table.c.current_cost * sale_items_table.c.quantity),
                    0,
                ).label("total_cost"),
                func.count(func.distinct(sales_table.c.id)).label("total_sales_count"),
            )
            .select_from(sale_items_table)
            .join(sales_table, sale_items_table.c.sale_id == sales_table.c.id)
            .join(products_table, sale_items_table.c.product_id == products_table.c.id)
            .where(sales_table.c.cash_close_id == cash_close_id)
        ).fetchone()

        revenue = Decimal(str(row.total_revenue))
        cost = Decimal(str(row.total_cost))
        profit = revenue - cost
        if revenue > Decimal("0"):
            margin = (profit / revenue * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            margin = Decimal("0.00")

        return {
            "total_revenue": revenue,
            "total_cost_estimate": cost,
            "gross_profit": profit,
            "margin_percent": margin,
            "total_sales_count": row.total_sales_count,
        }

    def get_movements_totals_by_close_ids(
        self, close_ids: list[int]
    ) -> dict[int, Decimal]:
        """Retorna la suma neta de movimientos manuales para cada arqueo indicado.

        Realiza una sola query agrupada para evitar N+1 al cargar el historial.

        Args:
            close_ids: Lista de IDs de arqueos a consultar.

        Returns:
            Diccionario ``{cash_close_id: suma_neta}``. Los arqueos sin
            movimientos no aparecen (usar ``.get(id, Decimal("0"))``).
        """
        if not close_ids:
            return {}

        from sqlalchemy import func, select

        rows = self._session.execute(
            select(
                cash_movements_table.c.cash_close_id,
                func.sum(cash_movements_table.c.amount).label("total"),
            )
            .where(cash_movements_table.c.cash_close_id.in_(close_ids))
            .group_by(cash_movements_table.c.cash_close_id)
        ).fetchall()

        return {row.cash_close_id: Decimal(str(row.total)) for row in rows}

    def get_sales_totals_for_date(self, day: date) -> dict[str, Decimal]:
        """Computa los totales de ventas del día agrupados por método de pago.

        Consulta la tabla ``sales`` directamente (sin depender de los campos
        pre-acumulados de ``cash_closes``) para garantizar consistencia aunque
        las ventas no tengan ``cash_close_id`` asignado.

        Args:
            day: Fecha a consultar.

        Returns:
            Diccionario ``{payment_method_value: total_amount}``. Solo incluye
            métodos con al menos una venta del día. Ejemplo::

                {"EFECTIVO": Decimal("12500.00"), "DEBITO": Decimal("3200.00")}
        """
        from sqlalchemy import func, select

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
