"""Vista de inyección directa de stock (pestaña QWidget, F7).

Vive dentro del QTabWidget de MainWindow como tab "Inyectar Stock (F7)".
Implementa IStockInjectView. Layout construido por código (sin .ui file).

Flujo de uso:
    1. Operador ingresa la cantidad en _spin_qty (izquierda).
    2. Escribe código de barras o nombre en _search_input (derecha) y presiona Enter.
       · Código numérico  → SearchByBarcodeWorker → inyección directa si se encuentra.
       · Texto parcial    → SearchByNameWorker  → si 1 resultado: inyección directa;
                                                   si varios: lista _results_list para selección.
    3. Si se inyecta correctamente, la fila del producto aparece/actualiza en
       la tabla inferior con todo el detalle y el stock actualizado.

Layout:
    QVBoxLayout raíz
    ├── QGroupBox "Inyectar stock"
    │   └── QHBoxLayout
    │       ├── QVBoxLayout izquierdo
    │       │   ├── QLabel "Cantidad a agregar"
    │       │   └── QSpinBox _spin_qty  (mín:1, máx:9999, valor:1)
    │       └── QVBoxLayout derecho
    │           ├── QLabel "Código de barras o nombre"
    │           └── QLineEdit _search_input
    ├── QListWidget _results_list  (oculto por defecto)
    ├── QLabel _status_label
    └── QGroupBox "Productos modificados en esta sesión"
        └── QTableWidget _injected_table
            columnas: Código | Nombre | Categoría | Costo | Precio | Margen % | Stock | Stock Mín
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.product import Product


class StockInjectView(QWidget):
    """Vista de inyección directa de stock como QWidget pestaña.

    Implementa IStockInjectView. La lógica de presentación está delegada
    al StockInjectPresenter, inyectado mediante set_presenter().

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
        self._injected_rows: dict[int, int] = {}  # {product.id: row_index}
        self._build_ui()

    def set_presenter(self, presenter) -> None:
        """Inyecta el StockInjectPresenter y conecta las señales Qt.

        Args:
            presenter: StockInjectPresenter ya configurado con esta vista.
        """
        self._presenter = presenter
        self._search_input.returnPressed.connect(self._on_search_entered)
        self._results_list.itemActivated.connect(self._on_result_item_activated)

    # ------------------------------------------------------------------
    # IStockInjectView implementation
    # ------------------------------------------------------------------

    def show_search_results(self, products: list[Product]) -> None:
        """Muestra la lista de productos encontrados por nombre.

        Args:
            products: Lista de productos a mostrar en la lista de selección.
        """
        self._results_list.clear()
        for product in products:
            item = QListWidgetItem(
                f"{product.name}  —  stock actual: {product.stock}"
            )
            item.setData(Qt.UserRole, product)
            self._results_list.addItem(item)
        self._results_list.setVisible(True)
        self._results_list.setFocus()

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Muestra un mensaje de estado en el label inferior.

        Args:
            message: Texto a mostrar.
            is_error: Si True, texto en rojo; si False, en gris oscuro.
        """
        from src.infrastructure.ui.theme import DANGER_COLOR, TEXT_PRIMARY_COLOR

        self._status_label.setText(message)
        color = DANGER_COLOR if is_error else TEXT_PRIMARY_COLOR
        self._status_label.setStyleSheet(f"color: {color};")

    def add_or_update_injected_row(self, product: Product) -> None:
        """Agrega o actualiza la fila del producto en la tabla de sesión.

        Args:
            product: Producto con stock ya actualizado.
        """
        category_name = str(product.category_id) if product.category_id else ""
        price = product.current_price.amount

        if product.id in self._injected_rows:
            row = self._injected_rows[product.id]
        else:
            row = self._injected_table.rowCount()
            self._injected_table.insertRow(row)
            self._injected_rows[product.id] = row

        self._injected_table.setItem(row, 0, QTableWidgetItem(product.barcode))
        self._injected_table.setItem(row, 1, QTableWidgetItem(product.name))
        self._injected_table.setItem(row, 2, QTableWidgetItem(category_name))
        self._injected_table.setItem(
            row, 3, QTableWidgetItem(f"{product.current_cost:,.2f}")
        )
        self._injected_table.setItem(row, 4, QTableWidgetItem(f"{price:,.2f}"))
        self._injected_table.setItem(
            row, 5, QTableWidgetItem(f"{product.margin_percent:.2f}")
        )
        self._injected_table.setItem(row, 6, QTableWidgetItem(str(product.stock)))
        self._injected_table.setItem(row, 7, QTableWidgetItem(str(product.min_stock)))

    def get_quantity(self) -> int:
        """Retorna la cantidad del spinbox.

        Returns:
            Entero >= 1.
        """
        return self._spin_qty.value()

    def clear_search(self) -> None:
        """Limpia el campo de búsqueda, oculta resultados y devuelve foco al spinbox."""
        self._search_input.clear()
        self._results_list.clear()
        self._results_list.setVisible(False)
        self._spin_qty.setFocus()
        self._spin_qty.selectAll()

    def on_view_activated(self) -> None:
        """Llamado por MainWindow al activar esta pestaña; limpia estado y da foco."""
        self._results_list.clear()
        self._results_list.setVisible(False)
        self._search_input.clear()
        self._status_label.setText("")
        self._spin_qty.setFocus()
        self._spin_qty.selectAll()

    # ------------------------------------------------------------------
    # Construcción interna del UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout completo de la vista programáticamente."""
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # --- Texto descriptivo ---
        from src.infrastructure.ui.theme import PALETTE

        info = QLabel(
            "<b>Inyectar stock</b> — Carga rápida de stock optimizada para "
            "escaneo con lector de barras.<br>"
            "<span style='color:#0369a1;'>"
            "Ingresá la <b>cantidad</b> primero, luego escaneá o escribí el "
            "código/nombre y presioná Enter. "
            "Si hay un único resultado, el stock se suma directamente."
            "</span>"
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"background:{PALETTE.info_surface}; border:1px solid {PALETTE.info_border};"
            f" border-radius:6px; padding:8px 10px; color:{PALETTE.info_text}; font-size:12px;"
        )
        root.addWidget(info)

        # --- QGroupBox Inyectar stock ---
        inject_group = QGroupBox("Inyectar stock")
        inject_row = QHBoxLayout(inject_group)
        inject_row.setSpacing(16)

        # Panel izquierdo: cantidad
        left = QVBoxLayout()
        left.setSpacing(4)
        lbl_qty = QLabel("Cantidad a agregar")
        self._spin_qty = QSpinBox()
        self._spin_qty.setMinimum(1)
        self._spin_qty.setMaximum(9999)
        self._spin_qty.setValue(1)
        self._spin_qty.setFixedWidth(120)
        self._spin_qty.setFixedHeight(36)
        left.addWidget(lbl_qty)
        left.addWidget(self._spin_qty)
        left.addStretch()
        inject_row.addLayout(left)

        # Panel derecho: buscador
        right = QVBoxLayout()
        right.setSpacing(4)
        lbl_search = QLabel("Código de barras o nombre del producto")
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Escanee o escriba y presione Enter…")
        self._search_input.setFixedHeight(36)
        right.addWidget(lbl_search)
        right.addWidget(self._search_input)
        right.addStretch()
        inject_row.addLayout(right, stretch=1)

        root.addWidget(inject_group)

        # --- Lista de resultados (oculta por defecto) ---
        self._results_list = QListWidget()
        self._results_list.setVisible(False)
        self._results_list.setMaximumHeight(160)
        root.addWidget(self._results_list)

        # --- Status label ---
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addWidget(self._status_label)

        # --- QGroupBox Productos modificados en esta sesión ---
        session_group = QGroupBox("Productos modificados en esta sesión")
        session_layout = QVBoxLayout(session_group)
        session_layout.setContentsMargins(4, 4, 4, 4)

        self._injected_table = QTableWidget(0, 8)
        self._injected_table.setHorizontalHeaderLabels(
            [
                "Código",
                "Nombre",
                "Categoría",
                "Costo",
                "Precio",
                "Margen %",
                "Stock",
                "Stock Mín",
            ]
        )
        self._injected_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._injected_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._injected_table.horizontalHeader().setStretchLastSection(True)
        session_layout.addWidget(self._injected_table)

        root.addWidget(session_group)

    # ------------------------------------------------------------------
    # Handlers Qt internos
    # ------------------------------------------------------------------

    def _on_search_entered(self) -> None:
        """Enter en _search_input: determina tipo de búsqueda y lanza el worker."""
        text = self._search_input.text().strip()
        if not text or self._presenter is None:
            return

        self._results_list.setVisible(False)
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
        if self._presenter is None:
            return
        product = item.data(Qt.UserRole)
        if product is None:
            return
        result = self._presenter.on_product_selected_from_list(product)
        self._results_list.setVisible(False)
        if result is not None:
            self._launch_injection(*result)

    # ------------------------------------------------------------------
    # Creación de workers
    # ------------------------------------------------------------------

    def _launch_barcode_search(self, barcode: str) -> None:
        """Lanza SearchByBarcodeWorker; conecta al handler local para inyección directa.

        Args:
            barcode: Código de barras a buscar.
        """
        from src.infrastructure.ui.workers.db_worker import SearchByBarcodeWorker

        worker = SearchByBarcodeWorker(self._session_factory, barcode)
        worker.product_found.connect(self._on_barcode_found)
        worker.not_found.connect(self._presenter.on_barcode_not_found)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _launch_name_search(self, query: str) -> None:
        """Lanza SearchByNameWorker; conecta al handler local para inyección directa.

        Args:
            query: Texto parcial del nombre a buscar.
        """
        from src.infrastructure.ui.workers.db_worker import SearchByNameWorker

        worker = SearchByNameWorker(self._session_factory, query)
        worker.results_ready.connect(self._on_search_results_ready)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_barcode_found(self, product: Product) -> None:
        """Slot intermedio: delega al presenter y lanza la inyección si procede.

        Args:
            product: Producto encontrado por SearchByBarcodeWorker.
        """
        result = self._presenter.on_barcode_found(product)
        if result is not None:
            self._launch_injection(*result)

    def _on_search_results_ready(self, products: list[Product]) -> None:
        """Slot intermedio: delega al presenter y lanza la inyección si procede.

        Args:
            products: Resultados de SearchByNameWorker.
        """
        result = self._presenter.on_search_results_ready(products)
        if result is not None:
            self._launch_injection(*result)

    def _confirm_injection(self, product: Product, qty: int) -> bool:
        """Muestra diálogo de confirmación antes de persistir la inyección de stock.

        Args:
            product: Producto que se va a modificar.
            qty: Cantidad a agregar.

        Returns:
            True si el usuario confirmó, False si canceló.
        """
        resulting_stock = product.stock + qty

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Confirmar inyección de stock")
        dialog.setText(
            f"<b>Producto:</b> {product.name}<br>"
            f"<b>Cantidad a agregar:</b> {qty} u.<br>"
            f"<b>Stock actual:</b> {product.stock}<br>"
            f"<b>Stock resultante:</b> {resulting_stock}"
        )
        btn_ok = dialog.addButton("Confirmar", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        return dialog.clickedButton() == btn_ok

    def _launch_injection(self, product: Product, quantity: int) -> None:
        """Confirma con el usuario y lanza UpdateStockWorker para incrementar el stock.

        Args:
            product: Producto a actualizar.
            quantity: Cantidad a agregar.
        """
        if not self._confirm_injection(product, quantity):
            return

        from src.infrastructure.ui.workers.product_worker import UpdateStockWorker

        worker = UpdateStockWorker(
            self._session_factory, product.id, "increment", quantity
        )
        worker.stock_updated.connect(self._presenter.on_stock_injected)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
