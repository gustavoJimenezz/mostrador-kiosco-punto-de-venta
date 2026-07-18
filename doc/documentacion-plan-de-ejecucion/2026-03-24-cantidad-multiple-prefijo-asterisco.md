# Carga de cantidad múltiple con prefijo N*

**Fecha:** 2026-03-24

## Resumen

Se implementó la posibilidad de ingresar una cantidad antes de escanear o buscar un producto usando el formato `N*código` o `N*nombre`. Esto permite al cajero cargar varias unidades de un mismo artículo en una sola operación, sin tener que escanear repetidamente o editar la cantidad manualmente en el carrito.

## Cambios Principales

- `SalePresenter._add_product_to_cart` acepta parámetro `quantity: int = 1` en lugar de incrementar siempre en 1.
- `SalePresenter.on_barcode_found` y `on_product_selected_from_list` propagán el parámetro `quantity` al método interno.
- Se agregó validación de stock para cantidad inicial > 1 (cuando el producto aún no está en el carrito).
- `MainWindow._on_barcode_entered` parsea el prefijo `N*` antes de lanzar el worker; para barcode usa un lambda que captura la cantidad, para búsqueda por nombre almacena la cantidad en `_pending_quantity`.
- `MainWindow._on_search_item_selected` consume y resetea `_pending_quantity` al agregar el producto seleccionado de la lista.
- Se agregó `_pending_quantity: int = 1` como atributo de instancia inicializado en `__init__`.
- Se agregó `QLabel#barcode_hint_label` en `main_window.ui` debajo del input, con texto explicativo del formato `N*`.

## Flujo de Trabajo

```
Cajero escribe "3*7790001234" y presiona Enter
    │
    ▼
_on_barcode_entered detecta "*" → prefix="3", rest="7790001234"
    │
    ├─ rest.isdigit() → SearchByBarcodeWorker(text="7790001234")
    │       │
    │       └─ product_found → lambda p, q=3: presenter.on_barcode_found(p, 3)
    │                               │
    │                               └─ _add_product_to_cart(product, quantity=3)
    │
    └─ rest no es dígito (ej: "3*coca") → _pending_quantity = 3
            │
            └─ SearchByNameWorker(text="coca")
                    │
                    └─ results_ready → show_search_results (lista visible)
                            │
                            └─ cajero selecciona ítem → _on_search_item_selected
                                    │
                                    └─ on_product_selected_from_list(product, quantity=3)
                                            │
                                            └─ _add_product_to_cart(product, quantity=3)
```

Sin prefijo, el comportamiento es idéntico al anterior (agrega 1 unidad).

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/presenters/sale_presenter.py` | `_add_product_to_cart`, `on_barcode_found` y `on_product_selected_from_list` con parámetro `quantity` |
| `src/infrastructure/ui/windows/main_window.py` | Parseo de prefijo `N*`, atributo `_pending_quantity`, conexión con lambda |
| `src/infrastructure/ui/windows/main_window.ui` | Nuevo `QLabel#barcode_hint_label` debajo del input + estilo CSS |

## Notas Técnicas

- El prefijo acepta cualquier entero positivo; si el número es 0 o negativo se normaliza a 1 (`max(1, int(prefix))`).
- La cantidad pendiente `_pending_quantity` se resetea a 1 inmediatamente después de consumirse en `_on_search_item_selected`, evitando que afecte búsquedas posteriores si el cajero cancela la selección.
- El label hint usa `font-size: 11px` y `color: #6b7280` para ser informativo sin competir visualmente con el input principal.
