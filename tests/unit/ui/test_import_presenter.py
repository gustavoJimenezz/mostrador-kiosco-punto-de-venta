"""Tests unitarios del ImportPresenter (MVP).

No requieren PySide6 ni base de datos. El ImportPresenter es Python puro
y se testea con una FakeImportView que implementa IImportView en memoria.

Cubre los criterios de aceptación del Ticket 3.2:
- on_file_load_error: muestra mensaje de error.
- on_file_loaded: actualiza combos de mapeo, preview y status.
- on_import_requested con campos faltantes: muestra error de validación.
- on_import_requested con net_cost ausente: muestra error con nombre correcto.
- on_import_completed: muestra resumen con contadores.
- on_import_error: muestra mensaje de error con is_error=True.
- on_progress_updated: llama show_progress con el valor recibido.
- on_file_selected: actualiza estado y guarda file_path (worker mockeado).
- on_import_requested con file_path ausente: muestra error.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from src.application.use_cases.update_bulk_prices import ImportResult, ImportRowError
from src.infrastructure.ui.presenters.import_presenter import (
    ImportPresenter,
    _AUTOMAP_ALIASES,
    _IGNORE,
    _UNASSIGNED,
)


# ---------------------------------------------------------------------------
# FakeImportView: implementación mínima de IImportView para tests
# ---------------------------------------------------------------------------


class FakeImportView:
    """Vista falsa que registra todas las llamadas del presenter."""

    def __init__(self) -> None:
        self.status_message: str = ""
        self.status_is_error: bool = False
        self.progress_visible: bool = False
        self.progress_value: int = -1
        self.import_button_enabled: bool = False
        self.file_info_filename: str = ""
        self.file_info_row_count: int = 0
        self.mapping_table_headers: list[str] = []
        self.mapping_status = None
        self.preview_headers: list[str] = []
        self.preview_rows: list[list[str]] = []
        self._ask_file_path_return: Optional[Path] = None
        self._mock_mapping: dict[str, str] = {}

    def show_status(self, message: str, is_error: bool = False) -> None:
        self.status_message = message
        self.status_is_error = is_error

    def show_progress(self, visible: bool, value: int = -1) -> None:
        self.progress_visible = visible
        if value >= 0:
            self.progress_value = value

    def enable_import_button(self, enabled: bool) -> None:
        self.import_button_enabled = enabled

    def show_file_info(self, filename: str, row_count: int) -> None:
        self.file_info_filename = filename
        self.file_info_row_count = row_count

    def show_mapping_table(self, headers: list[str]) -> None:
        self.mapping_table_headers = list(headers)

    def show_mapping_status(self, status) -> None:
        self.mapping_status = status

    def get_column_mapping(self) -> dict[str, str]:
        return self._mock_mapping

    def show_preview(self, headers: list[str], rows: list[list[str]]) -> None:
        self.preview_headers = list(headers)
        self.preview_rows = [list(r) for r in rows]

    def ask_file_path(self) -> Optional[Path]:
        return self._ask_file_path_return


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_view() -> FakeImportView:
    return FakeImportView()


@pytest.fixture
def session_factory() -> MagicMock:
    return MagicMock()


@pytest.fixture
def presenter(fake_view: FakeImportView, session_factory: MagicMock) -> ImportPresenter:
    return ImportPresenter(fake_view, session_factory)


def _make_import_result(
    inserted: int = 3,
    updated: int = 2,
    skipped: int = 1,
    errors: list | None = None,
) -> ImportResult:
    result = ImportResult()
    result.inserted = inserted
    result.updated = updated
    result.skipped = skipped
    result.errors = errors or []
    return result


# ---------------------------------------------------------------------------
# Tests: on_file_load_error
# ---------------------------------------------------------------------------


def test_on_file_load_error_shows_error_status(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_file_load_error("No se pudo leer el archivo")

    assert "No se pudo leer el archivo" in fake_view.status_message
    assert fake_view.status_is_error is True


def test_on_file_load_error_hides_progress(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_file_load_error("fallo")

    assert fake_view.progress_visible is False


# ---------------------------------------------------------------------------
# Tests: on_file_loaded
# ---------------------------------------------------------------------------


def test_on_file_loaded_updates_column_mapping(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    headers = ["cod_barra", "descripcion", "precio_costo"]
    rows = [["7790001", "Fideos", "1250,50"]]

    presenter.on_file_loaded(headers, rows)

    assert fake_view.mapping_table_headers == headers


def test_on_file_loaded_updates_preview(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    headers = ["barcode", "name", "cost_price"]
    rows = [["123", "Producto A", "500"], ["456", "Producto B", "300"]]

    presenter.on_file_loaded(headers, rows)

    assert fake_view.preview_headers == headers
    assert fake_view.preview_rows == rows


def test_on_file_loaded_shows_row_count_in_file_info(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    headers = ["barcode", "name"]
    rows = [["1", "A"], ["2", "B"], ["3", "C"]]

    presenter.on_file_loaded(headers, rows)

    assert fake_view.file_info_row_count == 3


def test_on_file_loaded_shows_filename_when_file_path_set(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter._current_file_path = Path("/tmp/lista_precios.xlsx")
    headers = ["barcode", "name"]
    rows = [["1", "A"]]

    presenter.on_file_loaded(headers, rows)

    assert fake_view.file_info_filename == "lista_precios.xlsx"


def test_on_file_loaded_hides_progress_after_load(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_file_loaded(["col1"], [["val1"]])

    assert fake_view.progress_visible is False


def test_on_file_loaded_shows_status_with_row_count(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_file_loaded(["col"], [["a"], ["b"]])

    assert "2" in fake_view.status_message
    assert fake_view.status_is_error is False


# ---------------------------------------------------------------------------
# Tests: on_import_requested — validación de campos requeridos
# ---------------------------------------------------------------------------


def test_on_import_requested_missing_all_required_shows_error(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    # Nuevo formato: {campo_destino: col_archivo}; sin los 3 requeridos
    mapping = {"category": "columna_b"}

    presenter.on_import_requested(mapping)

    assert fake_view.status_is_error is True
    assert "barcode" in fake_view.status_message
    assert "name" in fake_view.status_message
    assert "net_cost" in fake_view.status_message


def test_on_import_requested_missing_net_cost_shows_error(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    # Nuevo formato: {campo_destino: col_archivo}; net_cost ausente
    mapping = {
        "barcode": "col_barcode",
        "name": "col_name",
        "category": "col_category",
    }

    presenter.on_import_requested(mapping)

    assert fake_view.status_is_error is True
    assert "net_cost" in fake_view.status_message


def test_on_import_requested_missing_barcode_shows_error(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    # Nuevo formato: {campo_destino: col_archivo}; barcode ausente
    mapping = {
        "name": "col_name",
        "net_cost": "col_cost",
    }

    presenter.on_import_requested(mapping)

    assert fake_view.status_is_error is True
    assert "barcode" in fake_view.status_message


def test_on_import_requested_without_file_path_shows_error(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    """Todos los campos requeridos mapeados pero sin file_path seleccionado."""
    mapping = {
        "barcode": "col_barcode",
        "name": "col_name",
        "net_cost": "col_cost",
    }
    presenter._current_file_path = None

    presenter.on_import_requested(mapping)

    assert fake_view.status_is_error is True
    assert "archivo" in fake_view.status_message.lower()


# ---------------------------------------------------------------------------
# Tests: on_import_completed
# ---------------------------------------------------------------------------


def test_on_import_completed_shows_summary(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    result = _make_import_result(inserted=10, updated=5, skipped=2, errors=[])

    presenter.on_import_completed(result)

    assert "10" in fake_view.status_message
    assert "5" in fake_view.status_message
    assert "2" in fake_view.status_message
    assert fake_view.status_is_error is False


def test_on_import_completed_shows_error_count(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    errors = [
        ImportRowError(row_number=3, barcode="123", reason="barcode inválido")
    ]
    result = _make_import_result(errors=errors)

    presenter.on_import_completed(result)

    assert "1" in fake_view.status_message


def test_on_import_completed_hides_progress(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_import_completed(_make_import_result())

    assert fake_view.progress_visible is False


def test_on_import_completed_enables_import_button(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_import_completed(_make_import_result())

    assert fake_view.import_button_enabled is True


# ---------------------------------------------------------------------------
# Tests: on_import_error
# ---------------------------------------------------------------------------


def test_on_import_error_shows_error_status(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_import_error("Conexión rechazada por MariaDB")

    assert "Conexión rechazada por MariaDB" in fake_view.status_message
    assert fake_view.status_is_error is True


def test_on_import_error_hides_progress(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_import_error("error")

    assert fake_view.progress_visible is False


def test_on_import_error_enables_import_button(
    presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    presenter.on_import_error("error")

    assert fake_view.import_button_enabled is True


# ---------------------------------------------------------------------------
# Tests: on_progress_updated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 25, 50, 75, 100])
def test_on_progress_updated_delegates_to_view(
    presenter: ImportPresenter, fake_view: FakeImportView, value: int
) -> None:
    presenter.on_progress_updated(value)

    assert fake_view.progress_visible is True
    assert fake_view.progress_value == value


# ---------------------------------------------------------------------------
# Tests: on_file_selected (worker mockeado)
# ---------------------------------------------------------------------------


@patch("src.infrastructure.ui.workers.import_worker.FileLoadWorker")
def test_on_file_selected_shows_loading_state(
    MockFileLoadWorker, presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    mock_worker = MagicMock()
    MockFileLoadWorker.return_value = mock_worker

    presenter.on_file_selected(Path("/tmp/precios.csv"))

    assert "precios.csv" in fake_view.status_message
    assert fake_view.progress_visible is True
    assert fake_view.import_button_enabled is False


@patch("src.infrastructure.ui.workers.import_worker.FileLoadWorker")
def test_on_file_selected_stores_file_path(
    MockFileLoadWorker, presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    mock_worker = MagicMock()
    MockFileLoadWorker.return_value = mock_worker
    path = Path("/tmp/lista.xlsx")

    presenter.on_file_selected(path)

    assert presenter._current_file_path == path


@patch("src.infrastructure.ui.workers.import_worker.FileLoadWorker")
def test_on_file_selected_starts_worker(
    MockFileLoadWorker, presenter: ImportPresenter, fake_view: FakeImportView
) -> None:
    mock_worker = MagicMock()
    MockFileLoadWorker.return_value = mock_worker

    presenter.on_file_selected(Path("/tmp/precios.csv"))

    mock_worker.start.assert_called_once()


# ---------------------------------------------------------------------------
# FakeAutoDetectView: extiende FakeImportView simulando la auto-detección
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Normaliza eliminando diacríticos y convirtiendo a minúsculas."""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


class FakeAutoDetectView(FakeImportView):
    """FakeView que simula la auto-detección de columnas de _MappingTableWidget."""

    def show_mapping_table(self, headers: list[str]) -> None:
        super().show_mapping_table(headers)
        norm_to_orig = {_normalize(h): h for h in headers}
        detected: dict[str, str] = {}
        for field_name, aliases in _AUTOMAP_ALIASES.items():
            detected[field_name] = _UNASSIGNED
            for alias in aliases:
                if _normalize(alias) in norm_to_orig:
                    detected[field_name] = norm_to_orig[_normalize(alias)]
                    break
        self._mock_mapping = detected


# ---------------------------------------------------------------------------
# Tests: TestImportPresenterOnImportRequested (Ticket 3.4)
# ---------------------------------------------------------------------------


class TestImportPresenterOnImportRequested:
    """Verifica la validación completa en on_import_requested (Ticket 3.4)."""

    def _make_presenter(self):
        view = FakeImportView()
        sf = MagicMock()
        p = ImportPresenter(view, sf)
        p._current_file_path = Path("/tmp/lista.csv")
        return p, view

    @patch("src.infrastructure.ui.workers.import_worker.ImportWorker")
    def test_mapping_valido_lanza_worker(self, MockImportWorker) -> None:
        """Mapping completo sin duplicados pasa validación y lanza ImportWorker."""
        mock_worker = MagicMock()
        MockImportWorker.return_value = mock_worker
        presenter, view = self._make_presenter()

        mapping = {
            "barcode": "col_ean",
            "name": "col_desc",
            "net_cost": "col_costo",
        }
        presenter.on_import_requested(mapping)

        mock_worker.start.assert_called_once()
        assert view.status_is_error is False

    def test_mapping_con_campo_faltante_muestra_error(self) -> None:
        """Mapping sin net_cost muestra error con nombre del campo faltante."""
        presenter, view = self._make_presenter()

        mapping = {
            "barcode": "col_ean",
            "name": "col_desc",
        }
        presenter.on_import_requested(mapping)

        assert view.status_is_error is True
        assert "net_cost" in view.status_message

    def test_mapping_con_columna_duplicada_muestra_error(self) -> None:
        """Dos campos destino asignados a la misma columna muestran error de conflicto."""
        presenter, view = self._make_presenter()

        mapping = {
            "barcode": "col_ean",
            "name": "col_ean",   # misma columna que barcode
            "net_cost": "col_costo",
        }
        presenter.on_import_requested(mapping)

        assert view.status_is_error is True
        assert "conflicto" in view.status_message.lower() or "misma columna" in view.status_message.lower()

    def test_sin_archivo_seleccionado_muestra_error(self) -> None:
        """Si _current_file_path es None, muestra error sin lanzar worker."""
        presenter, view = self._make_presenter()
        presenter._current_file_path = None

        mapping = {
            "barcode": "col_ean",
            "name": "col_desc",
            "net_cost": "col_costo",
        }
        presenter.on_import_requested(mapping)

        assert view.status_is_error is True
        assert "archivo" in view.status_message.lower()


# ---------------------------------------------------------------------------
# Tests: TestImportPresenterAutoDetect (coherente con Ticket 3.3)
# ---------------------------------------------------------------------------


class TestImportPresenterAutoDetect:
    """Verifica que on_file_loaded dispara show_mapping_table con auto-detección correcta."""

    def _make_presenter_with_autodetect(self):
        view = FakeAutoDetectView()
        sf = MagicMock()
        p = ImportPresenter(view, sf)
        p._current_file_path = Path("/tmp/lista.csv")
        return p, view

    def test_autodetecta_columnas_por_nombre_exacto(self) -> None:
        """Headers ['barcode', 'name', 'net_cost'] se auto-mapean sin intervención."""
        presenter, view = self._make_presenter_with_autodetect()
        headers = ["barcode", "name", "net_cost"]

        presenter.on_file_loaded(headers, [])

        mapping = view.get_column_mapping()
        assert mapping["barcode"] == "barcode"
        assert mapping["name"] == "name"
        assert mapping["net_cost"] == "net_cost"

    def test_autodetecta_columnas_por_alias(self) -> None:
        """Header 'codigo' se mapea a 'barcode'; 'costo_neto' se mapea a 'net_cost'."""
        presenter, view = self._make_presenter_with_autodetect()
        headers = ["codigo", "descripcion", "costo_neto"]

        presenter.on_file_loaded(headers, [])

        mapping = view.get_column_mapping()
        assert mapping["barcode"] == "codigo"
        assert mapping["name"] == "descripcion"
        assert mapping["net_cost"] == "costo_neto"

    def test_no_autodetecta_columna_ambigua(self) -> None:
        """Header sin alias conocido queda sin asignar."""
        presenter, view = self._make_presenter_with_autodetect()
        headers = ["col_x", "col_y", "col_z"]

        presenter.on_file_loaded(headers, [])

        mapping = view.get_column_mapping()
        assert mapping.get("barcode") == _UNASSIGNED
        assert mapping.get("name") == _UNASSIGNED
        assert mapping.get("net_cost") == _UNASSIGNED
