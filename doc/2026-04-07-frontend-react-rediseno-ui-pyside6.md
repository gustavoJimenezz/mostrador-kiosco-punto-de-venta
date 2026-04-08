# Rediseño del Frontend React — Paridad visual y funcional con UI PySide6

**Fecha:** 2026-04-07

---

## Resumen

Se reescribió completamente el frontend React de la v2.0 para replicar el estilo visual y la funcionalidad de la interfaz PySide6 original. El nuevo frontend usa un tema claro con indigo como color primario (mismo esquema que el `theme.py` del sistema Qt), implementa todos los atajos de teclado F1–F12 y expone todas las vistas del panel de administrador a través de una navegación lateral. Además, se agregaron tres endpoints FastAPI faltantes para soportar el historial de ventas, historial de arqueos y listado de movimientos.

---

## Cambios Principales

### Backend — Nuevos endpoints
- `GET /api/sales?date=YYYY-MM-DD` — historial de ventas del día con detalle de ítems (nombre de producto, cantidad, precio, subtotal)
- `GET /api/cash/history?start=&end=` — listado de cierres de caja en un rango de fechas
- `GET /api/cash/movements/{cash_close_id}` — movimientos manuales de un arqueo específico

### Frontend — Reescritura completa
- **Tema:** modo claro con variables CSS; paleta idéntica al `theme.py` de PySide6 (`#4f46e5` indigo, `#f9fafb` superficie, `#059669` éxito, `#dc2626` peligro)
- **Navegación por tabs:** Venta (F1) · Caja (F10) · Admin (F5, solo admin)
- **Panel Admin con sidebar** equivalente al `AdminPanelView` Qt
- **Diálogo de vuelto** para pagos en efectivo con F12
- **Dropdown de búsqueda** por nombre con navegación con flechas (equivalente al `QListWidget` de resultados)
- Método `upload()` agregado al cliente HTTP para importación multipart

---

## Flujo de Trabajo

### Navegación general
```
Usuario autenticado
        │
        ├─ F1  → Tab Venta  (POS)
        ├─ F10 → Tab Caja
        └─ F5/F2/F6/F7/F9 → Tab Admin (solo rol admin)
                                    └─ Sidebar selecciona sección activa
```

### Pantalla de venta (POS)
```
Operador escanea/escribe
        │
        ├─ Solo dígitos → GET /api/products/barcode/{bc}
        └─ Texto libre  → GET /api/products/search?q= → Dropdown de resultados
                                          └─ Selección → addItem() en cartStore

F4       → POST /api/sales  { payment_method: EFECTIVO }
F12      → ChangeDialog → ingresar monto recibido → calcular vuelto → POST /api/sales
Supr     → removeItem(último)
F1       → clear() carrito + ir a tab Venta
```

### Panel de administrador
```
Tab Admin
  └─ Sidebar
        ├─ Inventario (F5)        → CRUD GET/POST/PUT/DELETE /api/products
        ├─ Historial de caja      → GET /api/cash/history?start=&end=
        ├─ Historial de ventas (F2) → GET /api/sales?date=
        ├─ Editar stock (F6)      → PUT /api/products/{id} { stock: N }
        ├─ Inyectar stock (F7)    → PUT /api/products/{id} { stock: actual + inject }
        └─ Importar (F9)          → POST /api/import (multipart) + polling GET /api/import/status
```

### Caja (F10)
```
GET /api/cash/state
        ├─ Cerrada → formulario "Abrir caja" → POST /api/cash/open
        └─ Abierta → resumen de ventas del día
                   ├─ Formulario "Cerrar caja" → POST /api/cash/close
                   ├─ Formulario "Movimiento manual" → POST /api/cash/movements
                   └─ GET /api/cash/movements/{id} → listado de movimientos
```

---

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/web/routers/cash.py` | Agregados `GET /history` y `GET /movements/{id}` |
| `src/infrastructure/web/routers/pos.py` | Agregado `GET /sales?date=` |
| `frontend/src/index.css` | Reescritura completa — tema claro con variables CSS |
| `frontend/src/api/client.ts` | Agregado método `upload()` para multipart |
| `frontend/src/App.tsx` | Reescritura — layout con header + tabs + atajos F-key globales |
| `frontend/src/pages/Login.tsx` | Reescritura — tema claro, selector de operador + PIN |
| `frontend/src/pages/POS.tsx` | Reescritura — dropdown de búsqueda, controles de cantidad, F4/F12/Supr/Esc |
| `frontend/src/pages/CashView.tsx` | **Nuevo** — abrir/cerrar caja, movimientos manuales |
| `frontend/src/pages/AdminPanel.tsx` | **Nuevo** — sidebar con navegación entre secciones |
| `frontend/src/pages/admin/InventoryView.tsx` | **Nuevo** — CRUD productos + gestión de categorías |
| `frontend/src/pages/admin/SalesHistoryView.tsx` | **Nuevo** — ventas por fecha con detalle expandible |
| `frontend/src/pages/admin/CashHistoryView.tsx` | **Nuevo** — arqueos por rango de fechas |
| `frontend/src/pages/admin/StockEditView.tsx` | **Nuevo** — edición directa de stock (set) |
| `frontend/src/pages/admin/StockInjectView.tsx` | **Nuevo** — inyección de unidades al stock existente |
| `frontend/src/pages/admin/ImportView.tsx` | **Nuevo** — upload CSV/XLSX con polling de progreso |
| `frontend/src/components/ChangeDialog.tsx` | **Nuevo** — modal de vuelto para F12 |

---

## Notas Técnicas

**Tema visual:** Las variables CSS en `index.css` replican exactamente los tokens del `_Palette` dataclass en `theme.py` (`PALETTE.primary = #4f46e5`, `PALETTE.surface = #f9fafb`, etc.). Esto garantiza coherencia visual entre el diseño documentado y el sistema anterior.

**Atajos de teclado:** Los atajos de navegación global (F1, F2, F5, F6, F7, F9, F10) se manejan en `App.tsx` y están activos en cualquier pestaña. F4, F12, Supr y Esc son exclusivos de `POS.tsx` y solo están activos mientras el componente está montado (tab Venta activo).

**StockEdit vs StockInject:** `StockEditView` establece el stock al valor ingresado (reemplazo directo). `StockInjectView` suma la cantidad ingresada al stock actual (stock += inject). Ambos usan `PUT /api/products/{id}` con el valor final calculado client-side.

**Polling de importación:** `ImportView` usa `setInterval` de 2 segundos durante una importación activa para consultar `GET /api/import/status`. El intervalo se limpia automáticamente cuando el estado cambia a `done` o `error`.

**Base de datos en desarrollo:** El `DATABASE_URL` del `.env` apunta a MariaDB en Docker (`localhost:3308`). Para usar SQLite sin Docker cambiar a `sqlite:///pos_dev.db`; la app detecta el dialecto automáticamente en el lifespan de `app.py`.

**Comandos de desarrollo:**
```bash
# Terminal 1 — FastAPI
poetry run python3 web_main.py       # http://localhost:8000

# Terminal 2 — Vite (proxy /api/* → :8000)
cd frontend && npm run dev           # http://localhost:5173
```
