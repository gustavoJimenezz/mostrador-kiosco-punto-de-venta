"""Ventana principal del punto de venta (PySide6).

Implementa ISaleView. Toda la lógica de presentación está delegada al
SalePresenter. Esta clase solo maneja Qt: carga el .ui, conecta señales
y gestiona los workers QThread para operaciones de DB.

Atajos de teclado (keyboard-first):
    F1  - Nueva venta (limpia carrito)
    F2  - Activar/desactivar búsqueda por nombre
    F4  - Confirmar venta / Cobrar
    F9  - Importar lista de precios CSV/Excel (importación masiva)
    F10 - Cierre de caja
    Esc - Cancelar búsqueda, volver al barcode_input
    Enter (en barcode_input)  - Buscar producto por código
    Enter (en search_results) - Agregar producto seleccionado al carrito
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.price import Price
from src.domain.models.product import Product
from src.domain.models.sale import PaymentMethod, Sale
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

        self._load_ui()
        self._setup_shortcuts()

    @property
    def import_view(self):
        """Retorna la instancia de ImportView (pestaña de importación).

        Returns:
            ImportView insertada en el tab "📥 Importar (F9)".
        """
        return self._import_view

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
        """Actualiza el label del total de la venta."""
        self._total_label.setText(f"TOTAL: ${total.amount:,.2f}")

    def show_search_results(self, products: list[Product]) -> None:
        """Muestra la lista de resultados de búsqueda por nombre."""
        self._search_results.clear()
        for product in products:
            item = QListWidgetItem(
                f"{product.name}  —  ${product.current_price.amount:,.2f}"
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

    def show_sale_confirmed(self, sale: Sale) -> None:
        """Muestra confirmación de venta exitosa y devuelve el foco al barcode."""
        self.statusBar().showMessage(
            f"✓ Venta #{str(sale.id)[:8]}... confirmada"
            f" — Total: ${sale.total_amount.amount:,.2f}",
            5000,
        )
        self._barcode_input.setFocus()

    def show_payment_dialog(self) -> Optional[PaymentMethod]:
        """Muestra el diálogo modal de selección de método de pago.

        Returns:
            PaymentMethod seleccionado, o None si se canceló.
        """
        return _PaymentDialog.select(self)

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
        tab_import = ui_widget.findChild(QWidget, "tab_import")
        self._import_view = ImportView()
        tab_layout = QVBoxLayout(tab_import)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(self._import_view)

        self._barcode_input = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit,
            "barcode_input",
        )
        self._search_input = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit,
            "search_input",
        )
        self._search_results = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QListWidget"]).QListWidget,
            "search_results",
        )
        self._cart_table = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QTableWidget"]).QTableWidget,
            "cart_table",
        )
        self._total_label = ui_widget.findChild(QLabel, "total_label")

        btn_new = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_new_sale",
        )
        btn_search = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_search",
        )
        btn_confirm = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_confirm",
        )
        btn_cash_close = ui_widget.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton,
            "btn_cash_close",
        )

        self._barcode_input.returnPressed.connect(self._on_barcode_entered)
        self._search_input.returnPressed.connect(self._on_search_by_name)
        self._search_results.itemActivated.connect(self._on_search_item_selected)
        btn_new.clicked.connect(self._on_new_sale)
        btn_search.clicked.connect(self._toggle_search)
        btn_confirm.clicked.connect(self._on_confirm_sale)
        btn_cash_close.clicked.connect(self._on_cash_close)

        self._barcode_input.setFocus()

    def _setup_shortcuts(self) -> None:
        """Registra los atajos de teclado globales F1-F10 y Escape."""
        QShortcut(QKeySequence("F1"), self).activated.connect(self._on_new_sale)
        QShortcut(QKeySequence("F2"), self).activated.connect(self._toggle_search)
        QShortcut(QKeySequence("F4"), self).activated.connect(self._on_confirm_sale)
        QShortcut(QKeySequence("F9"), self).activated.connect(self._on_open_import)
        QShortcut(QKeySequence("F10"), self).activated.connect(self._on_cash_close)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape)

    # ------------------------------------------------------------------
    # Handlers de eventos Qt (delegan toda lógica al presenter)
    # ------------------------------------------------------------------

    def _on_barcode_entered(self) -> None:
        """Enter en barcode_input: lanza SearchByBarcodeWorker."""
        barcode = self._barcode_input.text().strip()
        if not barcode or not self._presenter:
            return
        self._barcode_input.clear()

        worker = SearchByBarcodeWorker(self._session_factory, barcode)
        worker.product_found.connect(self._presenter.on_barcode_found)
        worker.not_found.connect(self._presenter.on_barcode_not_found)
        worker.error_occurred.connect(self._presenter.on_search_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_search_by_name(self) -> None:
        """Enter en search_input: lanza SearchByNameWorker."""
        query = self._search_input.text().strip()
        if not query or not self._presenter:
            return

        worker = SearchByNameWorker(self._session_factory, query)
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
        self._search_input.setVisible(False)
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

    def _on_open_import(self) -> None:
        """F9: navega al tab de importación masiva de lista de precios."""
        self._tab_widget.setCurrentIndex(1)

    def _on_cash_close(self) -> None:
        """F10: cierre de caja."""
        if self._presenter:
            self._presenter.on_cash_close()

    def _toggle_search(self) -> None:
        """F2: activa o desactiva el campo de búsqueda por nombre."""
        visible = not self._search_input.isVisible()
        self._search_input.setVisible(visible)
        if visible:
            self._search_input.setFocus()
            self._search_input.selectAll()
        else:
            self._search_results.setVisible(False)
            self._barcode_input.setFocus()

    def _on_escape(self) -> None:
        """Escape: cancela búsqueda y vuelve el foco al barcode_input."""
        self._search_input.setVisible(False)
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
                "Si sale ahora, los datos se perderán.\n"
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


class _PaymentDialog(QDialog):
    """Diálogo modal para seleccionar el método de pago.

    Keyboard-first: el cajero selecciona con flechas y confirma con Enter.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Método de Pago")
        self.setModal(True)
        self._selected: Optional[PaymentMethod] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Seleccione el método de pago:"))

        self._radio_cash = QRadioButton("Efectivo  (EFECTIVO)")
        self._radio_debit = QRadioButton("Débito  (DEBITO)")
        self._radio_transfer = QRadioButton("Transferencia / Mercado Pago  (TRANSFERENCIA)")
        self._radio_cash.setChecked(True)

        layout.addWidget(self._radio_cash)
        layout.addWidget(self._radio_debit)
        layout.addWidget(self._radio_transfer)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accepted)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accepted(self) -> None:
        if self._radio_cash.isChecked():
            self._selected = PaymentMethod.CASH
        elif self._radio_debit.isChecked():
            self._selected = PaymentMethod.DEBIT
        else:
            self._selected = PaymentMethod.TRANSFER
        self.accept()

    @classmethod
    def select(cls, parent=None) -> Optional[PaymentMethod]:
        """Muestra el diálogo y retorna el método seleccionado.

        Args:
            parent: QWidget padre para centrar el diálogo.

        Returns:
            PaymentMethod seleccionado, o None si se canceló.
        """
        dialog = cls(parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog._selected
        return None
