"""Vista de arqueo de caja (diálogo modal F10).

Muestra el resumen de la sesión activa y permite realizar el cierre.
Los movimientos manuales se gestionan desde la pestaña "Movimientos".
Layout construido por código (sin .ui file).

Layout:
    QVBoxLayout raíz
    ├── QGroupBox "Sesión de caja"
    │   └── QLabel _lbl_status
    ├── QGroupBox "Ventas del día"
    │   ├── QLabel _lbl_sales_cash
    │   ├── QLabel _lbl_sales_debit
    │   ├── QLabel _lbl_sales_transfer
    │   └── QLabel _lbl_total_sales (bold, destacado)
    ├── QGroupBox "Cierre de caja"
    │   ├── QLabel _lbl_movements_total
    │   ├── QHBoxLayout: QLabel "Monto contado ($):" · QDoubleSpinBox · QPushButton "Cerrar caja"
    │   └── QLabel _lbl_difference
    └── QLabel _status_label
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.cash_close import CashClose


class CashCloseView(QWidget):
    """Vista de gestión del arqueo de caja diario (pestaña F10).

    Implementa ICashView. Toda la lógica de negocio está delegada al
    CashPresenter. Esta clase solo gestiona Qt.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._presenter = None
        self._active_workers: list = []
        self._active_cash_close_id: Optional[int] = None
        self._session_changed_callback: Optional[Callable[[bool], None]] = None
        self._build_ui()

    def set_presenter(self, presenter) -> None:
        """Inyecta el CashPresenter.

        Args:
            presenter: CashPresenter configurado con esta vista.
        """
        self._presenter = presenter

    def set_session_changed_callback(self, callback: Callable[[bool], None]) -> None:
        """Registra un callback que se invoca al cambiar el estado de la sesión de caja.

        Args:
            callback: Función que recibe True cuando la caja se abre y False cuando se cierra.
        """
        self._session_changed_callback = callback

    def on_view_activated(self) -> None:
        """Recarga el estado del arqueo al navegar a esta pestaña."""
        self._load_state()

    # ------------------------------------------------------------------
    # ICashView implementation
    # ------------------------------------------------------------------

    def show_session_open(self, cash_close: CashClose) -> None:
        """Actualiza los widgets para mostrar sesión abierta."""
        from src.infrastructure.ui.theme import SUCCESS_COLOR

        self._active_cash_close_id = cash_close.id
        hora = cash_close.opened_at.strftime("%H:%M")
        self._lbl_status.setText(
            f"✓ Sesión abierta desde las {hora}  "
            f"(monto inicial: ${cash_close.opening_amount:,.2f})"
        )
        self._lbl_status.setStyleSheet(f"color: {SUCCESS_COLOR}; font-weight: bold;")
        self._btn_close.setEnabled(True)
        if self._session_changed_callback:
            self._session_changed_callback(True)

    def show_session_closed(self) -> None:
        """Actualiza los widgets para mostrar que no hay sesión activa."""
        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        self._active_cash_close_id = None
        self._lbl_status.setText("No hay caja abierta. Abrila desde el botón superior.")
        self._lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY_COLOR};")
        self._btn_close.setEnabled(False)
        self._lbl_difference.setText("")
        if self._session_changed_callback:
            self._session_changed_callback(False)

    def show_sales_summary(
        self,
        cash: Decimal,
        debit: Decimal,
        transfer: Decimal,
    ) -> None:
        """Actualiza los labels de ventas del día."""
        self._lbl_sales_cash.setText(f"Efectivo:        ${cash:>12,.2f}")
        self._lbl_sales_debit.setText(f"Débito:          ${debit:>12,.2f}")
        self._lbl_sales_transfer.setText(f"Transferencia:   ${transfer:>12,.2f}")
        total = cash + debit + transfer
        self._lbl_total_sales.setText(f"TOTAL VENTAS:    ${total:>12,.2f}")

    def show_movements_total(self, total: Decimal) -> None:
        """Muestra el total neto de movimientos manuales de la sesión.

        Args:
            total: Suma neta (positivo = ingresos netos, negativo = egresos netos).
        """
        from src.infrastructure.ui.theme import DANGER_COLOR, SUCCESS_COLOR, TEXT_SECONDARY_COLOR

        if total > Decimal("0"):
            texto = f"Movimientos manuales: +${total:,.2f}"
            color = SUCCESS_COLOR
        elif total < Decimal("0"):
            texto = f"Movimientos manuales: -${abs(total):,.2f}"
            color = DANGER_COLOR
        else:
            texto = "Movimientos manuales: $0,00"
            color = TEXT_SECONDARY_COLOR
        self._lbl_movements_total.setText(texto)
        self._lbl_movements_total.setStyleSheet(
            f"font-family: monospace; color: {color};"
        )

    def show_close_result(self, difference: Optional[Decimal]) -> None:
        """Muestra la diferencia (sobrante/faltante) al cerrar la caja."""
        from src.infrastructure.ui.theme import DANGER_COLOR, SUCCESS_COLOR

        if difference is None:
            self._lbl_difference.setText("")
            return
        if difference >= Decimal("0"):
            self._lbl_difference.setText(
                f"Sobrante: ${difference:,.2f}"
            )
            self._lbl_difference.setStyleSheet(f"color: {SUCCESS_COLOR}; font-weight: bold;")
        else:
            self._lbl_difference.setText(
                f"Faltante: ${abs(difference):,.2f}"
            )
            self._lbl_difference.setStyleSheet(f"color: {DANGER_COLOR}; font-weight: bold;")

    def show_error(self, message: str) -> None:
        """Muestra mensaje de error en el label de estado."""
        from src.infrastructure.ui.theme import DANGER_COLOR

        self._status_label.setText(f"⚠ {message}")
        self._status_label.setStyleSheet(f"color: {DANGER_COLOR};")

    def show_success(self, message: str) -> None:
        """Muestra mensaje de éxito en el label de estado."""
        from src.infrastructure.ui.theme import SUCCESS_COLOR

        self._status_label.setText(f"✓ {message}")
        self._status_label.setStyleSheet(f"color: {SUCCESS_COLOR};")

    # ------------------------------------------------------------------
    # Handlers Qt
    # ------------------------------------------------------------------

    def _on_close_clicked(self) -> None:
        """Inicia el flujo de cierre: carga el informe y muestra el diálogo de confirmación."""
        if not self._presenter:
            return
        amount = Decimal(str(self._spin_closing.value()))
        if not self._presenter.on_close_session_requested(amount):
            return

        cash_close_id = self._presenter.get_active_cash_close_id()
        if cash_close_id is None:
            return

        from src.infrastructure.ui.workers.cash_worker import LoadCashReportWorker

        worker = LoadCashReportWorker(self._session_factory, cash_close_id, amount)
        worker.report_ready.connect(self._on_report_ready)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_report_ready(self, report_data: dict) -> None:
        """Muestra el diálogo de informe y ejecuta el cierre si el usuario confirma.

        Args:
            report_data: Datos del informe emitidos por ``LoadCashReportWorker``.
        """
        from PySide6.QtWidgets import QDialog

        from src.infrastructure.ui.dialogs.cash_close_report_dialog import (
            CashCloseReportDialog,
        )

        cash_close = report_data.get("cash_close")
        if cash_close is None:
            self._presenter.on_worker_error("No se pudo cargar el informe de cierre.")
            return

        dialog = CashCloseReportDialog(cash_close, report_data, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Usuario confirmó: lanzar el worker de cierre con datos de ganancia
        profit = report_data.get("profit", {})
        from src.infrastructure.ui.workers.cash_worker import CloseCashCloseWorker

        worker = CloseCashCloseWorker(
            self._session_factory,
            report_data["closing_amount"],
            gross_profit_estimate=profit.get("gross_profit"),
            total_cost_estimate=profit.get("total_cost_estimate"),
        )
        worker.closed.connect(self._presenter.on_session_closed)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout de la vista por código."""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # --- Sesión ------------------------------------------------
        grp_session = QGroupBox("Sesión de caja")
        v_session = QVBoxLayout(grp_session)

        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        self._lbl_status = QLabel("Sin sesión activa.")
        self._lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY_COLOR};")
        v_session.addWidget(self._lbl_status)
        root.addWidget(grp_session)

        # --- Ventas del día ----------------------------------------
        grp_sales = QGroupBox("Ventas del día")
        v_sales = QVBoxLayout(grp_sales)
        _mono = "font-family: monospace;"

        self._lbl_sales_cash = QLabel("Efectivo:        $        0,00")
        self._lbl_sales_cash.setStyleSheet(_mono)
        self._lbl_sales_debit = QLabel("Débito:          $        0,00")
        self._lbl_sales_debit.setStyleSheet(_mono)
        self._lbl_sales_transfer = QLabel("Transferencia:   $        0,00")
        self._lbl_sales_transfer.setStyleSheet(_mono)
        self._lbl_total_sales = QLabel("TOTAL VENTAS:    $        0,00")
        self._lbl_total_sales.setStyleSheet(
            f"{_mono} font-weight: bold; font-size: 14px;"
        )
        for lbl in (
            self._lbl_sales_cash,
            self._lbl_sales_debit,
            self._lbl_sales_transfer,
            self._lbl_total_sales,
        ):
            v_sales.addWidget(lbl)
        root.addWidget(grp_sales)

        # --- Cierre -----------------------------------------------
        grp_close = QGroupBox("Cierre de caja")
        v_close = QVBoxLayout(grp_close)

        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        self._lbl_movements_total = QLabel("Movimientos manuales: $0,00")
        self._lbl_movements_total.setStyleSheet(
            f"font-family: monospace; color: {TEXT_SECONDARY_COLOR};"
        )
        v_close.addWidget(self._lbl_movements_total)

        row_close = QHBoxLayout()
        row_close.addWidget(QLabel("Monto contado ($):"))
        self._spin_closing = QDoubleSpinBox()
        self._spin_closing.setRange(0, 9999999.99)
        self._spin_closing.setDecimals(2)
        self._spin_closing.setSingleStep(100)
        row_close.addWidget(self._spin_closing)
        from src.infrastructure.ui.theme import get_btn_primary_stylesheet

        self._btn_close = QPushButton("Cerrar caja")
        self._btn_close.setStyleSheet(get_btn_primary_stylesheet())
        self._btn_close.clicked.connect(self._on_close_clicked)
        row_close.addWidget(self._btn_close)
        row_close.addStretch()
        v_close.addLayout(row_close)

        self._lbl_difference = QLabel("")
        self._lbl_difference.setAlignment(Qt.AlignmentFlag.AlignRight)
        v_close.addWidget(self._lbl_difference)
        root.addWidget(grp_close)

        # --- Estado -----------------------------------------------
        self._status_label = QLabel("")
        root.addWidget(self._status_label)
        root.addStretch()

        # Estado inicial: sin sesión
        self.show_session_closed()

    def _load_state(self) -> None:
        """Lanza el worker para cargar el estado actual del arqueo."""
        from src.infrastructure.ui.workers.cash_worker import LoadCashStateWorker

        worker = LoadCashStateWorker(self._session_factory)
        if self._presenter:
            worker.state_loaded.connect(self._presenter.on_state_loaded)
            worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
