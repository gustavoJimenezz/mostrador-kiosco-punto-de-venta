"""Vista de arqueo de caja (pestaña QWidget, F10).

Vive dentro del QTabWidget de MainWindow como tab "Cierre de Caja (F10)".
Layout construido por código (sin .ui file).

Layout:
    QVBoxLayout raíz
    ├── QGroupBox "Sesión de caja"
    │   ├── QLabel _lbl_status
    │   ├── QHBoxLayout: QLabel "Monto inicial ($):" · QDoubleSpinBox · QPushButton "Abrir caja"
    ├── QGroupBox "Ventas del día"
    │   ├── QLabel _lbl_sales_cash
    │   ├── QLabel _lbl_sales_debit
    │   ├── QLabel _lbl_sales_transfer
    │   └── QLabel _lbl_total_sales (bold, destacado)
    ├── QGroupBox "Movimientos manuales"
    │   ├── QTableWidget _movements_table (Hora · Descripción · Monto)
    │   └── QHBoxLayout: QLineEdit _input_desc · QDoubleSpinBox _spin_amount
    │       · QPushButton "Ingreso" · QPushButton "Egreso"
    ├── QGroupBox "Cierre"
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
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement


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
        self._active_cash_close_id = cash_close.id
        hora = cash_close.opened_at.strftime("%H:%M")
        self._lbl_status.setText(
            f"✓ Sesión abierta desde las {hora}  "
            f"(monto inicial: ${cash_close.opening_amount:,.2f})"
        )
        self._lbl_status.setStyleSheet("color: #059669; font-weight: bold;")
        self._btn_close.setEnabled(True)
        self._btn_income.setEnabled(True)
        self._btn_expense.setEnabled(True)
        if self._session_changed_callback:
            self._session_changed_callback(True)

    def show_session_closed(self) -> None:
        """Actualiza los widgets para mostrar que no hay sesión activa."""
        self._active_cash_close_id = None
        self._lbl_status.setText("No hay caja abierta. Abrila desde el botón superior.")
        self._lbl_status.setStyleSheet("color: #6b7280;")
        self._btn_close.setEnabled(False)
        self._btn_income.setEnabled(False)
        self._btn_expense.setEnabled(False)
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

    def show_movements(self, movements: list[CashMovement]) -> None:
        """Actualiza la tabla de movimientos manuales."""
        from PySide6.QtGui import QColor

        self._movements_table.setRowCount(0)
        for mov in movements:
            row = self._movements_table.rowCount()
            self._movements_table.insertRow(row)
            hora = mov.created_at.strftime("%H:%M")
            color = "#059669" if mov.is_income else "#dc2626"
            signo = "+" if mov.is_income else "-"
            monto_str = f"{signo}${abs(mov.amount):,.2f}"

            self._movements_table.setItem(row, 0, QTableWidgetItem(hora))
            self._movements_table.setItem(row, 1, QTableWidgetItem(mov.description))
            monto_item = QTableWidgetItem(monto_str)
            monto_item.setForeground(QColor(color))
            self._movements_table.setItem(row, 2, monto_item)

    def show_close_result(self, difference: Optional[Decimal]) -> None:
        """Muestra la diferencia (sobrante/faltante) al cerrar la caja."""
        if difference is None:
            self._lbl_difference.setText("")
            return
        if difference >= Decimal("0"):
            self._lbl_difference.setText(
                f"Sobrante: ${difference:,.2f}"
            )
            self._lbl_difference.setStyleSheet("color: #059669; font-weight: bold;")
        else:
            self._lbl_difference.setText(
                f"Faltante: ${abs(difference):,.2f}"
            )
            self._lbl_difference.setStyleSheet("color: #dc2626; font-weight: bold;")

    def show_error(self, message: str) -> None:
        """Muestra mensaje de error en el label de estado."""
        self._status_label.setText(f"⚠ {message}")
        self._status_label.setStyleSheet("color: #dc2626;")

    def show_success(self, message: str) -> None:
        """Muestra mensaje de éxito en el label de estado."""
        self._status_label.setText(f"✓ {message}")
        self._status_label.setStyleSheet("color: #059669;")

    # ------------------------------------------------------------------
    # Handlers Qt
    # ------------------------------------------------------------------

    def _on_close_clicked(self) -> None:
        """Cierra la sesión de caja con el monto contado."""
        if not self._presenter:
            return
        amount = Decimal(str(self._spin_closing.value()))
        if not self._presenter.on_close_session_requested(amount):
            return

        from src.infrastructure.ui.workers.cash_worker import CloseCashCloseWorker

        worker = CloseCashCloseWorker(self._session_factory, amount)
        worker.closed.connect(self._presenter.on_session_closed)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_add_movement(self, is_income: bool) -> None:
        """Registra un movimiento manual (ingreso o egreso).

        Args:
            is_income: True para ingreso (monto positivo), False para egreso (negativo).
        """
        if not self._presenter:
            return
        raw_amount = Decimal(str(self._spin_movement.value()))
        signed_amount = raw_amount if is_income else -raw_amount
        description = self._input_desc.text().strip()

        if not self._presenter.on_add_movement_requested(signed_amount, description):
            return

        cash_close_id = self._presenter.get_active_cash_close_id()
        if cash_close_id is None:
            return

        from src.infrastructure.ui.workers.cash_worker import AddMovementWorker

        worker = AddMovementWorker(
            self._session_factory,
            cash_close_id,
            signed_amount,
            description,
        )
        worker.movement_added.connect(self._presenter.on_movement_added)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()
        self._input_desc.clear()
        self._spin_movement.setValue(0.0)

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

        self._lbl_status = QLabel("Sin sesión activa.")
        self._lbl_status.setStyleSheet("color: #6b7280;")
        v_session.addWidget(self._lbl_status)
        root.addWidget(grp_session)

        # --- Ventas del día ----------------------------------------
        grp_sales = QGroupBox("Ventas del día")
        v_sales = QVBoxLayout(grp_sales)
        font_mono = "font-family: monospace;"

        self._lbl_sales_cash = QLabel("Efectivo:        $        0,00")
        self._lbl_sales_cash.setStyleSheet(font_mono)
        self._lbl_sales_debit = QLabel("Débito:          $        0,00")
        self._lbl_sales_debit.setStyleSheet(font_mono)
        self._lbl_sales_transfer = QLabel("Transferencia:   $        0,00")
        self._lbl_sales_transfer.setStyleSheet(font_mono)
        self._lbl_total_sales = QLabel("TOTAL VENTAS:    $        0,00")
        self._lbl_total_sales.setStyleSheet(
            f"{font_mono} font-weight: bold; font-size: 14px;"
        )
        for lbl in (
            self._lbl_sales_cash,
            self._lbl_sales_debit,
            self._lbl_sales_transfer,
            self._lbl_total_sales,
        ):
            v_sales.addWidget(lbl)
        root.addWidget(grp_sales)

        # --- Movimientos manuales ----------------------------------
        grp_movements = QGroupBox("Movimientos manuales")
        v_mov = QVBoxLayout(grp_movements)

        self._movements_table = QTableWidget(0, 3)
        self._movements_table.setHorizontalHeaderLabels(
            ["Hora", "Descripción", "Monto"]
        )
        self._movements_table.horizontalHeader().setStretchLastSection(True)
        self._movements_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._movements_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._movements_table.setFixedHeight(130)
        v_mov.addWidget(self._movements_table)

        row_mov = QHBoxLayout()
        self._input_desc = QLineEdit()
        self._input_desc.setPlaceholderText("Descripción del movimiento...")
        row_mov.addWidget(self._input_desc, stretch=3)
        self._spin_movement = QDoubleSpinBox()
        self._spin_movement.setRange(0.01, 999999.99)
        self._spin_movement.setDecimals(2)
        self._spin_movement.setSingleStep(100)
        row_mov.addWidget(self._spin_movement, stretch=1)
        self._btn_income = QPushButton("+ Ingreso")
        self._btn_income.setStyleSheet("background-color: #059669; color: white;")
        self._btn_income.clicked.connect(
            lambda: self._on_add_movement(is_income=True)
        )
        self._btn_expense = QPushButton("− Egreso")
        self._btn_expense.setStyleSheet("background-color: #dc2626; color: white;")
        self._btn_expense.clicked.connect(
            lambda: self._on_add_movement(is_income=False)
        )
        row_mov.addWidget(self._btn_income)
        row_mov.addWidget(self._btn_expense)
        v_mov.addLayout(row_mov)
        root.addWidget(grp_movements)

        # --- Cierre -----------------------------------------------
        grp_close = QGroupBox("Cierre de caja")
        v_close = QVBoxLayout(grp_close)

        row_close = QHBoxLayout()
        row_close.addWidget(QLabel("Monto contado ($):"))
        self._spin_closing = QDoubleSpinBox()
        self._spin_closing.setRange(0, 9999999.99)
        self._spin_closing.setDecimals(2)
        self._spin_closing.setSingleStep(100)
        row_close.addWidget(self._spin_closing)
        self._btn_close = QPushButton("Cerrar caja")
        self._btn_close.setStyleSheet("background-color: #4f46e5; color: white;")
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
