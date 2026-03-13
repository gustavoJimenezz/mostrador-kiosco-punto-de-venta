"""Caso de uso: importación masiva de precios de proveedores.

DTOs:
    ProductImportRow  — fila validada lista para persistir.
    ImportRowError    — error de validación de una fila (no aborta el lote).
    ImportResult      — resultado agregado de la operación.

El use case recibe solo DTOs ya validados (sin Polars). La validación
schema + filas ocurre en ``BulkPriceImporter`` (infraestructura).

Estrategia de upsert (performance < 3 s para 5.000 filas):
    1. Un solo ``SELECT IN`` para los barcodes recibidos.
    2. INSERT masivo para productos nuevos.
    3. UPDATE individual + INSERT de historial para cambios de costo.
    4. Un único ``commit()`` al finalizar.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from src.infrastructure.persistence.tables import price_history_table, products_table

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ProductImportRow:
    """DTO de una fila ya validada del CSV/Excel del proveedor.

    Attributes:
        barcode: Código de barras EAN-13 del producto.
        name: Nombre o descripción del producto.
        cost_price: Costo de compra en ARS (Decimal, siempre > 0).
        margin_percent: Margen de ganancia en porcentaje (ej: 30.00).
        stock: Stock inicial o a actualizar.
        min_stock: Nivel mínimo de stock para alerta.
        source_row: Número de fila original en el archivo (para trazabilidad).
    """

    barcode: str
    name: str
    cost_price: Decimal
    margin_percent: Decimal
    stock: int
    min_stock: int
    source_row: int


@dataclass
class ImportRowError:
    """Error de validación de una fila del CSV/Excel.

    Un error de fila no aborta el lote; se acumula y se reporta al final.

    Attributes:
        row_number: Número de fila en el archivo original (base 1).
        barcode: Barcode de la fila, si estaba disponible.
        reason: Descripción del error de validación.
    """

    row_number: int
    barcode: str
    reason: str


@dataclass
class ImportResult:
    """Resultado agregado de la importación masiva.

    Attributes:
        inserted: Cantidad de productos nuevos insertados.
        updated: Cantidad de productos existentes actualizados.
        skipped: Cantidad de filas sin cambios (costo idéntico).
        errors: Lista de errores de validación por fila.
    """

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[ImportRowError] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total de filas procesadas (sin errores)."""
        return self.inserted + self.updated + self.skipped


class UpdateBulkPrices:
    """Caso de uso: upsert masivo de productos y registro de historial de precios.

    Recibe filas ya validadas (``list[ProductImportRow]``) y ejecuta:

    - INSERT masivo para barcodes no existentes.
    - UPDATE de ``current_cost``, ``margin_percent``, ``stock``, ``min_stock``
      para barcodes existentes con costo distinto.
    - INSERT masivo en ``price_history`` para cada cambio de costo.
    - Un único ``commit()`` al finalizar (todo o nada).

    Args:
        session: Sesión SQLAlchemy activa. El caller es responsable de cerrarla.
    """

    def __init__(self, session: Session) -> None:
        """Inicializa el use case con la sesión de base de datos.

        Args:
            session: Sesión SQLAlchemy 2.0 activa.
        """
        self._session = session

    def execute(self, rows: list[ProductImportRow]) -> ImportResult:
        """Ejecuta el upsert masivo.

        Args:
            rows: Lista de DTOs validados. Si está vacía, retorna resultado vacío.

        Returns:
            ImportResult con contadores de insertados, actualizados y omitidos.
        """
        result = ImportResult()

        if not rows:
            return result

        all_barcodes = [row.barcode for row in rows]

        # --- 1. Consulta masiva: qué barcodes ya existen ---
        stmt = select(
            products_table.c.id,
            products_table.c.barcode,
            products_table.c.current_cost,
        ).where(products_table.c.barcode.in_(all_barcodes))

        existing: dict[str, dict] = {
            row.barcode: {"id": row.id, "current_cost": row.current_cost}
            for row in self._session.execute(stmt)
        }

        # --- 2. Separar en nuevos vs. existentes ---
        new_products: list[dict] = []
        updates: list[tuple[str, dict, ProductImportRow]] = []  # (barcode, existing_data, row)

        for row in rows:
            if row.barcode not in existing:
                new_products.append(
                    {
                        "barcode": row.barcode,
                        "name": row.name,
                        "current_cost": row.cost_price,
                        "margin_percent": row.margin_percent,
                        "stock": row.stock,
                        "min_stock": row.min_stock,
                    }
                )
            else:
                updates.append((row.barcode, existing[row.barcode], row))

        # --- 3. INSERT masivo de productos nuevos ---
        if new_products:
            self._session.execute(products_table.insert(), new_products)
            result.inserted = len(new_products)

        # --- 4. UPDATE para existentes con cambio de costo + historial ---
        now = datetime.datetime.now()
        history_entries: list[dict] = []

        for barcode, existing_data, row in updates:
            old_cost = Decimal(str(existing_data["current_cost"]))

            if old_cost == row.cost_price:
                result.skipped += 1
                continue

            self._session.execute(
                products_table.update()
                .where(products_table.c.barcode == barcode)
                .values(
                    current_cost=row.cost_price,
                    margin_percent=row.margin_percent,
                    stock=row.stock,
                    min_stock=row.min_stock,
                )
            )

            history_entries.append(
                {
                    "product_id": existing_data["id"],
                    "old_cost": old_cost,
                    "new_cost": row.cost_price,
                    "updated_at": now,
                }
            )
            result.updated += 1

        # --- 5. INSERT masivo de historial de precios ---
        if history_entries:
            self._session.execute(price_history_table.insert(), history_entries)

        # --- 6. Commit único (atomicidad) ---
        self._session.commit()

        return result
