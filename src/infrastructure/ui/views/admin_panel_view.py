"""Panel de Administrador unificado (PySide6).

Agrupa todas las vistas exclusivas del rol administrador en un único widget
con navegación lateral izquierda (QListWidget) y área de contenido derecha
(QStackedWidget). Reemplaza las pestañas individuales que antes ocupaban el
QTabWidget principal.

Secciones disponibles:
    - Inventario (ProductManagementView)  — F5, selección por defecto
    - Historial de caja (CashHistoryView)
    - Historial de ventas (SalesHistoryView)
    - Editar stock (StockEditView)         — F6
    - Inyectar stock (StockInjectView)     — F7
    - Importar (ImportView)                — F9
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QWidget,
)

# Mapeo clave → índice en el stacked widget
_NAV_INDEX: dict[str, int] = {
    "inventory": 0,
    "cash_history": 1,
    "sales_history": 2,
    "stock_edit": 3,
    "stock_inject": 4,
    "import": 5,
}

_NAV_LABELS: list[tuple[str, str]] = [
    ("inventory",    "Inventario"),
    ("cash_history", "Historial de caja"),
    ("sales_history","Historial de ventas"),
    ("stock_edit",   "Editar stock"),
    ("stock_inject", "Inyectar stock"),
    ("import",       "Importar"),
]

_NAV_LIST_STYLESHEET = """
QListWidget {
    border: none;
    border-right: 1px solid #e5e7eb;
    background: #f3f4f6;
    outline: 0;
    padding: 8px 0;
}
QListWidget::item {
    padding: 10px 16px;
    color: #374151;
    font-size: 13px;
    border-radius: 0;
}
QListWidget::item:hover {
    background: #eef2ff;
    color: #4f46e5;
}
QListWidget::item:selected {
    background: #eef2ff;
    color: #4f46e5;
    font-weight: bold;
    border-left: 3px solid #4f46e5;
}
"""


class AdminPanelView(QWidget):
    """Widget contenedor del panel de administrador.

    Layout horizontal:
        - Izquierda: QListWidget con las opciones de navegación (ancho fijo 200 px).
        - Derecha: QStackedWidget con las vistas correspondientes a cada opción.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
                         Se propaga a todas las sub-vistas que lo requieren.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._build_ui()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout horizontal: lista de nav + stacked widget."""
        from src.infrastructure.ui.views.cash_history_view import CashHistoryView
        from src.infrastructure.ui.views.import_view import ImportView
        from src.infrastructure.ui.views.product_management_view import (
            ProductManagementView,
        )
        from src.infrastructure.ui.views.sales_history_view import SalesHistoryView
        from src.infrastructure.ui.views.stock_edit_view import StockEditView
        from src.infrastructure.ui.views.stock_inject_view import StockInjectView

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Lista de navegación ────────────────────────────────────────
        self._nav_list = QListWidget()
        self._nav_list.setFixedWidth(200)
        self._nav_list.setStyleSheet(_NAV_LIST_STYLESHEET)
        self._nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        for _key, label in _NAV_LABELS:
            item = QListWidgetItem(label)
            self._nav_list.addItem(item)

        layout.addWidget(self._nav_list)

        # ── Stacked widget con las vistas ──────────────────────────────
        self._stack = QStackedWidget()

        self._inventory_view = ProductManagementView(
            session_factory=self._session_factory
        )
        self._cash_history_view = CashHistoryView(
            session_factory=self._session_factory
        )
        self._sales_history_view = SalesHistoryView(
            session_factory=self._session_factory
        )
        self._stock_edit_view = StockEditView(
            session_factory=self._session_factory
        )
        self._stock_inject_view = StockInjectView(
            session_factory=self._session_factory
        )
        self._import_view = ImportView()

        self._stack.addWidget(self._inventory_view)     # índice 0
        self._stack.addWidget(self._cash_history_view)  # índice 1
        self._stack.addWidget(self._sales_history_view) # índice 2
        self._stack.addWidget(self._stock_edit_view)    # índice 3
        self._stack.addWidget(self._stock_inject_view)  # índice 4
        self._stack.addWidget(self._import_view)        # índice 5

        layout.addWidget(self._stack, stretch=1)

        # ── Conexión: clic en la lista → cambiar vista ─────────────────
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)

        # Selección inicial: Inventario (índice 0)
        self._nav_list.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Slots internos
    # ------------------------------------------------------------------

    def _on_nav_changed(self, row: int) -> None:
        """Cambia la vista activa en el stacked widget y la activa.

        Args:
            row: Índice del ítem seleccionado en la lista de navegación.
        """
        if row < 0:
            return
        self._stack.setCurrentIndex(row)
        self._activate_current_view()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def navigate_to(self, key: str) -> None:
        """Navega a la sección identificada por ``key``.

        Selecciona el ítem correspondiente en la lista y muestra la vista
        asociada en el stacked widget.

        Args:
            key: Identificador de la sección. Valores válidos:
                 ``"inventory"``, ``"cash_history"``, ``"sales_history"``,
                 ``"stock_edit"``, ``"stock_inject"``, ``"import"``.
        """
        index = _NAV_INDEX.get(key)
        if index is None:
            return
        self._nav_list.setCurrentRow(index)

    def on_view_activated(self) -> None:
        """Activa la sub-vista actualmente visible en el stacked widget.

        Llamado por ``MainWindow._on_tab_changed`` cada vez que el usuario
        navega al tab "Panel Administrador".
        """
        self._activate_current_view()

    def _activate_current_view(self) -> None:
        """Llama ``on_view_activated()`` en la sub-vista actualmente visible."""
        current = self._stack.currentWidget()
        if current is not None and hasattr(current, "on_view_activated"):
            current.on_view_activated()

    # ── Propiedades para inyección de presenters ───────────────────────

    @property
    def inventory_view(self):
        """Retorna la vista de inventario (ProductManagementView).

        Returns:
            ProductManagementView instanciada dentro del panel.
        """
        return self._inventory_view

    @property
    def cash_history_view(self):
        """Retorna la vista de historial de caja (CashHistoryView).

        Returns:
            CashHistoryView instanciada dentro del panel.
        """
        return self._cash_history_view

    @property
    def sales_history_view(self):
        """Retorna la vista de historial de ventas (SalesHistoryView).

        Returns:
            SalesHistoryView instanciada dentro del panel.
        """
        return self._sales_history_view

    @property
    def stock_edit_view(self):
        """Retorna la vista de edición de stock (StockEditView).

        Returns:
            StockEditView instanciada dentro del panel.
        """
        return self._stock_edit_view

    @property
    def stock_inject_view(self):
        """Retorna la vista de inyección de stock (StockInjectView).

        Returns:
            StockInjectView instanciada dentro del panel.
        """
        return self._stock_inject_view

    @property
    def import_view(self):
        """Retorna la vista de importación masiva (ImportView).

        Returns:
            ImportView instanciada dentro del panel.
        """
        return self._import_view
