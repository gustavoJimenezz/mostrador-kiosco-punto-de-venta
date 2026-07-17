# Modernización del Sistema de Estilos UI (Modo Claro) — Issue #25

**Fecha:** 2026-03-24

## Resumen

Centralización completa de todos los estilos QSS dispersos en 16 archivos `.py` y 182 líneas embebidas en `main_window.ui` dentro de un único módulo `theme.py` con paleta de modo claro. Se eliminaron todos los colores hex hard-codeados de las vistas, se modernizó el diseño visual con un sistema de tokens consistente y se mejoró la proporcionalidad de tablas y responsividad de layouts.

## Cambios Principales

- Creado `src/infrastructure/ui/theme.py`: paleta centralizada con 26 tokens de color, 7 constantes semánticas y 12 funciones `get_*_stylesheet()`
- Creado `tests/unit/ui/test_theme.py`: 39 tests unitarios que validan tokens, constantes y funciones sin necesidad de `QApplication`
- Eliminado el bloque `<property name="styleSheet">` de `main_window.ui` (182 líneas de QSS embebido)
- Migrados 15 archivos de vistas y diálogos para usar exclusivamente la paleta centralizada
- Resultado: 0 colores hex hard-codeados en archivos de vista (excepto los excluidos por diseño intencional)

## Flujo de Trabajo

```
main_window.ui (QSS embebido eliminado)
        ↓
theme.py::get_global_stylesheet()
        ↓ aplicado en main_window.py::_load_ui() tras setCentralWidget()
        ↓ hereda por cascada Qt a todos los widgets hijos
Vistas / Diálogos hijos de MainWindow
        → usan constantes SUCCESS_COLOR, DANGER_COLOR, etc. para colores dinámicos

Diálogos independientes (LoginWindow, OpenCashDialog, AdminPinDialog)
        → aplican get_dialog_stylesheet() en su propio __init__ (no heredan de MainWindow)
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/theme.py` | **Creado** — módulo central: `_Palette`, `PALETTE`, constantes semánticas, 12 funciones de stylesheet |
| `tests/unit/ui/test_theme.py` | **Creado** — 39 tests unitarios de paleta y funciones |
| `src/infrastructure/ui/windows/main_window.ui` | Eliminado bloque `<property name="styleSheet">` (182 líneas) |
| `src/infrastructure/ui/windows/main_window.py` | Aplica `get_global_stylesheet()`; 5 `setStyleSheet` inline → funciones de theme |
| `src/infrastructure/ui/windows/login_window.py` | Aplica `get_dialog_stylesheet()`; 9 `setStyleSheet` inline → constantes/funciones |
| `src/infrastructure/ui/windows/open_cash_dialog.py` | Aplica `get_dialog_stylesheet()`; colores `#ffffff` → `TEXT_PRIMARY_COLOR`; botones → funciones |
| `src/infrastructure/ui/dialogs/admin_pin_dialog.py` | Aplica `get_dialog_stylesheet()`; 6 `setStyleSheet` → `get_pin_input_stylesheet()` + funciones |
| `src/infrastructure/ui/dialogs/cash_close_dialog.py` | `setStyleSheet("padding: 6px 20px;")` → `get_btn_secondary_stylesheet()` |
| `src/infrastructure/ui/dialogs/cash_close_report_dialog.py` | 11 `setStyleSheet` + `QColor` hardcodeados → constantes semánticas y `PALETTE.border` |
| `src/infrastructure/ui/views/cash_close_view.py` | 14 `setStyleSheet` → constantes/funciones; `_btn_close` → `get_btn_primary_stylesheet()` |
| `src/infrastructure/ui/views/cash_movements_view.py` | 9 `setStyleSheet` + `QColor` → constantes y funciones de botón success/danger |
| `src/infrastructure/ui/views/cash_history_view.py` | 5 `setStyleSheet` + 4 `QColor` → constantes; `_btn_search` → `get_btn_primary_stylesheet()` |
| `src/infrastructure/ui/views/import_view.py` | 4 `setStyleSheet` → `PALETTE.danger_light/warning_light/success_light` y constantes |
| `src/infrastructure/ui/views/sales_history_view.py` | 4 `setStyleSheet` → `DANGER_COLOR`, `TEXT_SECONDARY_COLOR` |
| `src/infrastructure/ui/views/product_management_view.py` | 1 `setStyleSheet` → `DANGER_COLOR`, `TEXT_PRIMARY_COLOR` |
| `src/infrastructure/ui/views/stock_edit_view.py` | 1 `setStyleSheet` → `DANGER_COLOR`, `TEXT_PRIMARY_COLOR` |
| `src/infrastructure/ui/views/stock_inject_view.py` | 1 `setStyleSheet` → `DANGER_COLOR`, `TEXT_PRIMARY_COLOR` |

## Estructura de `theme.py`

### Paleta (`_Palette` — frozen dataclass)

| Grupo | Tokens |
|-------|--------|
| Fondos | `surface`, `surface_card`, `surface_input`, `surface_hover` |
| Primario (índigo) | `primary` `#4f46e5`, `primary_hover`, `primary_light` |
| Texto | `text_primary` `#374151`, `text_secondary`, `text_hint` |
| Bordes | `border` `#e5e7eb`, `border_focus` |
| Semánticos | `success` `#059669`, `danger` `#dc2626`, `warning_amber`, `teal`, `info` |
| Superficies semánticas | `danger_light`, `warning_light`, `success_light`, `info_surface`, `info_border`, `info_text` |
| Botón secundario | `btn_secondary_bg`, `btn_secondary_text`, `btn_secondary_hover` |

### Constantes exportadas

```python
SUCCESS_COLOR, DANGER_COLOR, WARNING_COLOR, INFO_COLOR
TEXT_PRIMARY_COLOR, TEXT_SECONDARY_COLOR, TEXT_HINT_COLOR
```

### Funciones de stylesheet

| Función | Uso |
|---------|-----|
| `get_global_stylesheet()` | Aplicado en `MainWindow`; hereda a toda la jerarquía Qt |
| `get_dialog_stylesheet()` | Diálogos independientes sin parent `MainWindow` |
| `get_btn_primary_stylesheet()` | Botones de acción principal (índigo) |
| `get_btn_secondary_stylesheet()` | Botones secundarios (gris) |
| `get_btn_success_stylesheet()` | Botones de ingreso / confirmación (verde) |
| `get_btn_danger_stylesheet()` | Botones de egreso / eliminación (rojo) |
| `get_btn_warning_stylesheet()` | Botones de advertencia (ámbar) |
| `get_btn_corner_teal_stylesheet()` | Botón "Cerrar caja" del corner widget |
| `get_btn_corner_primary_stylesheet()` | Botón admin desbloqueado |
| `get_btn_corner_secondary_stylesheet()` | Botón admin bloqueado |
| `get_pin_input_stylesheet()` | Campo PIN con tipografía de 24px y letter-spacing |
| `get_cash_status_badge_stylesheet()` | Badge de estado de caja en la barra superior |

## Notas Técnicas

- **Herencia de stylesheet en Qt:** Al aplicar `setStyleSheet()` en `QMainWindow`, todos los widgets hijos heredan los estilos por cascada. Los diálogos instanciados antes de `MainWindow` (login, apertura de caja, PIN admin) deben aplicar `get_dialog_stylesheet()` explícitamente.
- **Colores dinámicos en runtime:** Los métodos que calculan color condicionalmente (ej. sobrante/faltante en conciliación de efectivo) usan `f"color: {SUCCESS_COLOR};"` en lugar de strings hardcodeados.
- **`QColor` vs `setStyleSheet`:** Ambos patrones fueron migrados — los `QColor(hex)` en items de tabla se reemplazaron con `QColor(SUCCESS_COLOR)`.
- **Archivos excluidos intencionalmente:** `change_dialog.py`, `sale_receipt_dialog.py` y `sale_view.py` mantienen su estilo terminal oscuro por diseño; no fueron modificados.
- **Tests previos sin cambios:** 2 fallos pre-existentes no relacionados (`test_cash_movement.py` ImportError de `MovementType`; 1 assertion en `test_main_window_close_event.py`). Los 39 tests nuevos pasan en verde; suite total: 503/504.
