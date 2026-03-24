"""Vista de edición de stock (pestaña QWidget, F6).

Vive dentro del QTabWidget de MainWindow como tab "Editar Stock (F6)".
Implementa IStockEditView. Layout construido por código (sin .ui file).

Layout:
    QVBoxLayout raíz
    ├── QGroupBox "Buscar producto"
    │   ├── QLineEdit _search_input  (placeholder: "Código de barras o nombre…")
    │   └── QListWidget _results_list  (oculto por defecto)
    ├── QGroupBox "Ajuste de stock" (_form_group, oculto por defecto)
    │   ├── QLabel _lbl_product_name
    │   ├── QLabel _lbl_current_stock
    │   ├── QHBoxLayout: QRadioButton _radio_add / _radio_remove
    │   ├── QSpinBox _spin_qty
    │   └── QPushButton _btn_confirm
    ├── QLabel _status_label
    └── QGroupBox "Productos editados en esta sesión"
        └── QTableWidget _edited_table
            columnas: Código | Nombre | Categoría | Costo | Precio | Margen % | Stock | Stock Mín
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.product import Product


class StockEditView(QWidget):
    """Vista de edición rápida de stock como QWidget pestaña.

    Implementa IStockEditView. La lógica de presentación está delegada
    al StockEditPresenter, inyectado mediante set_presenter().

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
            Se pasa a los workers creados en esta vista.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._presenter = None
        self._active_workers: list = []
        self._edited_rows: dict[int, int] = {}  # {product.id: row_index}
        self._build_ui()

    def set_presenter(self, presenter) -> None:
        """Inyecta el StockEditPresenter y conecta las señales Qt.

        Args:
            presenter: StockEditPresenter ya configurado con esta vista.
        """
        self._presenter = presenter
        self._search_input.returnPressed.connect(self._on_search_entered)
        self._results_list.itemActivated.connect(self._on_result_item_activated)
        self._btn_confirm.clicked.connect(self._on_confirm_clicked)

    # ------------------------------------------------------------------
    # IStockEditView implementation
    # ------------------------------------------------------------------

    def show_search_results(self, products: list[Product]) -> None:
        """Muestra la lista de productos encontrados por nombre.

        Args:
            products: Lista de productos a mostrar en la lista de selección.
        """
        self._results_list.clear()
        for product in products:
            item = QListWidgetItem(
                f"{product.name}  —  stock: {product.stock}"
            )
            item.setData(Qt.UserRole, product)
            self._results_list.addItem(item)
        self._results_list.setVisible(True)
        self._results_list.setFocus()

    def show_product_form(self, product: Product) -> None:
        """Muestra el formulario de ajuste con los datos del producto.

        Args:
            product: Producto seleccionado para editar stock.
        """
        self._lbl_product_name.setText(f"<b>{product.name}</b>  ({product.barcode})")
        self._lbl_current_stock.setText(f"Stock : {product.stock}")
        self._radio_add.setChecked(True)
        self._spin_qty.setValue(1)
        self._form_group.setVisible(True)
        self._spin_qty.setFocus()

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Muestra un mensaje de estado en el label inferior.

        Args:
            message: Texto a mostrar.
            is_error: Si True, texto en rojo; si False, en gris oscuro.
        """
        self._status_label.setText(message)
        color = "#dc2626" if is_error else "#374151"
        self._status_label.setStyleSheet(f"color: {color};")

    def add_or_update_edited_row(self, product: Product) -> None:
        """Agrega o actualiza la fila del producto en la tabla de sesión.

        Args:
            product: Producto con stock ya actualizado.
        """
        category_name = str(product.category_id) if product.category_id else ""
        price = product.current_price.amount

        if product.id in self._edited_rows:
            row = self._edited_rows[product.id]
        else:
            row = self._edited_table.rowCount()
            self._edited_table.insertRow(row)
            self._edited_rows[product.id] = row

        self._edited_table.setItem(row, 0, QTableWidgetItem(product.barcode))
        self._edited_table.setItem(row, 1, QTableWidgetItem(product.name))
        self._edited_table.setItem(row, 2, QTableWidgetItem(category_name))
        self._edited_table.setItem(row, 3, QTableWidgetItem(f"{product.current_cost:,.2f}"))
        self._edited_table.setItem(row, 4, QTableWidgetItem(f"{price:,.2f}"))
        self._edited_table.setItem(row, 5, QTableWidgetItem(f"{product.margin_percent:.2f}"))
        self._edited_table.setItem(row, 6, QTableWidgetItem(str(product.stock)))
        self._edited_table.setItem(row, 7, QTableWidgetItem(str(product.min_stock)))

    def get_operation(self) -> str:
        """Retorna la operación seleccionada.

        Returns:
            ``"increment"`` si está seleccionado el radio de agregar,
            ``"decrement"`` en caso contrario.
        """
        return "increment" if self._radio_add.isChecked() else "decrement"

    def get_quantity(self) -> int:
        """Retorna la cantidad del spinbox.

        Returns:
            Entero >= 1.
        """
        return self._spin_qty.value()

    def reset_form(self) -> None:
        """Resetea el formulario a estado inicial y devuelve foco al buscador."""
        self._spin_qty.setValue(1)
        self._radio_add.setChecked(True)
        self._search_input.clear()
        self._search_input.setFocus()

    def on_view_activated(self) -> None:
        """Llamado por MainWindow al activar esta pestaña; limpia estado y da foco."""
        self._results_list.clear()
        self._results_list.setVisible(False)
        self._form_group.setVisible(False)
        self._status_label.setText("")
        self._search_input.clear()
        self._search_input.setFocus()

    # ------------------------------------------------------------------
    # Construcción interna del UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout completo de la vista programáticamente."""
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # --- QGroupBox Buscar producto ---
        search_group = QGroupBox("Buscar producto")
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Código de barras o nombre…")
        search_layout.addWidget(self._search_input)

        self._results_list = QListWidget()
        self._results_list.setVisible(False)
        self._results_list.setMaximumHeight(150)
        search_layout.addWidget(self._results_list)

        root.addWidget(search_group)

        # --- QGroupBox Ajuste de stock (oculto por defecto) ---
        self._form_group = QGroupBox("Ajuste de stock")
        self._form_group.setVisible(False)
        form_layout = QVBoxLayout(self._form_group)
        form_layout.setSpacing(8)

        self._lbl_product_name = QLabel("")
        self._lbl_product_name.setWordWrap(True)
        form_layout.addWidget(self._lbl_product_name)

        self._lbl_current_stock = QLabel("Stock actual: —")
        form_layout.addWidget(self._lbl_current_stock)

        radio_row = QHBoxLayout()
        self._radio_add = QRadioButton("+ Agregar")
        self._radio_remove = QRadioButton("- Retirar")
        self._radio_add.setChecked(True)
        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._radio_add)
        self._btn_group.addButton(self._radio_remove)
        radio_row.addWidget(self._radio_add)
        radio_row.addWidget(self._radio_remove)
        radio_row.addStretch()
        form_layout.addLayout(radio_row)

        self._spin_qty = QSpinBox()
        self._spin_qty.setMinimum(1)
        self._spin_qty.setMaximum(9999)
        self._spin_qty.setValue(1)
        form_layout.addWidget(self._spin_qty)

        self._btn_confirm = QPushButton("Confirmar  [Enter]")
        self._btn_confirm.setFixedHeight(40)
        form_layout.addWidget(self._btn_confirm)

        root.addWidget(self._form_group)

        # --- Status label ---
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addWidget(self._status_label)

        # --- QGroupBox Productos editados en esta sesión ---
        session_group = QGroupBox("Productos editados en esta sesión")
        session_layout = QVBoxLayout(session_group)
        session_layout.setContentsMargins(4, 4, 4, 4)

        self._edited_table = QTableWidget(0, 8)
        self._edited_table.setHorizontalHeaderLabels(
            ["Código", "Nombre", "Categoría", "Costo", "Precio", "Margen %", "Stock", "Stock Mín"]
        )
        self._edited_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._edited_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._edited_table.horizontalHeader().setStretchLastSection(True)
        session_layout.addWidget(self._edited_table)

        root.addWidget(session_group)

    # ------------------------------------------------------------------
    # Handlers Qt internos
    # ------------------------------------------------------------------

    def _on_search_entered(self) -> None:
        """Enter en _search_input: lanza worker de búsqueda por barcode o nombre."""
        text = self._search_input.text().strip()
        if not text or self._presenter is None:
            return

        self._results_list.setVisible(False)
        self._form_group.setVisible(False)
        self._status_label.setText("")

        if text.isdigit():
            self._launch_barcode_search(text)
        else:
            self._launch_name_search(text)

    def _on_result_item_activated(self, item: QListWidgetItem) -> None:
        """Usuario activó un ítem de la lista de resultados.

        Args:
            item: Ítem activado (contiene el Product en UserRole).
        """
        product = item.data(Qt.UserRole)
        if product and self._presenter:
            self._presenter.on_product_selected_from_list(product)
        self._results_list.setVisible(False)

    def _confirm_stock_change(
        self, product: Product, operation: str, qty: int
    ) -> bool:
        """Muestra diálogo de confirmación antes de persistir el ajuste de stock.

        Args:
            product: Producto que se va a modificar.
            operation: ``"increment"`` o ``"decrement"``.
            qty: Cantidad a modificar.

        Returns:
            True si el usuario confirmó, False si canceló.
        """
        op_label = "Agregar" if operation == "increment" else "Retirar"
        if operation == "increment":
            resulting_stock = product.stock + qty
        else:
            resulting_stock = product.stock - qty

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Confirmar ajuste de stock")
        dialog.setText(
            f"<b>Producto:</b> {product.name}<br>"
            f"<b>Operación:</b> {op_label} {qty} u.<br>"
            f"<b>Stock actual:</b> {product.stock}<br>"
            f"<b>Stock resultante:</b> {resulting_stock}"
        )
        btn_ok = dialog.addButton("Confirmar", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        return dialog.clickedButton() == btn_ok

    def _on_confirm_clicked(self) -> None:
        """Botón Confirmar: valida con presenter, pide confirmación y lanza UpdateStockWorker."""
        if self._presenter is None:
            return
        result = self._presenter.on_confirm_stock_edit_requested()
        if result is None:
            return
        product, operation, qty = result
        if not self._confirm_stock_change(product, operation, qty):
            return
        self._launch_update_stock_worker(product, operation, qty)

    # ------------------------------------------------------------------
    # Creación de workers (UI responsable)
    # ------------------------------------------------------------------

    def _launch_barcode_search(self, barcode: str) -> None:
        """Lanza SearchByBarcodeWorker para el código dado.

        Args:
            barcode: Código de barras a buscar.
        """
        from src.infrastructure.ui.workers.db_worker import SearchByBarcodeWorker

        worker = SearchByBarcodeWorker(self._session_factory, barcode)
        worker.product_found.connect(self._presenter.on_barcode_found)
        worker.not_found.connect(self._presenter.on_barcode_not_found)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _launch_name_search(self, query: str) -> None:
        """Lanza SearchByNameWorker para la consulta dada.

        Args:
            query: Texto parcial del nombre a buscar.
        """
        from src.infrastructure.ui.workers.db_worker import SearchByNameWorker

        worker = SearchByNameWorker(self._session_factory, query)
        worker.results_ready.connect(self._presenter.on_search_results_ready)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _launch_update_stock_worker(
        self, product: Product, operation: str, quantity: int
    ) -> None:
        """Lanza UpdateStockWorker para actualizar el stock del producto.

        Args:
            product: Producto a actualizar.
            operation: ``"increment"`` o ``"decrement"``.
            quantity: Cantidad a modificar.
        """
        from src.infrastructure.ui.workers.product_worker import UpdateStockWorker

        worker = UpdateStockWorker(
            self._session_factory, product.id, operation, quantity
        )
        worker.stock_updated.connect(self._presenter.on_stock_updated)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
