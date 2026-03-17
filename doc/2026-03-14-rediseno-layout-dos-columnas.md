# Rediseño de interfaz — layout dos columnas con paleta clean/high-contrast

**Fecha:** 2026-03-14

## Resumen

Reemplazo del layout vertical monocolumna del POS por un diseño de dos columnas inspirado en la maqueta `maqueteado/opcion1.html`. Se aplicó una paleta visual indigo/emerald con estilo clean/high-contrast directamente en el archivo `.ui` mediante QSS inline, sin modificar la capa Python.

## Cambios Principales

- Reescritura completa de `src/infrastructure/ui/windows/main_window.ui`
- Layout raíz cambiado de `QVBoxLayout` a `QHBoxLayout`
- División de la interfaz en `left_panel` (flexible) y `right_panel` (fijo 400px)
- Botones de acción reorganizados de fila horizontal a grilla 2×2 (`QGridLayout`)
- `total_label` movido al panel derecho como elemento visual dominante (52px, fondo indigo #4f46e5)
- QSS completo incrustado en `styleSheet` de `central_widget` con paleta indigo/emerald
- Sin cambios en `main_window.py` — compatibilidad total con todos los `findChild` existentes

## Flujo de Trabajo

```
[QHBoxLayout: main_layout]
        |
        ├── [left_panel — QVBoxLayout, stretch]
        │       ├── barcode_row  (QHBoxLayout)
        │       │       ├── barcode_label
        │       │       └── barcode_input
        │       ├── search_row   (QHBoxLayout)
        │       │       ├── search_label
        │       │       └── search_input  (visible=false por defecto)
        │       ├── search_results  (QListWidget, maxH=200, visible=false)
        │       └── cart_table   (QTableWidget, stretch vertical)
        │
        └── [right_panel — QVBoxLayout, fijo 400px]
                ├── total_label  (indigo, 52px, centrado)
                ├── action_buttons_container
                │       └── buttons_grid  (QGridLayout 2×2)
                │               ├── [0,0] btn_new_sale   "F1 - Nueva Venta"
                │               ├── [0,1] btn_search     "F2 - Buscar"
                │               ├── [1,0] btn_cash_close "F10 - Cierre Caja"
                │               └── [1,1] btn_confirm    "F4 - Cobrar" (emerald)
                └── spacer vertical
```

**Punto de entrada:** `QUiLoader` carga `main_window.ui` en `MainWindowPresenter.__init__`.

**Proceso:** El QSS incrustado en `central_widget.styleSheet` se aplica en cascada a todos los widgets hijos. PySide6 respeta `minimumWidth`/`maximumWidth` para fijar el panel derecho.

**Resultado:** La UI presenta al operador el carrito a la izquierda (espacio completo) y el total + botones a la derecha, estilo POS moderno.

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/windows/main_window.ui` | Reescritura completa: nuevo layout + QSS |

## Notas Técnicas

- **Compatibilidad Python:** Todos los `objectName` se preservaron intactos (`barcode_input`, `search_input`, `search_results`, `cart_table`, `total_label`, `btn_new_sale`, `btn_search`, `btn_cash_close`, `btn_confirm`). Ningún `findChild` en `main_window.py` se ve afectado.
- **Toggle de búsqueda:** `_toggle_search` sigue funcionando; Qt colapsa automáticamente el espacio de `search_input` y `search_results` al ocultarlos dentro del `QVBoxLayout`.
- **QSS inline vs archivo externo:** Se optó por incrustarlo en el `.ui` para mantener el componente autocontenido y simplificar el despliegue.
- **Paleta:** Indigo `#4f46e5` para acento principal y fondo del total; Emerald `#10b981` para `btn_confirm`; grises neutros `#f9fafb` / `#e5e7eb` / `#6b7280` para fondo y textos secundarios.
- **Ancho fijo del panel derecho:** Implementado con `minimumWidth = maximumWidth = 400` sobre `right_panel`, sin necesidad de `QSizePolicy` explícita en el `.ui`.
