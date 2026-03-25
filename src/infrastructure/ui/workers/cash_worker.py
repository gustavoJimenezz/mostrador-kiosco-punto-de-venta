"""Workers QThread para operaciones de arqueo de caja.

Evitan bloquear el hilo principal de Qt durante consultas y escrituras
relacionadas con la sesión de caja y los movimientos manuales.

Workers disponibles:
    LoadCashStateWorker  — carga el estado actual del arqueo (sesión + movimientos + totales).
    LoadCashReportWorker — carga el informe detallado previo al cierre (rentabilidad + conciliación).
    OpenCashCloseWorker  — abre un nuevo arqueo o retorna el existente.
    CloseCashCloseWorker — cierra el arqueo activo con el monto contado y datos de ganancia.
    AddMovementWorker    — registra un movimiento manual (ingreso o egreso).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement


class LoadCashStateWorker(QThread):
    """Carga el estado completo del arqueo activo: sesión, movimientos y totales.

    Signals:
        state_loaded (dict): Emitida con el estado del arqueo::

            {
                "cash_close": CashClose | None,
                "movements": list[CashMovement],
                "sales_totals": dict[str, Decimal],   # {método: total}
            }

        error_occurred (str): Mensaje de error si falla la consulta.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        day: Fecha para calcular los totales de ventas.
    """

    state_loaded = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory

    def run(self) -> None:
        """Carga el arqueo activo, sus movimientos y los totales de la sesión."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_cash_repository import (
                MariadbCashRepository,
            )

            repo = MariadbCashRepository(session)
            cash_close = repo.get_open()
            movements = repo.list_movements(cash_close.id) if cash_close else []
            totals = (
                {
                    "EFECTIVO": cash_close.total_sales_cash,
                    "DEBITO": cash_close.total_sales_debit,
                    "TRANSFERENCIA": cash_close.total_sales_transfer,
                }
                if cash_close
                else {}
            )

            self.state_loaded.emit(
                {
                    "cash_close": cash_close,
                    "movements": movements,
                    "sales_totals": totals,
                }
            )
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class LoadCashReportWorker(QThread):
    """Carga el informe de cierre para previsualización antes de confirmar el arqueo.

    Consulta en paralelo los movimientos manuales, los totales de ventas por
    método de pago y los datos de rentabilidad (ganancia bruta estimada).
    Se lanza desde ``CashCloseView`` al presionar "Cerrar caja" y antes de
    mostrar el diálogo de confirmación de cierre.

    Signals:
        report_ready (dict): Emitida con todos los datos del informe::

            {
                "cash_close": CashClose,          # arqueo activo
                "closing_amount": Decimal,        # monto ingresado por el cajero
                "movements": list[CashMovement],  # movimientos manuales del período
                "sales_totals": dict[str, Decimal],
                "profit": {
                    "total_revenue": Decimal,
                    "total_cost_estimate": Decimal,
                    "gross_profit": Decimal,
                    "margin_percent": Decimal,
                    "total_sales_count": int,
                },
            }

        error_occurred (str): Mensaje de error si falla alguna consulta.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        cash_close_id: ID del arqueo abierto actualmente.
        closing_amount: Monto contado físicamente (ingresado por el cajero).
    """

    report_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        cash_close_id: int,
        closing_amount: Decimal,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._cash_close_id = cash_close_id
        self._closing_amount = closing_amount

    def run(self) -> None:
        """Carga datos de rentabilidad, movimientos y totales de ventas."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_cash_repository import (
                MariadbCashRepository,
            )

            repo = MariadbCashRepository(session)
            cash_close = repo.get_open()
            movements = repo.list_movements(self._cash_close_id)
            profit_data = repo.get_profit_data_for_session(self._cash_close_id)
            totals = (
                {
                    "EFECTIVO": cash_close.total_sales_cash,
                    "DEBITO": cash_close.total_sales_debit,
                    "TRANSFERENCIA": cash_close.total_sales_transfer,
                }
                if cash_close
                else {}
            )

            self.report_ready.emit(
                {
                    "cash_close": cash_close,
                    "closing_amount": self._closing_amount,
                    "movements": movements,
                    "sales_totals": totals,
                    "profit": profit_data,
                }
            )
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class OpenCashCloseWorker(QThread):
    """Abre un arqueo de caja (o retorna el existente si ya hay uno abierto).

    Signals:
        opened (CashClose): Emitida con el arqueo activo.
        error_occurred (str): Mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        opening_amount: Fondo inicial de caja (solo si se crea uno nuevo).
    """

    opened = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        opening_amount: Decimal,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._opening_amount = opening_amount

    def run(self) -> None:
        """Ejecuta GetOrOpenCashClose en el hilo separado."""
        session = self._session_factory()
        try:
            from src.application.use_cases.get_or_open_cash_close import (
                GetOrOpenCashClose,
            )
            from src.infrastructure.persistence.mariadb_cash_repository import (
                MariadbCashRepository,
            )

            repo = MariadbCashRepository(session)
            uc = GetOrOpenCashClose(repo)
            cash_close = uc.execute(opening_amount=self._opening_amount)
            self.opened.emit(cash_close)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class CloseCashCloseWorker(QThread):
    """Cierra el arqueo activo con el monto físico contado y datos de rentabilidad.

    Signals:
        closed (CashClose): Emitida con el arqueo cerrado.
        error_occurred (str): Mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        closing_amount: Monto contado físicamente al cierre.
        gross_profit_estimate: Ganancia bruta estimada del período (opcional).
        total_cost_estimate: Costo de mercadería vendida estimado (opcional).
    """

    closed = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        closing_amount: Decimal,
        gross_profit_estimate: Optional[Decimal] = None,
        total_cost_estimate: Optional[Decimal] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._closing_amount = closing_amount
        self._gross_profit_estimate = gross_profit_estimate
        self._total_cost_estimate = total_cost_estimate

    def run(self) -> None:
        """Ejecuta CloseCashClose en el hilo separado."""
        session = self._session_factory()
        try:
            from src.application.use_cases.close_cash_close import CloseCashClose
            from src.infrastructure.persistence.mariadb_cash_repository import (
                MariadbCashRepository,
            )

            repo = MariadbCashRepository(session)
            uc = CloseCashClose(repo)
            cash_close = uc.execute(
                closing_amount=self._closing_amount,
                gross_profit_estimate=self._gross_profit_estimate,
                total_cost_estimate=self._total_cost_estimate,
            )
            self.closed.emit(cash_close)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class AddMovementWorker(QThread):
    """Registra un movimiento manual de caja (ingreso o egreso).

    Signals:
        movement_added (CashMovement): Emitida con el movimiento persistido.
        error_occurred (str): Mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        cash_close_id: ID del arqueo activo.
        amount: Monto del movimiento (positivo = ingreso, negativo = egreso).
        description: Texto descriptivo.
    """

    movement_added = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        cash_close_id: int,
        amount: Decimal,
        description: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._cash_close_id = cash_close_id
        self._amount = amount
        self._description = description

    def run(self) -> None:
        """Ejecuta AddCashMovement en el hilo separado."""
        session = self._session_factory()
        try:
            from src.application.use_cases.add_cash_movement import AddCashMovement
            from src.infrastructure.persistence.mariadb_cash_repository import (
                MariadbCashRepository,
            )

            repo = MariadbCashRepository(session)
            uc = AddCashMovement(repo)
            movement = uc.execute(
                cash_close_id=self._cash_close_id,
                amount=self._amount,
                description=self._description,
            )
            self.movement_added.emit(movement)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()
