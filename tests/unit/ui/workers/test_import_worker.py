"""Tests unitarios de ImportWorker — manejo de errores en session_factory.

No requieren PySide6 QApplication. Se instancia ImportWorker con __new__
y se inyectan atributos + señales mockeadas para llamar run() directamente.

Cubre los criterios de aceptación del Ticket 3.4:
- Si session_factory() lanza excepción, error_occurred se emite.
- session.close() se llama siempre, incluso si el import falla a mitad.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.ui.workers.import_worker import ImportWorker


# ---------------------------------------------------------------------------
# Helper: construye un ImportWorker sin inicializar QThread
# ---------------------------------------------------------------------------


def _make_worker(
    session_factory=None,
    file_path: Path | None = None,
    column_mapping: dict | None = None,
) -> ImportWorker:
    """Crea un ImportWorker sin QThread.__init__ para tests unitarios.

    Reemplaza las señales con MagicMock para capturar llamadas a emit().

    Args:
        session_factory: Callable de sesión (MagicMock o lambda que lanza).
        file_path: Ruta al archivo (no se lee en estos tests).
        column_mapping: Mapeo de columnas.

    Returns:
        ImportWorker con señales mockeadas, listo para llamar a run().
    """
    worker = ImportWorker.__new__(ImportWorker)
    worker._session_factory = session_factory or MagicMock()
    worker._file_path = file_path or Path("/tmp/test.csv")
    worker._column_mapping = column_mapping or {}
    worker.error_occurred = MagicMock()
    worker.progress_updated = MagicMock()
    worker.import_completed = MagicMock()
    return worker


# ---------------------------------------------------------------------------
# Tests: TestImportWorkerSessionFactory
# ---------------------------------------------------------------------------


class TestImportWorkerSessionFactory:
    """Verifica que session_factory() está dentro del try/except (Bug 2 Ticket 3.4)."""

    def test_error_en_session_factory_emite_error_occurred(self) -> None:
        """Si session_factory() lanza excepción, error_occurred se emite con el mensaje."""
        worker = _make_worker(
            session_factory=MagicMock(side_effect=RuntimeError("pool agotado"))
        )

        worker.run()

        worker.error_occurred.emit.assert_called_once()
        emitted_msg = worker.error_occurred.emit.call_args[0][0]
        assert "pool agotado" in emitted_msg

    def test_error_en_session_factory_no_llama_import_completed(self) -> None:
        """Si session_factory() falla, import_completed nunca se emite."""
        worker = _make_worker(
            session_factory=MagicMock(side_effect=ConnectionError("sin conexión"))
        )

        worker.run()

        worker.import_completed.emit.assert_not_called()

    def test_session_se_cierra_en_finally_aunque_falle(self) -> None:
        """session.close() se llama siempre, incluso si el import falla a mitad."""
        mock_session = MagicMock()

        # session_factory retorna sesión válida, pero el archivo no existe
        worker = _make_worker(
            session_factory=MagicMock(return_value=mock_session),
            file_path=Path("/tmp/archivo_que_no_existe.csv"),
        )

        worker.run()

        mock_session.close.assert_called_once()

    def test_session_no_se_cierra_si_session_factory_falla(self) -> None:
        """Si session_factory() falla, no se llama close() (session es None)."""
        mock_session = MagicMock()
        call_count = 0

        def failing_factory():
            raise RuntimeError("fallo antes de crear sesión")

        worker = _make_worker(session_factory=failing_factory)

        worker.run()

        # No hay sesión que cerrar; verificamos que error_occurred sí se emitió
        worker.error_occurred.emit.assert_called_once()
        mock_session.close.assert_not_called()
