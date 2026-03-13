"""Tests unitarios para BulkPriceImporter, UpdateBulkPrices e ImportPresenter.

Cobertura:
    BulkPriceImporter:
        - Parse CSV con formato argentino (coma decimal, punto de miles).
        - Columnas opcionales con defaults.
        - Acumulación de errores por fila (no aborta el lote).
        - Error al faltar columnas requeridas.
        - Error si el archivo no existe.
        - Extensión no soportada.

    UpdateBulkPrices:
        - INSERT de productos nuevos.
        - UPDATE de productos existentes con cambio de costo + historial.
        - Skip de productos sin cambio de costo.
        - Lote vacío retorna resultado vacío.

    ImportPresenter:
        - on_select_file_requested devuelve None si el usuario cancela.
        - on_select_file_requested actualiza estado si hay archivo.
        - on_import_completed muestra resumen correcto.
        - on_import_error muestra mensaje de error.
"""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, call, patch

import pytest

from src.application.use_cases.update_bulk_prices import (
    ImportResult,
    ImportRowError,
    ProductImportRow,
    UpdateBulkPrices,
)
from src.infrastructure.importers.bulk_price_importer import BulkPriceImporter
from src.infrastructure.ui.windows.import_dialog import ImportPresenter


# ---------------------------------------------------------------------------
# Helpers: CSV en memoria (sin archivos en disco)
# ---------------------------------------------------------------------------

def _write_csv(tmp_path: Path, content: str) -> Path:
    """Escribe un CSV temporal y retorna su Path."""
    file = tmp_path / "test.csv"
    file.write_text(content, encoding="utf-8")
    return file


# ---------------------------------------------------------------------------
# Fixtures de datos (10 productos)
# Nota: campos numéricos con coma decimal DEBEN estar entrecomillados en CSV,
# ya que la coma también es el delimitador del archivo.
# ---------------------------------------------------------------------------

# CSV con formato argentino: punto de miles + coma decimal (campos entrecomillados)
CSV_VALID = """\
barcode,name,cost_price,margin_percent,stock,min_stock
7790001000001,Coca Cola 500ml,"1.250,50","30,00",50,5
7790001000002,Pepsi 500ml,"1.100,00","28,00",30,3
7790001000003,Agua Ser 500ml,"450,00","40,00",100,10
7790001000004,Alfajor Jorgito,"350,00","50,00",200,20
7790001000005,Galletitas Oreo,"980,00","35,00",80,8
7790001000006,Chocolate Milka,"2.100,00","45,00",40,4
7790001000007,Papas Lays,"1.500,00","38,00",60,6
7790001000008,Caramelos Halls,"200,00","60,00",150,15
7790001000009,Shampoo Sedal,"3.200,00","30,00",25,2
7790001000010,Cuaderno Gloria,"5.800,00","25,00",15,1
"""

# CSV con formato inglés estándar (punto decimal), sin separador de miles
CSV_MINIMAL = """\
barcode,name,cost_price
7790001000001,Coca Cola 500ml,1250
7790001000002,Pepsi 500ml,1100
"""

# CSV con filas erróneas mezcladas con una fila válida
CSV_WITH_ERRORS = """\
barcode,name,cost_price,margin_percent,stock,min_stock
,Producto sin barcode,100,30,1,0
7790001000001,,1000,30,1,0
7790001000002,Producto con costo cero,0,30,1,0
7790001000003,Producto costo negativo,-100,30,1,0
7790001000004,Producto valido,500,30,1,0
"""

CSV_MISSING_COLUMN = """\
barcode,name
7790001000001,Coca Cola 500ml
"""


# ---------------------------------------------------------------------------
# Tests: BulkPriceImporter — parsing
# ---------------------------------------------------------------------------

class TestBulkPriceImporterParse:
    def test_parse_csv_formato_argentino(self, tmp_path: Path) -> None:
        """CSV con coma decimal y punto de miles se convierte correctamente.

        Algoritmo: remove "." → replace "," → "." → Decimal.
        Ejemplo: "1.250,50" → "1250,50" → "1250.50" → Decimal("1250.50").
        """
        csv_file = _write_csv(tmp_path, CSV_VALID)
        result = BulkPriceImporter().parse(csv_file)

        assert len(result.valid_rows) == 10
        assert result.errors == []
        assert result.valid_rows[0].barcode == "7790001000001"
        assert result.valid_rows[0].cost_price == Decimal("1250.50")
        assert result.valid_rows[0].margin_percent == Decimal("30.00")

    def test_parse_csv_formato_entero(self, tmp_path: Path) -> None:
        """CSV con precios como enteros (sin decimales) se convierte correctamente."""
        csv_file = _write_csv(tmp_path, CSV_MINIMAL)
        result = BulkPriceImporter().parse(csv_file)

        assert len(result.valid_rows) == 2
        assert result.valid_rows[0].cost_price == Decimal("1250")
        assert result.valid_rows[1].cost_price == Decimal("1100")

    def test_columnas_opcionales_con_defaults(self, tmp_path: Path) -> None:
        """Columnas opcionales ausentes usan defaults: margin=30, stock=0, min_stock=0."""
        csv_file = _write_csv(tmp_path, CSV_MINIMAL)
        result = BulkPriceImporter().parse(csv_file)

        row = result.valid_rows[0]
        assert row.margin_percent == Decimal("30")
        assert row.stock == 0
        assert row.min_stock == 0

    def test_errores_de_fila_no_abortan_lote(self, tmp_path: Path) -> None:
        """Filas inválidas acumulan errores pero el lote continúa."""
        csv_file = _write_csv(tmp_path, CSV_WITH_ERRORS)
        result = BulkPriceImporter().parse(csv_file)

        assert len(result.valid_rows) == 1
        assert result.valid_rows[0].barcode == "7790001000004"
        assert len(result.errors) == 4

    def test_error_barcode_vacio(self, tmp_path: Path) -> None:
        """Fila con barcode vacío genera ImportRowError con razón correcta."""
        csv_file = _write_csv(tmp_path, CSV_WITH_ERRORS)
        result = BulkPriceImporter().parse(csv_file)

        barcode_errors = [e for e in result.errors if "barcode" in e.reason.lower()]
        assert len(barcode_errors) == 1
        assert barcode_errors[0].row_number == 2

    def test_columna_requerida_faltante_lanza_error(self, tmp_path: Path) -> None:
        """CSV sin columna requerida lanza ValueError con nombres de columnas."""
        csv_file = _write_csv(tmp_path, CSV_MISSING_COLUMN)
        with pytest.raises(ValueError, match="cost_price"):
            BulkPriceImporter().parse(csv_file)

    def test_archivo_no_existe(self, tmp_path: Path) -> None:
        """Archivo inexistente lanza FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            BulkPriceImporter().parse(tmp_path / "no_existe.csv")

    def test_extension_no_soportada(self, tmp_path: Path) -> None:
        """Archivo con extensión no soportada lanza ValueError."""
        bad_file = tmp_path / "lista.txt"
        bad_file.write_text("barcode,name,cost_price\n")
        with pytest.raises(ValueError, match=".txt"):
            BulkPriceImporter().parse(bad_file)

    def test_source_row_corresponde_a_numero_de_fila(self, tmp_path: Path) -> None:
        """source_row en DTO corresponde al número de fila real (base 2)."""
        csv_file = _write_csv(tmp_path, CSV_MINIMAL)
        result = BulkPriceImporter().parse(csv_file)

        assert result.valid_rows[0].source_row == 2
        assert result.valid_rows[1].source_row == 3


# ---------------------------------------------------------------------------
# Tests: _parse_decimal (casos edge)
# ---------------------------------------------------------------------------

class TestParseDecimal:
    def test_formato_argentino_completo(self) -> None:
        """'1.250,50' → Decimal('1250.50') (punto de miles eliminado, coma → punto)."""
        result = BulkPriceImporter._parse_decimal("1.250,50")
        assert result == Decimal("1250.50")

    def test_solo_coma_decimal(self) -> None:
        """'1250,50' → Decimal('1250.50')."""
        result = BulkPriceImporter._parse_decimal("1250,50")
        assert result == Decimal("1250.50")

    def test_formato_ingles(self) -> None:
        """'1250.50' con formato inglés — el punto se elimina → '125050'."""
        result = BulkPriceImporter._parse_decimal("1250.50")
        # Comportamiento documentado: punto de miles se elimina primero
        assert result == Decimal("125050")

    def test_entero_simple(self) -> None:
        """'500' → Decimal('500')."""
        result = BulkPriceImporter._parse_decimal("500")
        assert result == Decimal("500")

    def test_string_vacio_retorna_none(self) -> None:
        result = BulkPriceImporter._parse_decimal("")
        assert result is None

    def test_string_invalido_retorna_none(self) -> None:
        result = BulkPriceImporter._parse_decimal("no_es_numero")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: UpdateBulkPrices (mock de sesión SQLAlchemy)
# ---------------------------------------------------------------------------

def _make_row(barcode: str, cost: str = "1000", i: int = 1) -> ProductImportRow:
    """Factory de ProductImportRow para tests."""
    return ProductImportRow(
        barcode=barcode,
        name=f"Producto {barcode}",
        cost_price=Decimal(cost),
        margin_percent=Decimal("30.00"),
        stock=10,
        min_stock=1,
        source_row=i + 1,
    )


class TestUpdateBulkPrices:
    def _make_session(self, existing_rows: list[dict] | None = None):
        """Crea un mock de Session con resultados preconfigurados para SELECT."""
        session = MagicMock()

        if existing_rows is None:
            existing_rows = []

        # Simular execute() → resultado iterable con atributos .barcode, .id, .current_cost
        mock_rows = []
        for data in existing_rows:
            mock_row = MagicMock()
            mock_row.barcode = data["barcode"]
            mock_row.id = data["id"]
            mock_row.current_cost = data["current_cost"]
            mock_rows.append(mock_row)

        session.execute.return_value = iter(mock_rows)
        return session

    def test_lote_vacio_retorna_resultado_vacio(self) -> None:
        """Un lote vacío retorna ImportResult con todos los contadores en 0."""
        session = self._make_session()
        result = UpdateBulkPrices(session).execute([])

        assert result.inserted == 0
        assert result.updated == 0
        assert result.skipped == 0
        session.commit.assert_not_called()

    def test_insert_productos_nuevos(self) -> None:
        """Productos con barcodes no existentes se insertan masivamente."""
        session = self._make_session(existing_rows=[])
        rows = [_make_row("7790001000001"), _make_row("7790001000002")]

        # Primer execute = SELECT (retorna vacío), segundo = INSERT
        session.execute.side_effect = [iter([]), MagicMock()]

        result = UpdateBulkPrices(session).execute(rows)

        assert result.inserted == 2
        assert result.updated == 0
        assert result.skipped == 0
        session.commit.assert_called_once()

    def test_update_con_cambio_de_costo(self) -> None:
        """Producto existente con costo distinto genera UPDATE + historial."""
        existing = [{"barcode": "7790001000001", "id": 1, "current_cost": Decimal("800")}]
        session = self._make_session(existing_rows=existing)

        mock_existing_result = MagicMock()
        mock_existing_result.barcode = "7790001000001"
        mock_existing_result.id = 1
        mock_existing_result.current_cost = Decimal("800")
        session.execute.side_effect = [iter([mock_existing_result]), MagicMock(), MagicMock(), MagicMock()]

        row = _make_row("7790001000001", cost="1000")
        result = UpdateBulkPrices(session).execute([row])

        assert result.updated == 1
        assert result.inserted == 0
        assert result.skipped == 0
        session.commit.assert_called_once()

    def test_skip_sin_cambio_de_costo(self) -> None:
        """Producto existente con mismo costo se omite (skipped)."""
        existing = [{"barcode": "7790001000001", "id": 1, "current_cost": Decimal("1000")}]
        session = self._make_session(existing_rows=existing)

        mock_existing_result = MagicMock()
        mock_existing_result.barcode = "7790001000001"
        mock_existing_result.id = 1
        mock_existing_result.current_cost = Decimal("1000")
        session.execute.side_effect = [iter([mock_existing_result])]

        row = _make_row("7790001000001", cost="1000")
        result = UpdateBulkPrices(session).execute([row])

        assert result.skipped == 1
        assert result.updated == 0
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: ImportPresenter (FakeImportView)
# ---------------------------------------------------------------------------

class FakeImportView:
    """Vista falsa para testear ImportPresenter sin Qt."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path
        self.status_messages: list[str] = []
        self.progress_visible: list[bool] = []
        self.button_enabled: list[bool] = []
        self.closed = False

    def show_status(self, message: str) -> None:
        self.status_messages.append(message)

    def show_progress(self, visible: bool) -> None:
        self.progress_visible.append(visible)

    def enable_select_button(self, enabled: bool) -> None:
        self.button_enabled.append(enabled)

    def ask_file_path(self) -> Optional[Path]:
        return self._file_path

    def close_dialog(self) -> None:
        self.closed = True


class TestImportPresenter:
    def test_on_select_file_retorna_none_si_usuario_cancela(self) -> None:
        """Si ask_file_path retorna None, on_select_file_requested retorna None."""
        view = FakeImportView(file_path=None)
        presenter = ImportPresenter(view)

        result = presenter.on_select_file_requested()

        assert result is None
        assert view.status_messages == []
        assert view.progress_visible == []

    def test_on_select_file_actualiza_estado_si_hay_archivo(self, tmp_path: Path) -> None:
        """Si el usuario selecciona un archivo, el presenter actualiza estado."""
        file = tmp_path / "lista.csv"
        file.touch()
        view = FakeImportView(file_path=file)
        presenter = ImportPresenter(view)

        result = presenter.on_select_file_requested()

        assert result == file
        assert any("lista.csv" in msg for msg in view.status_messages)
        assert True in view.progress_visible
        assert False in view.button_enabled

    def test_on_import_completed_muestra_resumen(self) -> None:
        """on_import_completed muestra resumen con contadores correctos."""
        view = FakeImportView()
        presenter = ImportPresenter(view)

        import_result = ImportResult(inserted=5, updated=3, skipped=2, errors=[])
        presenter.on_import_completed(import_result)

        assert any("5" in msg for msg in view.status_messages)
        assert any("3" in msg for msg in view.status_messages)
        assert False in view.progress_visible
        assert True in view.button_enabled

    def test_on_import_error_muestra_mensaje(self) -> None:
        """on_import_error muestra el mensaje de error recibido."""
        view = FakeImportView()
        presenter = ImportPresenter(view)

        presenter.on_import_error("Conexión rechazada")

        assert any("Conexión rechazada" in msg for msg in view.status_messages)
        assert False in view.progress_visible
        assert True in view.button_enabled

    def test_on_import_completed_muestra_cantidad_errores(self) -> None:
        """Resumen incluye la cantidad de errores de fila."""
        view = FakeImportView()
        presenter = ImportPresenter(view)

        errors = [
            ImportRowError(row_number=3, barcode="123", reason="costo inválido"),
            ImportRowError(row_number=7, barcode="", reason="barcode vacío"),
        ]
        import_result = ImportResult(inserted=8, updated=0, skipped=1, errors=errors)
        presenter.on_import_completed(import_result)

        assert any("2" in msg for msg in view.status_messages)
