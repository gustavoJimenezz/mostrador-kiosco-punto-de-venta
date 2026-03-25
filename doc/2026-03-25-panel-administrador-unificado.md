# Panel de Administrador Unificado

**Fecha:** 2026-03-25

## Resumen

Se consolidaron las seis vistas exclusivas del rol administrador (que ocupaban pestañas individuales en el `QTabWidget` principal) en un único tab llamado **"Panel Administrador"**. Este panel presenta una columna de navegación izquierda (`QListWidget`) y un área de contenido derecha (`QStackedWidget`), similar al patrón de panel de configuración clásico. El objetivo fue simplificar la interfaz y eliminar la proliferación de pestañas en la barra superior de la ventana principal.

## Cambios Principales

- Creado el widget `AdminPanelView` que encapsula las seis vistas admin con navegación lateral
- La vista de **Inventario** (antes "Productos F5") es la sección activa por defecto al abrir el panel
- Los shortcuts F5, F6, F7, F9 navegan al panel y seleccionan la sección correspondiente
- `_ADMIN_TAB_INDICES` reducido de `[1, 2, 3, 4, 6, 7]` a `[2]` (un solo tab protegido)
- La pestaña **Movimientos de caja** (visible para todos) pasó del índice 5 al índice 1
- Eliminado el placeholder `tab_import` del archivo `.ui` (ya no se usa directamente)
- El `_DEV_RELOAD_MAP` fue vaciado (hot-reload de sub-vistas dentro del panel no está soportado)

## Flujo de Trabajo

**Acceso al panel:**
```
Usuario hace clic en "🔒 Administrador"
  → AdminPinDialog valida PIN
    → Se revela Tab 2 "Panel Administrador"
      → Por defecto muestra la sección "Inventario"
```

**Navegación interna:**
```
Clic en ítem de la lista izquierda (o shortcut F5/F6/F7/F9)
  → QListWidget.currentRowChanged
    → QStackedWidget.setCurrentIndex(row)
      → on_view_activated() de la sub-vista activa
```

**Shortcuts de navegación al panel:**

| Tecla | Sección activada |
|-------|-----------------|
| F5 | Inventario |
| F6 | Editar stock |
| F7 | Inyectar stock |
| F9 | Importar |

**Opciones del panel (en orden de aparición):**

| Índice | Sección | Vista subyacente |
|--------|---------|-----------------|
| 0 | Inventario | `ProductManagementView` |
| 1 | Historial de caja | `CashHistoryView` |
| 2 | Historial de ventas | `SalesHistoryView` |
| 3 | Editar stock | `StockEditView` |
| 4 | Inyectar stock | `StockInjectView` |
| 5 | Importar | `ImportView` |

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/views/admin_panel_view.py` | **Creado.** Nuevo widget con `QListWidget` (200 px) + `QStackedWidget`. Expone propiedades para inyección de presenters y método `navigate_to(key)`. |
| `src/infrastructure/ui/windows/main_window.py` | **Modificado.** Reemplazados 6 `addTab()` de admin por un único `AdminPanelView`. Actualizados: `_ADMIN_TAB_INDICES`, propiedades de vistas, `set_*_presenter()`, shortcuts F5/F6/F7/F9, `_on_tab_changed()` y `_DEV_RELOAD_MAP`. |

## Notas Técnicas

- `AdminPanelView` hereda de `QWidget` y se embebe en el `QTabWidget` principal (no es un `QDialog`). Esto mantiene coherencia con el resto de la arquitectura de vistas.
- El estilo de la lista de navegación (`_NAV_LIST_STYLESHEET`) usa los colores del sistema de tema (`#4f46e5` primario, `#eef2ff` hover/seleccionado, `#f3f4f6` fondo). No requiere importar `theme.py` ya que los valores están referenciados directamente en el stylesheet de la lista.
- La señal `currentRowChanged` de `QListWidget` activa tanto el cambio de índice en el `QStackedWidget` como la llamada a `on_view_activated()` de la sub-vista. Esto garantiza que cada vista cargue sus datos al mostrarse, igual que antes con `_on_tab_changed`.
- Al ocultarse el panel (botón "✕ Ocultar panel"), `_lock_admin_tabs()` oculta únicamente el índice 2. La pestaña de Movimientos de caja (índice 1) permanece visible para todos los usuarios.
