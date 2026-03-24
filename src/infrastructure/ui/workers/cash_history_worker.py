"""Worker QThread para el historial de cierres de caja."""

from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import QThread, Signal


class LoadCashHistoryWorker(QThread):
    """Carga el historial de arqueos de caja para un rango de fechas.

    Signals:
        closes_loaded (list): Emitida con la lista de CashClose.
        error_occurred (str): Mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        start: Fecha de inicio (inclusivo).
        end: Fecha de fin (inclusivo).
    """

    closes_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        start: date,
        end: date,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._start = start
        self._end = end

    def run(self) -> None:
        """Ejecuta la consulta de arqueos en el hilo separado."""
        session = self._session_factory()
        try:
            from src.application.use_cases.list_cash_closes import ListCashCloses
            from src.infrastructure.persistence.mariadb_cash_repository import (
                MariadbCashRepository,
            )

            repo = MariadbCashRepository(session)
            uc = ListCashCloses(repo)
            closes = uc.execute(self._start, self._end)
            self.closes_loaded.emit(closes)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()
