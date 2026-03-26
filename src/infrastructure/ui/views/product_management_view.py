"""Vista de gestión de productos (pestaña QWidget).

Vive dentro del QTabWidget de MainWindow como tab "Productos (F5)".
Implementa IProductManagementView. Layout construido por código (sin .ui file).

Layout:
    QHBoxLayout raíz
    ├── Panel izquierdo (~280px)
    │   ├── QLineEdit _search_input  ("Buscar…")
    │   ├── QListWidget _product_list
    │   └── QPushButton _btn_new ("+ Nuevo")
    └── Panel derecho
        ├── QGroupBox "Datos"
        │   ├── QLineEdit _field_barcode
        │   ├── QLineEdit _field_name
        │   ├── QComboBox _combo_category
        │   ├── QLineEdit _field_stock
        │   └── QLineEdit _field_min_stock
        ├── QGroupBox "Precios"
        │   ├── QLineEdit _field_cost
        │   ├── QDoubleSpinBox _spin_margin  (0–9999.99, step 0.5)
        │   └── QLineEdit _field_final_price (editable — Caso B)
        ├── QLabel _status_label
        └── QHBoxLayout botones
            ├── QPushButton _btn_save ("Guardar  F5")
            └── QPushButton _btn_delete ("Eliminar")
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.category import Category
from src.domain.models.product import Product


class ProductManagementView(QWidget):
    """Vista de gestión de productos como QWidget pestaña.

    Implementa IProductManagementView. La lógica de presentación está
    delegada al ProductPresenter, inyectado mediante set_presenter().

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
        self._build_ui()

    def set_presenter(self, presenter) -> None:
        """Inyecta el ProductPresenter y conecta las señales Qt.

        Args:
            presenter: ProductPresenter ya configurado con esta vista.
        """
        self._presenter = presenter
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._product_list.currentItemChanged.connect(self._on_product_item_changed)
        self._btn_new.clicked.connect(self._on_new_clicked)
        self._field_cost.textChanged.connect(self._on_cost_changed)
        self._spin_margin.valueChanged.connect(self._on_margin_changed)
        self._field_final_price.textChanged.connect(self._on_final_price_changed)
        self._btn_save.clicked.connect(self._on_save_clicked)
        self._btn_delete.clicked.connect(self._on_delete_clicked)

    # ------------------------------------------------------------------
    # IProductManagementView implementation
    # ------------------------------------------------------------------

    def show_product_list(self, products: list[Product]) -> None:
        """Puebla la lista lateral con todos los productos.

        Args:
            products: Lista de productos a mostrar.
        """
        self._product_list.clear()
        for product in products:
            item = QListWidgetItem(product.name)
            item.setData(Qt.UserRole, product)
            self._product_list.addItem(item)

    def show_product_in_form(self, product: Product, categories: list[Category]) -> None:
        """Carga los datos de un producto en el formulario.

        Args:
            product: Producto a mostrar.
            categories: Lista de categorías para el combo.
        """
        self._field_barcode.setText(product.barcode)
        self._field_name.setText(product.name)
        self._field_stock.setText(str(product.stock))
        self._field_min_stock.setText(str(product.min_stock))

        self._field_cost.blockSignals(True)
        self._field_cost.setText(str(product.current_cost))
        self._field_cost.blockSignals(False)

        # Poblar combo de categorías
        self._combo_category.blockSignals(True)
        self._combo_category.clear()
        self._combo_category.addItem("(sin categoría)", None)
        for cat in categories:
            self._combo_category.addItem(cat.name, cat.id)
        if product.category_id is not None:
            idx = self._combo_category.findData(product.category_id)
            if idx >= 0:
                self._combo_category.setCurrentIndex(idx)
        self._combo_category.blockSignals(False)

        self._spin_margin.blockSignals(True)
        self._spin_margin.setValue(float(product.margin_percent))
        self._spin_margin.blockSignals(False)

        self._field_final_price.blockSignals(True)
        self._field_final_price.setText(str(product.current_price.amount))
        self._field_final_price.blockSignals(False)

    def clear_form(self) -> None:
        """Limpia todos los campos del formulario para un nuevo producto."""
        self._field_barcode.clear()
        self._field_name.clear()
        self._field_stock.setText("0")
        self._field_min_stock.setText("0")

        self._field_cost.blockSignals(True)
        self._field_cost.setText("0")
        self._field_cost.blockSignals(False)

        self._combo_category.blockSignals(True)
        self._combo_category.clear()
        self._combo_category.addItem("(sin categoría)", None)
        self._combo_category.blockSignals(False)

        self._spin_margin.blockSignals(True)
        self._spin_margin.setValue(0.0)
        self._spin_margin.blockSignals(False)

        self._field_final_price.blockSignals(True)
        self._field_final_price.clear()
        self._field_final_price.blockSignals(False)

        self._status_label.setText("")

    def set_final_price_display(self, price: Decimal) -> None:
        """Actualiza el campo de precio final sin disparar señales.

        Args:
            price: Precio calculado a mostrar.
        """
        self._field_final_price.blockSignals(True)
        self._field_final_price.setText(str(price))
        self._field_final_price.blockSignals(False)

    def set_margin_display(self, margin: Decimal) -> None:
        """Actualiza el campo de margen sin disparar señales.

        Args:
            margin: Margen calculado a mostrar.
        """
        self._spin_margin.blockSignals(True)
        self._spin_margin.setValue(float(margin))
        self._spin_margin.blockSignals(False)

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

    def show_delete_confirmation(self, product_name: str) -> bool:
        """Muestra un diálogo de confirmación antes de eliminar.

        Args:
            product_name: Nombre del producto a eliminar.

        Returns:
            True si el usuario confirmó la eliminación.
        """
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Confirmar eliminación")
        dialog.setText(f"¿Está seguro que desea eliminar '{product_name}'?")
        btn_delete = dialog.addButton("Eliminar", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        return dialog.clickedButton() == btn_delete

    def set_save_button_enabled(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón Guardar.

        Args:
            enabled: True para habilitar.
        """
        self._btn_save.setEnabled(enabled)

    def set_delete_button_enabled(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón Eliminar.

        Args:
            enabled: True para habilitar.
        """
        self._btn_delete.setEnabled(enabled)

    def get_form_data(self) -> dict:
        """Retorna los datos actuales del formulario.

        Returns:
            Dict con claves: barcode, name, category_id, stock, min_stock,
            cost, margin, final_price.
        """
        return {
            "barcode": self._field_barcode.text().strip(),
            "name": self._field_name.text().strip(),
            "category_id": self._combo_category.currentData(),
            "stock": self._field_stock.text().strip() or "0",
            "min_stock": self._field_min_stock.text().strip() or "0",
            "cost": self._field_cost.text().strip() or "0",
            "margin": self._spin_margin.value(),
            "final_price": self._field_final_price.text().strip() or "0",
        }

    def on_view_activated(self) -> None:
        """Llamado por MainWindow al activar esta pestaña; lanza ListAllProductsWorker."""
        if self._presenter is None:
            return
        self._presenter.on_view_activated()
        self._launch_list_all_worker()

    # ------------------------------------------------------------------
    # Construcción interna del UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout completo de la vista programáticamente."""
        from src.infrastructure.ui.theme import PALETTE

        outer = QVBoxLayout(self)
        outer.setSpacing(8)
        outer.setContentsMargins(12, 12, 12, 12)

        # --- Texto descriptivo ---
        info = QLabel(
            "<b>Inventario</b> — Consulta, crea, edita y elimina productos del catálogo.<br>"
            "<span style='color:#0369a1;'>"
            "<b>Buscar:</b> filtra por nombre en tiempo real. "
            "<b>+ Nuevo:</b> limpia el formulario para agregar un producto. "
            "<b>Guardar (F5):</b> guarda los cambios. "
            "<b>Eliminar:</b> borra el producto seleccionado."
            "</span>"
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"background:{PALETTE.info_surface}; border:1px solid {PALETTE.info_border};"
            f" border-radius:6px; padding:8px 10px; color:{PALETTE.info_text}; font-size:12px;"
        )
        outer.addWidget(info)

        root = QHBoxLayout()
        root.setSpacing(12)
        outer.addLayout(root, stretch=1)

        # --- Panel izquierdo ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Buscar…")
        self._search_input.setFixedWidth(260)
        left_panel.addWidget(self._search_input)

        self._product_list = QListWidget()
        self._product_list.setFixedWidth(260)
        self._product_list.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        left_panel.addWidget(self._product_list)

        self._btn_new = QPushButton("+ Nuevo")
        self._btn_new.setFixedWidth(260)
        left_panel.addWidget(self._btn_new)

        root.addLayout(left_panel)

        # --- Panel derecho ---
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # QGroupBox Datos
        data_group = QGroupBox("Datos")
        data_form = QFormLayout(data_group)
        data_form.setSpacing(6)

        self._field_barcode = QLineEdit()
        self._field_barcode.setPlaceholderText("EAN-13 / código interno")
        data_form.addRow("Código de barras:", self._field_barcode)

        self._field_name = QLineEdit()
        self._field_name.setPlaceholderText("Nombre del producto")
        data_form.addRow("Nombre:", self._field_name)

        self._combo_category = QComboBox()
        self._combo_category.addItem("(sin categoría)", None)
        data_form.addRow("Categoría:", self._combo_category)

        self._field_stock = QLineEdit()
        self._field_stock.setText("0")
        self._field_stock.setPlaceholderText("0")
        data_form.addRow("Stock:", self._field_stock)

        self._field_min_stock = QLineEdit()
        self._field_min_stock.setText("0")
        self._field_min_stock.setPlaceholderText("0")
        data_form.addRow("Stock mínimo:", self._field_min_stock)

        right_panel.addWidget(data_group)

        # QGroupBox Precios
        price_group = QGroupBox("Precios")
        price_form = QFormLayout(price_group)
        price_form.setSpacing(6)

        self._field_cost = QLineEdit()
        self._field_cost.setPlaceholderText("0.00")
        price_form.addRow("Costo (ARS):", self._field_cost)

        self._spin_margin = QDoubleSpinBox()
        self._spin_margin.setRange(0.0, 9999.99)
        self._spin_margin.setSingleStep(0.5)
        self._spin_margin.setDecimals(2)
        self._spin_margin.setSuffix(" %")
        price_form.addRow("Margen:", self._spin_margin)

        self._field_final_price = QLineEdit()
        self._field_final_price.setPlaceholderText("0.00")
        price_form.addRow("Precio final (ARS):", self._field_final_price)

        right_panel.addWidget(price_group)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_panel.addWidget(self._status_label)

        right_panel.addStretch()

        # Botones Guardar / Eliminar
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_save = QPushButton("Guardar  F5")
        self._btn_save.setFixedHeight(40)
        btn_row.addWidget(self._btn_save)

        self._btn_delete = QPushButton("Eliminar")
        self._btn_delete.setFixedHeight(40)
        self._btn_delete.setEnabled(False)
        btn_row.addWidget(self._btn_delete)

        right_panel.addLayout(btn_row)
        root.addLayout(right_panel)

    # ------------------------------------------------------------------
    # Handlers Qt internos
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, text: str) -> None:
        """Filtra la lista de productos localmente según el texto de búsqueda."""
        text_lower = text.lower()
        for i in range(self._product_list.count()):
            item = self._product_list.item(i)
            if item is not None:
                item.setHidden(text_lower not in item.text().lower())

    def _on_product_item_changed(self, current, _previous) -> None:
        """Usuario seleccionó un ítem en la lista; lanza LoadProductWorker."""
        if current is None or self._presenter is None:
            return
        product = current.data(Qt.UserRole)
        if product is None or product.id is None:
            return
        self._presenter.on_product_selected(product.id)
        self._launch_load_product_worker(product.id)

    def _on_new_clicked(self) -> None:
        """Botón '+ Nuevo': limpia selección en lista y notifica al presenter."""
        self._product_list.clearSelection()
        if self._presenter:
            self._presenter.on_new_product_requested()

    def _on_cost_changed(self, text: str) -> None:
        """Campo costo modificado: notifica al presenter."""
        if self._presenter:
            self._presenter.on_cost_changed(text)

    def _on_margin_changed(self, value: float) -> None:
        """Spin de margen modificado: notifica al presenter."""
        if self._presenter:
            self._presenter.on_margin_changed(str(value))

    def _on_final_price_changed(self, text: str) -> None:
        """Campo precio final modificado: notifica al presenter."""
        if self._presenter:
            self._presenter.on_final_price_changed(text)

    def _on_save_clicked(self) -> None:
        """Botón Guardar: valida con presenter y lanza SaveProductWorker."""
        if self._presenter is None:
            return
        product = self._presenter.on_save_requested()
        if product is None:
            return
        self._launch_save_worker(product)

    def _on_delete_clicked(self) -> None:
        """Botón Eliminar: pide confirmación al presenter y lanza DeleteProductWorker."""
        if self._presenter is None:
            return
        confirmed = self._presenter.on_delete_requested()
        if not confirmed:
            return
        if self._presenter._selected_product is None:
            return
        product_id = self._presenter._selected_product.id
        if product_id is None:
            return
        self._launch_delete_worker(product_id)

    # ------------------------------------------------------------------
    # Creación de workers (UI responsable)
    # ------------------------------------------------------------------

    def _launch_list_all_worker(self) -> None:
        """Lanza ListAllProductsWorker y conecta sus señales."""
        from src.infrastructure.ui.workers.product_worker import ListAllProductsWorker

        worker = ListAllProductsWorker(self._session_factory)
        worker.products_loaded.connect(self._presenter.on_products_loaded)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _launch_load_product_worker(self, product_id: int) -> None:
        """Lanza LoadProductWorker para el producto dado.

        Args:
            product_id: ID del producto a cargar.
        """
        from src.infrastructure.ui.workers.product_worker import LoadProductWorker

        worker = LoadProductWorker(self._session_factory, product_id)
        worker.product_loaded.connect(self._presenter.on_product_fetched)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _launch_save_worker(self, product) -> None:
        """Lanza SaveProductWorker con el producto validado.

        Args:
            product: Entidad Product a persistir.
        """
        from src.infrastructure.ui.workers.product_worker import SaveProductWorker

        worker = SaveProductWorker(self._session_factory, product)
        worker.save_completed.connect(self._presenter.on_save_completed)
        worker.save_completed.connect(lambda _: self._launch_list_all_worker())
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _launch_delete_worker(self, product_id: int) -> None:
        """Lanza DeleteProductWorker para el producto dado.

        Args:
            product_id: ID del producto a eliminar.
        """
        from src.infrastructure.ui.workers.product_worker import DeleteProductWorker

        worker = DeleteProductWorker(self._session_factory, product_id)
        worker.delete_completed.connect(self._presenter.on_delete_completed)
        worker.delete_completed.connect(self._launch_list_all_worker)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
