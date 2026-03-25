"""Widget compacto de historial de ventas del día (panel derecho de venta).

Muestra las ventas del día actual en una tabla scrolleable embebida en la
columna derecha de la ventana de venta, entre el TotalWidget y los botones
de acción. Se actualiza automáticamente tras cada venta confirmada.

Layout::

    MiniSalesHistoryWidget (QWidget)
    └── QVBoxLayout
        ├── QHBoxLayout (header)
        │   ├── QLabel "Ventas de hoy"
        │   └── QLabel _lbl_total  (total diario, bold)
        └── QTableWidget _table  (Hora · Método · Total, scroll nativo)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.sale import Sale


class MiniSalesHistoryWidget(QWidget):
    """Panel compacto de historial de ventas del día embebido en la columna derecha.

    Auto-contenido: carga sus propios datos vía worker reutilizando
    LoadSalesWorker. No requiere presenter externo.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._sales: list[Sale] = []
        self._active_workers: list = []
        self._build_ui()
        self.refresh()

    def refresh(self) -> None:
        """Recarga las ventas del día actual desde la base de datos."""
        today = QDate.currentDate().toPython()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())

        from src.infrastructure.ui.workers.sales_history_worker import LoadSalesWorker

        worker = LoadSalesWorker(self._session_factory, start, end)
        worker.sales_loaded.connect(self._on_sales_loaded)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    # ------------------------------------------------------------------
    # Slots internos
    # ------------------------------------------------------------------

    def _on_sales_loaded(self, sales: list[Sale]) -> None:
        """Actualiza la tabla y el total diario con las ventas recibidas.

        Args:
            sales: Lista de Sale del día actual.
        """
        self._sales = sales
        self._table.setRowCount(0)

        total_dia = Decimal("0")
        for sale in reversed(sales):  # más reciente primero
            row = self._table.rowCount()
            self._table.insertRow(row)

            hora = sale.timestamp.strftime("%H:%M:%S")
            metodo = sale.payment_method.value
            total_str = f"${sale.total_amount.amount:,.2f}"
            total_dia += sale.total_amount.amount

            btn = QPushButton("ver")
            btn.setStyleSheet(
                "QPushButton {"
                "  font-size: 11px; font-weight: 500;"
                "  border: none; border-right: 1px solid #888; border-radius: 0px; background: transparent;"
                "}"
                "QPushButton:hover {"
                "  background: #e0e0e0;"
                "}"
            )
            btn.clicked.connect(lambda _checked, s=sale: self._open_detail_dialog(s))
            self._table.setCellWidget(row, 0, btn)

            hora_item = QTableWidgetItem(hora)
            hora_item.setData(Qt.UserRole, sale)
            hora_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 1, hora_item)

            metodo_item = QTableWidgetItem(metodo)
            metodo_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 2, metodo_item)

            total_item = QTableWidgetItem(total_str)
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, 3, total_item)

        self._lbl_total.setText(f"${total_dia:,.2f}")

    def _on_row_clicked(self) -> None:
        """Abre el diálogo de detalle de la venta seleccionada."""
        row = self._table.currentRow()
        if row < 0:
            return
        hora_item = self._table.item(row, 0)
        if hora_item is None:
            return
        sale: Sale = hora_item.data(Qt.UserRole)
        if sale is None:
            return
        self._open_detail_dialog(sale)

    def _open_detail_dialog(self, sale: Sale) -> None:
        """Carga y muestra el detalle de ítems de la venta en un diálogo compacto.

        Args:
            sale: Venta cuyo detalle se desea ver.
        """
        from src.infrastructure.ui.workers.sales_history_worker import (
            LoadSaleDetailWorker,
        )

        worker = LoadSaleDetailWorker(self._session_factory, sale.id)
        worker.detail_loaded.connect(
            lambda items: self._show_detail_dialog(sale, items)
        )
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _show_detail_dialog(self, sale: Sale, items: list[dict]) -> None:
        """Construye y muestra el QDialog con el detalle de ítems.

        Args:
            sale: Venta a mostrar.
            items: Lista de dicts con product_name, quantity, price_at_sale, subtotal.
        """
        hora = sale.timestamp.strftime("%H:%M:%S")
        total = f"${sale.total_amount.amount:,.2f}"

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Venta {hora} — {total}")
        dlg.resize(480, 280)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        lbl = QLabel(
            f"<b>{hora}</b> · {sale.payment_method.value} · <b>{total}</b>"
        )
        layout.addWidget(lbl)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(
            ["Producto", "Cant.", "P. unitario", "Subtotal"]
        )
        table.horizontalHeader().setStretchLastSection(False)
        from PySide6.QtWidgets import QHeaderView

        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)

        for item in items:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(item["product_name"]))
            table.setItem(row, 1, QTableWidgetItem(str(item["quantity"])))
            table.setItem(
                row, 2, QTableWidgetItem(f"${item['price_at_sale']:,.2f}")
            )
            table.setItem(
                row, 3, QTableWidgetItem(f"${item['subtotal']:,.2f}")
            )

        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        dlg.exec()

    # ------------------------------------------------------------------
    # Construcción de UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout del widget por código."""
        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(4)

        # --- Header ---------------------------------------------------
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("Ventas de hoy")
        lbl_title.setStyleSheet(
            f"font-size: 11px; color: {TEXT_SECONDARY_COLOR}; font-weight: bold;"
        )
        header.addWidget(lbl_title)

        header.addStretch()

        self._lbl_total = QLabel("$0,00")
        self._lbl_total.setStyleSheet(
            "font-size: 12px; font-weight: bold;"
        )
        self._lbl_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self._lbl_total)

        root.addLayout(header)

        # --- Tabla ----------------------------------------------------
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["", "Hora", "Método", "Total"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setDefaultSectionSize(80)
        self._table.setColumnWidth(0, 80)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("font-size: 11px;")
        self._table.itemDoubleClicked.connect(self._on_row_clicked)

        root.addWidget(self._table, stretch=1)

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos.

        Args:
            worker: Worker QThread que finalizó.
        """
        if worker in self._active_workers:
            self._active_workers.remove(worker)
