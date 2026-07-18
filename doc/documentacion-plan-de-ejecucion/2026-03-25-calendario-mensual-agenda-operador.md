# Calendario Mensual con Agenda por Día

**Fecha:** 2026-03-25

## Resumen

Se implementó una nueva pestaña "Calendario" visible para todos los usuarios, ubicada entre "Movimientos de caja" y "Panel Administrador". Permite al operador registrar notas de texto libre por día (visitas de proveedores, entregas, promociones, etc.) en un diseño de agenda con renglones sobre fondo oscuro. Las notas persisten localmente en un archivo JSON sin requerir conexión a la base de datos.

## Cambios Principales

- Nuevo widget `CalendarDayCell`: celda de día con número en esquina superior, renglones dibujados vía `paintEvent` y editor de texto libre (`QPlainTextEdit`).
- Nueva vista `CalendarView`: grilla mensual 7 columnas (Lun–Dom), navegación mes/año con flechas, tema oscuro propio (grafito + cian), auto-guardado con debounce de 800 ms.
- Nuevo presenter `CalendarPresenter`: protocolo `ICalendarView` + carga/persistencia de notas en `~/.config/kiosco-pos/calendar_notes.json`.
- Paleta oscura del calendario añadida en `theme.py` como constantes `CAL_*` independientes del tema global claro.
- Pestaña "Panel Administrador" desplazada de índice 2 → 3; "Calendario" ocupa el índice 2.
- Corrección del mecanismo de lock/unlock del Panel Administrador: `_ADMIN_TAB_INDICES` actualizado de `[2]` a `[3]`, atajos F5/F6/F7/F9 actualizados.
- 17 tests unitarios en `test_main_window_admin_tabs.py` que verifican el comportamiento de visibilidad del Panel Administrador y los atajos de teclado.

## Flujo de Trabajo

**Escritura de una nota:**

```
Usuario escribe en celda
  → CalendarDayCell.textChanged
  → CalendarView._on_cell_text_changed(date_key, text)
  → _pending_saves[date_key] = text
  → QTimer.start(800ms)     ← se reinicia con cada tecla
      [800ms de silencio]
  → _flush_pending_saves()
  → CalendarPresenter.on_note_changed(date_key, text)
  → _notes[date_key] = text
  → json.dump → ~/.config/kiosco-pos/calendar_notes.json
```

**Carga al activar la pestaña:**

```
Usuario navega a "Calendario"
  → MainWindow._on_tab_changed(index=2)
  → CalendarView.on_view_activated()
  → CalendarPresenter.on_view_activated()
  → view.load_notes(self._notes)
  → CalendarDayCell.set_text() por cada celda del mes visible
```

**Cambio de mes:**

```
Usuario presiona ◀ o ▶
  → _on_prev_month() / _on_next_month()
  → Ajusta (year, month)
  → _rebuild_grid()
      → calendar.monthcalendar(year, month)  ← stdlib Python
      → Instancia CalendarDayCell × (28–42 celdas)
      → presenter.on_view_activated() → carga notas del mes
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/widgets/calendar_day_cell.py` | **Nuevo** — Widget celda de día con `paintEvent` de renglones y señal `text_changed(date_key, text)` |
| `src/infrastructure/ui/views/calendar_view.py` | **Nuevo** — Vista principal del calendario: grilla, navegación, debounce, tema oscuro |
| `src/infrastructure/ui/presenters/calendar_presenter.py` | **Nuevo** — Protocolo `ICalendarView` + lógica de persistencia JSON |
| `src/infrastructure/ui/theme.py` | **Modificado** — 18 constantes `CAL_*` al final del módulo (paleta oscura independiente) |
| `src/infrastructure/ui/windows/main_window.py` | **Modificado** — Tab Calendario en índice 2; `_ADMIN_TAB_INDICES = [3]`; atajos F5–F9 a índice 3; `set_calendar_presenter()` + `@property calendar_view` |
| `src/main.py` | **Modificado** — Instanciación e inyección de `CalendarPresenter` con ruta JSON |
| `tests/unit/ui/test_main_window_admin_tabs.py` | **Nuevo** — 17 tests unitarios de visibilidad de tabs y atajos de teclado |

## Notas Técnicas

- **Persistencia JSON sin DB:** Las notas son datos del operador local; no se replican entre terminales en un setup multi-terminal. Formato: `{"YYYY-MM-DD": "texto de la nota"}`. El archivo se crea automáticamente al guardar la primera nota.
- **Tema oscuro aislado:** `CalendarView` aplica `setStyleSheet()` solo sobre sí misma. Las constantes `CAL_*` en `theme.py` están fuera del dataclass `_Palette` para no contaminar el tema claro global.
- **Renglones alineados con la fuente:** El `paintEvent` de `CalendarDayCell` usa `QFontMetrics.lineSpacing()` en runtime para que las líneas coincidan exactamente con el interlineado del texto, independientemente de resolución o DPI.
- **Días de relleno no editables:** Celdas con `is_current_month=False` tienen el `QPlainTextEdit` deshabilitado y no emiten señales.
- **Índices de pestañas resultantes:** `0` = POS, `1` = Movimientos de caja, `2` = Calendario, `3` = Panel Administrador.
- **Regresión bloqueada por tests:** Si `_ADMIN_TAB_INDICES` vuelve a apuntar al índice 2 (Calendario), o los atajos F5–F9 usan `setCurrentIndex(2)`, los tests fallan inmediatamente.
