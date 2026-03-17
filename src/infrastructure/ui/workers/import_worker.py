"""Workers QThread para carga de archivos e importación masiva con mapeo de columnas.

FileLoadWorker  — Lee el archivo con Polars y emite headers + primeras 100 filas
                  para preview (no lanza excepciones; usa error_occurred).
ImportWorker    — Carga el archivo completo, aplica column_mapping y ejecuta el
                  use case UpdateBulkPrices. Reporta progreso determinado 0–100.

Uso típico::

    worker = FileLoadWorker(file_path)
    worker.headers_loaded.connect(presenter.on_file_loaded_headers)
    worker.rows_loaded.connect(presenter.on_file_loaded_rows)
    worker.error_occurred.connect(presenter.on_file_load_error)
    worker.start()
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal


class FileLoadWorker(QThread):
    """Worker para cargar un archivo CSV/Excel y emitir headers + primeras 100 filas.

    Todo se lee como String (``infer_schema_length=0``) para preservar el
    formato numérico argentino (coma decimal, punto de miles).

    Signals:
        headers_loaded (list[str]): Nombres de columnas del archivo.
        rows_loaded (list[list[str]]): Primeras 100 filas como listas de strings.
        progress_updated (int): Progreso 0–100.
        error_occurred (str): Error al leer el archivo.

    Args:
        file_path: Ruta al archivo CSV o Excel (.xlsx/.xls).
        parent: QObject padre (opcional).
    """

    headers_loaded = Signal(list)
    rows_loaded = Signal(list)
    progress_updated = Signal(int)
    error_occurred = Signal(str)

    def __init__(self, file_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._file_path = file_path

    def run(self) -> None:
        """Carga el archivo y emite headers + rows en el hilo separado."""
        try:
            import polars as pl

            self.progress_updated.emit(10)

            path = self._file_path
            suffix = path.suffix.lower()

            if suffix == ".csv":
                df = pl.read_csv(path, infer_schema_length=0)
            elif suffix in {".xlsx", ".xls"}:
                df = pl.read_excel(path, infer_schema_length=0)
            else:
                self.error_occurred.emit(
                    f"Extensión no soportada: '{suffix}'. Use .csv, .xlsx o .xls."
                )
                return

            self.progress_updated.emit(60)

            headers = df.columns
            preview_df = df.head(100)
            rows = [
                [str(v) if v is not None else "" for v in row]
                for row in preview_df.iter_rows()
            ]

            self.progress_updated.emit(100)
            self.headers_loaded.emit(headers)
            self.rows_loaded.emit(rows)

        except Exception as exc:
            self.error_occurred.emit(str(exc))


class ImportWorker(QThread):
    """Worker para importación masiva con mapeo interactivo de columnas.

    Aplica ``column_mapping`` al DataFrame antes de llamar a
    ``BulkPriceImporter.parse_dataframe()`` + ``UpdateBulkPrices.execute()``.
    Reporta progreso determinado en cuatro etapas: lectura, parsing, upsert, fin.

    Signals:
        progress_updated (int): Progreso 0–100.
        import_completed (ImportResult): Resultado final de la importación.
        error_occurred (str): Error inesperado (no de validación de filas).

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        file_path: Ruta al archivo CSV o Excel a importar.
        column_mapping: Diccionario ``{campo_destino: col_archivo}``.
                        Las columnas mapeadas a ``"(ignorar)"`` se descartan.
                        Campos destino: ``barcode``, ``name``, ``net_cost``, ``category``.
        parent: QObject padre (opcional).
    """

    progress_updated = Signal(int)
    import_completed = Signal(object)   # ImportResult
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        file_path: Path,
        column_mapping: dict[str, str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._file_path = file_path
        self._column_mapping = column_mapping

    def run(self) -> None:
        """Ejecuta el parsing + upsert en el hilo separado."""
        session = None
        try:
            session = self._session_factory()

            import polars as pl

            from src.application.use_cases.update_bulk_prices import UpdateBulkPrices
            from src.infrastructure.importers.bulk_price_importer import BulkPriceImporter
            from src.infrastructure.persistence.mariadb_category_repository import MariaDbCategoryRepository

            self.progress_updated.emit(10)

            path = self._file_path
            suffix = path.suffix.lower()
            if suffix == ".csv":
                df = pl.read_csv(path, infer_schema_length=0)
            elif suffix in {".xlsx", ".xls"}:
                df = pl.read_excel(path, infer_schema_length=0)
            else:
                self.error_occurred.emit(f"Extensión no soportada: '{suffix}'.")
                return

            self.progress_updated.emit(40)

            parsed = BulkPriceImporter().parse_dataframe(df, self._column_mapping)

            self.progress_updated.emit(70)

            category_repo = MariaDbCategoryRepository(session)
            result = UpdateBulkPrices(session, category_repo).execute(parsed.valid_rows)
            result.errors.extend(parsed.errors)

            self.progress_updated.emit(100)
            self.import_completed.emit(result)

        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            if session is not None:
                session.close()
