# Ticket 9 — Compilación con Nuitka (.exe)

**Fecha:** 2026-03-26

## Resumen

Implementación del sistema de compilación con Nuitka para generar el ejecutable `POS.exe` de Windows. Se crearon un archivo de configuración centralizado (`build_config.py`) y un script de compilación (`build.bat`) que permiten producir un ejecutable standalone sin requerir Python en la máquina del cliente.

El objetivo principal fue cubrir la Epic 5 (Empaquetado y Distribución): un operador o técnico con Windows 11 puede correr `build.bat` y obtener un `POS.exe` listo para distribuir a cualquier kiosco.

---

## Cambios Principales

- Nuevo `build_config.py` con todos los parámetros Nuitka centralizados (nombre, versión, empresa, modo, flags)
- Nuevo `build.bat` que lee la configuración, valida el entorno y ejecuta la compilación en 5 pasos
- Soporte para dos modos de distribución: `--onefile` y `--standalone`, seleccionables por argumento o en el config
- Metadatos del ejecutable embebidos: nombre, versión, empresa y descripción visibles en Propiedades de Windows
- Ícono configurable (`--windows-icon-from-ico`) con advertencia si el archivo no existe
- Consola de Windows deshabilitada (`--windows-console-mode=disable`) — la app es GUI pura
- UAC admin configurado (`--windows-uac-admin`) para acceso a recursos del sistema
- `.gitignore` actualizado: agregado `*.build/` (directorio temporal que Nuitka crea durante la compilación)

---

## Flujo de Trabajo

```
[build.bat ejecutado en Windows 11]
        ↓
[Lee build_config.py via poetry run python]
    → APP_NAME, APP_VERSION, BUILD_MODE, flags...
        ↓
[Verifica que Nuitka esté instalado]
    → poetry run python -m nuitka --version
        ↓
[Crea directorio dist/ si no existe]
        ↓
[Construye flags del comando Nuitka dinámicamente]
    → --standalone [+ --onefile si BUILD_MODE=onefile]
    → --enable-plugin=pyside6
    → --windows-uac-admin
    → --windows-console-mode=disable
    → --lto=yes (si OPT_LEVEL=2)
    → metadatos + ícono
        ↓
[Ejecuta: poetry run python -m nuitka <flags> src/main.py]
        ↓
[Salida: dist/POS.exe  ó  dist/POS.dist/]
```

### Modos de distribución

| Modo | Salida | Cuándo usar |
|------|--------|-------------|
| `standalone` (defecto) | `dist/POS.dist/` — carpeta con el exe y dependencias | PCs con HDD o CPUs antiguas (kioscos típicos); arranque rápido porque no hay descompresión |
| `onefile` | `dist/POS.exe` — ejecutable único autodescomprimible | PCs con SSD donde la simplicidad de un solo archivo es prioritaria |

---

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `build_config.py` | **Nuevo** — parámetros Nuitka centralizados (modo, versión, flags, rutas) |
| `build.bat` | **Nuevo** — script de compilación Windows con lectura dinámica del config |
| `.gitignore` | **Modificado** — agregado `*.build/` junto a los exclusiones Nuitka existentes |

---

## Notas Técnicas

- **Nuitka solo en la máquina de compilación:** el `.exe` resultante corre en cualquier Windows sin Python, sin Nuitka ni dependencias instaladas.
- **`poetry run` obligatorio:** el script usa `poetry run python -m nuitka` en lugar de `python -m nuitka` para garantizar que se usa el entorno Poetry del proyecto, consistente con las convenciones del proyecto.
- **Argumento sobreescribe config:** `build.bat --onefile` o `build.bat --standalone` ignoran el `BUILD_MODE` de `build_config.py`, útil para compilaciones puntuales sin editar el archivo.
- **LTO habilitado con `OPTIMIZATION_LEVEL=2`:** Link Time Optimization reduce el tamaño del ejecutable final a costa de mayor tiempo de compilación.
- **Ícono opcional:** si `ICON_PATH` no existe en disco, el script continúa con una advertencia en lugar de abortar.
