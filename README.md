# Mostrador Kiosco — Punto de Venta

Sistema POS offline-first para kioscos en Argentina. Soporta operación sin internet, historial de precios ante inflación y navegación keyboard-first (F1-F12).

---

## Estado del plan de ejecución

| Ticket | Descripción | Estado |
|--------|-------------|--------|
| 1.1 | Modelos de dominio + Value Object Price | ✅ |
| 1.2 | Puertos de persistencia | ✅ |
| 2.1 | Adaptador MariaDB + SQLAlchemy 2.0 | ✅ |
| 2.2 | Motor de búsqueda FullText (< 50ms / 5K SKUs) | ✅ |
| **3.1** | **Presenters MVP + Navegación Keyboard-First** | ✅ |
| 3.2 | Importador Polars (CSV/Excel) | ⏳ |
| 4.1 | Impresión térmica ESC/POS (Windows) | ⏳ |
| 4.2 | Escalado DPI multi-resolución (Windows) | ⏳ |
| 5.1 | Compilación Nuitka → POS.exe | ⏳ |
| 5.2 | Instalador Inno Setup | ⏳ |

---

## Requisitos previos

Tener instalado antes de comenzar:

| Programa | Versión mínima | Instalación |
|----------|---------------|-------------|
| Python | 3.12+ | [python.org/downloads](https://www.python.org/downloads/) |
| Poetry | 1.8+ | `curl -sSL https://install.python-poetry.org \| python3 -` |
| Docker | 24+ | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| Git | cualquiera | `sudo apt install git` |

> Docker se usa solo para levantar MariaDB en desarrollo. En producción se instala MariaDB nativo junto con la app.

---

## Puesta en marcha

**Paso 1 — Levantar MariaDB**

```bash
docker run -d --name mariadb-pos \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=kiosco_pos \
  -p 3306:3306 mariadb:10.11
```

**Paso 2 — Instalar dependencias**

```bash
poetry install
```

**Paso 3 — Configurar conexión a la base de datos**

```bash
export DATABASE_URL="mysql+pymysql://root:root@localhost:3306/kiosco_pos"
```

**Paso 4 — Crear tablas**

```bash
poetry run alembic upgrade head
```

**Paso 5 — Ejecutar la aplicación**

```bash
poetry run python src/main.py
```

---

## Credenciales por defecto 

Al ejecutar `alembic upgrade head` se crea automáticamente un usuario administrador:

| Campo | Valor |
|-------|-------|
| Usuario | `Administrador` |
| PIN | `1234` |
| Rol | Admin (acceso completo) |

> **Importante:** Cambiar el PIN desde Configuración → Usuarios tras el primer inicio.

---

## Tests

```bash
# Unitarios (sin DB)
poetry run pytest tests/ -m "not integration" -v

# Con cobertura del dominio
poetry run pytest tests/domain/ tests/unit/ --cov=src/domain --cov-report=term-missing

# Integración (requiere MariaDB)
POS_TEST_DB_URL="mysql+pymysql://root:root@localhost:3306/kiosco_test" \
  poetry run pytest -m integration -v
```

---

## Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `F1` | Nueva venta |
| `F2` | Buscar por nombre |
| `F4` | Confirmar venta / Cobrar |
| `F10` | Cierre de caja *(próximamente)* |
| `Esc` | Cancelar búsqueda |
| `Enter` | Confirmar / buscar barcode |

---

## Herramientas de desarrollo

### Hot-reload de vistas (Ctrl+R)

Durante el desarrollo es posible recargar la vista de la pestaña activa **sin reiniciar la aplicación** presionando `Ctrl+R`.

**Cómo funciona:**

1. Recarga el módulo Python de la vista con `importlib.reload()`.
2. Destruye el widget actual y crea una nueva instancia de la clase.
3. Re-inyecta el presenter existente en la nueva vista.

**Pestañas compatibles:**

| Pestaña | Vista recargada |
|---------|----------------|
| F9 — Importar | `ImportView` |
| F5 — Productos | `ProductManagementView` |
| F6 — Editar Stock | `StockEditView` |
| F7 — Inyectar Stock | `StockInjectView` |
| F2 — Historial | `SalesHistoryView` |
| Historial de caja | `CashHistoryView` |

> La pestaña principal (venta) no es recargable porque su layout proviene de un archivo `.ui`.

**Limitación:** no recarga dependencias transitivas. Si el cambio está en un widget importado por la vista, reiniciar la aplicación.

### Cómo eliminar esta funcionalidad antes de producción

Todo el código de hot-reload está marcado con la etiqueta `[DEV_ONLY]`. Para ubicar y eliminar todos los puntos:

```bash
grep -rn "\[DEV_ONLY\]" src/
```

Archivos afectados: `src/infrastructure/ui/windows/main_window.py`

Elementos a eliminar:
- `import importlib` (línea marcada con `[DEV_ONLY]`)
- Línea `self._tab_import = tab_import` en `_load_ui()`
- Líneas `self._*_presenter = presenter` en cada setter `set_*_presenter()`
- Línea del shortcut `Ctrl+R` en `_setup_shortcuts()`
- Bloque completo delimitado por los comentarios `[DEV_ONLY]` (clase `_DEV_RELOAD_MAP` + método `_dev_reload_view()`)
