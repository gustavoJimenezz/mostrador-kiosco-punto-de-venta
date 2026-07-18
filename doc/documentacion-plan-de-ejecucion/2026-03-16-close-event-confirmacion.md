# Modal de Confirmación al Cerrar la Aplicación (closeEvent)

**Fecha:** 2026-03-16
**Ticket:** #23 — `feat(ui/main): modal de confirmación al cerrar la aplicación`

## Resumen

Se implementó la intercepción del evento de cierre de la ventana principal para exigir confirmación explícita del usuario antes de terminar el proceso. Si hay una venta en curso, el modal adapta su mensaje para advertir sobre la pérdida de datos del carrito activo.

## Cambios Principales

- Nuevo método `closeEvent(event)` en `MainWindow` que intercepta toda ruta de cierre (Alt+F4, botón X, `sys.exit`)
- Nuevo método `_shutdown_database()` que detiene el `DatabaseLauncher` si está activo
- Nuevo método `_restore_barcode_focus()` que devuelve el foco al lector de barras tras cancelar el modal
- Nuevo método `has_active_sale_items() -> bool` en `SalePresenter` para consultar si hay ítems en el carrito
- Imports agregados en `main_window.py`: `QCloseEvent`, `QMessageBox`
- Nuevo archivo de tests unitarios con 8 casos cubriendo todos los flujos del DoD

## Flujo de Trabajo

**Punto de entrada:** El usuario intenta cerrar la ventana (Alt+F4, botón X o `sys.exit`). Qt dispara `closeEvent`.

**Proceso:**
1. `closeEvent` consulta `presenter.has_active_sale_items()`
2. Si hay venta en curso → mensaje advierte pérdida de datos
3. Si el carrito está vacío → mensaje genérico de confirmación
4. Se muestra `QMessageBox.Warning` con botones "Salir" y "Cancelar"
5. El usuario elige

**Resultado:**
```
[closeEvent]
    ↓
[¿Venta en curso?] → Sí → Mensaje con advertencia de pérdida de datos
                   → No → Mensaje genérico
    ↓
[QMessageBox] → "Salir"    → _shutdown_database() → event.accept() [APP CIERRA]
             → "Cancelar" → event.ignore() → _restore_barcode_focus() [APP SIGUE]
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/windows/main_window.py` | `closeEvent`, `_shutdown_database`, `_restore_barcode_focus`; imports `QCloseEvent` y `QMessageBox` |
| `src/infrastructure/ui/presenters/sale_presenter.py` | Nuevo método `has_active_sale_items() -> bool` |
| `tests/unit/ui/test_main_window_close_event.py` | Nuevo — 8 tests unitarios |

## Notas Técnicas

- `event.ignore()` en la rama "Cancelar" es obligatorio; sin él Qt cierra la ventana de igual manera.
- Se usa `dialog.addButton()` explícito en lugar de `QMessageBox.question()` estático para controlar los textos de los botones en español.
- `_shutdown_database` usa guard `hasattr(self, '_db_launcher')` para no romper si el launcher aún no fue inyectado (integración futura con Ticket 11).
- Los tests parchean `_load_ui` y `_setup_shortcuts` para instanciar `MainWindow` sin el archivo `.ui`, y parchean `QMessageBox` para simular la elección del usuario sin mostrar ventanas reales.
