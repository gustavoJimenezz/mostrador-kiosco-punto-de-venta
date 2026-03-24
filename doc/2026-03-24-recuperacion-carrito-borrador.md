# Recuperación de carrito ante cortes de luz o cierres inesperados

**Fecha:** 2026-03-24

## Resumen

Se implementó la persistencia del carrito de venta en progreso mediante un archivo JSON local. Cada modificación del carrito se guarda automáticamente en disco, de modo que al reiniciar la aplicación tras un corte de luz o cierre involuntario, los productos cargados se restauran en pantalla sin pérdida de información.

## Cambios Principales

- Nuevo puerto `DraftCartRepository` en la capa de dominio (contrato de persistencia del borrador)
- Nueva implementación `JsonDraftCartRepository` con escritura atómica (archivo temporal + `os.replace`) en `~/.kiosco_pos/draft_cart.json`
- Nuevo caso de uso `RestoreDraftCart`: carga IDs del borrador, busca productos en DB y valida stock antes de restaurar
- `SalePresenter` ahora acepta un `draft_repo` opcional; guarda el borrador en cada cambio del carrito y lo elimina al completar o cancelar la venta
- `main.py` instancia el repositorio de borrador, lo inyecta al presenter y ejecuta la restauración automática al inicio si existe un borrador
- Mensaje de cierre actualizado: ya no advierte pérdida de datos sino que informa que la venta se guardará

## Flujo de Trabajo

### Guardado (en cada operación sobre el carrito)

```
Cajero agrega/modifica/elimina producto
  → SalePresenter actualiza _cart
  → _save_draft() serializa {product_id: quantity}
  → JsonDraftCartRepository.save() escribe ~/.kiosco_pos/draft_cart.json (atómico)
```

### Restauración al inicio

```
main.py inicia → draft_repo.has_draft() = True
  → RestoreDraftCart.execute()
      → load() lee {product_id: quantity} del archivo JSON
      → get_by_id() consulta cada producto en DB (precio y stock actualizados)
      → recorta cantidad si supera stock disponible
      → omite productos eliminados del catálogo
  → presenter.restore_from_draft(items)
      → puebla _cart
      → refresca tabla del carrito y total en pantalla
```

### Limpieza (fin de venta o nueva venta)

```
F4/F12 → venta confirmada → on_sale_completed() → _clear_cart()
  → draft_repo.clear() → elimina draft_cart.json

F1 (nueva venta) → on_new_sale() → _clear_cart()
  → draft_repo.clear() → elimina draft_cart.json
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/domain/ports/draft_cart_repository.py` | Nuevo — Puerto Protocol con `save / load / clear / has_draft` |
| `src/domain/ports/__init__.py` | Exporta `DraftCartRepository` |
| `src/infrastructure/persistence/json_draft_cart_repository.py` | Nuevo — Implementación JSON con escritura atómica |
| `src/application/use_cases/restore_draft_cart.py` | Nuevo — Caso de uso de restauración con validación de stock |
| `src/infrastructure/ui/presenters/sale_presenter.py` | Inyección de `draft_repo`; `_save_draft()` en cada cambio; `restore_from_draft()`; `_clear_cart()` limpia el borrador |
| `src/infrastructure/ui/windows/main_window.py` | Mensaje de `closeEvent` actualizado |
| `src/main.py` | Instancia `JsonDraftCartRepository`, restaura borrador antes de `window.show()` |

## Notas Técnicas

- **Escritura atómica:** `save()` escribe en un `.tmp` y luego llama `os.replace()`. En sistemas POSIX y NTFS, `os.replace` es atómico, lo que garantiza que un corte de luz durante la escritura no deje el archivo en estado corrupto. Si el proceso muere antes de `os.replace`, el archivo anterior queda intacto.
- **Retrocompatibilidad:** `draft_repo` es un parámetro opcional en `SalePresenter.__init__`. Los tests unitarios existentes (47) no requieren cambios y siguen pasando sin inyectar el repositorio.
- **Stock actualizado:** Al restaurar, los precios y el stock se obtienen de la DB en ese momento, no del borrador. Si la cantidad guardada supera el stock actual (por ejemplo, otra terminal vendió ese producto), la cantidad se recorta al máximo disponible.
- **Ubicación del archivo:** `~/.kiosco_pos/draft_cart.json`. En Windows compila a `C:\Users\<usuario>\.kiosco_pos\draft_cart.json`. El directorio se crea automáticamente si no existe.
