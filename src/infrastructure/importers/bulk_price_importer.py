"""Adaptador de importación masiva de listas de precios de proveedores.

Lee archivos CSV o Excel (xlsx/xls) usando Polars con todo como ``String``
para manejar el formato numérico argentino (coma decimal, punto de miles).

Columnas requeridas:
    barcode       — Código de barras EAN-13.
    name          — Nombre/descripción del producto.
    cost_price    — Costo de compra (ej: "1.250,50" o "1250.50").

Columnas opcionales (con defaults):
    margin_percent — Margen de ganancia % (default: "30.00").
    stock          — Stock inicial (default: "0").
    min_stock      — Stock mínimo para alerta (default: "0").

Uso::

    result = BulkPriceImporter().parse("/ruta/lista.csv")
    # result.valid_rows  → list[ProductImportRow]
    # result.errors      → list[ImportRowError]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Union

import polars as pl

from src.application.use_cases.update_bulk_prices import ImportRowError, ProductImportRow

_REQUIRED_COLUMNS = {"barcode", "name", "cost_price"}
_UNASSIGNED = "(sin asignar)"
_IGNORE = "(ignorar)"

_OPTIONAL_DEFAULTS: dict[str, str] = {
    "margin_percent": "30",   # Entero; _parse_decimal lo convierte a Decimal("30")
    "stock": "0",
    "min_stock": "0",
}


@dataclass
class ParseResult:
    """Resultado del parsing de un archivo CSV/Excel.

    Attributes:
        valid_rows: Filas correctamente validadas, listas para el use case.
        errors: Errores por fila (no abortan el lote).
    """

    valid_rows: list[ProductImportRow] = field(default_factory=list)
    errors: list[ImportRowError] = field(default_factory=list)


class BulkPriceImporter:
    """Adaptador Polars para importación de listas de precios de proveedores.

    Lee CSV o Excel, valida schema y filas, y produce DTOs limpios.
    Los errores de fila se acumulan sin abortar el lote completo.
    """

    def parse(self, file_path: Union[str, Path]) -> ParseResult:
        """Lee y valida un archivo CSV o Excel de lista de precios.

        Args:
            file_path: Ruta al archivo CSV (.csv) o Excel (.xlsx/.xls).

        Returns:
            ParseResult con filas válidas y errores por fila.

        Raises:
            ValueError: Si el archivo no tiene extensión soportada.
            FileNotFoundError: Si el archivo no existe.
            Exception: Si Polars no puede leer el archivo (formato inválido).
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {path}")

        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pl.read_csv(path, infer_schema_length=0)
        elif suffix in {".xlsx", ".xls"}:
            df = pl.read_excel(path, infer_schema_length=0)
        else:
            raise ValueError(
                f"Extensión no soportada: '{suffix}'. Use .csv, .xlsx o .xls."
            )

        return self.parse_dataframe(df)

    def parse_dataframe(
        self,
        df: pl.DataFrame,
        column_mapping: dict[str, str] | None = None,
        global_margin: Decimal | None = None,
    ) -> ParseResult:
        """Valida y construye DTOs desde un DataFrame ya cargado.

        Si ``column_mapping`` se provee (``{campo_destino: col_archivo}``),
        renombra las columnas antes de validar. Las entradas cuya columna sea
        ``_UNASSIGNED`` o ``_IGNORE`` se omiten. El campo destino ``net_cost``
        se traduce internamente a ``cost_price`` para el validador.

        Si ``global_margin`` se provee, sobreescribe incondicionalmente el
        ``margin_percent`` de cada fila, ignorando el valor del archivo.

        Args:
            df: DataFrame de Polars (todo como String).
            column_mapping: Mapeo ``{campo_destino: nombre_columna_archivo}``.
                            Campos destino: ``barcode``, ``name``, ``net_cost``,
                            ``category``.
                            Si es None, se usa el DataFrame sin modificaciones.
            global_margin: Margen de ganancia porcentual a aplicar a todas las
                           filas. Si es None, se usa el valor del archivo o el
                           default de 30%.

        Returns:
            ParseResult con filas válidas y errores acumulados.
        """
        if column_mapping:
            rename_map: dict[str, str] = {}
            _ALIAS = {"net_cost": "cost_price"}

            for dest_field, file_col in column_mapping.items():
                if file_col in {_UNASSIGNED, _IGNORE, ""}:
                    continue
                if file_col not in df.columns:
                    continue
                internal = _ALIAS.get(dest_field, dest_field)
                rename_map[file_col] = internal

            if rename_map:
                df = df.rename(rename_map)

        return self._validate_and_build(df, global_margin=global_margin)

    def _validate_and_build(
        self,
        df: pl.DataFrame,
        global_margin: Decimal | None = None,
    ) -> ParseResult:
        """Valida el schema del DataFrame y construye los DTOs.

        Args:
            df: DataFrame de Polars (todo como String).
            global_margin: Si se provee, sobreescribe el margen de cada fila.

        Returns:
            ParseResult con filas válidas y errores acumulados.
        """
        result = ParseResult()

        # Validar columnas requeridas
        missing = _REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Columnas requeridas ausentes: {', '.join(sorted(missing))}. "
                f"Columnas presentes: {', '.join(df.columns)}"
            )

        for row_idx, row_data in enumerate(df.iter_rows(named=True), start=2):
            # row_idx comienza en 2 (fila 1 = encabezado)
            self._process_row(row_idx, row_data, result, global_margin=global_margin)

        return result

    def _process_row(
        self,
        row_number: int,
        row_data: dict,
        result: ParseResult,
        global_margin: Decimal | None = None,
    ) -> None:
        """Valida y convierte una fila individual.

        Errores de validación se agregan a ``result.errors`` sin lanzar excepción.

        Args:
            row_number: Número de fila en el archivo original (base 2 por encabezado).
            row_data: Diccionario con los valores de la fila como strings.
            result: ParseResult donde acumular válidos o errores.
            global_margin: Si se provee, reemplaza incondicionalmente el margen de la fila.
        """
        barcode = (row_data.get("barcode") or "").strip()

        if not barcode:
            result.errors.append(
                ImportRowError(
                    row_number=row_number,
                    barcode="",
                    reason="Campo 'barcode' vacío o ausente.",
                )
            )
            return

        name = (row_data.get("name") or "").strip()
        if not name:
            result.errors.append(
                ImportRowError(
                    row_number=row_number,
                    barcode=barcode,
                    reason="Campo 'name' vacío o ausente.",
                )
            )
            return

        cost_raw = (row_data.get("cost_price") or "").strip()
        cost_price = self._parse_decimal(cost_raw)
        if cost_price is None or cost_price <= Decimal("0"):
            result.errors.append(
                ImportRowError(
                    row_number=row_number,
                    barcode=barcode,
                    reason=f"'cost_price' inválido o <= 0: '{cost_raw}'.",
                )
            )
            return

        if global_margin is not None:
            margin_percent = global_margin
        else:
            margin_raw = (
                row_data.get("margin_percent") or _OPTIONAL_DEFAULTS["margin_percent"]
            ).strip()
            margin_percent = self._parse_decimal(margin_raw)
            if margin_percent is None or margin_percent < Decimal("0"):
                result.errors.append(
                    ImportRowError(
                        row_number=row_number,
                        barcode=barcode,
                        reason=f"'margin_percent' inválido: '{margin_raw}'.",
                    )
                )
                return

        stock = self._parse_int(
            (row_data.get("stock") or _OPTIONAL_DEFAULTS["stock"]).strip()
        )
        if stock is None:
            result.errors.append(
                ImportRowError(
                    row_number=row_number,
                    barcode=barcode,
                    reason=f"'stock' inválido: '{row_data.get('stock')}'.",
                )
            )
            return

        min_stock = self._parse_int(
            (row_data.get("min_stock") or _OPTIONAL_DEFAULTS["min_stock"]).strip()
        )
        if min_stock is None:
            result.errors.append(
                ImportRowError(
                    row_number=row_number,
                    barcode=barcode,
                    reason=f"'min_stock' inválido: '{row_data.get('min_stock')}'.",
                )
            )
            return

        category_name = (row_data.get("category") or "").strip()

        result.valid_rows.append(
            ProductImportRow(
                barcode=barcode,
                name=name,
                cost_price=cost_price,
                margin_percent=margin_percent,
                stock=stock,
                min_stock=min_stock,
                source_row=row_number,
                category_name=category_name,
            )
        )

    @staticmethod
    def _parse_decimal(value: str) -> Decimal | None:
        """Convierte un string numérico a Decimal detectando el formato automáticamente.

        Heurística:
            - Si contiene coma → formato argentino (coma=decimal, punto=miles).
              Ej: "1.250,50" → Decimal("1250.50"), "843,00" → Decimal("843.00").
            - Si no contiene coma → formato inglés o entero (punto=decimal).
              Ej: "843.00" → Decimal("843.00"), "1250" → Decimal("1250").

        Args:
            value: String numérico a convertir.

        Returns:
            Decimal si la conversión es exitosa, None si el formato es inválido.
        """
        if not value:
            return None
        try:
            if "," in value:
                # Formato argentino: eliminar puntos de miles, reemplazar coma decimal
                normalized = value.replace(".", "").replace(",", ".")
            else:
                # Formato inglés o entero: usar tal cual
                normalized = value
            return Decimal(normalized)
        except InvalidOperation:
            return None

    @staticmethod
    def _parse_int(value: str) -> int | None:
        """Convierte un string a entero.

        Args:
            value: String numérico entero.

        Returns:
            int si la conversión es exitosa, None si el formato es inválido.
        """
        if not value:
            return 0
        try:
            return int(value)
        except ValueError:
            return None
