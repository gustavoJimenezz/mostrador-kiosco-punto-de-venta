# Fix: Edición de producto existente + Margen global en importador

**Fecha:** 2026-03-19

## Resumen

Se corrigieron dos bugs independientes: el primero impedía editar un producto ya existente (el sistema lo trataba como nuevo y colisionaba con el UNIQUE de código de barras); el segundo afectaba al parser de decimales del importador, que eliminaba incorrectamente el punto como si fuera separador de miles en precios con formato inglés (ej: `843.00` se leía como `84300`). Adicionalmente, se incorporó la funcionalidad de margen global en la UI del importador, permitiendo sobreescribir el margen de todas las filas del archivo con un valor único elegido por el usuario.

---

## Cambios Principales

- **Fix `session.add()` → `session.merge()`** en `MariadbProductRepository.save()`: permite actualizar productos existentes desde una sesión nueva sin violar el constraint UNIQUE de `barcode`.
- **Margen global en el importador**: nuevo checkbox + spinner en `ImportView` que, al estar activado, aplica un margen uniforme a todas las filas importadas, ignorando la columna `margin_percent` del archivo.
- **Fix `_parse_decimal`**: nueva heurística que distingue formato argentino (con coma) de formato inglés/entero (sin coma), eliminando el bug que interpretaba `843.00` como `84300`.
- **`margin_percent` con default `Decimal("30")`** en el modelo `Product`, evitando errores cuando el campo no está presente en el archivo importado.
- **Tests actualizados**: dos tests nuevos para `global_margin` y corrección del test de formato inglés que documentaba el comportamiento incorrecto anterior.

---

## Flujo de Trabajo

### Fix edición de producto

```
Usuario edita producto → Presenter construye Product(id=X) transiente
→ SaveProductWorker abre sesión nueva
→ session.merge(product)       ← detecta id existente → emite UPDATE
→ session.flush() + commit()
→ save_completed emitido con producto actualizado
```

**Antes (bug):**
```
session.add(product con id=X)  ← objeto transiente → intenta INSERT
→ IntegrityError: UNIQUE constraint 'barcode'
```

---

### Margen global en importador

```
Usuario activa checkbox "Margen global" → ingresa valor (ej: 45%)
→ _on_import_clicked() incluye global_margin en el mapping dict
→ ImportPresenter extrae global_margin del dict
→ ImportWorker recibe global_margin
→ BulkPriceImporter.parse_dataframe(..., global_margin=45)
→ _process_row(): si global_margin is not None → usa ese valor
                  si global_margin is None     → usa columna del archivo o default 30%
```

---

### Fix `_parse_decimal`

```
Antes:  "843.00" → elimina puntos → "84300" → Decimal("84300")  ← BUG
Ahora:  "843.00" → sin coma → formato inglés → Decimal("843.00")  ✓

        "1.250,50" → tiene coma → elimina puntos, coma→punto → Decimal("1250.50")  ✓
```

---

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/persistence/mariadb_product_repository.py` | `session.add()` → `session.merge()` en `save()` |
| `src/domain/models/product.py` | `margin_percent` con default `Decimal("30")` |
| `src/infrastructure/importers/bulk_price_importer.py` | Parámetro `global_margin` propagado en `parse_dataframe`, `_validate_and_build` y `_process_row`; nueva heurística en `_parse_decimal` |
| `src/infrastructure/ui/views/import_view.py` | Checkbox + `QDoubleSpinBox` para margen global; `global_margin` incluido en el dict emitido por `import_requested` |
| `src/infrastructure/ui/presenters/import_presenter.py` | Extrae `global_margin` del dict de mapeo antes de pasarlo al worker |
| `src/infrastructure/ui/workers/import_worker.py` | Acepta y propaga `global_margin` a `BulkPriceImporter` |
| `tests/unit/importers/test_bulk_importer.py` | Tests `test_global_margin_sobreescribe_margen_de_fila`, `test_sin_global_margin_usa_margen_del_archivo`, `test_formato_ingles_no_multiplica_por_100`; corrección de `test_formato_ingles` |

---

## Notas Técnicas

- **Por qué `merge()` y no `add()`:** `SaveProductWorker` crea una sesión nueva por cada operación (requisito de threading en SQLAlchemy). El objeto `Product` construido por el presenter es **transiente** (sin estado de sesión). `session.add()` sobre un objeto transiente con PK siempre emite `INSERT`; `session.merge()` consulta primero la identity map y luego la DB por PK, emitiendo `UPDATE` si el registro existe.
- **`merge()` retorna la instancia gestionada:** el objeto original pasado a `merge()` queda sin trackin; el objeto retornado (`merged`) es el que está vinculado a la sesión. El worker devuelve `merged` al presenter.
- **Margen global vs columna del archivo:** son mutuamente excluyentes por fila. Si `global_margin` está presente, se salta completamente la lectura de `margin_percent` del CSV/Excel, incluyendo su validación. Si la columna no existe en el archivo, el comportamiento por defecto (`Decimal("30")`) también aplica.
- **Heurística `_parse_decimal`:** la presencia de coma es el discriminador. No existe formato válido que use coma como separador de miles sin coma decimal (el formato argentino siempre usa coma como decimal).
