"""Vista del historial de ventas (pestaña QWidget, F2).

Vive dentro del QTabWidget de MainWindow como tab "Historial (F2)".
Layout construido por código (sin .ui file).

Layout:
    QVBoxLayout raíz
    ├── QGroupBox "Filtros"
    │   └── QHBoxLayout: QLabel · QDateEdit _date_filter · QPushButton "Buscar"
    │       · QLabel _lbl_daily_total
    ├── QTableWidget _sales_table (Hora · Método · Ítems · Total)
    └── QGroupBox "Detalle de venta" (_grp_detail, oculto hasta seleccionar)
        └── QTableWidget _items_table (Producto · Cant · P. unitario · Subtotal)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.sale import Sale


class SalesHistoryView(QWidget):
    """Vista de consulta del historial de ventas (pestaña F2).

    Implementa ISalesHistoryView. Toda la lógica delegada al
    SalesHistoryPresenter. Esta clase solo gestiona Qt.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._presenter = None
        self._active_workers: list = []
        self._build_ui()

    def set_presenter(self, presenter) -> None:
        """Inyecta el SalesHistoryPresenter.

        Args:
            presenter: SalesHistoryPresenter configurado con esta vista.
        """
        self._presenter = presenter

    def on_view_activated(self) -> None:
        """Lanza la búsqueda para la fecha seleccionada al activar la pestaña."""
        self._search_sales()

    # ------------------------------------------------------------------
    # ISalesHistoryView implementation
    # ------------------------------------------------------------------

    def show_sales(self, sales: list[Sale]) -> None:
        """Muestra la lista de ventas en la tabla principal."""
        self._sales_table.setRowCount(0)
        self._grp_detail.setVisible(False)

        for sale in sales:
            row = self._sales_table.rowCount()
            self._sales_table.insertRow(row)

            hora = sale.timestamp.strftime("%H:%M:%S")
            metodo = sale.payment_method.value
            total = f"${sale.total_amount.amount:,.2f}"

            hora_item = QTableWidgetItem(hora)
            hora_item.setData(Qt.UserRole, sale)
            self._sales_table.setItem(row, 0, hora_item)
            self._sales_table.setItem(row, 1, QTableWidgetItem(metodo))
            self._sales_table.setItem(row, 2, QTableWidgetItem(total))

    def show_sale_detail(self, items: list[dict]) -> None:
        """Muestra el detalle de ítems de la venta seleccionada."""
        self._items_table.setRowCount(0)
        for item in items:
            row = self._items_table.rowCount()
            self._items_table.insertRow(row)
            self._items_table.setItem(
                row, 0, QTableWidgetItem(item["product_name"])
            )
            self._items_table.setItem(
                row, 1, QTableWidgetItem(str(item["quantity"]))
            )
            self._items_table.setItem(
                row,
                2,
                QTableWidgetItem(f"${item['price_at_sale']:,.2f}"),
            )
            self._items_table.setItem(
                row, 3, QTableWidgetItem(f"${item['subtotal']:,.2f}")
            )
        self._grp_detail.setVisible(True)

    def show_daily_total(self, total: Decimal) -> None:
        """Actualiza el label del total del día."""
        self._lbl_daily_total.setText(f"Total del día: ${total:,.2f}")

    def show_error(self, message: str) -> None:
        """Muestra mensaje de error en el label de estado."""
        self._lbl_status.setText(f"⚠ {message}")
        self._lbl_status.setStyleSheet("color: #dc2626;")

    def show_loading(self, loading: bool) -> None:
        """Muestra u oculta el indicador de carga."""
        self._btn_search.setEnabled(not loading)
        self._lbl_status.setText("Cargando..." if loading else "")
        self._lbl_status.setStyleSheet("color: #6b7280;")

    # ------------------------------------------------------------------
    # Handlers Qt
    # ------------------------------------------------------------------

    def _search_sales(self) -> None:
        """Lanza el worker para cargar ventas de la fecha seleccionada."""
        from datetime import datetime

        if self._presenter:
            self._presenter.on_search_requested()

        qdate = self._date_filter.date()
        py_date = qdate.toPython()
        start = datetime.combine(py_date, datetime.min.time())
        end = datetime.combine(py_date, datetime.max.time())

        from src.infrastructure.ui.workers.sales_history_worker import LoadSalesWorker

        worker = LoadSalesWorker(self._session_factory, start, end)
        if self._presenter:
            worker.sales_loaded.connect(self._presenter.on_sales_loaded)
            worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_sale_selected(self) -> None:
        """Carga el detalle de la venta seleccionada en la tabla."""
        row = self._sales_table.currentRow()
        if row < 0 or not self._presenter:
            return

        sale = self._presenter.get_sale_by_row(row)
        if sale is None:
            return

        from src.infrastructure.ui.workers.sales_history_worker import (
            LoadSaleDetailWorker,
        )

        worker = LoadSaleDetailWorker(self._session_factory, sale.id)
        worker.detail_loaded.connect(self._presenter.on_detail_loaded)
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

        # --- Filtros -----------------------------------------------
        grp_filters = QGroupBox("Filtros")
        h_filters = QHBoxLayout(grp_filters)

        h_filters.addWidget(QLabel("Fecha:"))
        self._date_filter = QDateEdit()
        self._date_filter.setDate(QDate.currentDate())
        self._date_filter.setCalendarPopup(True)
        h_filters.addWidget(self._date_filter)

        self._btn_search = QPushButton("Buscar")
        self._btn_search.clicked.connect(self._search_sales)
        h_filters.addWidget(self._btn_search)

        h_filters.addStretch()
        self._lbl_daily_total = QLabel("Total del día: $0,00")
        self._lbl_daily_total.setStyleSheet("font-weight: bold; font-size: 13px;")
        h_filters.addWidget(self._lbl_daily_total)
        root.addWidget(grp_filters)

        # --- Tabla de ventas ---------------------------------------
        self._sales_table = QTableWidget(0, 3)
        self._sales_table.setHorizontalHeaderLabels(["Hora", "Método de pago", "Total"])
        self._sales_table.horizontalHeader().setStretchLastSection(True)
        self._sales_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._sales_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._sales_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._sales_table.itemSelectionChanged.connect(self._on_sale_selected)
        root.addWidget(self._sales_table, stretch=2)

        # --- Detalle de venta (oculto por defecto) -----------------
        self._grp_detail = QGroupBox("Detalle de venta")
        v_detail = QVBoxLayout(self._grp_detail)

        self._items_table = QTableWidget(0, 4)
        self._items_table.setHorizontalHeaderLabels(
            ["Producto", "Cant.", "P. unitario", "Subtotal"]
        )
        self._items_table.horizontalHeader().setStretchLastSection(False)
        self._items_table.horizontalHeader().setSectionResizeMode(
            0,
            __import__(
                "PySide6.QtWidgets", fromlist=["QHeaderView"]
            ).QHeaderView.ResizeMode.Stretch,
        )
        self._items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._items_table.setFixedHeight(150)
        v_detail.addWidget(self._items_table)
        self._grp_detail.setVisible(False)
        root.addWidget(self._grp_detail, stretch=1)

        # --- Estado ------------------------------------------------
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color: #6b7280;")
        root.addWidget(self._lbl_status)

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
