"""Vista de importación masiva de listas de precios (pestaña QWidget).

Reemplaza el modal ImportDialog. Vive dentro del QTabWidget de MainWindow
como tab "📥 Importar (F9)". Implementa IImportView.

Layout:
    1. Área de archivo     — QLabel + QLineEdit readonly + QPushButton "Seleccionar..."
    1b. Info de formato    — QLabel HTML con resumen de formato CSV/Excel aceptado
    1c. Banner de estado   — QLabel dinámico (amarillo/rojo/verde según mapeo)
    2. Sección de mapeo    — QGroupBox (oculta hasta cargar archivo)
       ├── _MappingTableWidget: 4 filas fijas (barcode, name, net_cost, category)
       └── QTableView para preview (QStandardItemModel, primeras 100 filas)
    3. Footer de progreso  — QProgressBar (0–100) + QLabel multiline de estado
    4. QPushButton "Importar" — deshabilitado hasta mapeo mínimo válido

Señales emitidas (conectadas al ImportPresenter desde set_presenter()):
    file_selected(Path)     — cuando el usuario confirma la selección de archivo
    import_requested(dict)  — cuando pulsa "Importar"; dict = {campo_destino: col_archivo}
"""

from __future__ import annotations

import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.infrastructure.ui.presenters.import_presenter import (
    MappingStatus,
    _AUTOMAP_ALIASES,
)

_DEST_FIELDS: list[tuple[str, bool]] = [
    ("barcode", True),
    ("name", True),
    ("net_cost", True),
    ("category", False),
]
_UNASSIGNED = "(sin asignar)"
_IGNORE = "(ignorar)"


def _normalize(s: str) -> str:
    """Normaliza un string eliminando diacríticos y convirtiendo a minúsculas.

    Args:
        s: String a normalizar.

    Returns:
        String en minúsculas sin caracteres diacríticos.
    """
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


class _MappingTableWidget(QTableWidget):
    """Tabla de 4 filas fijas para mapear campos destino a columnas del archivo.

    Cada fila corresponde a un campo destino (barcode, name, net_cost, category).
    La columna 1 muestra un QComboBox con las columnas del archivo cargado.
    Los campos requeridos se muestran en negrita con asterisco.

    Signals:
        mapping_changed: Emitida cuando el usuario cambia algún combo.
    """

    mapping_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(len(_DEST_FIELDS), 2, parent)
        self._setup_table()

    def _setup_table(self) -> None:
        """Inicializa cabeceras, items y combos de la tabla."""
        self.setHorizontalHeaderLabels(["Campo destino", "Columna del archivo"])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.horizontalHeader().setStretchLastSection(True)

        for row_idx, (field_name, required) in enumerate(_DEST_FIELDS):
            label = f"{field_name} *" if required else field_name
            item = QTableWidgetItem(label)
            if required:
                font = QFont()
                font.setBold(True)
                item.setFont(font)
            self.setItem(row_idx, 0, item)

            combo = QComboBox()
            combo.addItem(_UNASSIGNED)
            combo.currentIndexChanged.connect(self.mapping_changed)
            self.setCellWidget(row_idx, 1, combo)

    def populate(self, headers: list[str]) -> None:
        """Repopula todos los combos con las columnas del archivo.

        Args:
            headers: Nombres de columnas del archivo cargado.
        """
        options = [_UNASSIGNED] + headers
        for row_idx in range(self.rowCount()):
            combo = self.cellWidget(row_idx, 1)
            if combo is not None:
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(options)
                combo.blockSignals(False)

    def auto_detect(self, headers: list[str]) -> None:
        """Intenta pre-seleccionar combos basándose en alias conocidos de los headers.

        Usa ``_AUTOMAP_ALIASES`` y normalización sin acentos para la detección.
        Si encuentra un alias coincidente, pre-selecciona el combo correspondiente.

        Args:
            headers: Nombres de columnas del archivo cargado.
        """
        norm_to_orig = {_normalize(h): h for h in headers}
        for row_idx, (field_name, _) in enumerate(_DEST_FIELDS):
            aliases = _AUTOMAP_ALIASES.get(field_name, set())
            combo = self.cellWidget(row_idx, 1)
            if combo is None:
                continue
            combo.blockSignals(True)
            for alias in aliases:
                norm_alias = _normalize(alias)
                if norm_alias in norm_to_orig:
                    original = norm_to_orig[norm_alias]
                    idx = combo.findText(original)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    break
            combo.blockSignals(False)

    def get_mapping(self) -> dict[str, str]:
        """Retorna el mapeo actual ``{campo_destino: columna_del_archivo}``.

        Returns:
            Dict con los 4 campos destino y la columna asignada o ``_UNASSIGNED``.
        """
        result: dict[str, str] = {}
        for row_idx, (field_name, _) in enumerate(_DEST_FIELDS):
            combo = self.cellWidget(row_idx, 1)
            if combo is not None:
                result[field_name] = combo.currentText()
        return result


class ImportView(QWidget):
    """Vista de importación masiva como QWidget pestaña.

    Implementa IImportView. La lógica de presentación está delegada al
    ImportPresenter, que se inyecta mediante set_presenter().

    Args:
        parent: QWidget padre (opcional).
    """

    file_selected = Signal(object)    # Path
    import_requested = Signal(dict)   # {campo_destino: col_archivo}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

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
        from src.infrastructure.ui.theme import DANGER_COLOR, TEXT_PRIMARY_COLOR

        self._status_label.setText(message)
        color = DANGER_COLOR if is_error else TEXT_PRIMARY_COLOR
        self._status_label.setStyleSheet(f"color: {color};")

    def show_progress(self, visible: bool, value: int = -1) -> None:
        """Muestra u oculta la barra de progreso.

        Args:
            visible: True para mostrar, False para ocultar.
            value: Valor 0–100. Si es -1, no se modifica el valor actual.
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

    def show_mapping_table(self, headers: list[str]) -> None:
        """Popula la tabla de mapeo y activa auto-detección de columnas.

        Muestra el groupbox de mapeo y recalcula el banner de estado.

        Args:
            headers: Nombres de columnas del archivo.
        """
        self._mapping_widget.populate(headers)
        self._mapping_widget.auto_detect(headers)
        self._mapping_group.setVisible(True)
        self._on_mapping_changed()

    def get_column_mapping(self) -> dict[str, str]:
        """Retorna el mapeo actual ``{campo_destino: columna_del_archivo}``.

        Returns:
            Dict con los 4 campos destino y la columna asignada.
        """
        return self._mapping_widget.get_mapping()

    def show_mapping_status(self, status: MappingStatus) -> None:
        """Actualiza el banner de estado del mapeo y habilita/deshabilita "Importar".

        Args:
            status: MappingStatus con mensaje, color de fondo y flag de validez.
        """
        self._banner_label.setText(status.message)
        self._banner_label.setStyleSheet(
            f"background:{status.bg_color}; border-radius:6px; padding:8px 10px;"
        )
        self._btn_import.setEnabled(status.valid)

    def show_preview(self, headers: list[str], rows: list[list[str]]) -> None:
        """Carga los datos en el QTableView de preview.

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

        # --- 1b. Texto informativo de formato ---
        from src.infrastructure.ui.theme import PALETTE

        info_label = QLabel(
            "<b>Formato aceptado:</b>"
            "<ul style='margin:4px 0 0 0; padding-left:18px;'>"
            "<li><b>CSV</b> — codificación UTF-8, separador coma <code>,</code> o "
            "punto y coma <code>;</code>, primera fila = encabezados.</li>"
            "<li><b>Excel</b> — archivos <code>.xlsx</code> o <code>.xls</code>, "
            "primera hoja, primera fila = encabezados.</li>"
            "</ul>"
            "<b>Columnas requeridas:</b> <code>barcode</code> (EAN-13), "
            "<code>name</code> (nombre del producto), <code>net_cost</code> "
            "(costo neto en ARS, ej: <code>1500.50</code>). "
            "Columna opcional: <code>category</code>. "
            "El orden y nombre de columnas no importa; se mapean en el paso siguiente."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            f"background:{PALETTE.info_surface}; border:1px solid {PALETTE.info_border};"
            f" border-radius:6px; padding:8px 10px; color:{PALETTE.info_text}; font-size:12px;"
        )
        root.addWidget(info_label)

        # --- 1c. Banner de estado del mapeo ---
        self._banner_label = QLabel("Seleccione un archivo para comenzar.")
        self._banner_label.setWordWrap(True)
        self._banner_label.setStyleSheet(
            f"background:{PALETTE.surface}; border-radius:6px; padding:8px 10px;"
            f" color:{PALETTE.text_primary};"
        )
        root.addWidget(self._banner_label)

        # --- 2. Sección de mapeo (oculta hasta cargar archivo) ---
        self._mapping_group = QGroupBox("Mapeo de columnas")
        self._mapping_group.setVisible(False)
        mapping_layout = QVBoxLayout(self._mapping_group)
        mapping_layout.setSpacing(4)
        mapping_layout.setContentsMargins(8, 12, 8, 8)

        # Tabla de mapeo invertida (4 filas fijas)
        self._mapping_widget = _MappingTableWidget()
        self._mapping_widget.setMaximumHeight(160)
        self._mapping_widget.mapping_changed.connect(self._on_mapping_changed)
        mapping_layout.addWidget(self._mapping_widget)

        # Sección margen global
        margin_row = QHBoxLayout()
        margin_row.setSpacing(8)

        self._chk_global_margin = QCheckBox("Aplicar margen de ganancia global al importar:")
        margin_row.addWidget(self._chk_global_margin)

        self._spin_global_margin = QDoubleSpinBox()
        self._spin_global_margin.setRange(0.0, 9999.99)
        self._spin_global_margin.setSingleStep(0.5)
        self._spin_global_margin.setDecimals(2)
        self._spin_global_margin.setSuffix(" %")
        self._spin_global_margin.setValue(30.0)
        self._spin_global_margin.setFixedWidth(110)
        self._spin_global_margin.setEnabled(False)
        margin_row.addWidget(self._spin_global_margin)
        margin_row.addStretch()

        self._chk_global_margin.toggled.connect(self._spin_global_margin.setEnabled)
        mapping_layout.addLayout(margin_row)

        # QTableView para preview
        self._preview_table = QTableView()
        self._preview_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
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
        """Obtiene el mapeo actual (con margen global si está habilitado) y emite import_requested."""
        mapping = self.get_column_mapping()
        if self._chk_global_margin.isChecked():
            mapping["global_margin"] = Decimal(str(self._spin_global_margin.value()))
        else:
            mapping["global_margin"] = None
        self.import_requested.emit(mapping)

    def _on_mapping_changed(self) -> None:
        """Recalcula el banner de estado basándose en el mapeo actual."""
        mapping = self.get_column_mapping()

        # Detectar campos requeridos sin asignar
        missing = [
            field
            for field, required in _DEST_FIELDS
            if required and mapping.get(field, _UNASSIGNED) in {_UNASSIGNED, _IGNORE}
        ]

        # Detectar columnas del archivo asignadas a ≥2 campos destino
        assigned_cols = [
            col for col in mapping.values() if col not in {_UNASSIGNED, _IGNORE}
        ]
        has_duplicates = len(assigned_cols) != len(set(assigned_cols))

        from src.infrastructure.ui.theme import PALETTE

        if has_duplicates:
            status = MappingStatus(
                message="Error: la misma columna del archivo está asignada a más de un campo destino.",
                bg_color=PALETTE.danger_light,
                valid=False,
            )
        elif missing:
            campos = ", ".join(f"'{f}'" for f in missing)
            status = MappingStatus(
                message=f"Campos requeridos sin asignar: {campos}.",
                bg_color=PALETTE.warning_light,
                valid=False,
            )
        else:
            status = MappingStatus(
                message="Mapeo completo. Todos los campos requeridos están asignados.",
                bg_color=PALETTE.success_light,
                valid=True,
            )

        self.show_mapping_status(status)
