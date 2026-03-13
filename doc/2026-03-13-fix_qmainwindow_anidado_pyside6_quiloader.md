# Fix: QMainWindow anidado en QUiLoader — ventana sin tamaño ni layout

**Fecha:** 2026-03-13

## Resumen

Al ejecutar `poetry run python src/main.py`, la ventana aparecía con tamaño mínimo (200×100 px) en lugar de 960×640 px y sin ningún widget visible. El problema era que `QUiLoader` cargaba el `.ui` cuyo root era `QMainWindow` y luego ese objeto se establecía como `centralWidget` de otra `QMainWindow` Python, generando un anidamiento inválido que Qt no puede resolver correctamente.

## Síntoma

```
geometry: PySide6.QtCore.QRect(0, 0, 200, 100)   # ← esperado: 960x640
centralWidget type: QMainWindow                    # ← incorrecto: debería ser QWidget
```

## Causa Raíz

`QUiLoader.load()` devuelve el widget raíz definido en el `.ui`. El archivo tenía:

```xml
<widget class="QMainWindow" name="MainWindow">
```

Luego en `_load_ui`:

```python
ui_widget = loader.load(str(_UI_PATH), self)  # retorna QMainWindow
self.setCentralWidget(ui_widget)               # ← anida QMainWindow dentro de QMainWindow
```

Qt no soporta un `QMainWindow` como `centralWidget` de otro `QMainWindow`. El resultado es que el layout interno es ignorado y la geometría queda en el valor mínimo por defecto.

## Cambios Principales

- **`main_window.ui`** — root cambiado de `QMainWindow` a `QWidget`. Se elimina la capa `<widget name="centralwidget">` y el `<widget class="QStatusBar">` (el `QMainWindow` Python provee su propia status bar).
- **`main_window.py` (`_load_ui`)** — se añaden `setWindowTitle("Mostrador POS")` y `resize(960, 640)` explícitos, ya que el título y tamaño ya no vienen del root del `.ui`.

## Flujo de Trabajo

```
[main.py] → [MainWindow.__init__] → [_load_ui()]
    → QUiLoader.load(.ui)          # retorna QWidget (central_widget)
    → setCentralWidget(ui_widget)  # asignación directa, sin anidamiento
    → setWindowTitle / resize      # configurados desde Python
    → findChild(...)               # encuentra todos los widgets hijos correctamente
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/windows/main_window.ui` | Root cambiado de `QMainWindow` a `QWidget`; eliminada la envoltura `centralwidget` y la `QStatusBar` |
| `src/infrastructure/ui/windows/main_window.py` | `_load_ui`: añadidos `setWindowTitle` y `resize` explícitos |

## Resultado Verificado

```
geometry: PySide6.QtCore.QRect(0, 0, 960, 640)   # ✓ tamaño correcto
centralWidget type: QWidget                        # ✓ tipo correcto
title: Mostrador POS                               # ✓ título correcto
```

## Notas Técnicas

- El patrón correcto con `QUiLoader` en PySide6 es que el `.ui` defina **solo el contenido** (un `QWidget` raíz), mientras que la clase Python hereda de `QMainWindow` y provee `statusBar`, atajos de teclado, título y geometría.
- Si en el futuro se edita el `.ui` con Qt Designer, al abrir un archivo con root `QWidget` (en lugar de `QMainWindow`) Designer no incluirá `statusBar` ni `menuBar` en la paleta — esto es correcto e intencional.
