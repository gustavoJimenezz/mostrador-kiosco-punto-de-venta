# Plan de Implementación Completo — Kiosco POS

**Fecha:** 2026-03-31
**Estado:** En desarrollo

---

## Stack Tecnológico

| Capa | Herramienta | Notas |
|------|-------------|-------|
| Lenguaje | Python 3.12+ | Tipado estático con `typing` |
| Validación | Pydantic v2 | Solo en capa de aplicación |
| UI | PySide6 (Qt) | Patrón MVP; archivos `.ui` cargados dinámicamente |
| ORM | SQLAlchemy 2.0 | Mapeo imperativo (no declarativo) |
| Base de datos | MariaDB | InnoDB/Aria; preparado para multi-terminal |
| Migraciones | Alembic | Control de versiones del esquema |
| Importación masiva | Polars | Listas Excel de proveedores |
| Compilación | Nuitka | Python → C++ → binario nativo |
| Distribución Windows | Inno Setup | `.exe` con MariaDB Portable bundleado |
| Distribución Linux | `dpkg-deb` | `.deb` con MariaDB vía `apt` |

---

## Arquitectura Hexagonal (Ports & Adapters)

```
src/
├── domain/               # Core puro — CERO dependencias externas
│   ├── models/           # Product, Sale, CashClose, Price (Value Object)
│   ├── services/         # PriceCalculator, StockManager
│   └── ports/            # Interfaces/Protocolos (ProductRepository, PrinterBase)
├── application/
│   └── use_cases/        # ProcessSale, UpdateBulkPrices, GetProductByCode
├── infrastructure/
│   ├── persistence/      # SQLAlchemy + MariaDB (implementa ports de dominio)
│   ├── ui/               # PySide6 Windows, Widgets, Presenters (MVP)
│   └── hardware/         # PrinterAdapter (por OS), BarcodeAdapter, printer_factory.py
└── main.py               # Composition Root — inyección de dependencias
```

**Regla fundamental:** el dominio no puede importar nada de `infrastructure/` ni de `application/`.

---

## Reglas de Negocio Críticas

| Regla | Detalle |
|-------|---------|
| Aritmética monetaria | Siempre `decimal.Decimal` con `ROUND_HALF_UP`. Nunca `float` para precios en ARS. |
| Precio histórico inmutable | `sale_items.price_at_sale` guarda el precio en el momento de venta. No se recalcula retroactivamente. |
| Atomicidad en ventas | Stock + registro de venta + movimiento de caja en una sola transacción DB. O todo o nada. |
| Offline-first | La app inicia sin internet. Chequeos de licencias/actualizaciones son asincrónicos. |
| UI no bloqueante | Consultas a DB en `QThread`. Si el hilo principal se bloquea, el lector de barras pierde caracteres. |

---

## Epics y Tickets

### Epic 1: Dominio Puro — Entorno: Ubuntu/Linux

| Ticket | Descripción | Prioridad | DoD |
|--------|-------------|-----------|-----|
| 1.1 | Modelos de dominio y lógica de precios (`Product`, `Sale`, `Price`) | Crítica | Cobertura de tests unitarios 100% en cálculos de margen y precios. |
| 1.2 | Puerto de persistencia — definición de `ProductRepository` (Protocol/ABC) | Alta | Interfaz testeada con `MockRepository` en memoria. |

---

### Epic 2: Infraestructura y Adaptadores de Datos — Entorno: Ubuntu/Linux (o Docker)

| Ticket | Descripción | Prioridad | DoD |
|--------|-------------|-----------|-----|
| 2.1 | Adaptador MariaDB con SQLAlchemy 2.0 (mapeo imperativo, pool de conexiones) | Alta | Integración exitosa entre entidades de dominio y tablas de MariaDB. |
| 2.2 | Motor de búsqueda indexada: índice en `barcode`, FullText en `name` | Alta | Búsqueda por nombre en < 50ms con 5.000 registros. |

---

### Epic 3: Interfaz de Usuario — Entorno: Ubuntu/Linux (validación visual en Windows)

| Ticket | Descripción | Prioridad | DoD |
|--------|-------------|-----------|-----|
| 3.1 | Presenters y navegación keyboard-first (F1-F12) con `QThread` para DB | Crítica | Agregar productos al carrito y ver el total usando solo teclado. |
| 3.2 | Adaptador de importación Polars — carga masiva de listas Excel/CSV | Media | CSV de 5.000 filas procesado y guardado en < 3 segundos. |

---

### Epic 4: Adaptadores de Hardware — Entorno: Windows 11 (obligatorio)

| Ticket | Descripción | Prioridad | DoD |
|--------|-------------|-----------|-----|
| 4.1 | Adaptador de impresión térmica con `pywin32` + ESC/POS, rutas UNC | Media | Ticket de prueba impreso desde la app. |
| 4.2 | Escalado DPI (`Qt.HighDpiScaleFactorRoundingPolicy`) para monitores mixtos | Baja | App proporcional en diferentes resoluciones de Windows. |

---

### Epic 5: Compilación y Distribución Windows — Entorno: Windows 11 (obligatorio)

| Ticket | Descripción | Prioridad | DoD |
|--------|-------------|-----------|-----|
| 5.1 | Compilación con Nuitka → `POS.exe` (`--onefile` o `--standalone`) | Alta | Ejecutable funcional sin Python instalado. |
| 5.2 | Instalador con Inno Setup — bundlea `POS.exe` + MariaDB Portable | Media | `Instalar_POS.exe` instala el sistema completo. |

---

### Epic 6: Compilación y Distribución Ubuntu/Linux — Entorno: Ubuntu 22.04 / 24.04 LTS

| Ticket | GitHub | Descripción | Prioridad | DoD |
|--------|--------|-------------|-----------|-----|
| 6.1 | [#29](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues/29) | Adaptador de impresión térmica para Linux (CUPS / `/dev/usb/lp0`) | Media | Ticket impreso en Ubuntu; test unitario con `MockPrinter`. |
| 6.2 | [#30](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues/30) | Abstracción cross-platform en el Composition Root (`printer_factory.py`) | Alta | `main.py` inyecta adaptadores correctos en ambos OS sin `if sys.platform` dispersos. |
| 6.3 | [#31](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues/31) | Script de compilación Nuitka para Linux — binario ELF (`scripts/build_linux.sh`) | Alta | Binario `pos` funcional en Ubuntu 22.04 limpio (verificado con Docker). |
| 6.4 | [#32](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues/32) | Creación del paquete `.deb` con `dpkg-deb` — estructura `DEBIAN/`, `.desktop`, scripts pre/post | Alta | `dpkg -i kiosco-pos_*.deb` instala sin errores; `lintian` sin errores nivel `E`. |
| 6.5 | [#33](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues/33) | Instalación y configuración de MariaDB en Ubuntu vía `apt` + script `postinst` idempotente | Alta | Post-instalación crea DB, usuario y aplica migraciones Alembic sin intervención manual. |
| 6.6 | [#34](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues/34) | Tests de instalación end-to-end en Ubuntu limpio con Docker + Xvfb | Media | `scripts/test_deb.sh` pasa en Ubuntu 22.04 y 24.04. |

**Orden de ejecución recomendado para Epic 6:** 6.2 → 6.1 → 6.3 → 6.5 → 6.4 → 6.6

---

## Comparativa de Distribución: Windows vs Linux

| Aspecto | Windows | Linux |
|---------|---------|-------|
| Impresión | `pywin32` + rutas UNC (`\\localhost\Ticketera`) | CUPS + `/dev/usb/lp0` + regla `udev` |
| MariaDB | Portable (bundleada en el instalador) | `apt install mariadb-server` + `postinst` |
| Compilación | `nuitka --onefile` → `POS.exe` | `nuitka --onefile` → binario ELF `pos` |
| Distribución | Inno Setup → `Instalar_POS.exe` | `dpkg-deb` → `kiosco-pos_*.deb` |
| Tests integración | Windows 11 físico | Docker `ubuntu:22.04` + `Xvfb` |
| Escalado DPI | `Qt.HighDpiScaleFactorRoundingPolicy` | Nativo en Linux (Qt lo maneja) |

---

## Convenciones de Desarrollo

- Usar siempre `poetry run python3` para ejecutar scripts o módulos.
- Ejecutar tests con `poetry run pytest`.
- El skill `/committing` se invoca solo cuando el usuario lo solicita explícitamente.
- Cobertura 100% en `domain/`. Tests unitarios corren en Linux con `MockRepository` en memoria.
- Tests de integración de hardware requieren Windows 11.
