"""Diálogo de importación masiva de listas de precios (F9).

Arquitectura MVP:
    IImportView   — Protocol que ImportDialog implementa.
    ImportPresenter — Lógica de presentación (Python puro, testeable).
    ImportDialog  — QDialog que implementa IImportView.

Flujo:
    F9 en MainWindow → ImportDialog.exec() →
    Usuario selecciona archivo con QFileDialog →
    ImportDialog lanza ImportWorker (QThread) →
    Worker emite import_completed(ImportResult) →
    ImportPresenter.on_import_completed() muestra resumen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.application.use_cases.update_bulk_prices import ImportResult


@runtime_checkable
class IImportView(Protocol):
    """Interfaz que ImportDialog implementa.

    Define el contrato entre ImportPresenter y la vista Qt.
    Implementaciones alternativas (FakeImportView) se usan en tests.
    """

    def show_status(self, message: str) -> None:
        """Muestra un mensaje de estado al usuario.

        Args:
            message: Texto a mostrar en el label de estado.
        """
        ...

    def show_progress(self, visible: bool) -> None:
        """Muestra u oculta el indicador de progreso.

        Args:
            visible: True para mostrar, False para ocultar.
        """
        ...

    def enable_select_button(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón de selección de archivo.

        Args:
            enabled: True para habilitar, False para deshabilitar.
        """
        ...

    def ask_file_path(self) -> Optional[Path]:
        """Abre el QFileDialog y retorna la ruta seleccionada.

        Returns:
            Path al archivo seleccionado, o None si el usuario canceló.
        """
        ...

    def close_dialog(self) -> None:
        """Cierra el diálogo."""
        ...


class ImportPresenter:
    """Presenter para el diálogo de importación masiva (MVP).

    Python puro: no importa PySide6. Completamente testeable con FakeImportView.

    Args:
        view: Objeto que implementa IImportView.
    """

    def __init__(self, view: IImportView) -> None:
        """Inicializa el presenter con la vista inyectada.

        Args:
            view: Implementación de IImportView (ImportDialog o FakeImportView).
        """
        self._view = view

    def on_select_file_requested(self) -> Optional[Path]:
        """Maneja la solicitud de selección de archivo.

        Abre el diálogo de archivo. Si el usuario selecciona uno, actualiza
        el estado y retorna la ruta para que la vista lance el worker.

        Returns:
            Path al archivo seleccionado, o None si se canceló.
        """
        file_path = self._view.ask_file_path()
        if file_path is None:
            return None

        self._view.show_status(f"Procesando: {file_path.name}...")
        self._view.show_progress(True)
        self._view.enable_select_button(False)
        return file_path

    def on_import_completed(self, result: ImportResult) -> None:
        """Maneja el resultado exitoso de la importación.

        Args:
            result: ImportResult con contadores y lista de errores por fila.
        """
        self._view.show_progress(False)
        self._view.enable_select_button(True)

        summary = (
            f"Importación completada:\n"
            f"  • Nuevos: {result.inserted}\n"
            f"  • Actualizados: {result.updated}\n"
            f"  • Sin cambios: {result.skipped}\n"
            f"  • Errores de fila: {len(result.errors)}"
        )
        self._view.show_status(summary)

    def on_import_error(self, error_message: str) -> None:
        """Maneja un error inesperado durante la importación.

        Args:
            error_message: Descripción del error recibida desde el worker.
        """
        self._view.show_progress(False)
        self._view.enable_select_button(True)
        self._view.show_status(f"Error en la importación:\n{error_message}")


class ImportDialog(QDialog):
    """Diálogo modal de importación masiva de listas de precios (F9).

    Implementa IImportView. Lanza ImportWorker en un hilo separado para
    no bloquear el hilo principal de Qt durante el procesamiento del CSV.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory, parent=None) -> None:
        """Inicializa el diálogo con su layout y presenter.

        Args:
            session_factory: Callable que retorna una nueva Session de SQLAlchemy.
            parent: QWidget padre (opcional).
        """
        super().__init__(parent)
        self._session_factory = session_factory
        self._active_worker = None

        self.setWindowTitle("Importar Lista de Precios (F9)")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._build_ui()
        self._presenter = ImportPresenter(self)

    def _build_ui(self) -> None:
        """Construye el layout del diálogo programáticamente."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(
            QLabel(
                "Seleccione un archivo CSV o Excel (.xlsx) con las columnas:\n"
                "barcode, name, cost_price  [+ margin_percent, stock, min_stock]"
            )
        )

        self._btn_select = QPushButton("Seleccionar archivo…")
        self._btn_select.clicked.connect(self._on_select_clicked)
        layout.addWidget(self._btn_select)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # modo indeterminado
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # IImportView implementation
    # ------------------------------------------------------------------

    def show_status(self, message: str) -> None:
        """Muestra un mensaje de estado en el label del diálogo.

        Args:
            message: Texto a mostrar.
        """
        self._status_label.setText(message)

    def show_progress(self, visible: bool) -> None:
        """Muestra u oculta el progress bar indeterminado.

        Args:
            visible: True para mostrar, False para ocultar.
        """
        self._progress.setVisible(visible)

    def enable_select_button(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón de selección de archivo.

        Args:
            enabled: True para habilitar.
        """
        self._btn_select.setEnabled(enabled)

    def ask_file_path(self) -> Optional[Path]:
        """Abre QFileDialog para que el usuario seleccione el archivo.

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

    def close_dialog(self) -> None:
        """Cierra el diálogo."""
        self.accept()

    # ------------------------------------------------------------------
    # Handlers Qt internos
    # ------------------------------------------------------------------

    def _on_select_clicked(self) -> None:
        """Maneja el clic en 'Seleccionar archivo…'."""
        file_path = self._presenter.on_select_file_requested()
        if file_path is None:
            return

        self._launch_import_worker(file_path)

    def _launch_import_worker(self, file_path: Path) -> None:
        """Lanza ImportWorker en un hilo separado.

        Args:
            file_path: Ruta al archivo a importar.
        """
        from src.infrastructure.ui.workers.db_worker import ImportWorker

        worker = ImportWorker(self._session_factory, file_path)
        worker.import_completed.connect(self._presenter.on_import_completed)
        worker.error_occurred.connect(self._presenter.on_import_error)
        worker.finished.connect(self._cleanup_worker)
        self._active_worker = worker
        worker.start()

    def _cleanup_worker(self) -> None:
        """Libera la referencia al worker cuando termina."""
        self._active_worker = None
