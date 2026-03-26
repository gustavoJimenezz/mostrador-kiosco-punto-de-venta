"""Vista de gestión de categorías — CRUD (pestaña solo ADMIN).

Permite crear, renombrar y eliminar categorías del catálogo.
Layout construido por código (sin .ui file).

Layout:
    QHBoxLayout raíz
    ├── Panel izquierdo (ancho fijo 260 px)
    │   ├── QLabel "Categorías"
    │   ├── QListWidget _list_widget  (una fila por categoría)
    │   └── QPushButton "Nueva categoría"  _btn_new
    └── Panel derecho
        ├── QGroupBox "Detalle"
        │   ├── QLabel + QLineEdit _input_name
        │   ├── QPushButton "Guardar"   _btn_save   (primary)
        │   └── QPushButton "Eliminar"  _btn_delete (danger)
        └── QLabel _status_label
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
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.category import Category
from src.infrastructure.ui.theme import (
    PALETTE as _PALETTE,
    get_btn_danger_stylesheet,
    get_btn_primary_stylesheet,
    get_btn_secondary_stylesheet,
)

_PANEL_LEFT_WIDTH = 260


class CategoryManagementView(QWidget):
    """Vista CRUD de categorías (solo ADMIN).

    Implementa ICategoryManagementView. Toda la lógica de presentación está
    delegada al CategoryPresenter. Esta clase solo gestiona Qt.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._presenter = None
        self._active_workers: list = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Inyección del presenter
    # ------------------------------------------------------------------

    def set_presenter(self, presenter) -> None:
        """Inyecta el CategoryPresenter.

        Args:
            presenter: CategoryPresenter configurado con esta vista.
        """
        self._presenter = presenter

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout horizontal: lista de categorías + formulario."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # --- Texto descriptivo ---
        info = QLabel(
            "<b>Categorías</b> — Administra las categorías del catálogo de productos "
            "(crear, renombrar, eliminar).<br>"
            "<span style='color:#0369a1;'>"
            "<b>+ Nueva categoría:</b> abre el formulario vacío para crear una nueva. "
            "Seleccioná una de la lista para <b>editar</b> su nombre o <b>eliminarla</b>."
            "</span>"
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"background:{_PALETTE.info_surface}; border:1px solid {_PALETTE.info_border};"
            f" border-radius:6px; padding:8px 10px; color:{_PALETTE.info_text}; font-size:12px;"
        )
        outer.addWidget(info)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(self._build_left_panel())
        row.addWidget(self._build_right_panel(), stretch=1)
        outer.addLayout(row, stretch=1)

    def _build_left_panel(self) -> QWidget:
        """Construye el panel izquierdo con la lista de categorías."""
        panel = QWidget()
        panel.setFixedWidth(_PANEL_LEFT_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Categorías")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #374151;")
        layout.addWidget(title)

        self._list_widget = QListWidget()
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background: #ffffff;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                color: #374151;
            }
            QListWidget::item:hover {
                background: #eef2ff;
                color: #4f46e5;
            }
            QListWidget::item:selected {
                background: #eef2ff;
                color: #4f46e5;
                font-weight: bold;
            }
        """)
        self._list_widget.currentItemChanged.connect(self._on_list_selection_changed)
        layout.addWidget(self._list_widget, stretch=1)

        self._btn_new = QPushButton("+ Nueva categoría")
        self._btn_new.setStyleSheet(get_btn_secondary_stylesheet())
        self._btn_new.clicked.connect(self._on_new_clicked)
        layout.addWidget(self._btn_new)

        return panel

    def _build_right_panel(self) -> QWidget:
        """Construye el panel derecho con el formulario de detalle."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── GroupBox "Detalle" ─────────────────────────────────────────
        self._group_box = QGroupBox("Nueva categoría")
        self._group_box.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                color: #374151;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 8px;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)
        form_layout = QVBoxLayout(self._group_box)
        form_layout.setSpacing(10)

        lbl_name = QLabel("Nombre")
        lbl_name.setStyleSheet("font-size: 12px; color: #6b7280; font-weight: normal;")
        form_layout.addWidget(lbl_name)

        self._input_name = QLineEdit()
        self._input_name.setPlaceholderText("Ej: Bebidas, Cigarrillos…")
        self._input_name.setMaxLength(100)
        self._input_name.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 13px;
                background: #ffffff;
                color: #374151;
            }
            QLineEdit:focus {
                border-color: #4f46e5;
            }
        """)
        self._input_name.returnPressed.connect(self._on_save_clicked)
        form_layout.addWidget(self._input_name)

        # ── Botones Guardar / Eliminar ─────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_save = QPushButton("Guardar")
        self._btn_save.setStyleSheet(get_btn_primary_stylesheet())
        self._btn_save.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self._btn_save)

        self._btn_delete = QPushButton("Eliminar")
        self._btn_delete.setStyleSheet(get_btn_danger_stylesheet())
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete_clicked)
        btn_row.addWidget(self._btn_delete)

        form_layout.addLayout(btn_row)
        layout.addWidget(self._group_box)

        # ── Status label ───────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        layout.addWidget(self._status_label)

        layout.addStretch()
        return panel

    # ------------------------------------------------------------------
    # Ciclo de vida de la vista
    # ------------------------------------------------------------------

    def on_view_activated(self) -> None:
        """Llamado por AdminPanelView al mostrar esta sección. Carga la lista."""
        if self._presenter is None:
            return
        self._presenter.on_view_activated()
        self._load_categories()

    # ------------------------------------------------------------------
    # Manejadores de eventos Qt
    # ------------------------------------------------------------------

    def _on_list_selection_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        """Carga la categoría seleccionada en el formulario para editar."""
        if current is None:
            return
        category: Category = current.data(Qt.UserRole)
        if self._presenter:
            self._presenter.on_category_selected(category)
        self._group_box.setTitle(f"Editar: {category.name}")
        self._input_name.setText(category.name)
        self._btn_delete.setEnabled(True)
        self._status_label.setText("")

    def _on_new_clicked(self) -> None:
        """Limpia el formulario para crear una nueva categoría."""
        if self._presenter:
            self._presenter.on_new_requested()

    def _on_save_clicked(self) -> None:
        """Valida y lanza el worker de guardado."""
        if self._presenter is None:
            return
        category = self._presenter.on_save_requested(self._input_name.text())
        if category is None:
            return  # error de validación ya notificado a la vista

        self.set_form_enabled(False)
        self.show_loading(True)

        from src.infrastructure.ui.workers.category_worker import SaveCategoryWorker

        worker = SaveCategoryWorker(self._session_factory, category, parent=self)
        worker.category_saved.connect(self._on_category_saved)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._active_workers.remove(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_delete_clicked(self) -> None:
        """Pide confirmación y lanza el worker de eliminación."""
        if self._presenter is None:
            return
        category_id = self._presenter.on_delete_requested()
        if category_id is None:
            return

        name = self._presenter.editing_category_name
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar la categoría «{name}»?\n\n"
            "Los productos asignados a esta categoría quedarán sin categoría.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.set_form_enabled(False)
        self.show_loading(True)

        from src.infrastructure.ui.workers.category_worker import DeleteCategoryWorker

        worker = DeleteCategoryWorker(self._session_factory, category_id, parent=self)
        worker.category_deleted.connect(self._on_category_deleted)
        worker.error_occurred.connect(self._presenter.on_worker_error)
        worker.finished.connect(lambda: self._active_workers.remove(worker))
        self._active_workers.append(worker)
        worker.start()

    # ------------------------------------------------------------------
    # Callbacks de workers (redirigen al presenter y recargan la lista)
    # ------------------------------------------------------------------

    def _on_category_saved(self, category: Category) -> None:
        """Callback del SaveCategoryWorker: delega al presenter y recarga."""
        if self._presenter:
            self._presenter.on_category_saved(category)
        self._load_categories()

    def _on_category_deleted(self, category_id: int) -> None:
        """Callback del DeleteCategoryWorker: delega al presenter y recarga."""
        if self._presenter:
            self._presenter.on_category_deleted(category_id)
        self._load_categories()

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------

    def _load_categories(self) -> None:
        """Lanza el worker que recarga la lista completa de categorías."""
        from src.infrastructure.ui.workers.category_worker import ListCategoriesWorker

        worker = ListCategoriesWorker(self._session_factory, parent=self)
        worker.categories_loaded.connect(self._on_categories_loaded)
        worker.error_occurred.connect(self._on_load_error)
        worker.finished.connect(lambda: self._active_workers.remove(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_categories_loaded(self, categories: list[Category]) -> None:
        """Recibe la lista del worker y la muestra. Delega al presenter."""
        if self._presenter:
            self._presenter.on_categories_loaded(categories)
        self.show_categories(categories)

    def _on_load_error(self, message: str) -> None:
        """Error al cargar la lista de categorías."""
        if self._presenter:
            self._presenter.on_worker_error(message)

    # ------------------------------------------------------------------
    # ICategoryManagementView — implementación del protocolo
    # ------------------------------------------------------------------

    def show_categories(self, categories: list[Category]) -> None:
        """Muestra la lista de categorías en el QListWidget.

        Args:
            categories: Lista de categorías a mostrar.
        """
        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        for cat in categories:
            item = QListWidgetItem(cat.name)
            item.setData(Qt.UserRole, cat)
            self._list_widget.addItem(item)
        self._list_widget.blockSignals(False)

    def show_loading(self, loading: bool) -> None:
        """Muestra u oculta el indicador de carga en el status label.

        Args:
            loading: True para mostrar 'Cargando…', False para limpiar.
        """
        if loading:
            self._status_label.setStyleSheet("font-size: 12px; color: #6b7280;")
            self._status_label.setText("Cargando…")
        else:
            self._status_label.setText("")

    def show_success(self, message: str) -> None:
        """Muestra un mensaje de éxito en el status label.

        Args:
            message: Texto a mostrar en verde.
        """
        self._status_label.setStyleSheet("font-size: 12px; color: #059669; font-weight: bold;")
        self._status_label.setText(message)

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error en el status label.

        Args:
            message: Texto a mostrar en rojo.
        """
        self._status_label.setStyleSheet("font-size: 12px; color: #dc2626; font-weight: bold;")
        self._status_label.setText(message)

    def clear_form(self) -> None:
        """Limpia el formulario y lo deja en modo 'nueva categoría'."""
        self._input_name.clear()
        self._input_name.setFocus()
        self._list_widget.clearSelection()
        self._btn_delete.setEnabled(False)
        self._group_box.setTitle("Nueva categoría")
        self._status_label.setText("")

    def set_form_enabled(self, enabled: bool) -> None:
        """Habilita o deshabilita los controles del formulario.

        Args:
            enabled: True para habilitar, False para deshabilitar (durante operaciones async).
        """
        self._input_name.setEnabled(enabled)
        self._btn_save.setEnabled(enabled)
        self._btn_new.setEnabled(enabled)
        self._list_widget.setEnabled(enabled)
        # _btn_delete se habilita solo cuando hay una categoría seleccionada
        if enabled:
            self._btn_delete.setEnabled(self._list_widget.currentItem() is not None)
        else:
            self._btn_delete.setEnabled(False)
