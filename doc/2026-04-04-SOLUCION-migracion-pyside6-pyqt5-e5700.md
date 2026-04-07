# Solución: Migración PySide6 → PyQt5 para compatibilidad con Pentium E5700

## Contexto del problema

La PC del kiosco tiene un **Pentium Dual-Core E5700 @ 3.00GHz** (arquitectura Wolfdale, 2009).
El sistema operativo instalado es **Ubuntu 22.04 LTS**.

PySide6 instalado desde pip (wheel de PyPI) usa instrucciones de CPU **SSE4.2** que el E5700
no soporta. Esto provoca un crash con `SIGILL` (invalid opcode) al intentar correr o compilar
la aplicación. El problema se manifiesta en `libshiboken6.abi3.so.6.10`.

Intentos fallidos:
- Compilar el .deb en Ubuntu 24.04 → GLIBC 2.38 incompatible con Ubuntu 22.04 (GLIBC 2.35)
- Compilar en el E5700 con Ubuntu 22.04 → PySide6 de pip falla con SIGILL durante `poetry install`
- `python3-pyside6` vía apt → no existe en Ubuntu 22.04 (ni siquiera en universe)

## Solución validada

**PyQt5 funciona correctamente en el E5700 con Ubuntu 22.04.**

```bash
pip3 install PyQt5
python3 -c "from PyQt5.QtWidgets import QApplication; print('OK')"
# → OK
```

PyQt5 5.15.x usa wheels compiladas para `manylinux2014_x86_64` con instrucciones
compatibles con CPUs sin SSE4.2.

## Estrategia elegida: build-time source transformation (parche de build)

### Nombre técnico

`Build-time source transformation` (también llamado `build-time patching` o `compatibility shim`).
Es la misma idea que el preprocesador de C con `#ifdef LEGACY`, o la herramienta `2to3` de Python.

### Principio

El código fuente principal **nunca se modifica**. Sigue siendo 100% PySide6.
Solo cuando se necesita generar el paquete para el kiosco E5700, un script:

1. **Copia** `src/` a un directorio temporal (`/tmp/build_legacy/`).
2. **Transforma** la copia con reemplazos de texto (`sed`) sobre `src/infrastructure/ui/`:
   - `from PySide6.QtXxx` → `from PyQt5.QtXxx`
   - `Signal` → `pyqtSignal`
   - `Slot` → `pyqtSlot`
3. **Compila** con Nuitka desde la copia transformada (con PyQt5 en el entorno).
4. **Empaqueta** el binario en un `.deb` legacy.

```
src/ (PySide6 — intocable)
     │
     └─ build_linux_legacy.sh
          ├─ copia → /tmp/build_legacy/src/
          ├─ transforma (sed)
          ├─ compila con Nuitka + PyQt5
          └─ dist/kiosco-pos-legacy_<version>_amd64.deb
```

### Qué cambia en el proyecto

Solo se agregan dos archivos nuevos en `scripts/`:
- `scripts/build_linux_legacy.sh` — copia + transforma + compila
- `scripts/package_deb_legacy.sh` — empaqueta el binario en `.deb`

En `pyproject.toml` se agrega un grupo de dependencias opcional:
```toml
[tool.poetry.group.legacy.dependencies]
PyQt5 = ">=5.15.0"
```

### Qué NO cambia

- Ningún archivo en `src/` se toca.
- El build normal (Windows y Linux moderno) sigue usando PySide6.
- No hay branches adicionales que mantener.
- El build legacy se genera solo cuando se necesita (`poetry install --with legacy`).

---

## Próximo paso: migración PySide6 → PyQt5

La migración afecta exclusivamente `src/infrastructure/ui/`. El dominio, aplicación
y persistencia no se tocan.

### Cambios principales

| PySide6 | PyQt5 |
|---|---|
| `from PySide6.QtWidgets import ...` | `from PyQt5.QtWidgets import ...` |
| `from PySide6.QtCore import ...` | `from PyQt5.QtCore import ...` |
| `from PySide6.QtGui import ...` | `from PyQt5.QtGui import ...` |
| `Signal` | `pyqtSignal` |
| `Slot` | `pyqtSlot` |
| `QUiLoader` (runtime) | `uic.loadUi` |
| `exec()` en QApplication | `exec_()` (PyQt5 < 5.15) o `exec()` |

### Archivos a migrar (~50 archivos)

```
src/infrastructure/ui/app_config.py
src/infrastructure/ui/theme.py
src/infrastructure/ui/session.py
src/infrastructure/ui/dialogs/        (5 archivos)
src/infrastructure/ui/presenters/     (10 archivos)
src/infrastructure/ui/views/          (11 archivos)
src/infrastructure/ui/widgets/        (3 archivos)
src/infrastructure/ui/windows/        (4 archivos)
src/infrastructure/ui/workers/        (7 archivos)
```

### pyproject.toml

Reemplazar:
```toml
PySide6 = ">=6.7.0"
```
Por:
```toml
PyQt5 = ">=5.15.0"
```

## Datos de la PC legacy (kiosco)

| Componente | Detalle |
|---|---|
| CPU | Intel Pentium Dual-Core E5700 @ 3.00GHz |
| Arquitectura | x86-64 (Wolfdale, 2009) — sin SSE4.2, sin AVX |
| RAM | 8 GB |
| OS instalado | Ubuntu 22.04 LTS (Jammy) |
| GLIBC | 2.35 |
| Usuario | `kiosco` |

---

## Instrucciones para confirmar y activar el cambio en la PC legacy

Estas instrucciones se ejecutan **en la PC del kiosco (E5700)** una vez que el
paquete `.deb` legacy esté generado desde la PC de desarrollo.

### Paso 1 — Verificar que PyQt5 funciona (ya validado)

```bash
python3 -c "from PyQt5.QtWidgets import QApplication; print('OK')"
# Esperado: OK
```

### Paso 2 — Verificar que qtpy detecta PyQt5

```bash
pip3 install qtpy
QT_API=pyqt5 python3 -c "import qtpy; print(qtpy.API_NAME)"
# Esperado: PyQt5
```

### Paso 3 — Instalar el paquete legacy

```bash
sudo dpkg -i kiosco-pos-legacy_<version>_amd64.deb
sudo apt-get install -f   # si hay dependencias faltantes
```

### Paso 4 — Verificar la instalación

```bash
# Confirmar que el binario existe
ls -la /usr/bin/POS /usr/lib/kiosco-pos/POS

# Confirmar que MariaDB está activo
sudo systemctl status mariadb

# Confirmar que la DB fue creada
sudo mysql -e "SHOW DATABASES LIKE 'kiosco_pos';"

# Lanzar la app desde terminal para ver errores
/usr/bin/POS 2>&1
```

### Paso 5 — Si la app no abre

```bash
# Ver log de la app
tail -50 ~/.local/share/kiosco-pos/pos.log

# Ver errores del sistema
sudo dmesg | tail -20

# Forzar backend X11 si hay problema con Wayland
QT_QPA_PLATFORM=xcb /usr/bin/POS 2>&1
```

---

## Instrucciones para generar el paquete legacy (PC de desarrollo)

> **¿Tiene que ser la PC del kiosco (E5700)?**
> **No.** La compilación se puede hacer en **cualquier PC con Ubuntu 22.04**
> (física o VM). La restricción es el sistema operativo, no el hardware.
> Ubuntu 22.04 usa GLIBC 2.35 — compilar en esta versión garantiza que el
> binario sea compatible con el E5700. Compilar en Ubuntu 24.04 (GLIBC 2.38)
> producirá un binario que **no** funcionará en el E5700.
>
> Flujo recomendado:
> 1. **PC de desarrollo** (Ubuntu 22.04, CPU moderna) → genera el `.deb`
> 2. **E5700** (Ubuntu 22.04) → instala el `.deb` vía USB o red

### Prerequisitos en la PC de desarrollo

```bash
sudo apt update && sudo apt install -y \
    python3-dev python3-pip python3-venv \
    build-essential git curl \
    patchelf ccache \
    libmariadb-dev pkg-config \
    libgl1 libglib2.0-0 libxcb-cursor0 \
    mariadb-server

curl -sSL https://install.python-poetry.org | python3 -
# Cerrar y reabrir terminal
```

### Compilar versión legacy

```bash
git clone https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta.git
cd mostrador-kiosco-punto-de-venta

# Instalar dependencias incluyendo grupo legacy (PyQt5)
poetry install --with legacy

# Paso 1 — Verificar que la transformación sed es correcta (sin compilar)
bash scripts/build_linux_legacy.sh --dry-run
# Los archivos transformados quedan en /tmp/build_legacy/
# Verificar con:
grep -r 'PyQt5' /tmp/build_legacy/src/infrastructure/ui/ --include="*.py" | head -20
# No deben quedar referencias a PySide6 en ui/:
grep -r 'PySide6' /tmp/build_legacy/src/infrastructure/ui/ --include="*.py"

# Paso 2 — Compilar con backend PyQt5
QT_API=pyqt5 bash scripts/build_linux_legacy.sh --standalone

# Paso 3 — Empaquetar
bash scripts/package_deb_legacy.sh --standalone
```

El archivo generado queda en `dist/kiosco-pos-legacy_<version>_amd64.deb`.
Copiarlo a la PC del kiosco vía USB o red y seguir los pasos de instalación arriba.

---

## Prompt para retomar esta conversación

```
Estamos migrando la UI de PySide6 a PyQt5 en el proyecto mostrador-kiosco-punto-de-venta.

El motivo es que la PC del kiosco (Pentium E5700, Ubuntu 22.04) no soporta SSE4.2
y PySide6 de pip falla con SIGILL. PyQt5 fue validado y funciona correctamente.

El contexto completo está en doc/2026-04-04-SOLUCION-migracion-pyside6-pyqt5-e5700.md

Tarea pendiente: ejecutar la migración PySide6 → PyQt5 en src/infrastructure/ui/.
Cambiar imports, Signal→pyqtSignal, Slot→pyqtSlot, QUiLoader→uic.loadUi,
y actualizar pyproject.toml.

Arrancar por src/infrastructure/ui/workers/ que son los más simples,
luego views/, dialogs/, windows/, y por último app_config.py y theme.py.
```
