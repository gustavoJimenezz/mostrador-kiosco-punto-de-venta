"""Caso de uso: listar ventas por rango de fechas.

Provee el historial de ventas para la vista de consulta (F2).
Retorna entidades ``Sale`` sin ítems cargados; los ítems se obtienen
bajo demanda al seleccionar una venta en la vista.
"""

from __future__ import annotations

from datetime import datetime

from src.domain.models.sale import Sale
from src.domain.ports.sale_query_repository import SaleQueryRepository


class ListSales:
    """Lista las ventas registradas en un rango de fechas.

    Diseñado para la vista de historial (F2). Las ventas se retornan
    sin sus ítems para eficiencia; cargar el detalle de una venta
    específica es responsabilidad de la vista/presenter.

    Args:
        sale_query_repo: Repositorio de consulta de ventas.

    Examples:
        >>> uc = ListSales(repo)
        >>> sales = uc.execute(start=datetime(2026, 3, 1), end=datetime(2026, 3, 31))
        >>> isinstance(sales, list)
        True
    """

    def __init__(self, sale_query_repo: SaleQueryRepository) -> None:
        self._repo = sale_query_repo

    def execute(self, start: datetime, end: datetime) -> list[Sale]:
        """Retorna las ventas en el rango ``[start, end)``.

        Args:
            start: Fecha/hora de inicio (inclusivo).
            end: Fecha/hora de fin (exclusivo).

        Returns:
            Lista de Sale ordenada por timestamp descendente,
            con ``items=[]`` (sin ítems cargados).

        Raises:
            ValueError: Si ``start >= end``.
        """
        if start >= end:
            raise ValueError(
                f"El inicio del rango debe ser anterior al fin: {start} >= {end}"
            )
        return self._repo.list_by_date_range(start, end)
