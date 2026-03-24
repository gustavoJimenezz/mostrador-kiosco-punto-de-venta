"""Workers QThread para el historial de ventas.

Workers disponibles:
    LoadSalesWorker      — carga ventas de un rango de fechas.
    LoadSaleDetailWorker — carga los ítems con nombres de una venta.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from PySide6.QtCore import QThread, Signal

from src.domain.models.sale import Sale


class LoadSalesWorker(QThread):
    """Carga el listado de ventas para un rango de fechas.

    Signals:
        sales_loaded (list): Emitida con la lista de Sale (sin ítems cargados).
        error_occurred (str): Mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        start: Fecha/hora de inicio (inclusivo).
        end: Fecha/hora de fin (exclusivo).
    """

    sales_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        start: datetime,
        end: datetime,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._start = start
        self._end = end

    def run(self) -> None:
        """Ejecuta la consulta de ventas en el hilo separado."""
        session = self._session_factory()
        try:
            from src.application.use_cases.list_sales import ListSales
            from src.infrastructure.persistence.mariadb_sale_repository import (
                MariadbSaleRepository,
            )

            repo = MariadbSaleRepository(session)
            uc = ListSales(repo)
            sales = uc.execute(self._start, self._end)
            self.sales_loaded.emit(sales)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class LoadSaleDetailWorker(QThread):
    """Carga los ítems de una venta con nombre de producto para el panel de detalle.

    Signals:
        detail_loaded (list): Lista de dicts con
            ``product_name``, ``quantity``, ``price_at_sale``, ``subtotal``.
        error_occurred (str): Mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        sale_id: UUID de la venta a detallar.
    """

    detail_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        sale_id: UUID,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._sale_id = sale_id

    def run(self) -> None:
        """Carga los ítems de la venta en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_sale_repository import (
                MariadbSaleRepository,
            )

            repo = MariadbSaleRepository(session)
            items = repo.get_sale_items_with_names(self._sale_id)
            self.detail_loaded.emit(items)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()
