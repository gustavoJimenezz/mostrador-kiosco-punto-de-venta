"""Vista de historial de arqueos de caja (pestaña solo ADMIN).

Muestra todos los cierres de caja en un rango de fechas seleccionable.
Layout construido por código (sin .ui file).

Layout:
    QVBoxLayout raíz
    ├── QGroupBox "Filtro por fechas"
    │   └── QHBoxLayout: QLabel · QDateEdit (desde) · QLabel · QDateEdit (hasta)
    │                    · QPushButton "Buscar" · QLabel _lbl_loading
    ├── QTableWidget _table (Fecha · Apertura · Cierre · Fondo inicial ·
    │                        Ventas efectivo · Ventas débito · Ventas transf. ·
    │                        Total ventas · Monto contado · Diferencia · Estado)
    └── QLabel _status_label
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.cash_close import CashClose


class CashHistoryView(QWidget):
    """Vista de historial de arqueos de caja (solo ADMIN).

    Implementa ICashHistoryView. Toda la lógica de presentación está
    delegada al CashHistoryPresenter. Esta clase solo gestiona Qt.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        parent: QWidget padre (opcional).
    """

    _COLUMNS = [
        "Fecha",
        "Apertura",
        "Cierre",
        "Fondo inicial",
        "Ventas efectivo",
        "Ventas débito",
        "Ventas transf.",
        "Total ventas",
        "Monto contado",
        "Diferencia",
        "Estado",
    ]

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._presenter = None
        self._active_workers: list = []
        self._build_ui()

    def set_presenter(self, presenter) -> None:
        """Inyecta el CashHistoryPresenter.

        Args:
            presenter: CashHistoryPresenter configurado con esta vista.
        """
        self._presenter = presenter

    def on_view_activated(self) -> None:
        """Recarga el historial al navegar a esta pestaña."""
        self._load()

    # ------------------------------------------------------------------
    # ICashHistoryView implementation
    # ------------------------------------------------------------------

    def show_closes(self, closes: list[CashClose]) -> None:
        """Muestra la lista de arqueos en la tabla.

        Args:
            closes: Lista de CashClose a renderizar.
        """
        self._table.setRowCount(0)
        for cc in closes:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._fill_row(row, cc)

        count = len(closes)
        self._status_label.setText(
            f"{count} arqueo{'s' if count != 1 else ''} encontrado{'s' if count != 1 else ''}."
        )
        self._status_label.setStyleSheet("color: #374151;")

    def show_loading(self, loading: bool) -> None:
        """Muestra u oculta el indicador de carga.

        Args:
            loading: True para mostrar, False para ocultar.
        """
        self._lbl_loading.setVisible(loading)
        self._btn_search.setEnabled(not loading)

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error en la barra de estado.

        Args:
            message: Texto del error.
        """
        self._status_label.setText(f"⚠ {message}")
        self._status_label.setStyleSheet("color: #dc2626;")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout de la vista por código."""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # --- Filtro de fechas ------------------------------------------
        grp_filter = QGroupBox("Filtro por fechas")
        row_filter = QHBoxLayout(grp_filter)
        row_filter.setSpacing(8)

        row_filter.addWidget(QLabel("Desde:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("dd/MM/yyyy")
        today = QDate.currentDate()
        self._date_from.setDate(today.addDays(-30))
        row_filter.addWidget(self._date_from)

        row_filter.addWidget(QLabel("Hasta:"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("dd/MM/yyyy")
        self._date_to.setDate(today)
        row_filter.addWidget(self._date_to)

        self._btn_search = QPushButton("Buscar")
        self._btn_search.setStyleSheet(
            "QPushButton { padding: 4px 16px; border-radius: 4px;"
            "background: #4f46e5; color: white; border: none; }"
            "QPushButton:hover { background: #4338ca; }"
            "QPushButton:disabled { background: #a5b4fc; }"
        )
        self._btn_search.clicked.connect(self._on_search)
        row_filter.addWidget(self._btn_search)

        self._lbl_loading = QLabel("Cargando...")
        self._lbl_loading.setStyleSheet("color: #6b7280; font-style: italic;")
        self._lbl_loading.setVisible(False)
        row_filter.addWidget(self._lbl_loading)

        row_filter.addStretch()
        root.addWidget(grp_filter)

        # --- Tabla -----------------------------------------------------
        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._table, stretch=1)

        # --- Estado ----------------------------------------------------
        self._status_label = QLabel("Seleccione un rango de fechas y presione Buscar.")
        self._status_label.setStyleSheet("color: #6b7280;")
        root.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Handlers Qt
    # ------------------------------------------------------------------

    def _on_search(self) -> None:
        """Lanza el worker con el rango de fechas seleccionado."""
        if self._presenter:
            self._presenter.on_search_requested()

        qd_from = self._date_from.date()
        qd_to = self._date_to.date()
        start = date(qd_from.year(), qd_from.month(), qd_from.day())
        end = date(qd_to.year(), qd_to.month(), qd_to.day())

        from src.infrastructure.ui.workers.cash_history_worker import (
            LoadCashHistoryWorker,
        )

        worker = LoadCashHistoryWorker(self._session_factory, start, end)
        if self._presenter:
            worker.closes_loaded.connect(self._presenter.on_closes_loaded)
            worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Dispara la búsqueda automáticamente al activar la pestaña."""
        self._on_search()

    def _fill_row(self, row: int, cc: CashClose) -> None:
        """Rellena una fila de la tabla con los datos del arqueo.

        Args:
            row: Índice de fila en el QTableWidget.
            cc: Arqueo de caja a renderizar.
        """
        fecha = cc.opened_at.strftime("%d/%m/%Y")
        apertura = cc.opened_at.strftime("%H:%M")
        cierre = cc.closed_at.strftime("%H:%M") if cc.closed_at else "—"
        fondo = f"${cc.opening_amount:,.2f}"
        ventas_cash = f"${cc.total_sales_cash:,.2f}"
        ventas_debit = f"${cc.total_sales_debit:,.2f}"
        ventas_transf = f"${cc.total_sales_transfer:,.2f}"
        total_ventas = f"${cc.total_sales.amount:,.2f}"
        monto_contado = (
            f"${cc.closing_amount:,.2f}" if cc.closing_amount is not None else "—"
        )

        diferencia = cc.cash_difference
        if diferencia is None:
            diff_text = "—"
            diff_color = None
        elif diferencia >= Decimal("0"):
            diff_text = f"+${diferencia:,.2f}"
            diff_color = "#059669"
        else:
            diff_text = f"-${abs(diferencia):,.2f}"
            diff_color = "#dc2626"

        estado = "Abierta" if cc.is_open else "Cerrada"
        estado_color = "#d97706" if cc.is_open else "#374151"

        values = [
            fecha, apertura, cierre, fondo,
            ventas_cash, ventas_debit, ventas_transf, total_ventas,
            monto_contado, diff_text, estado,
        ]
        colors = [
            None, None, None, None,
            None, None, None, None,
            None, diff_color, estado_color,
        ]

        for col, (text, color) in enumerate(zip(values, colors)):
            item = QTableWidgetItem(text)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter
                if col in (0, 1, 2, 10)
                else Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if color:
                item.setForeground(QColor(color))
            self._table.setItem(row, col, item)

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
