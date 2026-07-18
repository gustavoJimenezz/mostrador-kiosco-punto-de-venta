# Fix: Rutas de Recursos en Ejecutable Compilado (Nuitka)

**Fecha:** 2026-03-27

## Resumen

Corrección de tres problemas que impedían que `POS.exe` (compilado con Nuitka) arrancara correctamente:

1. **Rutas de recursos rotas en el exe:** `main.py` usaba `Path(__file__).parent.parent` para localizar `vendor/mariadb` y `config/database.ini`, que funciona en desarrollo pero produce rutas incorrectas en el ejecutable compilado.
2. **Recursos no copiados al directorio de distribución:** `build.bat` no copiaba `vendor\mariadb`, `config\database.ini` ni `.env` después de que Nuitka terminaba de compilar.
3. **Base de datos no inicializada:** `scripts\prepare_vendor.bat` preparaba los binarios de MariaDB pero no creaba la base de datos `kiosco_pos` ni aplicaba las migraciones Alembic.

---

## Diagnóstico

El exe fallaba silenciosamente (consola deshabilitada con `--windows-console-mode=disable`) porque `launch_mariadb()` en `main.py` retornaba `False` antes de mostrar ninguna ventana Qt. La secuencia de fallos fue:

```
POS.exe arranca
  → load_dotenv() no encuentra .env (no estaba en main.dist\)
  → launch_mariadb() busca vendor\mariadb\ en ruta incorrecta
  → health check falla (sin DB kiosco_pos)
  → return False → sys.exit(1) silencioso
```

La confirmación de que el código fuente era correcto se hizo ejecutando:
```bash
DATABASE_URL="mysql+pymysql://root:@127.0.0.1:3306/kiosco_pos" poetry run python src/main.py
```
Resultado: exit code 0 — la app arrancó correctamente desde fuente.

---

## Cambios

### `src/main.py`

**Problema:** `Path(__file__).parent.parent` es correcto en desarrollo (`src/main.py` → raíz del proyecto) pero en Nuitka `__file__` apunta al exe, produciendo una ruta equivocada.

**Solución:** Detectar si corre como exe compilado con `sys.frozen` (Nuitka lo setea en `True`) y usar `Path(sys.executable).parent` en ese caso.

```python
# Antes
_PROJECT_ROOT = Path(__file__).parent.parent

# Después
if getattr(sys, "frozen", False):
    _PROJECT_ROOT = Path(sys.executable).parent   # dist\main.dist\
else:
    _PROJECT_ROOT = Path(__file__).parent.parent   # raíz del proyecto (dev)
```

Con este fix, en el exe compilado:
- `_VENDOR_PATH` → `dist\main.dist\vendor\mariadb\`
- `_CONFIG_PATH` → `dist\main.dist\config\database.ini`

### `build.bat`

Se agregaron tres mejoras:

**1. Cálculo correcto del nombre de carpeta de salida:**
Nuitka nombra la carpeta de distribución según el script de entrada (`src/main.py` → `main.dist`), ignorando `--output-filename`. El script ahora calcula esto dinámicamente:
```bat
for %%F in (%ENTRY_POINT%) do set DIST_FOLDER=%%~nF.dist
set DIST_PATH=%OUTPUT_DIR%\%DIST_FOLDER%
```
El mensaje de salida (`Salida: dist\POS.dist\`) quedaba incorrecto — ahora muestra `dist\main.dist\`.

**2. Paso post-build de copia de recursos (modo standalone):**
Después de que Nuitka termina, se copian automáticamente los tres recursos que el exe necesita en runtime:
```
vendor\mariadb\          → dist\main.dist\vendor\mariadb\
config\database.ini      → dist\main.dist\config\database.ini
.env                     → dist\main.dist\.env  (si existe)
```

**3. Limpieza del build anterior:**
Antes de compilar se elimina `dist\main.dist\` si existe, evitando mezclar archivos de builds anteriores.

### `scripts\prepare_vendor.bat`

Se agregó el **paso 6** (de 6): inicializar la base de datos `kiosco_pos` y aplicar las migraciones Alembic. Este paso se ejecuta una sola vez (usa marcador `.kiosco_initialized`).

Flujo del paso 6:
```
Iniciar mysqld temporalmente (start /B)
  → Esperar hasta 15s que mysqld responda
  → CREATE DATABASE kiosco_pos (utf8mb4)
  → poetry run alembic upgrade head
  → Crear marcador vendor\mariadb\data\kiosco_pos\.kiosco_initialized
  → Detener mysqld (mysqladmin shutdown → fallback taskkill)
```

También se corrigieron dos bugs menores preexistentes:
- **Typo:** `mysqadmin.exe` → `mysqladmin.exe` (faltaba la 'l'; el script funcionaba vía `taskkill /F` como fallback, pero sin shutdown graceful)
- **Contador de pasos:** actualizado de `[X/5]` a `[X/6]` en los primeros 5 pasos

### `COMPILAR.md`

Corregidas todas las referencias a `dist\POS.dist\` → `dist\main.dist\` (el nombre real que genera Nuitka).

---

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/main.py` | Modificado — fix `sys.frozen` para resolución de rutas en exe compilado |
| `build.bat` | Modificado — cálculo de `DIST_FOLDER`, paso post-build de recursos, limpieza previa |
| `scripts/prepare_vendor.bat` | Modificado — paso 6 (crear DB + migraciones), fix typo `mysqladmin`, contador `[X/6]` |
| `COMPILAR.md` | Modificado — referencias `POS.dist` → `main.dist` |
| `.env` | Nuevo — `DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3306/kiosco_pos` |

---

## Notas Técnicas

- **`sys.frozen` en Nuitka:** Nuitka setea `sys.frozen = True` en todos los modos de compilación (standalone y onefile). Es el mecanismo estándar para detectar ejecución como exe empaquetado, análogo a PyInstaller.
- **Nombre de carpeta Nuitka:** `--output-filename=POS.exe` solo renombra el ejecutable dentro de la carpeta. El nombre de la carpeta siempre deriva del script de entrada: `src/main.py` → `main.dist`. No hay flag de Nuitka para cambiar esto en modo standalone.
- **`.env` en `.gitignore`:** Confirmado que `.env` está en `.gitignore`. No se versiona.
- **Vendor en `.gitignore`:** `vendor/mariadb/*` está ignorado excepto `my.ini`. La carpeta completa con binarios y datos no se versiona; se genera con `prepare_vendor.bat`.
- **PIN por defecto del admin:** La migración `c9d8e7f6a5b4` crea el usuario `Administrador` con PIN `1234`. Debe cambiarse tras el primer uso.
