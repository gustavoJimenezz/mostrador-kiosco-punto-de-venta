# Ticket 20 — Pestaña "Gestión de Productos" con lógica de precios recíproca

**Fecha:** 2026-03-17

## Resumen

Implementación de la pestaña de gestión de productos (CRUD) dentro del `QTabWidget` de `MainWindow`, accesible mediante el atajo `F5`. Incluye un formulario completo para crear, editar y eliminar productos, con lógica recíproca bidireccional entre el campo de margen y el precio final: modificar el margen calcula el precio (Caso A) y modificar el precio calcula el margen (Caso B). Toda la lógica de negocio reside en el `ProductPresenter` (Python puro, sin dependencias Qt), siguiendo el patrón MVP ya establecido en el proyecto.

---

## Cambios Principales

- Creado `product_worker.py` con 4 workers QThread para operaciones CRUD asincrónicas
- Creado `product_presenter.py` con el protocolo `IProductManagementView` y la clase `ProductPresenter`
- Creada `product_management_view.py` con el layout completo construido por código (sin archivo `.ui`)
- Modificado `main_window.py`: nuevo tab "Productos (F5)", atajo F5, propiedad `product_management_view`, método `set_product_presenter()`, handler `_on_tab_changed()`
- Modificado `main.py`: instancia y conecta `ProductPresenter` en el composition root
- Creado `test_product_presenter.py` con 26 tests unitarios (sin DB ni Qt)

---

## Flujo de Trabajo

### Carga inicial de la pestaña

```
Usuario presiona F5 / hace clic en tab "Productos"
  → MainWindow._on_tab_changed(index=2)
  → ProductManagementView.on_view_activated()
  → presenter.on_view_activated()
  → Vista lanza ListAllProductsWorker (QThread)
  → Worker: MariadbProductRepository.list_all()
  → presenter.on_products_loaded(products)
  → view.show_product_list(products)  — puebla QListWidget
```

### Selección de un producto

```
Usuario hace clic en ítem de la lista
  → Vista lanza LoadProductWorker(product_id)
  → Worker: repo.get_by_id() + category_repo.list_all()
  → presenter.on_product_fetched({product, categories})
  → view.show_product_in_form(product, categories)
  → Habilita botón "Eliminar"
```

### Lógica recíproca Margen ↔ Precio Final

```
Usuario modifica Margen (QDoubleSpinBox)
  → on_margin_changed(margin_str)
  → Caso A: precio = costo × (1 + margen / 100)  [ROUND_HALF_UP]
  → view.set_final_price_display(precio)          [blockSignals=True → no bucle]

Usuario modifica Precio Final (QLineEdit)
  → on_final_price_changed(price_str)
  → Caso B: margen = ((precio / costo) - 1) × 100 [ROUND_HALF_UP]
  → view.set_margin_display(margen)               [blockSignals=True → no bucle]
  → Guard: si costo == 0, no actualiza (evita división por cero)
```

### Guardar producto

```
Usuario pulsa "Guardar F5"
  → view._on_save_clicked()
  → presenter.on_save_requested()  — valida form, construye Product o retorna None
  → Si válido: Vista lanza SaveProductWorker(product)
  → Worker: repo.save(product) + session.commit()
  → presenter.on_save_completed(product)
  → Vista lanza ListAllProductsWorker (refresca lista)
```

### Eliminar producto

```
Usuario pulsa "Eliminar"
  → view._on_delete_clicked()
  → presenter.on_delete_requested()
  → view.show_delete_confirmation(product_name)  — QMessageBox de confirmación
  → Si confirmado: Vista lanza DeleteProductWorker(product_id)
  → Worker: repo.delete(product_id) + session.commit()
  → presenter.on_delete_completed()
  → view.clear_form() + Vista lanza ListAllProductsWorker
```

---

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/ui/workers/product_worker.py` | **Nuevo** — 4 workers QThread: `ListAllProductsWorker`, `LoadProductWorker`, `SaveProductWorker`, `DeleteProductWorker` |
| `src/infrastructure/ui/presenters/product_presenter.py` | **Nuevo** — Protocolo `IProductManagementView` + clase `ProductPresenter` (Python puro) |
| `src/infrastructure/ui/views/product_management_view.py` | **Nueva** — `ProductManagementView` QWidget con layout programático de dos paneles |
| `src/infrastructure/ui/windows/main_window.py` | **Modificado** — Tab 2, atajo F5, propiedad `product_management_view`, `set_product_presenter()`, `_on_tab_changed()` |
| `src/main.py` | **Modificado** — Instancia y conecta `ProductPresenter` en composition root |
| `tests/unit/ui/test_product_presenter.py` | **Nuevo** — 26 tests unitarios: lógica recíproca, validación, callbacks de workers |

---

## Notas Técnicas

### Anti-bucle con `blockSignals`

La lógica recíproca (margen ↔ precio) usa `blockSignals(True/False)` al actualizar los campos desde el presenter para evitar que la señal del widget dispare nuevamente al presenter, generando un bucle infinito:

```python
def set_final_price_display(self, price: Decimal) -> None:
    self._field_final_price.blockSignals(True)
    self._field_final_price.setText(str(price))
    self._field_final_price.blockSignals(False)
```

### Workers creados en la vista, no en el presenter

Siguiendo el patrón del proyecto, el `ProductPresenter` es Python puro (sin imports Qt). Los workers `QThread` se instancian y conectan exclusivamente en `ProductManagementView`, manteniendo la testeabilidad del presenter con `FakeProductManagementView`.

### Aritmética monetaria

Toda operación de precio usa `decimal.Decimal` con `ROUND_HALF_UP`, nunca `float`. La conversión desde `QDoubleSpinBox` se hace via `Decimal(str(float_value))` para evitar imprecisiones de punto flotante.

### No se requirió migración Alembic

El campo `margin_percent` ya existía en la tabla `products` desde la migración inicial. Solo se construyó la UI y la capa de presentación.

### Atajos de teclado — estado actualizado

| Atajo | Acción |
|-------|--------|
| F1 | Nueva venta |
| F2 | Búsqueda por nombre |
| F4 | Confirmar venta |
| **F5** | **Gestión de productos (nuevo)** |
| F9 | Importar lista de precios |
| F10 | Cierre de caja |
