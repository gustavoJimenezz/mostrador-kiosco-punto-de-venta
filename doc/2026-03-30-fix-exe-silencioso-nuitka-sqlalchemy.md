# Fix: exe compilado no abre y no deja log — Nuitka + SQLAlchemy

**Fecha:** 2026-03-30
**Afecta:** build compilado con Nuitka (no ocurre en `poetry run python3 src/main.py`)
**Archivos modificados:** `src/main.py`, `build.bat`

---

## Síntoma

Al ejecutar `dist/main.dist/POS.exe`:
- La ventana no aparece.
- No se escribe ningún archivo `.log` en el Escritorio.
- Exit code: `1`.

El mismo código corriendo con `poetry run python3 src/main.py` funciona sin errores.

---

## Diagnóstico paso a paso

### Problema 1 — Bug en el manejador de errores de `main.py`

El bloque de entrada original era:

```python
if __name__ == "__main__":
    _log = Path.home() / "Desktop" / "pos_error.log"
    try:
        sys.exit(main())        # ← sys.exit() lanza SystemExit
    except Exception:           # ← SystemExit hereda de BaseException, NO de Exception
        _log.write_text(...)    # ← nunca se ejecuta
```

`SystemExit` es subclase de `BaseException`, no de `Exception`. Por eso, aunque
`main()` retornara `1` (error de DB) o lanzara cualquier excepción interna, el
log **nunca** se escribía.

**Fix aplicado en `src/main.py`:**

```python
if __name__ == "__main__":
    _log = Path.home() / "Desktop" / "pos_error.log"
    _exit_code = 1
    try:
        _exit_code = main()
    except Exception:
        _log.write_text(traceback.format_exc(), encoding="utf-8")
    else:
        if _exit_code != 0:
            _log.write_text(
                f"La aplicación terminó con código de salida {_exit_code}.\n"
                "Causa probable: MariaDB no disponible o el health check falló.\n"
                f"DATABASE_URL usada: {os.environ.get('DATABASE_URL', '(no definida)')}\n",
                encoding="utf-8",
            )
    sys.exit(_exit_code)
```

Separar `main()` de `sys.exit()` garantiza que el log se escriba tanto para
excepciones como para retornos de código no-cero.

---

### Problema 2 — Crash antes del bloque `__main__` (sin log)

Incluso con el fix anterior, si una excepción ocurre a **nivel de módulo**
(durante los imports, antes de llegar a `if __name__ == "__main__":`), no se
escribe ningún log.

Para capturar estos errores se usó `sys.excepthook` como trampa temprana:

```python
# Al inicio de main.py, antes de los imports de terceros
def _early_excepthook(exc_type, exc_value, exc_tb):
    import traceback as _tb
    try:
        _log = Path.home() / "Desktop" / "pos_startup.log"
        _log.write_text(
            f"EXCEPCIÓN NO MANEJADA: {exc_type.__name__}: {exc_value}\n"
            + "".join(_tb.format_tb(exc_tb)),
            encoding="utf-8",
        )
    except Exception:
        pass

sys.excepthook = _early_excepthook
```

> **Nota:** Este bloque es solo para diagnóstico. Fue removido del código
> fuente una vez identificada la causa raíz.

---

### Problema 3 — `pymysql` no incluido en el bundle

Con `--nofollow-import-to=sqlalchemy` activo, Nuitka corta el grafo de
dependencias de SQLAlchemy. `pymysql` es el driver MySQL que SQLAlchemy
usa en runtime y no es detectado automáticamente.

**Fix:** agregar `--include-package=pymysql` a `build.bat` (o copiarlo
manualmente desde el venv, ver Problema 4).

---

### Problema 4 — Conflicto `--nofollow-import-to` vs `--include-package`

La combinación `--nofollow-import-to=sqlalchemy` + `--include-package=sqlalchemy`
no funciona en Nuitka ≥ 4.x:

- `--nofollow-import-to=sqlalchemy` excluye el paquete del bundle Y activa
  un bloqueo en runtime (`excluded-module-usage` deployment flag).
- `--include-package=sqlalchemy` no sobreescribe esa exclusión.
- `--no-deployment-flag=excluded-module-usage` desactiva el bloqueo en runtime
  pero SQLAlchemy sigue sin estar en el bundle → `ModuleNotFoundError`.

Si se elimina `--nofollow-import-to=sqlalchemy` y se deja que Nuitka compile
SQLAlchemy a C++, ocurre la `LoaderStrategyException` documentada en
`2026-03-28-fix-nuitka-sqlalchemy-orm-strategies.md`: los decoradores
`@strategy_for` se ejecutan en compile-time (proceso de Nuitka) y el binario
arranca con `_all_strategies` vacío.

**Causa raíz final:** SQLAlchemy no puede compilarse con Nuitka a C++ y tampoco
puede incluirse como bytecode usando solo los flags de Nuitka.

---

## Solución final aplicada

### Estrategia

Excluir completamente SQLAlchemy y pymysql de la compilación Nuitka y copiarlos
manualmente desde el venv al directorio `dist/main.dist/` en el paso post-build.
Esto garantiza que ambos paquetes estén presentes como **bytecode Python puro**,
con semántica CPython completa, sin ninguna transformación de Nuitka.

### `build.bat` — flags de Nuitka

```bat
REM Excluir de compilacion; se copian manualmente en post-build.
set NUITKA_FLAGS=%NUITKA_FLAGS% --nofollow-import-to=sqlalchemy
set NUITKA_FLAGS=%NUITKA_FLAGS% --nofollow-import-to=pymysql
set NUITKA_FLAGS=%NUITKA_FLAGS% --no-deployment-flag=excluded-module-usage
```

`--no-deployment-flag=excluded-module-usage` es necesario para deshabilitar el
bloqueo en runtime que Nuitka agrega cuando un módulo es excluido con
`--nofollow-import-to`.

### `build.bat` — paso post-build (dentro del bloque `standalone`)

```bat
set VENV_SITEPACKAGES=.venv\Lib\site-packages

if exist "!VENV_SITEPACKAGES!\sqlalchemy" (
    powershell -NoProfile -Command ^
        "Copy-Item -Path '!VENV_SITEPACKAGES!\sqlalchemy' -Destination '%DIST_PATH%\sqlalchemy' -Recurse -Force"
    echo     OK — sqlalchemy copiado desde venv.
)

if exist "!VENV_SITEPACKAGES!\pymysql" (
    powershell -NoProfile -Command ^
        "Copy-Item -Path '!VENV_SITEPACKAGES!\pymysql' -Destination '%DIST_PATH%\pymysql' -Recurse -Force"
    echo     OK — pymysql copiado desde venv.
)
```

**Nota sobre `!VAR!` vs `%VAR%`:** dentro de bloques `if (...)` con
`setlocal EnableDelayedExpansion`, las variables definidas en el mismo bloque
deben referenciarse con `!VAR!`. Con `%VAR%` la expansión ocurre en
parse-time (antes del `set`) y el valor queda vacío.

---

## Resultado

```
dist\main.dist\
├── POS.exe
├── sqlalchemy\       ← copiado desde .venv\Lib\site-packages\sqlalchemy
├── pymysql\          ← copiado desde .venv\Lib\site-packages\pymysql
├── vendor\mariadb\
├── config\database.ini
└── src\infrastructure\ui\...
```

El exe abre correctamente. SQLAlchemy y pymysql ejecutan sus imports con
semántica Python estándar; los decoradores `@strategy_for` registran las
estrategias ORM en tiempo de ejecución sin interferencia de Nuitka.

---

## Checklist para futuros builds

- [ ] Verificar espacio en disco antes de compilar (Nuitka genera ~1-2 GB de
  archivos temporales).
- [ ] Si se actualiza SQLAlchemy o pymysql via `poetry update`, el post-build
  los copia automáticamente desde el venv — no se requiere acción manual.
- [ ] El `pos_error.log` en el Escritorio es el primer lugar a revisar si el
  exe falla al arrancar.
