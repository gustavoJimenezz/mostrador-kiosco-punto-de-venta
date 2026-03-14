"""Vista de importación masiva de listas de precios (pestaña QWidget).

Reemplaza el modal ImportDialog. Vive dentro del QTabWidget de MainWindow
como tab "📥 Importar (F9)". Implementa IImportView.

Layout:
    1. Área de archivo     — QLabel + QLineEdit readonly + QPushButton "Seleccionar..."
    2. Sección de mapeo    — QGroupBox (oculta hasta cargar archivo)
       ├── QScrollArea horizontal con un QComboBox por columna del archivo
       └── QTableView para preview (QStandardItemModel, primeras 100 filas)
    3. Footer de progreso  — QProgressBar (0–100) + QLabel multiline de estado
    4. QPushButton "Importar" — deshabilitado hasta mapeo mínimo válido

Señales emitidas (conectadas al ImportPresenter desde set_presenter()):
    file_selected(Path)     — cuando el usuario confirma la selección de archivo
    import_requested(dict)  — cuando pulsa "Importar"; dict = {col_archivo: campo}

Campos destino en los QComboBox:
    "(ignorar)", "barcode", "name", "net_cost", "category"
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

_FIELD_OPTIONS = ["(ignorar)", "barcode", "name", "net_cost", "category"]
_DEFAULT_COLUMN_WIDTH = 130
_REQUIRED_FIELDS = {"barcode", "name", "net_cost"}


class ImportView(QWidget):
    """Vista de importación masiva como QWidget pestaña.

    Implementa IImportView. La lógica de presentación está delegada al
    ImportPresenter, que se inyecta mediante set_presenter().

    Args:
        parent: QWidget padre (opcional).
    """

    file_selected = Signal(object)    # Path
    import_requested = Signal(dict)   # {col_archivo: campo_destino}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._combos: list[QComboBox] = []
        self._current_headers: list[str] = []
        self._build_ui()
        self._setup_scroll_sync()

    def set_presenter(self, presenter) -> None:
        """Inyecta el ImportPresenter y conecta las señales Qt.

        Args:
            presenter: ImportPresenter ya configurado con esta vista.
        """
        self.file_selected.connect(presenter.on_file_selected)
        self.import_requested.connect(presenter.on_import_requested)

    # ------------------------------------------------------------------
    # IImportView implementation
    # ------------------------------------------------------------------

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Muestra un mensaje de estado en el footer.

        Args:
            message: Texto a mostrar (puede ser multiline con \\n).
            is_error: Si True, texto en rojo; si False, texto en gris oscuro.
        """
        self._status_label.setText(message)
        color = "#dc2626" if is_error else "#374151"
        self._status_label.setStyleSheet(f"color: {color};")

    def show_progress(self, visible: bool, value: int = -1) -> None:
        """Muestra u oculta la barra de progreso.

        Args:
            visible: True para mostrar, False para ocultar.
            value: Valor 0–100. Si es -1, no se modifica el valor actual.
                   Si es 0 con visible=True sin valor previo, muestra como indeterminado.
        """
        self._progress.setVisible(visible)
        if visible and value >= 0:
            self._progress.setRange(0, 100)
            self._progress.setValue(value)

    def enable_import_button(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón "Importar".

        Args:
            enabled: True para habilitar.
        """
        self._btn_import.setEnabled(enabled)

    def show_file_info(self, filename: str, row_count: int) -> None:
        """Actualiza el título del groupbox de mapeo con nombre del archivo y filas.

        Args:
            filename: Nombre del archivo (sin ruta completa).
            row_count: Cantidad de filas en el preview (máx. 100).
        """
        if filename:
            self._mapping_group.setTitle(
                f"Mapeo de columnas — {filename} ({row_count} filas en preview)"
            )
        else:
            self._mapping_group.setTitle(
                f"Mapeo de columnas ({row_count} filas en preview)"
            )

    def show_column_mapping(self, headers: list[str]) -> None:
        """Crea un QComboBox por cada columna del archivo y muestra el groupbox.

        Args:
            headers: Nombres de columnas del archivo.
        """
        self._current_headers = headers

        # Limpiar combos existentes
        for combo in self._combos:
            combo.deleteLater()
        self._combos.clear()
        while self._combos_layout.count():
            item = self._combos_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Crear un combo por columna
        for _ in headers:
            combo = QComboBox()
            combo.addItems(_FIELD_OPTIONS)
            combo.setFixedWidth(_DEFAULT_COLUMN_WIDTH)
            combo.currentIndexChanged.connect(self._on_mapping_changed)
            self._combos_layout.addWidget(combo)
            self._combos.append(combo)

        # Stretch al final para que los combos no se expandan
        self._combos_layout.addStretch()
        self._mapping_group.setVisible(True)

    def show_preview(self, headers: list[str], rows: list[list[str]]) -> None:
        """Carga los datos en el QTableView de preview.

        Sincroniza los anchos de los QComboBox con las columnas de la tabla.

        Args:
            headers: Nombres de columnas.
            rows: Filas como listas de strings (máx. 100).
        """
        model = QStandardItemModel(len(rows), len(headers))
        model.setHorizontalHeaderLabels(headers)
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                model.setItem(row_idx, col_idx, QStandardItem(value or ""))
        self._preview_table.setModel(model)

        # Sincronizar anchos de combos con columnas de la tabla
        h_header = self._preview_table.horizontalHeader()
        for i, combo in enumerate(self._combos):
            combo.setFixedWidth(h_header.sectionSize(i))

    def ask_file_path(self) -> Optional[Path]:
        """Abre QFileDialog y retorna la ruta seleccionada.

        Returns:
            Path al archivo seleccionado, o None si el usuario canceló.
        """
        file_str, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar lista de precios",
            "",
            "Archivos de datos (*.csv *.xlsx *.xls);;Todos los archivos (*)",
        )
        if not file_str:
            return None
        return Path(file_str)

    # ------------------------------------------------------------------
    # Construcción interna del UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout completo de la vista programáticamente."""
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # --- 1. Área de selección de archivo ---
        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        file_row.addWidget(QLabel("Archivo:"))

        self._file_path_edit = QLineEdit()
        self._file_path_edit.setReadOnly(True)
        self._file_path_edit.setPlaceholderText("Seleccione un archivo CSV o Excel…")
        file_row.addWidget(self._file_path_edit)

        self._btn_select = QPushButton("Seleccionar…")
        self._btn_select.setFixedWidth(130)
        self._btn_select.clicked.connect(self._on_select_clicked)
        file_row.addWidget(self._btn_select)
        root.addLayout(file_row)

        # --- 2. Sección de mapeo (oculta hasta cargar archivo) ---
        self._mapping_group = QGroupBox("Mapeo de columnas")
        self._mapping_group.setVisible(False)
        mapping_layout = QVBoxLayout(self._mapping_group)
        mapping_layout.setSpacing(4)
        mapping_layout.setContentsMargins(8, 12, 8, 8)

        # Scroll horizontal para los QComboBox
        self._combos_scroll = QScrollArea()
        self._combos_scroll.setHorizontalScrollBarPolicy(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ScrollBarAlwaysOn
        )
        self._combos_scroll.setVerticalScrollBarPolicy(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ScrollBarAlwaysOff
        )
        self._combos_scroll.setWidgetResizable(False)
        self._combos_scroll.setFixedHeight(46)

        combos_widget = QWidget()
        self._combos_layout = QHBoxLayout(combos_widget)
        self._combos_layout.setSpacing(0)
        self._combos_layout.setContentsMargins(0, 0, 0, 0)
        self._combos_scroll.setWidget(combos_widget)
        mapping_layout.addWidget(self._combos_scroll)

        # QTableView para preview
        self._preview_table = QTableView()
        self._preview_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.setSelectionBehavior(
            __import__(
                "PySide6.QtWidgets", fromlist=["QAbstractItemView"]
            ).QAbstractItemView.SelectRows
        )
        self._preview_table.horizontalHeader().setStretchLastSection(True)
        mapping_layout.addWidget(self._preview_table)
        root.addWidget(self._mapping_group)

        # --- 3. Footer de progreso + status ---
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        progress_row.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        progress_row.addWidget(self._status_label)
        root.addLayout(progress_row)

        # --- 4. Botón Importar ---
        self._btn_import = QPushButton("Importar")
        self._btn_import.setEnabled(False)
        self._btn_import.setFixedHeight(44)
        self._btn_import.clicked.connect(self._on_import_clicked)
        root.addWidget(self._btn_import)

    def _setup_scroll_sync(self) -> None:
        """Sincroniza el scroll horizontal de los combos con la tabla de preview."""
        self._preview_table.horizontalScrollBar().valueChanged.connect(
            self._combos_scroll.horizontalScrollBar().setValue
        )
        self._combos_scroll.horizontalScrollBar().valueChanged.connect(
            self._preview_table.horizontalScrollBar().setValue
        )
        self._preview_table.horizontalHeader().sectionResized.connect(
            self._on_column_resized
        )

    # ------------------------------------------------------------------
    # Handlers Qt internos
    # ------------------------------------------------------------------

    def _on_select_clicked(self) -> None:
        """Abre el diálogo de archivo y emite file_selected si el usuario confirma."""
        file_path = self.ask_file_path()
        if file_path is not None:
            self._file_path_edit.setText(str(file_path))
            self.file_selected.emit(file_path)

    def _on_import_clicked(self) -> None:
        """Construye el dict de mapeo y emite import_requested."""
        mapping: dict[str, str] = {}
        for i, combo in enumerate(self._combos):
            if i < len(self._current_headers):
                mapping[self._current_headers[i]] = combo.currentText()
        self.import_requested.emit(mapping)

    def _on_mapping_changed(self) -> None:
        """Habilita el botón Importar cuando los campos requeridos están mapeados."""
        mapped = {c.currentText() for c in self._combos} - {"(ignorar)"}
        self._btn_import.setEnabled(_REQUIRED_FIELDS.issubset(mapped))

    def _on_column_resized(
        self, logical_index: int, _old_size: int, new_size: int
    ) -> None:
        """Sincroniza el ancho del QComboBox correspondiente al redimensionar columnas.

        Args:
            logical_index: Índice de la columna redimensionada.
            _old_size: Ancho anterior (no usado).
            new_size: Nuevo ancho en pixels.
        """
        if 0 <= logical_index < len(self._combos):
            self._combos[logical_index].setFixedWidth(new_size)
