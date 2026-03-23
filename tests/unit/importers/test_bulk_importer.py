"""Tests unitarios para BulkPriceImporter y UpdateBulkPrices.

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
"""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.application.use_cases.update_bulk_prices import (
    ImportResult,
    ImportRowError,
    ProductImportRow,
    UpdateBulkPrices,
)
from src.infrastructure.importers.bulk_price_importer import BulkPriceImporter
from tests.unit.domain.mocks.in_memory_category_repository import InMemoryCategoryRepository
from src.domain.models.category import Category


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
# Tests: BulkPriceImporter — parse_dataframe (nuevo formato {dest: col_archivo})
# ---------------------------------------------------------------------------

class TestBulkPriceImporterParseDataframe:
    """Tests de parse_dataframe() con el formato {campo_destino: col_archivo} (Ticket 3.3)."""

    def test_parse_dataframe_con_mapping_nuevo_formato(self) -> None:
        """parse_dataframe acepta {campo_destino: col_archivo} y renombra correctamente."""
        import polars as pl

        df = pl.DataFrame({
            "Código EAN": ["7790001000001", "7790001000002"],
            "Descripción": ["Coca Cola", "Pepsi"],
            "Costo Neto": ["1250", "1100"],
        })
        mapping = {
            "barcode": "Código EAN",
            "name": "Descripción",
            "net_cost": "Costo Neto",
        }

        result = BulkPriceImporter().parse_dataframe(df, mapping)

        assert len(result.valid_rows) == 2
        assert result.errors == []
        assert result.valid_rows[0].barcode == "7790001000001"
        assert result.valid_rows[0].name == "Coca Cola"

    def test_parse_dataframe_alias_net_cost_a_cost_price(self) -> None:
        """El alias net_cost→cost_price se aplica correctamente con el nuevo formato."""
        import polars as pl

        df = pl.DataFrame({
            "ean": ["7790001000001"],
            "prod": ["Fideos Don Victorio"],
            "precio": ["850"],
        })
        mapping = {
            "barcode": "ean",
            "name": "prod",
            "net_cost": "precio",
        }

        result = BulkPriceImporter().parse_dataframe(df, mapping)

        assert len(result.valid_rows) == 1
        assert result.valid_rows[0].cost_price == Decimal("850")

    def test_parse_dataframe_columna_ignorar_se_descarta(self) -> None:
        """Entradas con col_archivo '(ignorar)' se omiten sin romper el parsing."""
        import polars as pl

        df = pl.DataFrame({
            "barcode": ["7790001000001"],
            "name": ["Galletitas Oreo"],
            "cost_price": ["980"],
            "columna_extra": ["ignorada"],
        })
        mapping = {
            "barcode": "barcode",
            "name": "name",
            "net_cost": "cost_price",
            "category": "(ignorar)",
        }

        result = BulkPriceImporter().parse_dataframe(df, mapping)

        assert len(result.valid_rows) == 1
        assert result.errors == []

    def test_parse_dataframe_col_archivo_inexistente_se_ignora(self) -> None:
        """Si col_archivo no existe en el DataFrame, la entrada del mapping se omite sin error."""
        import polars as pl

        df = pl.DataFrame({
            "barcode": ["7790001000001"],
            "name": ["Alfajor Jorgito"],
            "cost_price": ["350"],
        })
        # "columna_que_no_existe" no está en el DataFrame
        mapping = {
            "barcode": "barcode",
            "name": "name",
            "net_cost": "cost_price",
            "category": "columna_que_no_existe",
        }

        result = BulkPriceImporter().parse_dataframe(df, mapping)

        assert len(result.valid_rows) == 1
        assert result.errors == []

    def test_parse_dataframe_sin_mapping_usa_nombres_directos(self) -> None:
        """Si column_mapping es None, el DataFrame se valida con sus nombres originales."""
        import polars as pl

        df = pl.DataFrame({
            "barcode": ["7790001000001", "7790001000002"],
            "name": ["Agua Ser 500ml", "Sprite 500ml"],
            "cost_price": ["450", "520"],
        })

        result = BulkPriceImporter().parse_dataframe(df, column_mapping=None)

        assert len(result.valid_rows) == 2
        assert result.errors == []

    def test_global_margin_sobreescribe_margen_de_fila(self) -> None:
        """global_margin reemplaza incondicionalmente el margin_percent de cada fila."""
        import polars as pl

        df = pl.DataFrame({
            "barcode": ["7790001000001", "7790001000002"],
            "name": ["Coca Cola", "Pepsi"],
            "cost_price": ["1250", "1100"],
            "margin_percent": ["20", "25"],
        })

        result = BulkPriceImporter().parse_dataframe(df, global_margin=Decimal("45"))

        assert result.valid_rows[0].margin_percent == Decimal("45")
        assert result.valid_rows[1].margin_percent == Decimal("45")

    def test_sin_global_margin_usa_margen_del_archivo(self) -> None:
        """Sin global_margin se respeta el margin_percent del archivo."""
        import polars as pl

        df = pl.DataFrame({
            "barcode": ["7790001000001"],
            "name": ["Coca Cola"],
            "cost_price": ["1250"],
            "margin_percent": ["20"],
        })

        result = BulkPriceImporter().parse_dataframe(df, global_margin=None)

        assert result.valid_rows[0].margin_percent == Decimal("20")


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
        """'1250.50' con formato inglés — el punto es decimal → Decimal('1250.50')."""
        result = BulkPriceImporter._parse_decimal("1250.50")
        assert result == Decimal("1250.50")

    def test_formato_ingles_no_multiplica_por_100(self) -> None:
        """'843.00' → Decimal('843.00'), no Decimal('84300') (bug previo)."""
        result = BulkPriceImporter._parse_decimal("843.00")
        assert result == Decimal("843.00")

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

def _make_row(
    barcode: str,
    cost: str = "1000",
    i: int = 1,
    category_name: str = "",
) -> ProductImportRow:
    """Factory de ProductImportRow para tests."""
    return ProductImportRow(
        barcode=barcode,
        name=f"Producto {barcode}",
        cost_price=Decimal(cost),
        margin_percent=Decimal("30.00"),
        stock=10,
        min_stock=1,
        source_row=i + 1,
        category_name=category_name,
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
# Tests: columna 'category' en BulkPriceImporter
# ---------------------------------------------------------------------------

class TestBulkPriceImporterCategory:
    """Tests de extracción del campo category en _process_row (Ticket 19)."""

    def test_columna_category_mapeada_se_extrae(self) -> None:
        """Columna 'category' mapeada → ProductImportRow.category_name se extrae."""
        import polars as pl

        df = pl.DataFrame({
            "barcode": ["7790001000001"],
            "name": ["Coca Cola 500ml"],
            "cost_price": ["1250"],
            "category": ["Bebidas"],
        })

        result = BulkPriceImporter().parse_dataframe(df)

        assert len(result.valid_rows) == 1
        assert result.valid_rows[0].category_name == "Bebidas"

    def test_sin_columna_category_category_name_vacio(self) -> None:
        """Sin columna 'category' en el DataFrame → category_name='' sin error."""
        import polars as pl

        df = pl.DataFrame({
            "barcode": ["7790001000001"],
            "name": ["Coca Cola 500ml"],
            "cost_price": ["1250"],
        })

        result = BulkPriceImporter().parse_dataframe(df)

        assert len(result.valid_rows) == 1
        assert result.valid_rows[0].category_name == ""
        assert result.errors == []


# ---------------------------------------------------------------------------
# Tests: resolución nombre→id en UpdateBulkPrices con InMemoryCategoryRepository
# ---------------------------------------------------------------------------

class TestUpdateBulkPricesConCategorias:
    """Tests de resolución de category_name → category_id (Ticket 19)."""

    def _make_session_insert(self):
        """Sesión mock que simula un SELECT vacío (productos nuevos) y permite INSERT."""
        session = MagicMock()
        session.execute.side_effect = [iter([]), MagicMock()]
        return session

    def test_categoria_existente_resuelve_id(self) -> None:
        """UpdateBulkPrices con repo resuelve nombre de categoría → category_id correcto."""
        category_repo = InMemoryCategoryRepository()
        golosinas = category_repo.save(Category(name="Golosinas"))

        session = self._make_session_insert()
        row = _make_row("7790001000001", category_name="Golosinas")

        UpdateBulkPrices(session, category_repo).execute([row])

        # Verificar que el INSERT incluyó category_id correcto
        insert_call_args = session.execute.call_args_list[1]
        values_list = insert_call_args[0][1]  # segundo argumento posicional = lista de dicts
        assert values_list[0]["category_id"] == golosinas.id

    def test_categoria_case_insensitive_y_trim(self) -> None:
        """'GOLOSINAS', 'golosinas' y '  Golosinas  ' resuelven al mismo category_id."""
        category_repo = InMemoryCategoryRepository()
        golosinas = category_repo.save(Category(name="Golosinas"))

        for name_variant in ["GOLOSINAS", "golosinas", "  Golosinas  "]:
            session = self._make_session_insert()
            row = _make_row("7790001000001", category_name=name_variant)
            UpdateBulkPrices(session, category_repo).execute([row])

            insert_call_args = session.execute.call_args_list[1]
            values_list = insert_call_args[0][1]
            assert values_list[0]["category_id"] == golosinas.id, (
                f"Falló para variant='{name_variant}'"
            )

    def test_categoria_inexistente_category_id_none(self) -> None:
        """Categoría no registrada → category_id=None, sin error."""
        category_repo = InMemoryCategoryRepository()
        # No se agrega ninguna categoría al repo

        session = self._make_session_insert()
        row = _make_row("7790001000001", category_name="CategoriaInexistente")
        UpdateBulkPrices(session, category_repo).execute([row])

        insert_call_args = session.execute.call_args_list[1]
        values_list = insert_call_args[0][1]
        assert values_list[0]["category_id"] is None

    def test_category_name_vacio_category_id_none(self) -> None:
        """category_name vacío → category_id=None, sin error."""
        category_repo = InMemoryCategoryRepository()
        category_repo.save(Category(name="Golosinas"))

        session = self._make_session_insert()
        row = _make_row("7790001000001", category_name="")
        UpdateBulkPrices(session, category_repo).execute([row])

        insert_call_args = session.execute.call_args_list[1]
        values_list = insert_call_args[0][1]
        assert values_list[0]["category_id"] is None

    def test_sin_category_repo_category_id_none(self) -> None:
        """Sin category_repo (None) → category_id=None para todos los productos."""
        session = self._make_session_insert()
        row = _make_row("7790001000001", category_name="Golosinas")
        UpdateBulkPrices(session, category_repo=None).execute([row])

        insert_call_args = session.execute.call_args_list[1]
        values_list = insert_call_args[0][1]
        assert values_list[0]["category_id"] is None
