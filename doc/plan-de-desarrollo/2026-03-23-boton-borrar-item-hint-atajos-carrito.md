# Botón "Borrar ítem" y label de ayuda en el carrito

**Fecha:** 2026-03-23

## Resumen

Se agregó un botón visual "Borrar ítem" en la pantalla de venta para eliminar con el mouse el producto seleccionado del carrito, complementando el atajo de teclado `Supr` ya existente. Se incorporó además un label de ayuda debajo del carrito que informa al operador los dos atajos disponibles para borrar (`F1` y `Supr`), con color oscuro para garantizar legibilidad.

## Cambios Principales

- Nuevo botón `btn_delete_item` (rojo/peligro) en la fila inferior del panel izquierdo, a la derecha del carrito
- Nuevo label `hint_delete_label` con el texto: _"F1 borra todo el carrito · Supr borra el ítem seleccionado"_
- CSS para `btn_delete_item`: estilo danger con borde rojo suave, hover rojo, estado disabled gris
- CSS para `hint_delete_label`: color `#374151` (oscuro legible), fuente 11px
- Conexión del botón a `_on_cart_delete_key` (mismo handler que la tecla `Supr`)

## Flujo de Trabajo

```
[Clic en "Borrar ítem"] → _on_cart_delete_key() → presenter.on_remove_selected_item(product_id) → carrito actualizado
[Tecla Supr en cart_table] → eventFilter → _on_cart_delete_key() → mismo flujo
```

- **Punto de entrada:** clic en `btn_delete_item` o tecla `Supr` con foco en `cart_table`
- **Proceso:** `_on_cart_delete_key` obtiene la fila seleccionada, extrae el `product_id` del rol `Qt.UserRole` y delega al presenter
- **Resultado:** la fila se elimina del carrito y el total se recalcula

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/windows/main_window.ui` | Nuevo CSS para `btn_delete_item` y `hint_delete_label`; nuevo layout `cart_actions_row` con label + spacer + botón debajo del `cart_table` |
| `src/infrastructure/ui/windows/main_window.py` | Búsqueda de `btn_delete_item` por nombre en `_load_ui` y conexión de su señal `clicked` a `_on_cart_delete_key` |

## Notas Técnicas

- El botón reutiliza exactamente el mismo handler `_on_cart_delete_key` que el `eventFilter` para la tecla `Supr`, sin duplicar lógica.
- El color del label se eligió `#374151` (gris oscuro base de la app) para máxima legibilidad sin competir visualmente con el contenido del carrito.
- El botón incluye estado `:disabled` en CSS para poder deshabilitarlo programáticamente cuando el carrito esté vacío (extensión futura).
