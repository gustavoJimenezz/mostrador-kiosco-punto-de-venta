"""Presenter MVP para la vista de importación masiva (ImportView).

Python puro: no importa PySide6. Completamente testeable con FakeImportView.

Flujo:
    Usuario selecciona archivo
    → ImportView emite file_selected(Path)
    → ImportPresenter.on_file_selected() lanza FileLoadWorker
    → on_file_loaded() actualiza tabla de mapeo + preview
    → Usuario mapea columnas y pulsa "Importar"
    → ImportView emite import_requested(dict)
    → ImportPresenter.on_import_requested() valida + lanza ImportWorker
    → on_import_completed() muestra resumen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

from src.application.use_cases.update_bulk_prices import ImportResult

_REQUIRED_FIELDS = {"barcode", "name", "net_cost"}

_UNASSIGNED = "(sin asignar)"
_IGNORE = "(ignorar)"

_AUTOMAP_ALIASES: dict[str, set[str]] = {
    "barcode":  {"barcode", "codigo", "código", "ean", "ean13", "cod_barras", "codigo_barras"},
    "name":     {"name", "nombre", "descripcion", "descripción", "producto", "articulo", "artículo"},
    "net_cost": {"net_cost", "costo", "precio", "precio_neto", "costo_neto", "cost_price", "precio_lista"},
    "category": {"category", "categoria", "categoría", "rubro"},
}


@dataclass
class MappingStatus:
    """Estado del mapeo de columnas para el banner de la vista.

    Attributes:
        message: Texto descriptivo del estado.
        bg_color: Color de fondo CSS (#rrggbb).
        valid: True si todos los campos requeridos están mapeados sin conflictos.
    """

    message: str
    bg_color: str
    valid: bool


@runtime_checkable
class IImportView(Protocol):
    """Contrato entre ImportPresenter e ImportView.

    Las implementaciones alternativas (FakeImportView) se usan en tests.
    """

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Muestra un mensaje de estado al usuario.

        Args:
            message: Texto a mostrar.
            is_error: Si True, mostrar en color de error.
        """
        ...

    def show_progress(self, visible: bool, value: int = -1) -> None:
        """Muestra u oculta la barra de progreso.

        Args:
            visible: True para mostrar, False para ocultar.
            value: Valor 0–100. Si es -1, no actualizar el valor actual.
        """
        ...

    def enable_import_button(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón de importar.

        Args:
            enabled: True para habilitar.
        """
        ...

    def show_file_info(self, filename: str, row_count: int) -> None:
        """Muestra el nombre del archivo y la cantidad de filas en preview.

        Args:
            filename: Nombre del archivo (sin ruta).
            row_count: Cantidad de filas en el preview (máx. 100).
        """
        ...

    def show_mapping_table(self, headers: list[str]) -> None:
        """Muestra la tabla de mapeo de columnas (4 filas fijas, una por campo destino).

        Args:
            headers: Nombres de columnas del archivo.
        """
        ...

    def show_mapping_status(self, status: MappingStatus) -> None:
        """Actualiza el banner de estado del mapeo.

        Args:
            status: MappingStatus con mensaje, color y flag de validez.
        """
        ...

    def get_column_mapping(self) -> dict[str, str]:
        """Retorna el mapeo actual {campo_destino: columna_del_archivo}.

        Returns:
            Dict con los 4 campos destino y la columna asignada (o _UNASSIGNED).
        """
        ...

    def show_preview(self, headers: list[str], rows: list[list[str]]) -> None:
        """Muestra las primeras filas del archivo en el QTableView de preview.

        Args:
            headers: Nombres de columnas.
            rows: Filas como listas de strings (máx. 100).
        """
        ...

    def ask_file_path(self) -> Optional[Path]:
        """Abre el QFileDialog y retorna la ruta seleccionada.

        Returns:
            Path al archivo seleccionado, o None si el usuario canceló.
        """
        ...


class ImportPresenter:
    """Presenter para la vista de importación masiva (MVP).

    Python puro: no importa PySide6. Completamente testeable con FakeImportView.

    Args:
        view: Objeto que implementa IImportView.
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
    """

    def __init__(self, view: IImportView, session_factory: Callable) -> None:
        self._view = view
        self._session_factory = session_factory
        self._current_file_path: Optional[Path] = None
        self._current_headers: list[str] = []
        self._current_rows: list[list[str]] = []
        self._worker = None

    # ------------------------------------------------------------------
    # Handlers de señales emitidas por ImportView
    # ------------------------------------------------------------------

    def on_file_selected(self, file_path: Path) -> None:
        """Maneja la selección de un archivo; lanza FileLoadWorker.

        Args:
            file_path: Ruta al archivo CSV o Excel seleccionado por el usuario.
        """
        from src.infrastructure.ui.workers.import_worker import FileLoadWorker

        self._current_file_path = file_path
        self._view.show_status(f"Cargando: {file_path.name}…")
        self._view.show_progress(True, 0)
        self._view.enable_import_button(False)

        worker = FileLoadWorker(file_path)
        worker.headers_loaded.connect(self._on_headers_loaded)
        worker.rows_loaded.connect(self._on_rows_loaded)
        worker.progress_updated.connect(self.on_progress_updated)
        worker.error_occurred.connect(self.on_file_load_error)
        worker.finished.connect(self._cleanup_worker)
        self._worker = worker
        worker.start()

    def on_import_requested(self, column_mapping: dict[str, str]) -> None:
        """Valida el mapeo de columnas y lanza ImportWorker si es válido.

        Requiere exactamente un campo mapeado a cada uno de: barcode, name, net_cost.
        Los campos mapeados a "(sin asignar)" o "(ignorar)" se consideran ausentes.

        Args:
            column_mapping: Diccionario ``{campo_destino: col_archivo}``.
        """
        missing = {
            field for field in _REQUIRED_FIELDS
            if column_mapping.get(field, _UNASSIGNED) in {_UNASSIGNED, _IGNORE}
        }
        if missing:
            campos = ", ".join(sorted(missing))
            self._view.show_status(
                f"Se requieren los campos: {campos}", is_error=True
            )
            return

        source_cols = [
            v for v in column_mapping.values()
            if v not in {_UNASSIGNED, _IGNORE, ""}
        ]
        if len(source_cols) != len(set(source_cols)):
            self._view.show_status(
                "Conflicto: la misma columna está asignada a más de un campo.",
                is_error=True,
            )
            return

        if self._current_file_path is None:
            self._view.show_status("No hay archivo seleccionado.", is_error=True)
            return

        from src.infrastructure.ui.workers.import_worker import ImportWorker

        self._view.show_status("Importando…")
        self._view.show_progress(True, 0)
        self._view.enable_import_button(False)

        worker = ImportWorker(
            self._session_factory, self._current_file_path, column_mapping
        )
        worker.progress_updated.connect(self.on_progress_updated)
        worker.import_completed.connect(self.on_import_completed)
        worker.error_occurred.connect(self.on_import_error)
        worker.finished.connect(self._cleanup_worker)
        self._worker = worker
        worker.start()

    # ------------------------------------------------------------------
    # Handlers de señales emitidas por los workers
    # ------------------------------------------------------------------

    def on_file_loaded(self, headers: list[str], rows: list[list[str]]) -> None:
        """Recibe headers y filas cargados. Método público para uso directo en tests.

        Args:
            headers: Nombres de columnas del archivo.
            rows: Primeras filas como lista de listas de strings (máx. 100).
        """
        self._current_headers = headers
        self._current_rows = rows
        self._view.show_mapping_table(headers)
        self._view.show_preview(headers, rows)
        filename = self._current_file_path.name if self._current_file_path else ""
        self._view.show_file_info(filename, len(rows))
        self._view.show_progress(False)
        self._view.show_status(f"Archivo cargado: {len(rows)} filas (preview).")

    def on_file_load_error(self, error: str) -> None:
        """Maneja un error al leer el archivo.

        Args:
            error: Mensaje de error del FileLoadWorker.
        """
        self._view.show_progress(False)
        self._view.show_status(f"Error al leer el archivo: {error}", is_error=True)

    def on_import_completed(self, result: ImportResult) -> None:
        """Muestra el resumen de la importación completada.

        Args:
            result: ImportResult con contadores y lista de errores por fila.
        """
        self._view.show_progress(False)
        self._view.enable_import_button(True)
        summary = (
            f"Importación completada:\n"
            f"  • Nuevos: {result.inserted}\n"
            f"  • Actualizados: {result.updated}\n"
            f"  • Sin cambios: {result.skipped}\n"
            f"  • Errores de fila: {len(result.errors)}"
        )
        self._view.show_status(summary)

    def on_import_error(self, error: str) -> None:
        """Maneja un error inesperado durante la importación.

        Args:
            error: Mensaje de error del ImportWorker.
        """
        self._view.show_progress(False)
        self._view.enable_import_button(True)
        self._view.show_status(f"Error en la importación:\n{error}", is_error=True)

    def on_progress_updated(self, value: int) -> None:
        """Actualiza el valor de la barra de progreso.

        Args:
            value: Valor 0–100 emitido por el worker activo.
        """
        self._view.show_progress(True, value)

    # ------------------------------------------------------------------
    # Handlers internos (conectados a señales de workers)
    # ------------------------------------------------------------------

    def _on_headers_loaded(self, headers: list[str]) -> None:
        self._current_headers = headers
        self._view.show_mapping_table(headers)

    def _on_rows_loaded(self, rows: list[list[str]]) -> None:
        self._current_rows = rows
        self._view.show_preview(self._current_headers, rows)
        filename = self._current_file_path.name if self._current_file_path else ""
        self._view.show_file_info(filename, len(rows))
        self._view.show_progress(False)
        self._view.show_status(f"Archivo cargado: {len(rows)} filas (preview).")

    def _cleanup_worker(self) -> None:
        self._worker = None
