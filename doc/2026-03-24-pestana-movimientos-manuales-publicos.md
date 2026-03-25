# Pestaña de Movimientos Manuales (acceso público) y Total en Historial de Caja

**Fecha:** 2026-03-24

## Resumen

Se extrajo la gestión de movimientos manuales de caja del diálogo de cierre (F10) y se trasladó a una pestaña propia visible para todos los usuarios, sin necesidad de acceso administrador. El diálogo de cierre ahora muestra únicamente el total neto de movimientos, y el historial de arqueos incorpora una columna nueva con ese mismo total por sesión.

## Cambios Principales

- **Nueva pestaña "Movimientos"** (índice 6, visible a todos): tabla con el listado completo de movimientos de la sesión activa, total neto destacado y formulario de ingreso/egreso.
- **Diálogo de cierre de caja (F10):** eliminado el bloque de tabla + formulario de movimientos; reemplazado por un único label `"Movimientos manuales: $X"` en el grupo "Cierre de caja".
- **Historial de arqueos (admin):** nueva columna **"Mov. manuales"** que muestra el total neto de movimientos de cada sesión (verde = ingreso neto, rojo = egreso neto).
- **`CashPresenter`:** nuevo protocolo `ICashMovementsView`, método `set_movements_view()` y helper `_compute_movements_total()`. Los callbacks `on_movement_added`, `on_session_opened` y `on_session_closed` propagan estado a ambas vistas.
- **`ICashView`:** `show_movements(list)` reemplazado por `show_movements_total(Decimal)`.
- **Worker de historial:** ahora emite `dict` con `closes` y `movements_totals` en lugar de `list` plano.
- **Repositorio:** nuevo método `get_movements_totals_by_close_ids()` — query agregada en batch para evitar N+1 al cargar el historial.
- **Tests:** `FakeCashView` actualizada; nuevo `FakeCashMovementsView`; dos tests nuevos para verificar propagación del total y de la lista.

## Flujo de Trabajo

### Registro de movimiento (usuario cualquiera)

```
[Pestaña "Movimientos"] → usuario ingresa descripción + monto
  → _on_add_movement() valida con CashPresenter.on_add_movement_requested()
  → AddMovementWorker persiste en DB
  → on_movement_added():
       ├─ CashCloseView.show_movements_total(total_neto)
       └─ CashMovementsView.show_movements(lista_completa)
```

### Apertura / cierre de sesión

```
[Abrir caja] → on_session_opened(cc)
  → CashCloseView.show_session_open(cc)  +  show_movements_total($0)
  → CashMovementsView.show_session_open(cc)  +  show_movements([])

[Cerrar caja] → on_session_closed(cc)
  → CashCloseView.show_session_closed()  +  show_movements_total($0)
  → CashMovementsView.show_session_closed()  +  show_movements([])
```

### Carga del historial con totales de movimientos

```
[Buscar en Historial de caja]
  → LoadCashHistoryWorker.run()
       ├─ ListCashCloses.execute(start, end) → lista de CashClose
       └─ get_movements_totals_by_close_ids(ids) → {id: total}
  → emit dict{"closes", "movements_totals"}
  → CashHistoryPresenter.on_closes_loaded(payload)
  → CashHistoryView.show_closes(closes, movements_totals)
       → _fill_row() lee movements_totals.get(cc.id, $0)
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/views/cash_movements_view.py` | **Nuevo.** Pestaña pública de movimientos manuales |
| `src/infrastructure/ui/views/cash_close_view.py` | Removido bloque movimientos; agregado `_lbl_movements_total` y `show_movements_total()` |
| `src/infrastructure/ui/presenters/cash_presenter.py` | `ICashMovementsView`, `set_movements_view()`, `_compute_movements_total()`, callbacks actualizados |
| `src/infrastructure/ui/views/cash_history_view.py` | Columna "Mov. manuales"; `show_closes` acepta `movements_totals`; alineación actualizada |
| `src/infrastructure/ui/presenters/cash_history_presenter.py` | `on_closes_loaded` desempaqueta dict; firma `show_closes` actualizada |
| `src/infrastructure/ui/workers/cash_history_worker.py` | Signal cambiada a `dict`; consulta batch de totales al emitir |
| `src/infrastructure/persistence/mariadb_cash_repository.py` | Nuevo método `get_movements_totals_by_close_ids()` |
| `src/infrastructure/ui/windows/main_window.py` | Tab "Movimientos" en índice 6; historial de caja pasa a índice 7; `_ADMIN_TAB_INDICES` actualizado; `set_movements_view` conectado en `set_cash_presenter` |
| `tests/unit/ui/test_cash_presenter.py` | `FakeCashView` actualizada; `FakeCashMovementsView` nuevo; tests adaptados |

## Notas Técnicas

- **Índices de pestañas:** el desplazamiento de "Historial de caja" de índice 6 a 7 requirió actualizar `_ADMIN_TAB_INDICES`, `_on_tab_changed` y el comentario del header de `main_window.py`.
- **Sin F-key asignada** para la nueva pestaña: el usuario accede haciendo clic directo. Se puede asignar un atajo libre (ej. F3 o F8) en una iteración futura.
- **Sincronización de estado:** el `CashPresenter` es la única fuente de verdad (`_movements`). Ambas vistas reciben actualizaciones desde el presenter; la vista de movimientos nunca consulta la DB directamente.
- **Historial N+1 eliminado:** `get_movements_totals_by_close_ids` usa una sola query `GROUP BY` en lugar de un `list_movements` por cada arqueo.
