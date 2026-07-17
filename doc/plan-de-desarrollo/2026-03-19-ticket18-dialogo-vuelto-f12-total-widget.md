# Diálogo de Vuelto F12 y TotalWidget con Font Scaling

**Fecha:** 2026-03-19
**Ticket:** #18

## Resumen

Se implementó F12 como atajo dedicado para pago en efectivo con cálculo de vuelto en tiempo real, mediante un diálogo estilo "display de cajero" (`ChangeDialog`). Adicionalmente, se reemplazó el `total_label` de fuente fija del `.ui` por `TotalWidget`, un `QLabel` que reduce dinámicamente su tamaño de fuente para evitar que montos grandes (ej: `$1.234.567,89`) sean recortados visualmente.

## Cambios Principales

- Nuevo widget `TotalWidget(QLabel)` con escalado dinámico de fuente (52pt → 24pt en pasos de 2pt)
- Nuevo diálogo modal `ChangeDialog` con fondo oscuro tipo POS, entrada numérica y vuelto calculado en tiempo real
- `ISaleView` extendida con `show_change_dialog(total: Price) -> bool`
- `SalePresenter` extendido con `on_cash_payment_requested()` para el flujo F12
- `MainWindow` integra F12 shortcut, reemplaza `total_label` por `TotalWidget` y lanza `ProcessSaleWorker` al confirmar
- 4 nuevos tests en `TestCashPayment` cubriendo los casos del flujo F12

## Flujo de Trabajo

### F12 — Pago en efectivo con vuelto

```
[F12] → SalePresenter.on_cash_payment_requested()
      → carrito vacío? → show_error(), return None
      → ChangeDialog.show_and_confirm(total)
            → cajero ingresa monto
            → vuelto calculado en tiempo real (textChanged)
            → confirmar habilitado solo si monto >= total
      → confirmó? → PaymentMethod.CASH
      → canceló?  → None
      → MainWindow lanza ProcessSaleWorker(cart, CASH)
      → [venta persistida en DB]
      → presenter.on_sale_completed() → limpia carrito
```

### TotalWidget — Escalado dinámico de fuente

```
[update_total(price)] → TotalWidget.set_total(price)
                      → setText("TOTAL: $X")
                      → _adjust_font_size()
                            → itera 52pt → 24pt (paso -2)
                            → QFontMetrics.horizontalAdvance(text) <= width - 48
                            → aplica primer tamaño que entra
[resizeEvent]         → _adjust_font_size() (re-evalúa al cambiar tamaño de ventana)
```

### F4 — Sin cambios

El flujo de F4 (`_PaymentDialog`) no fue modificado.

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/widgets/__init__.py` | Nuevo paquete de widgets |
| `src/infrastructure/ui/widgets/total_widget.py` | `TotalWidget(QLabel)` con font scaling |
| `src/infrastructure/ui/dialogs/__init__.py` | Nuevo paquete de diálogos |
| `src/infrastructure/ui/dialogs/change_dialog.py` | `ChangeDialog` — display de cajero con vuelto en tiempo real |
| `src/infrastructure/ui/presenters/sale_presenter.py` | `show_change_dialog` en `ISaleView` + `on_cash_payment_requested` en `SalePresenter` |
| `src/infrastructure/ui/windows/main_window.py` | F12 shortcut, `_on_cash_payment`, `show_change_dialog`, integración de `TotalWidget` |
| `tests/unit/ui/test_sale_presenter.py` | `FakeView.show_change_dialog` + clase `TestCashPayment` (4 tests) |

## Notas Técnicas

- **`ChangeDialog` sin PySide6 en tests:** El presenter es Python puro; `FakeView.show_change_dialog` simula el diálogo sin instanciar Qt. El diálogo real solo se instancia en `MainWindow`.
- **Margen horizontal en TotalWidget:** Se descuenta 48px del ancho disponible para respetar el padding del layout padre.
- **`QDoubleValidator` en `ChangeDialog`:** Permite entrada numérica con punto o coma como separador decimal; el cálculo normaliza con `text.replace(",", ".")` antes de convertir a `Decimal`.
- **Propiedad QSS dinámica:** `lbl_change` usa la propiedad `insufficient` para cambiar de color verde a rojo; requiere llamar `unpolish/polish` para que Qt re-evalúe el QSS al cambiar la propiedad.
- **`total_label` del `.ui`:** Se reemplaza programáticamente en `_load_ui()` usando `parent_layout.replaceWidget()`. El `TotalWidget` hereda el `objectName("total_label")` para seguir recibiendo los estilos QSS definidos en el `.ui`.
