# Sesión de Caja: Estado Abierto/Cerrado

**Fecha:** 2026-03-24

## Punto de verdad único

El único criterio para determinar si una caja está abierta es:

```
cash_closes.closed_at IS NULL
```

Ese campo nulo equivale a "sesión activa". Cuando se cierra la caja, se asigna un timestamp y el registro queda inmutable.

En el dominio, esto se expone como propiedad:

```python
# src/domain/models/cash_close.py
@property
def is_open(self) -> bool:
    return self.closed_at is None
```

No existe un campo `status`, un booleano `is_active` ni una tabla separada. Solo `closed_at`.

---

## Estados posibles en DB

| `closed_at` | `closing_amount` | Estado |
|-------------|-----------------|--------|
| `NULL` | `NULL` | Sesión abierta |
| `datetime` | `Decimal` | Sesión cerrada |

Ambas columnas son `nullable=True` en la tabla `cash_closes`. Siempre cambian juntas al cerrar.

---

## Cómo cada capa representa el estado

| Capa | Mecanismo | Valor cuando abierta | Valor cuando cerrada |
|------|-----------|---------------------|---------------------|
| DB (`cash_closes`) | columna `closed_at` | `NULL` | timestamp |
| Dominio (`CashClose`) | property `is_open` | `True` | `False` |
| Repositorio | `get_open()` retorna | instancia `CashClose` | `None` |
| Presenter (`CashPresenter`) | atributo `_active_close` | instancia `CashClose` | `None` |
| Vista (`CashCloseView`) | `_btn_close.setEnabled()` | `True` | `False` |

---

## Consulta que determina la sesión activa

```python
# src/infrastructure/persistence/mariadb_cash_repository.py
def get_open(self) -> Optional[CashClose]:
    return (
        self._session.query(CashClose)
        .filter(CashClose.closed_at == None)   # noqa: E711
        .order_by(CashClose.opened_at.desc())
        .first()
    )
```

Si retorna `None`, no hay sesión activa. El `.first()` garantiza que aunque existieran múltiples registros abiertos (situación anómala), se toma el más reciente.

---

## Apertura: idempotente por diseño

`GetOrOpenCashClose.execute()` primero consulta `get_open()`. Si ya existe una sesión abierta, la retorna sin crear nada. Solo hace `INSERT` si no hay ninguna:

```python
# src/application/use_cases/get_or_open_cash_close.py
existing = self._cash_repo.get_open()
if existing is not None:
    return existing   # idempotente

new_close = CashClose(opened_at=datetime.now(), opening_amount=opening_amount)
return self._cash_repo.save(new_close)
```

Esto protege contra doble apertura si el usuario navega varias veces a la pestaña F10.

---

## Cierre: mutación en el dominio + persistencia

```python
# src/application/use_cases/close_cash_close.py
cash_close = self._cash_repo.get_open()
if cash_close is None:
    raise ValueError("No hay ningún arqueo de caja abierto para cerrar.")

cash_close.close(closed_at=datetime.now(), closing_amount=closing_amount)
return self._cash_repo.save(cash_close)
```

`cash_close.close()` valida las invariantes (no está ya cerrada, el monto no es negativo, `closed_at >= opened_at`) y asigna los valores. El repositorio hace `UPDATE` del registro existente.

---

## Totales del día: sin pre-acumulación

El reporte de caja **no** depende de las columnas `total_sales_cash/debit/transfer` de `cash_closes`. Los totales se computan en tiempo real desde `sales`:

```sql
SELECT payment_method, SUM(total_amount)
FROM sales
WHERE timestamp BETWEEN :inicio_del_dia AND :fin_del_dia
GROUP BY payment_method
```

Esto garantiza consistencia aunque una venta no tenga `cash_close_id` asignado.

---

## Archivos de referencia

| Archivo | Rol |
|---------|-----|
| `src/domain/models/cash_close.py` | Entidad `CashClose`, property `is_open`, método `close()` |
| `src/domain/ports/cash_repository.py` | Puerto `CashCloseRepository` con contrato de `get_open()` |
| `src/infrastructure/persistence/tables.py` | Definición de `cash_closes_table` (columnas nullable) |
| `src/infrastructure/persistence/mariadb_cash_repository.py` | Implementación de `get_open()`, `save()` |
| `src/application/use_cases/get_or_open_cash_close.py` | Lógica de apertura idempotente |
| `src/application/use_cases/close_cash_close.py` | Lógica de cierre con validación |
| `src/infrastructure/ui/presenters/cash_presenter.py` | `_active_close`: estado en capa de presentación |
| `src/infrastructure/ui/views/cash_close_view.py` | Habilitación de botones según estado |
