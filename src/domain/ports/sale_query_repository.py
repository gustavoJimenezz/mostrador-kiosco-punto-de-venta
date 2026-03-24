"""Puerto de salida: consultas de historial de ventas (CQRS query side).

Separa las operaciones de lectura (reporting) del puerto de escritura
``SaleRepository``. Solo lo implementan adaptadores que soporten
consultas analíticas (MariaDB); los mocks de test solo implementan
lo necesario para cada caso de uso.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from src.domain.models.sale import Sale


@runtime_checkable
class SaleQueryRepository(Protocol):
    """Puerto de consulta de ventas para historial y reportes.

    Examples:
        >>> class MockQuery:
        ...     def list_by_date_range(self, s, e): return []
        ...     def get_daily_totals(self, d): return {}
        >>> isinstance(MockQuery(), SaleQueryRepository)
        True
    """

    def list_by_date_range(self, start: datetime, end: datetime) -> list[Sale]:
        """Lista ventas en el rango ``[start, end)``.

        Retorna entidades ``Sale`` con ``items=[]`` (sin ítems cargados)
        para eficiencia. Usar ``get_sale_items_display`` para el detalle.

        Args:
            start: Inicio del rango (inclusivo).
            end: Fin del rango (exclusivo).

        Returns:
            Lista de Sale ordenada por ``timestamp`` descendente.
        """
        ...

    def get_daily_totals(self, day: date) -> dict[str, Decimal]:
        """Retorna totales de ventas del día agrupados por método de pago.

        Args:
            day: Fecha a consultar.

        Returns:
            Diccionario ``{payment_method_value: total_amount}`` en Decimal.
            Solo incluye métodos con al menos una venta. Ejemplo::

                {"EFECTIVO": Decimal("12500.00"), "DEBITO": Decimal("3200.00")}
        """
        ...
