# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Instrucciones del Asistente

- **Idioma:** Comunicarse exclusivamente en **español**, con tono profesional, directo y técnico.
- **Rol:** Actuar como Ingeniero de Software Senior y Arquitecto de Soluciones.
- **Salida:** Sin introducciones ni explicaciones innecesarias. Si una tarea es ambigua, hacer preguntas aclaratorias antes de generar código. Usar bloques de código con el lenguaje especificado.
- **Enfoque:** Antes de escribir código complejo, explicar brevemente el enfoque a tomar.
- **Coherencia documental:** Todo lo que se implemente debe ser coherente con el contenido de `doc/aspectos-tecnicos.md` y `doc/plan-de-ejecucion.md`. Ante cualquier contradicción entre una instrucción puntual y la documentación, consultar al usuario antes de proceder.

## Project Overview

Sistema POS (Point-of-Sale) para kioscos en Argentina. Diseñado para operación offline-first, soporte multi-terminal y seguimiento de historial de precios ante inflación. El proyecto está en fase de desarrollo inicial (solo documentación en el primer commit; el código fuente aún no existe).

## Stack Tecnológico

| Capa | Herramienta | Notas |
|------|-------------|-------|
| Lenguaje | Python 3.12+ | Tipado estático con `typing` |
| Validación | Pydantic v2 | En capa de aplicación (no en dominio) |
| UI | PySide6 (Qt) | Patrón MVP; diseño en Qt Designer (.ui files) |
| ORM | SQLAlchemy 2.0 | Mapeo imperativo (no declarativo) |
| Base de datos | MariaDB | Motor InnoDB/Aria; soporta multi-terminal |
| Migraciones | Alembic | Control de versiones del esquema |
| Importación masiva | Polars | Reemplaza Pandas para listas Excel de proveedores |
| Compilación | Nuitka | Compila a C++; genera `.exe` para Windows |
| Instalador | Inno Setup | Empaqueta POS.exe + MariaDB Portable |

## Arquitectura Hexagonal (Ports & Adapters)

```
src/
├── domain/           # Core puro - CERO dependencias externas
│   ├── models/       # Product, Sale, CashClose, Price (Value Object)
│   ├── services/     # PriceCalculator, StockManager
│   └── ports/        # Interfaces/Protocolos (ProductRepository, PrinterBase)
├── application/
│   └── use_cases/    # ProcessSale, UpdateBulkPrices, GetProductByCode
├── infrastructure/
│   ├── persistence/  # SQLAlchemy + MariaDB (implementa ports de dominio)
│   ├── ui/           # PySide6 Windows, Widgets, Presenters (MVP)
│   └── hardware/     # PrinterAdapter (ESC/POS via pywin32), BarcodeAdapter
└── main.py           # Composition Root - inyección de dependencias
tests/                # Unitarios en Linux, Integración en Windows
alembic/              # Migraciones de DB
```

**Regla fundamental:** El dominio no puede importar nada de `infrastructure/` ni de `application/`. Los tests unitarios del dominio NO necesitan base de datos.

## Reglas Críticas de Negocio

- **Aritmética monetaria:** Usar siempre `decimal.Decimal` con `ROUND_HALF_UP`. Nunca `float` para precios o costos en ARS.
- **Precio histórico inmutable:** `sale_items.price_at_sale` guarda el precio en el momento de venta. Nunca recalcular retroactivamente.
- **Atomicidad en ventas:** El cierre de una venta (descuento de stock + registro de venta + movimiento de caja) debe ejecutarse en una sola transacción de DB. O todo, o nada.
- **Offline-first:** La app debe iniciar sin conexión a internet. Chequeos de licencias/actualizaciones deben ser asincrónicos.
- **UI no bloqueante:** Usar `QThread`/Worker para consultas a la DB. Si el hilo principal se bloquea, el lector de barras puede perder caracteres.

## Reglas de Desarrollo

1. **Calidad de Código:** Seguir Clean Code. Código modular y con responsabilidad única.
2. **Documentación:** Cada función nueva debe incluir docstring en Python (formato Google o NumPy).
3. **Manejo de Errores:** Priorizar manejo robusto de excepciones y validaciones de entrada en los límites del sistema (UI, importaciones, adaptadores de hardware).
4. **Comandos Python:** Usar siempre `python3` en lugar de `python` en cualquier comando de terminal (ej: `python3 -m ...`). Para ejecutar scripts o módulos del proyecto, preferir `poetry run python3 ...`.
5. **Skill `committing`:** No invocar el skill `/committing` de forma automática. Ejecutarlo solo cuando el usuario lo solicite explícitamente.

## Convenciones de Desarrollo

### Dominio
- Las entidades de dominio son clases Python puras (sin herencia de SQLAlchemy).
- Los Value Objects (ej: `Price`) deben ser inmutables.
- El mapeo ORM es **imperativo** en `infrastructure/persistence/`, nunca en las clases de dominio.

### UI (PySide6 / MVP)
- La lógica de presentación va en el **Presenter**, no en los Widgets.
- Los atajos de teclado F1-F12 son la interfaz primaria (keyboard-first).
- Los archivos `.ui` de Qt Designer se cargan dinámicamente.
- Configurar `Qt.HighDpiScaleFactorRoundingPolicy` para soporte multi-resolución en Windows.

### Base de Datos
- Índice en `products.barcode` (búsqueda por EAN-13).
- FullText Index en `products.name` (búsqueda fuzzy por nombre).
- Meta de performance: búsqueda por nombre < 50ms con 5,000 registros.
- Usar rutas UNC para impresoras térmicas en Windows (`\\localhost\Ticketera`).

### Tests
- Cobertura 100% en `domain/` (lógica de cálculo de precios y márgenes).
- Tests unitarios corren en Linux con `MockRepository` en memoria.
- Tests de integración (hardware, impresión) requieren Windows 11.
- **Ejecutar tests siempre con Poetry:** `poetry run pytest` (nunca `python -m pytest` directamente).

## Comandos de Compilación (Windows 11)

```bash
# Compilar a ejecutable único
python -m nuitka --standalone --show-memory --plugin-enable=pyside6 --windows-uac-admin --onefile main.py

# Para PCs con discos mecánicos: usar --standalone (carpeta) en lugar de --onefile
```

## Epics de Desarrollo (Plan de Ejecución)

| Epic | Entorno | Estado |
|------|---------|--------|
| 1. Dominio puro (modelos + ports) | Ubuntu/Linux | Pendiente |
| 2. Infraestructura MariaDB + SQLAlchemy | Ubuntu/Linux (o Docker) | Pendiente |
| 3. UI PySide6 + importador Polars | Ubuntu/Linux | Pendiente |
| 4. Adaptadores de hardware (impresora térmica, DPI) | Windows 11 | Pendiente |
| 5. Nuitka + Inno Setup | Windows 11 | Pendiente |
