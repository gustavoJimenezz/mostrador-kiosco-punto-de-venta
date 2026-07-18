# Ticket 3.3 — Tabla invertida de mapeo + banner de estado en ImportView

**Fecha:** 2026-03-16

## Resumen

Rediseño del widget de mapeo de columnas en la vista de importación masiva. Se reemplaza el esquema anterior (un `QComboBox` por cada columna del archivo, orientación horizontal) por una tabla invertida de 4 filas fijas —una por campo destino— que escala correctamente con cualquier cantidad de columnas. Se agrega un banner de estado dinámico que guía al usuario en tiempo real con colores semánticos (amarillo/rojo/verde).

## Cambios Principales

- Nuevo widget `_MappingTableWidget(QTableWidget)` con 4 filas fijas (`barcode`, `name`, `net_cost`, `category`) y auto-detección de columnas por alias normalizados
- Banner dinámico `_banner_label` con tres estados: campos faltantes (amarillo), columna duplicada (rojo), mapeo completo (verde)
- Nuevo dataclass `MappingStatus` en el presenter con `message`, `bg_color` y `valid`
- Constante `_AUTOMAP_ALIASES` con aliases en español/inglés para detección automática
- Inversión del formato de `column_mapping`: de `{col_archivo: campo_destino}` a `{campo_destino: col_archivo}`
- Eliminada lógica de `drop_cols` en `BulkPriceImporter.parse_dataframe()`
- Eliminada clase `TestImportPresenter` obsoleta de `test_bulk_importer.py` (referenciaba path inexistente)

## Flujo de Trabajo

**Punto de entrada:** El usuario selecciona un archivo CSV o Excel.

```
[Archivo seleccionado]
    → FileLoadWorker carga headers y filas
    → ImportPresenter._on_headers_loaded()
    → ImportView.show_mapping_table(headers)
        → _MappingTableWidget.populate(headers)   ← llena los combos
        → _MappingTableWidget.auto_detect(headers) ← pre-selecciona por alias
        → ImportView._on_mapping_changed()
            → _on_mapping_changed calcula MappingStatus
            → show_mapping_status(status) ← actualiza banner + botón
```

**Proceso de mapeo:**

1. La tabla muestra siempre 4 filas (los campos destino del sistema), campos requeridos en negrita con `*`
2. El usuario ajusta los combos si la auto-detección no acertó
3. Cada cambio en un combo dispara `mapping_changed` → recalcula el banner

**Auto-detección:**
- Normaliza los headers del archivo (minúsculas, sin acentos via `unicodedata`)
- Compara contra `_AUTOMAP_ALIASES` (ej: `"codigo"`, `"cod_barras"` → `barcode`)
- Pre-selecciona el combo si hay coincidencia; no sobreescribe si ya está seleccionado

**Validación del banner:**

| Condición | Color | Botón |
|-----------|-------|-------|
| Al menos un campo requerido sin asignar | Amarillo `#fef9c3` | Deshabilitado |
| Una columna del archivo asignada a ≥2 campos | Rojo `#fee2e2` | Deshabilitado |
| Los 3 campos requeridos asignados, sin duplicados | Verde `#dcfce7` | Habilitado |

**Importación:**
```
[Botón "Importar"]
    → ImportView._on_import_clicked()
    → import_requested.emit(get_column_mapping())  ← {campo_destino: col_archivo}
    → ImportPresenter.on_import_requested(mapping)
        → valida campos requeridos (nuevo formato invertido)
        → lanza ImportWorker
    → BulkPriceImporter.parse_dataframe(df, mapping)
        → itera {campo_destino: col_archivo}
        → renombra columnas del DataFrame
        → valida y construye DTOs
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/presenters/import_presenter.py` | Agrega `MappingStatus`, `_AUTOMAP_ALIASES`, `_UNASSIGNED`, `_IGNORE`; actualiza `IImportView` con `show_mapping_table`, `show_mapping_status`, `get_column_mapping`; invierte formato en `on_import_requested` |
| `src/infrastructure/ui/views/import_view.py` | Rediseño completo: nuevo `_MappingTableWidget`, banner `_banner_label`, elimina scroll de combos y sincronización de anchos |
| `src/infrastructure/importers/bulk_price_importer.py` | `parse_dataframe()` acepta nuevo formato `{campo_destino: col_archivo}`; elimina `drop_cols`; agrega `_UNASSIGNED`/`_IGNORE` |
| `tests/unit/ui/test_import_presenter.py` | `FakeImportView` actualizada con nuevos métodos; tests de `on_import_requested` migrados al nuevo formato |
| `tests/unit/importers/test_bulk_importer.py` | Elimina `FakeImportView` y `TestImportPresenter` obsoletos (referenciaban `import_dialog` inexistente) |

## Notas Técnicas

- **Sin circular imports:** `import_view.py` importa `MappingStatus` y `_AUTOMAP_ALIASES` desde `import_presenter.py`; el presenter nunca importa desde la vista.
- **Señales bloqueadas durante populate/auto_detect:** `blockSignals(True/False)` evita que el banner se recalcule N veces durante la carga inicial; solo se recalcula una vez al final de `show_mapping_table()`.
- **Columnas extra son inofensivas:** `_validate_and_build` solo usa las columnas renombradas por el mapeo; las columnas no mapeadas simplemente se ignoran en el DataFrame.
- **`_UNASSIGNED` vs `_IGNORE`:** Ambos valores se tratan como "sin mapear" en el presenter y en el importer. `_IGNORE` se mantiene por compatibilidad semántica para futuros casos donde el usuario quiera marcar explícitamente una columna como ignorada.
