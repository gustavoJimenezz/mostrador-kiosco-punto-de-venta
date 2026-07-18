# Fix: LoaderStrategyException — Nuitka + SQLAlchemy ORM

**Fecha:** 2026-03-28
**Afecta:** build compilado con Nuitka (no ocurre en desarrollo)
**Archivos modificados:** `src/infrastructure/persistence/mappings.py`, `build.bat`

---

## Error original

```
sqlalchemy.orm.exc.LoaderStrategyException: Can't find strategy
(('deferred', False), ('instrument', True)) for Product.min_stock
```

El error aparece la primera vez que SQLAlchemy ejecuta una query ORM sobre
cualquier entidad mapeada (`User`, `Product`, `CashClose`). El traceback
llega desde `session.scalars()` → `mapper._configure_registries()` →
`StrategizedProperty._strategy_lookup()`.

---

## Causa raíz

### Mecanismo de registro de SQLAlchemy

SQLAlchemy registra las estrategias de carga de columnas y relaciones en
`StrategizedProperty._all_strategies`, un `defaultdict` de clase definido en
`sqlalchemy/orm/interfaces.py`. El registro ocurre mediante decoradores en
`sqlalchemy/orm/strategies.py` que se ejecutan al importar ese módulo:

```python
# sqlalchemy/orm/strategies.py
@ColumnProperty.strategy_for(deferred=False, instrument=True)
class ColumnLoader(LoaderStrategy): ...

@ColumnProperty.strategy_for(deferred=True, instrument=True)
class DeferredColumnLoader(LoaderStrategy): ...
```

Si `strategies.py` nunca se importa, `_all_strategies` queda vacío y
cualquier acceso a un mapper falla con `LoaderStrategyException`.

### Por qué falla en Nuitka y no en desarrollo

Nuitka realiza análisis estático del AST para optimizar el binario. Cuando
encuentra `from sqlalchemy.orm.strategies import ClassName`, resuelve la
clase en **tiempo de compilación** en su propio proceso Python. Los
decoradores `@strategy_for` se ejecutan durante esa resolución en el proceso
del compilador. El binario final **no recibe ese registro**: arranca con
`_all_strategies` vacío.

Este problema es conocido en la comunidad Nuitka (issues #2262, #3778). No
existe un plugin oficial `--plugin-enable=sqlalchemy` que lo resuelva
automáticamente. El archivo de configuración de paquetes estándar de Nuitka
(`standard.nuitka-package.config.yml`) solo incluye los `.json` de
SQLAlchemy, no gestiona el registro de estrategias.

### Por qué fallaron los primeros intentos

| Intento | Por qué no funcionó |
|---------|---------------------|
| `import sqlalchemy.orm.strategies  # noqa: F401` | Nuitka elimina imports sin ningún nombre referenciado como "dead code" |
| `from ... import UndeferredColumnLoader` | `UndeferredColumnLoader` no existe en SQLAlchemy 2.0.x (fue renombrado a `ColumnLoader`), causaba `ImportError` antes del `try/except` → sin log |
| `from ... import ColumnLoader` (nombre correcto) | Nuitka sigue resolviendo el import estáticamente; los decoradores corren en compile-time, no en runtime |

---

## Solución aplicada

### `src/infrastructure/persistence/mappings.py`

Reemplazar todos los imports estáticos de `sqlalchemy.orm.strategies` por
llamadas a `importlib.import_module()`:

```python
import importlib as _importlib

_importlib.import_module("sqlalchemy.orm.strategies")
_importlib.import_module("sqlalchemy.orm.loading")
_importlib.import_module("sqlalchemy.orm.relationships")
_importlib.import_module("sqlalchemy.orm.properties")
```

**Por qué funciona:** `importlib.import_module()` es una llamada de función
con un argumento string. Nuitka no puede resolverla estáticamente y la
conserva como llamada de runtime. Cuando el programa arranca, Python ejecuta
la inicialización completa del módulo, incluidos los decoradores
`@strategy_for`, populando `_all_strategies` correctamente.

`sqlalchemy.orm.loading` se incluye porque importa `SelectInLoader` desde
`strategies`, reforzando la cadena de inicialización.

### `build.bat`

Reemplazar los flags de SQLAlchemy anteriores por:

```bat
set NUITKA_FLAGS=%NUITKA_FLAGS% --include-package=sqlalchemy.orm
set NUITKA_FLAGS=%NUITKA_FLAGS% --include-package=sqlalchemy.dialects.mysql
```

`--include-package=sqlalchemy.orm` incluye todos los módulos de `sqlalchemy/orm/`
(entre ellos `strategies`, `loading`, `relationships`, `properties`) sin compilar
el paquete completo de SQLAlchemy. Usar `--include-package=sqlalchemy` en su lugar
causa un error de **disco lleno** durante la compilación C porque Nuitka intenta
compilar toda la librería (`sqlalchemy.sql`, `sqlalchemy.engine`, todos los dialects)
generando archivos `.o` de varios GB.

---

## Si el error vuelve a aparecer en una futura versión

Si después de actualizar SQLAlchemy o Nuitka el error reaparece, el siguiente
escalón es usar:

```bat
--nofollow-import-to=sqlalchemy
```

Esto indica a Nuitka que no compile SQLAlchemy a C, incluyéndolo como
bytecode Python puro. Al ejecutarse en modo interpretado, todos los imports
y decoradores corren con semántica CPython estándar sin ninguna optimización
que pueda truncarlos. Requiere mantener `--include-package=sqlalchemy`.
