# Ticket 3.4 — fix(ui/importers): bugs en ImportWorker, ImportPresenter y tests coherentes con Ticket 3.3

**Fecha:** 2026-03-16

## Resumen

Corrección de tres bugs críticos detectados en el flujo de importación masiva de listas de precios: manejo silencioso de errores en `ImportWorker`, ausencia de validación de columnas duplicadas en `ImportPresenter`, y eliminación de un breakpoint de debug en producción. Se añaden tests unitarios completos coherentes con el nuevo formato de mapeo `{campo_destino: col_archivo}` introducido en el Ticket 3.3.

## Cambios Principales

- **Bug 2 corregido:** `session_factory()` movido dentro del bloque `try/except` en `ImportWorker.run()` para garantizar que cualquier falla en la creación de sesión emita `error_occurred` en lugar de terminar silenciosamente.
- **Bug 1 corregido:** `ImportPresenter.on_import_requested()` valida ahora que dos campos destino distintos no apunten a la misma columna del archivo antes de lanzar el worker.
- **Limpieza:** Eliminado `import pdb; pdb.set_trace()` de `on_import_error()`.
- **Docstring corregido:** `ImportWorker` actualizó la descripción de `column_mapping` al formato nuevo `{campo_destino: col_archivo}`.
- **5 tests nuevos** en `TestBulkPriceImporterParseDataframe`: cubren el nuevo formato de mapping, alias `net_cost→cost_price`, columnas ignoradas/inexistentes y ausencia de mapping.
- **7 tests nuevos** en `TestImportPresenterOnImportRequested` y `TestImportPresenterAutoDetect`: mapeo válido con worker, campo faltante, columna duplicada, sin archivo, auto-detección por nombre exacto, por alias y sin alias.
- **4 tests nuevos** en `TestImportWorkerSessionFactory`: error en session_factory emite señal, no emite import_completed, cierre garantizado en finally, sin close si la factory falla.
- **Nuevo directorio** `tests/unit/ui/workers/` con su `__init__.py`.

## Flujo de Trabajo

### Bug 2 — Session factory dentro del try

```
ImportWorker.run()
  ├── session = None
  ├── try:
  │     session = self._session_factory()   ← ahora dentro del try
  │     ... lectura Polars + parse + upsert ...
  │     import_completed.emit(result)
  ├── except Exception as exc:
  │     error_occurred.emit(str(exc))        ← captura fallas de factory
  └── finally:
        if session is not None: session.close()
```

### Bug 1 — Validación de duplicados en presenter

```
on_import_requested(column_mapping)
  ├── Validar campos requeridos ausentes  → show_status(error) si falta alguno
  ├── Validar columnas duplicadas         → show_status(error) si hay conflicto
  ├── Validar _current_file_path no None  → show_status(error) si no hay archivo
  └── Lanzar ImportWorker
```

### Estrategia de tests para ImportWorker (sin QApplication)

```
ImportWorker.__new__(ImportWorker)       ← bypass de QThread.__init__
  ├── Inyectar atributos manualmente     ← _session_factory, _file_path, etc.
  ├── Reemplazar señales con MagicMock   ← error_occurred.emit capturado
  └── Llamar worker.run() directamente   ← sin hilo, síncrono y testeable
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/workers/import_worker.py` | `session_factory()` dentro del `try`; `finally` con guardia `is not None`; docstring del mapping corregido |
| `src/infrastructure/ui/presenters/import_presenter.py` | Validación de columnas duplicadas en `on_import_requested()`; eliminado breakpoint de debug |
| `tests/unit/importers/test_bulk_importer.py` | Nueva clase `TestBulkPriceImporterParseDataframe` (5 tests) |
| `tests/unit/ui/test_import_presenter.py` | Nuevas clases `TestImportPresenterOnImportRequested` (4 tests) y `TestImportPresenterAutoDetect` (3 tests); helper `FakeAutoDetectView` y función `_normalize` |
| `tests/unit/ui/workers/__init__.py` | Nuevo archivo (init del paquete de tests de workers) |
| `tests/unit/ui/workers/test_import_worker.py` | Nuevo archivo con `TestImportWorkerSessionFactory` (4 tests) y helper `_make_worker` |

## Notas Técnicas

- **`FakeAutoDetectView`:** Extiende `FakeImportView` y simula la lógica de auto-detección de `_MappingTableWidget.auto_detect()` usando `_AUTOMAP_ALIASES` del presenter, sin depender de PySide6. Permite testear el comportamiento completo del flujo `on_file_loaded → show_mapping_table → auto-detect`.

- **Técnica `__new__` para workers:** Los tests de `ImportWorker` instancian el worker con `ImportWorker.__new__(ImportWorker)` e inyectan atributos manualmente. Esto evita la necesidad de `QApplication` o un display, manteniendo los tests puramente unitarios y ejecutables en Linux.

- **Bug 3 (parse_dataframe):** El código de `parse_dataframe()` ya implementaba correctamente el formato `{campo_destino: col_archivo}` desde el Ticket 3.3. El Ticket 3.4 sólo añade la cobertura de tests para confirmar ese comportamiento.

- **Cobertura total tras Ticket 3.4:** `poetry run pytest tests/unit/importers/ tests/unit/ui/` → 91 tests, 0 fallos.
