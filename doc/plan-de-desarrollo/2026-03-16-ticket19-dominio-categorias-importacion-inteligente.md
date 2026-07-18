# Ticket 19 — Dominio de Categorías e Importación Inteligente

**Fecha:** 2026-03-16

## Resumen

Implementación completa del ciclo de categorías en el sistema POS: se creó la entidad de dominio `Category`, su repositorio con protocolo hexagonal, la tabla `categories` en la base de datos con su FK hacia `products`, y la resolución automática de nombre→id durante la importación masiva de listas de precios.

El objetivo principal fue conectar el campo `category` (ya documentado como destino válido en el importador) con la lógica de persistencia, permitiendo que al importar un CSV/Excel se asigne automáticamente el `category_id` correcto al producto según el nombre de categoría presente en el archivo.

---

## Cambios Principales

- Nueva entidad de dominio `Category` (Python puro, sin dependencias externas) con validación de nombre (vacío, >100 caracteres)
- Nuevo protocolo `CategoryRepository` (`runtime_checkable`) con métodos `get_by_name`, `save` y `list_all`
- Implementación `MariaDbCategoryRepository` usando SQLAlchemy Core con búsqueda normalizada `LOWER(name)` para case-insensitive
- Nueva tabla `categories` en el esquema con índice en `name` y constraint `UNIQUE`
- FK `fk_products_category_id` en `products.category_id` con `ON DELETE SET NULL`
- Migración Alembic que aplica ambos cambios DDL de forma reversible
- Campo `category_name: str = ""` agregado a `ProductImportRow` (DTO del use case)
- `UpdateBulkPrices` recibe `category_repo` opcional e inyecta `category_id` en INSERT y UPDATE
- `BulkPriceImporter._process_row()` extrae el campo `category` del DataFrame
- `ImportWorker` crea `MariaDbCategoryRepository` e inyecta en `UpdateBulkPrices`
- 14 tests nuevos: 7 de dominio + 7 de integración unitaria (importer + use case)

---

## Flujo de Trabajo

### Importación masiva con resolución de categoría

```
[Archivo CSV/Excel]
       ↓
[FileLoadWorker] — lee con Polars, emite headers para mapping interactivo
       ↓
[ImportWorker.run()]
       ↓
[BulkPriceImporter.parse_dataframe(df, column_mapping)]
    → renombra columnas según mapeo del usuario
    → _process_row(): extrae category_name (opcional, default "")
    → ProductImportRow(..., category_name="Golosinas")
       ↓
[MariaDbCategoryRepository.list_all()]  ← 1 solo SELECT
    → category_map = {"golosinas": 3, "bebidas": 7, ...}
       ↓
[UpdateBulkPrices.execute(rows)]
    → para cada fila: category_id = category_map.get(category_name.strip().lower())
    → INSERT nuevos con category_id resuelto
    → UPDATE existentes con category_id resuelto
    → 1 commit() atómico
       ↓
[ImportResult] — contadores inserted/updated/skipped/errors
```

### Normalización de nombres (DoD)

| Entrada en archivo | Lookup key | category_id resuelto |
|--------------------|-----------|----------------------|
| `"GOLOSINAS"`      | `"golosinas"` | ✓ id correcto     |
| `"golosinas"`      | `"golosinas"` | ✓ id correcto     |
| `"  Golosinas  "`  | `"golosinas"` | ✓ id correcto     |
| `""`               | `""`          | `NULL` (sin error) |
| `"Inexistente"`    | `"inexistente"` | `NULL` (sin error)|

---

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/domain/models/category.py` | **Nuevo** — entidad `Category` con validación |
| `src/domain/ports/category_repository.py` | **Nuevo** — protocolo `CategoryRepository` |
| `src/infrastructure/persistence/mariadb_category_repository.py` | **Nuevo** — implementación SQLAlchemy Core |
| `alembic/versions/3f2a1b4c8d90_agregar_tabla_categories_y_fk.py` | **Nuevo** — migración DDL (categories + FK) |
| `tests/domain/test_category.py` | **Nuevo** — 7 tests de dominio puro |
| `tests/unit/domain/mocks/in_memory_category_repository.py` | **Nuevo** — mock para tests sin DB |
| `src/infrastructure/persistence/tables.py` | **Modificado** — `categories_table` + FK en `products.category_id` |
| `src/application/use_cases/update_bulk_prices.py` | **Modificado** — `category_name` en DTO, `category_repo` en `__init__`, resolución en `execute()` |
| `src/infrastructure/importers/bulk_price_importer.py` | **Modificado** — extrae `category_name` en `_process_row()` |
| `src/infrastructure/ui/workers/import_worker.py` | **Modificado** — inyecta `MariaDbCategoryRepository` en `UpdateBulkPrices` |
| `tests/unit/importers/test_bulk_importer.py` | **Modificado** — 7 casos nuevos de categorías |

---

## Notas Técnicas

- **Performance:** el mapa de categorías se carga con un único `SELECT *` antes del loop de upsert. No hay N+1 queries por fila.
- **Backward compatibility:** `category_repo` es `Optional` en `UpdateBulkPrices.__init__`. Sin repo, `category_id` queda `NULL` en todos los productos sin romper código existente.
- **ON DELETE SET NULL:** si se elimina una categoría de la tabla `categories`, los productos asociados quedan con `category_id = NULL` en lugar de violar la FK.
- **Mapeo imperativo:** `Category` no usa herencia de SQLAlchemy. El repositorio MariaDB opera directamente contra `categories_table` con SQLAlchemy Core, igual que el resto de repositorios del proyecto.
- **Migración Alembic:** la FK se agrega sobre la columna `category_id` ya existente (sin recrear la tabla), usando `op.create_foreign_key()`. El `down_revision` apunta a `1bafd69c0714` (migración inicial).
