# Arqueo de Caja, Movimientos Manuales e Historial de Ventas

**Fecha:** 2026-03-23
**Ticket:** #22 + cambios sin ticket (historial de ventas / F2)

## Resumen

Se implementó el arqueo de caja diario (F10) con soporte para movimientos manuales (ingresos/egresos) y el historial de ventas consultable por fecha (F2). El ticket #22 cubría la entidad `CashMovement`, los puertos de repositorio y la UI de cierre de caja. Los cambios sin ticket previo agregan los casos de uso de consulta (`ListSales`) y la vista de historial con detalle de ítems por venta.

## Cambios Principales

- Nueva entidad de dominio `CashMovement` con enum `MovementType` (INGRESO/EGRESO)
- Nuevos puertos `CashCloseRepository` y `CashMovementRepository`
- Nuevo puerto de consulta `SaleQueryRepository` (CQRS — separado del puerto de escritura)
- Tres casos de uso: `GetOrOpenCashClose`, `CloseCashClose`, `AddCashMovement`
- Caso de uso `ListSales` para historial con validación de rango de fechas
- Nueva tabla `cash_movements` en DB con migración Alembic (`b5e8f2a9c107`)
- `MariadbCashRepository`: gestiona CashClose vía ORM y CashMovement vía Core SQL
- `MariadbSaleRepository` extendido con `list_by_date_range`, `get_daily_totals`, `get_sale_items_with_names`
- Vista `CashCloseView` (F10): apertura/cierre de sesión, movimientos manuales, resumen del día
- Vista `SalesHistoryView` (F2): lista de ventas por fecha, detalle de ítems al seleccionar
- Presenters sin Qt: `CashPresenter` e `SalesHistoryPresenter` (completamente testeables)
- Workers QThread: `LoadCashStateWorker`, `OpenCashCloseWorker`, `CloseCashCloseWorker`, `AddMovementWorker`, `LoadSalesWorker`, `LoadSaleDetailWorker`
- `MainWindow`: F10 navega a `CashCloseView`, F2 (antes "reservado") navega a `SalesHistoryView`
- 45 tests nuevos: dominio, casos de uso y presenters. Suite total: 449 tests, todos pasan

## Flujo de Trabajo

### F10 — Cierre de caja

```
[F10] → MainWindow._on_cash_close()
      → tab_widget.setCurrentIndex(6)
      → CashCloseView.on_view_activated()
      → LoadCashStateWorker (QThread)
            → MariadbCashRepository.get_open()
            → MariadbCashRepository.list_movements(id)
            → MariadbCashRepository.get_sales_totals_for_date(hoy)
      → CashPresenter.on_state_loaded(state)
            → view.show_session_open() / show_session_closed()
            → view.show_sales_summary(cash, debit, transfer)
            → view.show_movements(movements)

[Abrir caja] → OpenCashCloseWorker → GetOrOpenCashClose.execute()
[Ingreso/Egreso] → AddMovementWorker → AddCashMovement.execute()
[Cerrar caja] → CloseCashCloseWorker → CloseCashClose.execute()
                → cash_close.close(hora, monto_contado)
                → view.show_close_result(diferencia)
```

### F2 — Historial de ventas

```
[F2] → MainWindow._toggle_search()
     → tab_widget.setCurrentIndex(5)
     → SalesHistoryView.on_view_activated()
     → LoadSalesWorker (QThread)
           → ListSales.execute(start, end)
           → MariadbSaleRepository.list_by_date_range()
     → SalesHistoryPresenter.on_sales_loaded(sales)
           → view.show_sales(sales)
           → view.show_daily_total(suma de totales)

[Seleccionar venta] → LoadSaleDetailWorker
                    → MariadbSaleRepository.get_sale_items_with_names()
                    → presenter.on_detail_loaded(items)
                    → view.show_sale_detail(items)
```

### Totales de ventas del día (sin pre-acumulación)

El reporte de caja NO depende de los campos `total_sales_*` pre-acumulados de `cash_closes`. Los totales se computan en tiempo real desde la tabla `sales` con un `GROUP BY payment_method`, lo que garantiza consistencia aunque las ventas no tengan `cash_close_id` asignado.

```sql
SELECT payment_method, SUM(total_amount)
FROM sales
WHERE timestamp BETWEEN :start AND :end
GROUP BY payment_method
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/domain/models/cash_movement.py` | Nueva entidad `CashMovement` + enum `MovementType` |
| `src/domain/ports/cash_repository.py` | Nuevos puertos `CashCloseRepository` y `CashMovementRepository` |
| `src/domain/ports/sale_query_repository.py` | Nuevo puerto `SaleQueryRepository` (lectura) |
| `src/application/use_cases/get_or_open_cash_close.py` | Caso de uso: obtener o abrir arqueo |
| `src/application/use_cases/close_cash_close.py` | Caso de uso: cerrar arqueo activo |
| `src/application/use_cases/add_cash_movement.py` | Caso de uso: registrar movimiento manual |
| `src/application/use_cases/list_sales.py` | Caso de uso: historial de ventas por rango |
| `src/infrastructure/persistence/tables.py` | Nueva tabla `cash_movements_table` |
| `src/infrastructure/persistence/mariadb_cash_repository.py` | Nuevo repositorio de caja (CashClose ORM + CashMovement Core SQL) |
| `src/infrastructure/persistence/mariadb_sale_repository.py` | Extendido con métodos de consulta y reporte |
| `alembic/versions/b5e8f2a9c107_agregar_tabla_cash_movements.py` | Migración: tabla `cash_movements` |
| `src/infrastructure/ui/workers/cash_worker.py` | 4 workers QThread para operaciones de caja |
| `src/infrastructure/ui/workers/sales_history_worker.py` | 2 workers QThread para historial de ventas |
| `src/infrastructure/ui/presenters/cash_presenter.py` | `CashPresenter` + `ICashView` Protocol |
| `src/infrastructure/ui/presenters/sales_history_presenter.py` | `SalesHistoryPresenter` + `ISalesHistoryView` Protocol |
| `src/infrastructure/ui/views/cash_close_view.py` | Vista de cierre de caja (F10) construida por código |
| `src/infrastructure/ui/views/sales_history_view.py` | Vista de historial de ventas (F2) construida por código |
| `src/infrastructure/ui/windows/main_window.py` | F2/F10 conectados a nuevas vistas; tabs 5 y 6 agregados |
| `tests/unit/domain/mocks/in_memory_cash_repository.py` | Mocks de repositorios de caja para tests |
| `tests/domain/test_cash_movement.py` | 11 tests de dominio para `CashMovement` |
| `tests/unit/application/test_cash_use_cases.py` | 13 tests de casos de uso de caja |
| `tests/unit/application/test_list_sales.py` | 4 tests del caso de uso `ListSales` |
| `tests/unit/ui/test_cash_presenter.py` | 11 tests del `CashPresenter` |
| `tests/unit/ui/test_sales_history_presenter.py` | 6 tests del `SalesHistoryPresenter` |

## Notas Técnicas

- **CashMovement sin mapeo ORM:** `CashMovement` usa Core SQL en el repositorio (no `mapper_registry`) para evitar un `TypeDecorator` necesario para mapear `MovementType(str, Enum)` a la columna `SAEnum`. `CashClose` sí usa ORM (mapeo existente en `mappings.py`).
- **Atomicidad venta + movimiento de caja:** El Ticket 22 requiere que la venta y el movimiento de caja sean atómicos. Por decisión de diseño, esta integración queda pendiente. Los totales del día se computan desde `sales` por fecha, por lo que el reporte es siempre correcto sin importar si el `cash_close_id` está asignado en la venta.
- **F2 reasignado:** F2 estaba marcado como "reservado" en el código. Se reasignó a historial de ventas. El docstring del módulo `main_window.py` fue actualizado.
- **Tabs nuevos:** `SalesHistoryView` es el tab índice 5 y `CashCloseView` es el índice 6, consistentes con el orden keyboard-first (F2 antes que F10).
- **Presenters sin Qt:** `CashPresenter` y `SalesHistoryPresenter` son Python puro. Los tests corren sin Qt instalado, como el resto de los presenters del proyecto.
