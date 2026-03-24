"""Ventana principal del punto de venta (PySide6).

Implementa ISaleView. Toda la lógica de presentación está delegada al
SalePresenter. Esta clase solo maneja Qt: carga el .ui, conecta señales
y gestiona los workers QThread para operaciones de DB.

Atajos de teclado (keyboard-first):
    F1  - Nueva venta (limpia carrito)
    F2  - Historial de ventas (listado por fecha con detalle de ítems)
    F4  - Confirmar venta / Cobrar
    F5  - Gestión de productos
    F6  - Editar stock
    F7  - Inyectar stock directamente
    F9  - Importar lista de precios CSV/Excel (importación masiva)
    F10 - Cierre de caja (abre modal)
    F12 - Cobrar en efectivo con diálogo de vuelto
    Supr - Eliminar producto seleccionado del carrito
    Esc - Ocultar resultados, volver al barcode_input
    Enter (en barcode_input)  - Si es dígito: busca por código; si no: busca por nombre
    Enter (en search_results) - Agregar producto seleccionado al carrito
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.price import Price
from src.domain.models.product import Product
from src.domain.models.sale import Sale
from src.infrastructure.ui.dialogs.change_dialog import ChangeDialog
from src.infrastructure.ui.dialogs.sale_receipt_dialog import SaleReceiptDialog
from src.infrastructure.ui.widgets.total_widget import TotalWidget
from src.infrastructure.ui.workers.db_worker import (
    ProcessSaleWorker,
    SearchByBarcodeWorker,
    SearchByNameWorker,
)

_UI_PATH = Path(__file__).parent / "main_window.ui"


class MainWindow(QMainWindow):
    """Ventana principal del POS. Implementa ISaleView.

    Carga la interfaz desde ``main_window.ui`` (Qt Designer) y conecta
    todos los widgets con el SalePresenter y los workers QThread.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
                         Se pasa a los workers para ejecutar DB en hilos separados.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._presenter = None
        self._active_workers: list = []
        self._elevate_use_case = None
        self._admin_btn = None  # se asigna en _load_ui

        self._load_ui()
        self._setup_shortcuts()

    @property
    def import_view(self):
        """Retorna la instancia de ImportView (pestaña de importación).

        Returns:
            ImportView insertada en el tab "📥 Importar (F9)".
        """
        return self._import_view

    @property
    def product_management_view(self):
        """Retorna la instancia de ProductManagementView (pestaña de productos).

        Returns:
            ProductManagementView insertada en el tab "Productos (F5)".
        """
        return self._product_management_view

    @property
    def stock_edit_view(self):
        """Retorna la instancia de StockEditView (pestaña de edición de stock).

        Returns:
            StockEditView insertada en el tab "Editar Stock (F6)".
        """
        return self._stock_edit_view

    @property
    def stock_inject_view(self):
        """Retorna la instancia de StockInjectView (pestaña de inyección de stock).

        Returns:
            StockInjectView insertada en el tab "Inyectar Stock (F7)".
        """
        return self._stock_inject_view

    def set_presenter(self, presenter) -> None:
        """Inyecta el SalePresenter en la ventana.

        Args:
            presenter: SalePresenter ya configurado con la vista.
        """
        self._presenter = presenter

    def set_import_presenter(self, presenter) -> None:
        """Inyecta el ImportPresenter en la ImportView.

        Args:
            presenter: ImportPresenter ya configurado con la ImportView.
        """
        self._import_view.set_presenter(presenter)

    def set_product_presenter(self, presenter) -> None:
        """Inyecta el ProductPresenter en la ProductManagementView.

        Args:
            presenter: ProductPresenter ya configurado con la vista.
        """
        self._product_management_view.set_presenter(presenter)

    def set_stock_edit_presenter(self, presenter) -> None:
        """Inyecta el StockEditPresenter en la StockEditView.

        Args:
            presenter: StockEditPresenter ya configurado con la vista.
        """
        self._stock_edit_view.set_presenter(presenter)

    def set_stock_inject_presenter(self, presenter) -> None:
        """Inyecta el StockInjectPresenter en la StockInjectView.

        Args:
            presenter: StockInjectPresenter ya configurado con la vista.
        """
        self._stock_inject_view.set_presenter(presenter)

    def set_cash_presenter(self, presenter) -> None:
        """Inyecta el CashPresenter en la CashCloseView.

        Args:
            presenter: CashPresenter ya configurado con la vista.
        """
        self._cash_close_view.set_presenter(presenter)

    def set_sales_history_presenter(self, presenter) -> None:
        """Inyecta el SalesHistoryPresenter en la SalesHistoryView.

        Args:
            presenter: SalesHistoryPresenter ya configurado con la vista.
        """
        self._sales_history_view.set_presenter(presenter)

    def set_cash_history_presenter(self, presenter) -> None:
        """Inyecta el CashHistoryPresenter en la CashHistoryView.

        Args:
            presenter: CashHistoryPresenter ya configurado con la vista.
        """
        self._cash_history_view.set_presenter(presenter)

    @property
    def cash_close_view(self):
        """Retorna la instancia de CashCloseView (pestaña F10)."""
        return self._cash_close_view

    @property
    def sales_history_view(self):
        """Retorna la instancia de SalesHistoryView (pestaña F2)."""
        return self._sales_history_view

    @property
    def cash_history_view(self):
        """Retorna la instancia de CashHistoryView (pestaña Historial de caja, solo ADMIN)."""
        return self._cash_history_view

    # ------------------------------------------------------------------
    # ISaleView implementation
    # ------------------------------------------------------------------

    def show_product_in_cart(self, product: Product, quantity: int) -> None:
        """Agrega o actualiza una fila en la tabla del carrito."""
        product_id = product.id
        for row in range(self._cart_table.rowCount()):
            name_item = self._cart_table.item(row, 0)
            if name_item and name_item.data(Qt.UserRole) == product_id:
                from PySide6.QtWidgets import QTableWidgetItem
                self._cart_table.setItem(row, 1, QTableWidgetItem(str(quantity)))
                subtotal = product.current_price * quantity
                self._cart_table.setItem(
                    row, 3, QTableWidgetItem(f"${subtotal.amount:,.2f}")
                )
                return

        from PySide6.QtWidgets import QTableWidgetItem
        row = self._cart_table.rowCount()
        self._cart_table.insertRow(row)

        name_item = QTableWidgetItem(product.name)
        name_item.setData(Qt.UserRole, product_id)
        self._cart_table.setItem(row, 0, name_item)
        self._cart_table.setItem(row, 1, QTableWidgetItem(str(quantity)))
        self._cart_table.setItem(
            row, 2, QTableWidgetItem(f"${product.current_price.amount:,.2f}")
        )
        subtotal = product.current_price * quantity
        self._cart_table.setItem(row, 3, QTableWidgetItem(f"${subtotal.amount:,.2f}"))

    def update_total(self, total: Price) -> None:
        """Actualiza el widget del total de la venta."""
        self._total_widget.set_total(total)

    def show_search_results(self, products: list[Product]) -> None:
        """Muestra la lista de resultados de búsqueda por nombre debajo del input."""
        self._search_results.clear()
        for product in products:
            item = QListWidgetItem(
                f"{product.name}  —  ${product.current_price.amount:,.2f}"
                f"  |  Stock: {product.stock}"
            )
            item.setData(Qt.UserRole, product)
            self._search_results.addItem(item)
        self._search_results.setVisible(True)
        self._search_results.setFocus()

    def clear_cart_display(self) -> None:
        """Limpia la tabla del carrito."""
        self._cart_table.setRowCount(0)

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error en la barra de estado (5 segundos)."""
        self.statusBar().showMessage(f"⚠ {message}", 5000)

    def show_stock_error(self, message: str) -> None:
        """Muestra un diálogo modal de error de stock.

        Interrumpe al cajero con un QMessageBox para que quede claro
        por qué el producto no se agregó al carrito.

        Args:
            message: Texto descriptivo del problema de stock.
        """
        QMessageBox.warning(self, "Sin stock", message)

    def show_sale_confirmed(self, sale: Sale) -> None:
        """Muestra el comprobante modal de venta y devuelve el foco al barcode."""
        cart = self._presenter.get_cart() if self._presenter else {}
        SaleReceiptDialog.show_receipt(sale, cart, self)
        self.statusBar().showMessage(
            f"✓ Venta #{str(sale.id)[:8]}... confirmada"
            f" — Total: ${sale.total_amount.amount:,.2f}",
            5000,
        )
        self._barcode_input.setFocus()

    def show_change_dialog(self, total: Price) -> bool:
        """Muestra el diálogo de vuelto para pago en efectivo (F12).

        Args:
            total: Monto total de la venta a cobrar.

        Returns:
            True si el cajero confirmó el cobro, False si canceló.
        """
        return ChangeDialog.show_and_confirm(total, self)

    # ------------------------------------------------------------------
    # Configuración interna
    # ------------------------------------------------------------------

    def _load_ui(self) -> None:
        """Carga el archivo .ui de Qt Designer y extrae los widgets."""
        from src.infrastructure.ui.views.import_view import ImportView

        loader = QUiLoader()
        ui_widget = loader.load(str(_UI_PATH), self)

        if ui_widget is None:
            raise RuntimeError(f"No se pudo cargar la interfaz: {_UI_PATH}")

        # El root del .ui es QWidget (central_widget); lo usamos directamente.
        self.setCentralWidget(ui_widget)
        self.setWindowTitle("Mostrador POS")
        self.resize(960, 640)

        # Extraer QTabWidget e insertar ImportView en el tab placeholder
        self._tab_widget = ui_widget.findChild(QTabWidget, "tab_widget")

        # Corner widget: indicador de caja + botones (esquina superior derecha).
        from PySide6.QtWidgets import QHBoxLayout as _QHBoxLayout
        from PySide6.QtWidgets import QPushButton as _QPushButton

        _corner = QWidget()
        _corner_layout = _QHBoxLayout(_corner)
        _corner_layout.setContentsMargins(0, 0, 4, 0)
        _corner_layout.setSpacing(6)

        # Label de estado de caja (visible solo cuando hay caja abierta)
        self._cash_status_label = QLabel("🟢 Caja abierta")
        self._cash_status_label.setStyleSheet(
            "color: #059669; font-size: 12px; font-weight: bold;"
            "padding: 4px 8px; background: #d1fae5; border-radius: 5px;"
        )
        self._cash_status_label.setVisible(False)
        _corner_layout.addWidget(self._cash_status_label)

        # Botón para abrir caja (visible solo cuando NO hay caja abierta)
        self._open_cash_btn = _QPushButton("Abrir caja")
        self._open_cash_btn.clicked.connect(self._on_open_cash_clicked)
        self._open_cash_btn.setStyleSheet(
            "QPushButton { padding: 4px 12px; border-radius: 5px;"
            "background: #ca8a04; color: white; border: none; font-size: 12px; }"
            "QPushButton:hover { background: #a16207; }"
        )
        _corner_layout.addWidget(self._open_cash_btn)

        self._cash_close_btn = _QPushButton("Cierre de caja")
        self._cash_close_btn.clicked.connect(self._on_cash_close)
        self._cash_close_btn.setStyleSheet(
            "QPushButton { padding: 4px 12px; border-radius: 5px;"
            "background: #0f766e; color: white; border: none; font-size: 12px; }"
            "QPushButton:hover { background: #0d9488; }"
        )
        _corner_layout.addWidget(self._cash_close_btn)

        self._admin_btn = _QPushButton("🔒 Administrador")
        self._admin_btn.clicked.connect(self._on_admin_access_requested)
        _corner_layout.addWidget(self._admin_btn)

        self._tab_widget.setCornerWidget(_corner)

        tab_import = ui_widget.findChild(QWidget, "tab_import")
        self._import_view = ImportView()
        tab_layout = QVBoxLayout(tab_import)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(self._import_view)

        # Tab 2: Gestión de Productos (F5) — construido programáticamente
        from src.infrastructure.ui.views.product_management_view import (
            ProductManagementView,
        )

        self._product_management_view = ProductManagementView(
            session_factory=self._session_factory
        )
        self._tab_widget.addTab(self._product_management_view, "Productos (F5)")

        # Tab 3: Editar Stock (F6) — construido programáticamente
        from src.infrastructure.ui.views.stock_edit_view import StockEditView

        self._stock_edit_view = StockEditView(session_factory=self._session_factory)
        self._tab_widget.addTab(self._stock_edit_view, "Editar Stock (F6)")

        # Tab 4: Inyectar Stock (F7) — construido programáticamente
        from src.infrastructure.ui.views.stock_inject_view import StockInjectView

        self._stock_inject_view = StockInjectView(session_factory=self._session_factory)
        self._tab_widget.addTab(self._stock_inject_view, "Inyectar Stock (F7)")

        # Tab 5: Historial de ventas (F2) — construido programáticamente
        from src.infrastructure.ui.views.sales_history_view import SalesHistoryView

        self._sales_history_view = SalesHistoryView(
            session_factory=self._session_factory
        )
        self._tab_widget.addTab(self._sales_history_view, "Historial (F2)")

        # Tab 6: Historial de cierres de caja (solo ADMIN) — construido programáticamente
        from src.infrastructure.ui.views.cash_history_view import CashHistoryView

        self._cash_history_view = CashHistoryView(
            session_factory=self._session_factory
        )
        self._tab_widget.addTab(self._cash_history_view, "Historial de caja")

        # Diálogo modal de cierre de caja (F10) — no es una pestaña
        from src.infrastructure.ui.dialogs.cash_close_dialog import CashCloseDialog

        self._cash_close_dialog = CashCloseDialog(
            session_factory=self._session_factory, parent=self
        )
        self._cash_close_view = self._cash_close_dialog.cash_close_view
        self._cash_close_view.set_session_changed_callback(self._on_cash_session_changed)

        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        # Carga el estado inicial de la caja para actualizar el indicador del corner.
        self._load_initial_cash_state()

        self._barcode_input = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit,
            "barcode_input",
        )
        self._search_results = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QListWidget"]).QListWidget,
            "search_results",
        )
        self._cart_table = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QTableWidget"]).QTableWidget,
            "cart_table",
        )
        original_total_label = ui_widget.findChild(QLabel, "total_label")
        self._total_widget = TotalWidget()
        self._total_widget.setObjectName("total_label")
        if original_total_label is not None:
            parent_layout = original_total_label.parent().layout()
            if parent_layout is not None:
                parent_layout.replaceWidget(original_total_label, self._total_widget)
            original_total_label.setParent(None)
        self._total_widget.set_total(Price("0"))

        btn_new = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_new_sale",
        )
        btn_confirm = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_confirm",
        )
        btn_cash_close = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_cash_close",
        )

        btn_delete_item = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_delete_item",
        )

        self._barcode_input.returnPressed.connect(self._on_barcode_entered)
        self._search_results.itemActivated.connect(self._on_search_item_selected)
        btn_new.clicked.connect(self._on_new_sale)
        btn_confirm.clicked.connect(self._on_confirm_sale)
        btn_cash_close.clicked.connect(self._on_cash_close)
        btn_delete_item.clicked.connect(self._on_cart_delete_key)
        self._cart_table.installEventFilter(self)

        # Bloquear tabs de admin DESPUÉS de haberlos agregado al tab widget.
        self._lock_admin_tabs()

        self._barcode_input.setFocus()

    def _load_initial_cash_state(self) -> None:
        """Consulta la DB en un worker para conocer si hay caja abierta al arrancar."""
        from datetime import date as _date

        from src.infrastructure.ui.workers.cash_worker import LoadCashStateWorker

        worker = LoadCashStateWorker(self._session_factory, _date.today())
        worker.state_loaded.connect(
            lambda state: self._on_cash_session_changed(state.get("cash_close") is not None)
        )
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_cash_session_changed(self, is_open: bool) -> None:
        """Actualiza el indicador y el botón de apertura según el estado de la caja.

        Args:
            is_open: True si hay arqueo abierto, False si está cerrado.
        """
        self._cash_status_label.setVisible(is_open)
        self._open_cash_btn.setVisible(not is_open)

    def _on_open_cash_clicked(self) -> None:
        """Botón 'Abrir caja': solicita el monto inicial y lanza el worker de apertura."""
        from decimal import Decimal

        from PySide6.QtWidgets import QInputDialog

        from src.infrastructure.ui.workers.cash_worker import OpenCashCloseWorker

        amount, ok = QInputDialog.getDouble(
            self,
            "Abrir caja",
            "Monto inicial ($):",
            value=0.0,
            min=0.0,
            max=999999.99,
            decimals=2,
        )
        if not ok:
            return

        worker = OpenCashCloseWorker(self._session_factory, Decimal(str(amount)))
        worker.opened.connect(lambda _cc: self._on_cash_session_changed(True))
        worker.opened.connect(
            lambda _cc: self.statusBar().showMessage("✓ Caja abierta correctamente.", 4000)
        )
        worker.error_occurred.connect(
            lambda msg: self.statusBar().showMessage(f"⚠ {msg}", 5000)
        )
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def set_elevate_use_case(self, use_case) -> None:
        """Inyecta el caso de uso ElevateToAdmin.

        Args:
            use_case: Instancia de ElevateToAdmin ya configurada.
        """
        self._elevate_use_case = use_case

    # Índices de las pestañas exclusivas de administrador.
    _ADMIN_TAB_INDICES = [1, 2, 3, 4, 6]

    def _lock_admin_tabs(self) -> None:
        """Oculta las pestañas de administrador y muestra el botón de acceso bloqueado."""
        for index in self._ADMIN_TAB_INDICES:
            self._tab_widget.setTabVisible(index, False)
        self._admin_btn.setText("🔒 Administrador")
        self._admin_btn.setStyleSheet(
            "QPushButton { padding: 4px 12px; border-radius: 5px;"
            "background: #e2e8f0; color: #475569; border: none; font-size: 12px; }"
            "QPushButton:hover { background: #cbd5e1; }"
        )

    def _unlock_admin_tabs(self) -> None:
        """Muestra las pestañas de administrador y actualiza el botón a desbloqueado."""
        for index in self._ADMIN_TAB_INDICES:
            self._tab_widget.setTabVisible(index, True)
        self._admin_btn.setText("🔓 Administrador")
        self._admin_btn.setStyleSheet(
            "QPushButton { padding: 4px 12px; border-radius: 5px;"
            "background: #4f46e5; color: white; border: none; font-size: 12px; }"
            "QPushButton:hover { background: #4338ca; }"
        )

    def _setup_shortcuts(self) -> None:
        """Registra los atajos de teclado globales F1-F12 y Escape."""
        QShortcut(QKeySequence("F1"), self).activated.connect(self._on_new_sale)
        QShortcut(QKeySequence("F2"), self).activated.connect(self._toggle_search)
        QShortcut(QKeySequence("F4"), self).activated.connect(self._on_confirm_sale)
        QShortcut(QKeySequence("F5"), self).activated.connect(self._on_open_products)
        QShortcut(QKeySequence("F6"), self).activated.connect(self._on_open_stock_edit)
        QShortcut(QKeySequence("F7"), self).activated.connect(self._on_open_stock_inject)
        QShortcut(QKeySequence("F9"), self).activated.connect(self._on_open_import)
        QShortcut(QKeySequence("F10"), self).activated.connect(self._on_cash_close)
        QShortcut(QKeySequence("F12"), self).activated.connect(self._on_cash_payment)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape)

    # ------------------------------------------------------------------
    # Handlers de eventos Qt (delegan toda lógica al presenter)
    # ------------------------------------------------------------------

    def _on_admin_access_requested(self) -> None:
        """Muestra el diálogo de PIN de administrador y desbloquea las pestañas si es correcto."""
        from src.infrastructure.ui.dialogs.admin_pin_dialog import AdminPinDialog

        dialog = AdminPinDialog(parent=self)
        while True:
            result = dialog.exec()
            if result != QDialog.DialogCode.Accepted:
                return
            if not hasattr(self, "_elevate_use_case") or self._elevate_use_case is None:
                return
            if self._elevate_use_case.execute(dialog.pin):
                self._unlock_admin_tabs()
                return
            dialog.show_error("PIN incorrecto. Intentá de nuevo.")

    def _on_barcode_entered(self) -> None:
        """Enter en barcode_input: auto-detecta tipo y lanza el worker correspondiente.

        Si el texto es puramente numérico lanza ``SearchByBarcodeWorker``;
        en caso contrario lanza ``SearchByNameWorker`` para búsqueda por nombre.
        """
        text = self._barcode_input.text().strip()
        if not text or not self._presenter:
            return

        self._search_results.setVisible(False)

        if text.isdigit():
            self._barcode_input.clear()
            worker = SearchByBarcodeWorker(self._session_factory, text)
            worker.product_found.connect(self._presenter.on_barcode_found)
            worker.not_found.connect(self._presenter.on_barcode_not_found)
            worker.error_occurred.connect(self._presenter.on_search_error)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            self._active_workers.append(worker)
            worker.start()
        else:
            worker = SearchByNameWorker(self._session_factory, text)
            worker.results_ready.connect(self._presenter.on_search_results_ready)
            worker.error_occurred.connect(self._presenter.on_search_error)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            self._active_workers.append(worker)
            worker.start()

    def _on_search_item_selected(self, item: QListWidgetItem) -> None:
        """Enter/doble clic en search_results: agrega producto al carrito."""
        product = item.data(Qt.UserRole)
        if product and self._presenter:
            self._presenter.on_product_selected_from_list(product)
        self._search_results.setVisible(False)
        self._barcode_input.clear()
        self._barcode_input.setFocus()

    def _on_new_sale(self) -> None:
        """F1: nueva venta."""
        if self._presenter:
            self._presenter.on_new_sale()
        self._barcode_input.setFocus()

    def _on_confirm_sale(self) -> None:
        """F4: confirmar venta. Solicita método de pago y lanza ProcessSaleWorker."""
        if not self._presenter:
            return

        payment_method = self._presenter.on_confirm_sale_requested()
        if payment_method is None:
            return

        cart = self._presenter.get_cart()
        worker = ProcessSaleWorker(self._session_factory, cart, payment_method)
        worker.sale_completed.connect(self._presenter.on_sale_completed)
        worker.error_occurred.connect(self._presenter.on_sale_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_open_products(self) -> None:
        """F5: navega al tab de gestión de productos (solo ADMIN)."""
        from src.infrastructure.ui.session import AppSession

        if not AppSession.is_admin():
            return
        self._tab_widget.setCurrentIndex(2)
        self._product_management_view.on_view_activated()

    def _on_open_stock_edit(self) -> None:
        """F6: navega al tab de edición de stock (solo ADMIN)."""
        from src.infrastructure.ui.session import AppSession

        if not AppSession.is_admin():
            return
        self._tab_widget.setCurrentIndex(3)
        self._stock_edit_view.on_view_activated()

    def _on_open_stock_inject(self) -> None:
        """F7: navega al tab de inyección directa de stock (solo ADMIN)."""
        from src.infrastructure.ui.session import AppSession

        if not AppSession.is_admin():
            return
        self._tab_widget.setCurrentIndex(4)
        self._stock_inject_view.on_view_activated()

    def _on_open_import(self) -> None:
        """F9: navega al tab de importación masiva de lista de precios (solo ADMIN)."""
        from src.infrastructure.ui.session import AppSession

        if not AppSession.is_admin():
            return
        self._tab_widget.setCurrentIndex(1)

    def _on_tab_changed(self, index: int) -> None:
        """Dispara on_view_activated al cambiar al tab de productos o stock.

        Args:
            index: Índice del tab activado.
        """
        if index == 2:
            self._product_management_view.on_view_activated()
        elif index == 3:
            self._stock_edit_view.on_view_activated()
        elif index == 4:
            self._stock_inject_view.on_view_activated()
        elif index == 5:
            self._sales_history_view.on_view_activated()
        elif index == 6:
            self._cash_history_view.on_view_activated()

    def _on_cash_close(self) -> None:
        """F10 / botón Cierre de caja: abre el modal de arqueo."""
        self._cash_close_dialog.open_and_activate()

    def _on_cash_payment(self) -> None:
        """F12: finalización de venta en efectivo con diálogo de vuelto."""
        if not self._presenter:
            return

        payment_method = self._presenter.on_cash_payment_requested()
        if payment_method is None:
            return

        cart = self._presenter.get_cart()
        worker = ProcessSaleWorker(self._session_factory, cart, payment_method)
        worker.sale_completed.connect(self._presenter.on_sale_completed)
        worker.error_occurred.connect(self._presenter.on_sale_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def eventFilter(self, obj, event) -> bool:
        """Captura Delete sobre cart_table para eliminar el ítem seleccionado.

        Args:
            obj: Objeto que generó el evento.
            event: Evento Qt recibido.

        Returns:
            True si el evento fue consumido, False para propagación normal.
        """
        if obj is self._cart_table and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                self._on_cart_delete_key()
                return True
        return super().eventFilter(obj, event)

    def _on_cart_delete_key(self) -> None:
        """Elimina del carrito el producto de la fila seleccionada (tecla Supr)."""
        if not self._presenter:
            return
        row = self._cart_table.currentRow()
        if row < 0:
            return
        name_item = self._cart_table.item(row, 0)
        if name_item:
            product_id = name_item.data(Qt.UserRole)
            self._presenter.on_remove_selected_item(product_id)

    def _toggle_search(self) -> None:
        """F2: navega al tab de historial de ventas."""
        self._tab_widget.setCurrentIndex(5)
        self._sales_history_view.on_view_activated()

    def _on_escape(self) -> None:
        """Escape: oculta resultados y devuelve el foco al barcode_input."""
        self._search_results.setVisible(False)
        self._barcode_input.setFocus()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Intercepta el cierre para requerir confirmación explícita del usuario.

        Muestra un QMessageBox de tipo Warning con botones "Salir" y "Cancelar".
        Si hay una venta en curso, el mensaje advierte sobre pérdida de datos.
        Toda ruta de cierre (Alt+F4, botón X, sys.exit) pasa por este modal.

        Args:
            event: Evento de cierre Qt. Se acepta o ignora según la elección.
        """
        sale_in_progress = (
            self._presenter.has_active_sale_items() if self._presenter else False
        )

        if sale_in_progress:
            message = (
                "Hay una venta en curso. "
                "Se guardará automáticamente y se restaurará al volver a abrir el sistema.\n"
                "¿Desea salir de todos modos?"
            )
        else:
            message = "¿Está seguro que desea salir del sistema?"

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Confirmar cierre")
        dialog.setText(message)

        btn_exit = dialog.addButton("Salir", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()

        if dialog.clickedButton() == btn_exit:
            self._shutdown_database()
            event.accept()
        else:
            event.ignore()
            self._restore_barcode_focus()

    def _shutdown_database(self) -> None:
        """Detiene el motor de base de datos si está activo.

        Invoca el shutdown del DatabaseLauncher solo si fue inyectado
        previamente mediante ``self._db_launcher``.
        """
        if hasattr(self, "_db_launcher"):
            self._db_launcher.stop()

    def _restore_barcode_focus(self) -> None:
        """Devuelve el foco al campo de lectura de código de barras.

        Llamado tras cancelar el modal de cierre para evitar que el lector
        de barras pierda caracteres al retornar el foco a la ventana.
        """
        self._barcode_input.setFocus()

    def _cleanup_worker(self, worker) -> None:
        """Elimina un worker completado de la lista de activos."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)


