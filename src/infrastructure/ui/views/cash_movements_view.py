"""Vista de movimientos manuales de caja (pestaña accesible a todos los usuarios).

Permite registrar ingresos y egresos manuales durante la sesión activa y
muestra el listado completo con el total neto de la jornada.
Layout construido por código (sin .ui file).

Layout:
    QVBoxLayout raíz
    ├── QGroupBox "Sesión activa"
    │   └── QLabel _lbl_session
    ├── QGroupBox "Movimientos de la sesión"
    │   ├── QTableWidget _table (Hora · Descripción · Monto)
    │   └── QLabel _lbl_total (total neto, bold)
    ├── QGroupBox "Registrar movimiento"
    │   └── QHBoxLayout: QLineEdit _input_desc · QDoubleSpinBox _spin_amount
    │       · QPushButton "Ingreso" · QPushButton "Egreso"
    └── QLabel _status_label
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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


class CashMovementsView(QWidget):
    """Vista de movimientos manuales de caja (pestaña pública).

    Implementa ICashMovementsView. Toda la lógica de negocio está delegada al
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
        self._build_ui()

    def set_presenter(self, presenter) -> None:
        """Inyecta el CashPresenter.

        Args:
            presenter: CashPresenter configurado con esta vista.
        """
        self._presenter = presenter

    def on_view_activated(self) -> None:
        """No requiere recarga activa: el presenter mantiene el estado al día."""

    # ------------------------------------------------------------------
    # ICashMovementsView implementation
    # ------------------------------------------------------------------

    def show_session_open(self, cash_close: CashClose) -> None:
        """Habilita el formulario y actualiza el label de sesión.

        Args:
            cash_close: Arqueo de caja activo.
        """
        from src.infrastructure.ui.theme import SUCCESS_COLOR

        self._active_cash_close_id = cash_close.id
        hora = cash_close.opened_at.strftime("%H:%M")
        self._lbl_session.setText(
            f"✓ Sesión abierta desde las {hora}  "
            f"(monto inicial: ${cash_close.opening_amount:,.2f})"
        )
        self._lbl_session.setStyleSheet(f"color: {SUCCESS_COLOR}; font-weight: bold;")
        self._btn_income.setEnabled(True)
        self._btn_expense.setEnabled(True)
        self._input_desc.setEnabled(True)
        self._spin_amount.setEnabled(True)

    def show_session_closed(self) -> None:
        """Deshabilita el formulario al no haber sesión activa."""
        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        self._active_cash_close_id = None
        self._lbl_session.setText(
            "No hay caja abierta. Abrila desde el botón de la barra superior."
        )
        self._lbl_session.setStyleSheet(f"color: {TEXT_SECONDARY_COLOR};")
        self._btn_income.setEnabled(False)
        self._btn_expense.setEnabled(False)
        self._input_desc.setEnabled(False)
        self._spin_amount.setEnabled(False)

    def show_movements(self, movements: list[CashMovement]) -> None:
        """Actualiza la tabla y el total neto de la sesión.

        Args:
            movements: Lista completa de movimientos del arqueo activo.
        """
        from src.infrastructure.ui.theme import DANGER_COLOR, SUCCESS_COLOR

        self._table.setRowCount(0)
        total = Decimal("0")
        for mov in movements:
            row = self._table.rowCount()
            self._table.insertRow(row)
            hora = mov.created_at.strftime("%H:%M")
            color = SUCCESS_COLOR if mov.is_income else DANGER_COLOR
            signo = "+" if mov.is_income else "-"
            monto_str = f"{signo}${abs(mov.amount):,.2f}"
            total += mov.amount

            self._table.setItem(row, 0, QTableWidgetItem(hora))
            self._table.setItem(row, 1, QTableWidgetItem(mov.description))
            monto_item = QTableWidgetItem(monto_str)
            monto_item.setForeground(QColor(color))
            monto_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 2, monto_item)

        self._update_total_label(total)

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error en el label de estado.

        Args:
            message: Texto del error.
        """
        from src.infrastructure.ui.theme import DANGER_COLOR

        self._status_label.setText(f"⚠ {message}")
        self._status_label.setStyleSheet(f"color: {DANGER_COLOR};")

    def show_success(self, message: str) -> None:
        """Muestra un mensaje de éxito en el label de estado.

        Args:
            message: Texto del mensaje.
        """
        from src.infrastructure.ui.theme import SUCCESS_COLOR

        self._status_label.setText(f"✓ {message}")
        self._status_label.setStyleSheet(f"color: {SUCCESS_COLOR};")

    # ------------------------------------------------------------------
    # Handlers Qt
    # ------------------------------------------------------------------

    def _on_add_movement(self, is_income: bool) -> None:
        """Registra un movimiento manual (ingreso o egreso).

        Args:
            is_income: True para ingreso (monto positivo), False para egreso (negativo).
        """
        if not self._presenter:
            return
        raw_amount = Decimal(str(self._spin_amount.value()))
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
        self._spin_amount.setValue(0.01)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout de la vista por código."""
        # Layout raíz centra horizontalmente el contenido
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        from src.infrastructure.ui.theme import PALETTE

        container = QWidget()
        container.setFixedWidth(720)
        container.setStyleSheet(
            f"QWidget {{ background-color: {PALETTE.surface_card};"
            f" border-radius: 12px; }}"
        )
        root = QVBoxLayout(container)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        outer.addStretch()
        outer.addWidget(container)
        outer.addStretch()

        # --- Sesión ------------------------------------------------
        grp_session = QGroupBox("Sesión activa")
        v_session = QVBoxLayout(grp_session)
        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        self._lbl_session = QLabel(
            "No hay caja abierta. Abrila desde el botón de la barra superior."
        )
        self._lbl_session.setStyleSheet(f"color: {TEXT_SECONDARY_COLOR};")
        v_session.addWidget(self._lbl_session)
        root.addWidget(grp_session)

        # --- Tabla + total -----------------------------------------
        grp_list = QGroupBox("Movimientos de la sesión")
        v_list = QVBoxLayout(grp_list)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Hora", "Descripción", "Monto"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        v_list.addWidget(self._table, stretch=1)

        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        self._lbl_total = QLabel("Total neto: $0,00")
        self._lbl_total.setStyleSheet(
            f"font-family: monospace; font-weight: bold; font-size: 14px; color: {TEXT_SECONDARY_COLOR};"
        )
        self._lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        v_list.addWidget(self._lbl_total)

        root.addWidget(grp_list, stretch=1)

        # --- Formulario de registro --------------------------------
        grp_form = QGroupBox("Registrar movimiento")
        row_form = QHBoxLayout(grp_form)

        self._input_desc = QLineEdit()
        self._input_desc.setPlaceholderText("Descripción del movimiento...")
        self._input_desc.setEnabled(False)
        row_form.addWidget(self._input_desc, stretch=3)

        self._spin_amount = QDoubleSpinBox()
        self._spin_amount.setRange(0.01, 999_999.99)
        self._spin_amount.setDecimals(2)
        self._spin_amount.setSingleStep(100)
        self._spin_amount.setEnabled(False)
        row_form.addWidget(self._spin_amount, stretch=1)

        from src.infrastructure.ui.theme import get_btn_danger_stylesheet, get_btn_success_stylesheet

        self._btn_income = QPushButton("+ Ingreso")
        self._btn_income.setStyleSheet(get_btn_success_stylesheet())
        self._btn_income.setEnabled(False)
        self._btn_income.clicked.connect(lambda: self._on_add_movement(is_income=True))
        row_form.addWidget(self._btn_income)

        self._btn_expense = QPushButton("− Egreso")
        self._btn_expense.setStyleSheet(get_btn_danger_stylesheet())
        self._btn_expense.setEnabled(False)
        self._btn_expense.clicked.connect(lambda: self._on_add_movement(is_income=False))
        row_form.addWidget(self._btn_expense)

        root.addWidget(grp_form)

        # --- Estado ------------------------------------------------
        self._status_label = QLabel("")
        root.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_total_label(self, total: Decimal) -> None:
        """Actualiza el label de total neto con color según signo.

        Args:
            total: Suma neta de movimientos.
        """
        from src.infrastructure.ui.theme import DANGER_COLOR, SUCCESS_COLOR, TEXT_SECONDARY_COLOR

        if total > Decimal("0"):
            texto = f"Total neto: +${total:,.2f}"
            color = SUCCESS_COLOR
        elif total < Decimal("0"):
            texto = f"Total neto: -${abs(total):,.2f}"
            color = DANGER_COLOR
        else:
            texto = "Total neto: $0,00"
            color = TEXT_SECONDARY_COLOR
        self._lbl_total.setText(texto)
        self._lbl_total.setStyleSheet(
            f"font-family: monospace; font-weight: bold; font-size: 14px; color: {color};"
        )

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos.

        Args:
            worker: Worker a eliminar.
        """
        if worker in self._active_workers:
            self._active_workers.remove(worker)
