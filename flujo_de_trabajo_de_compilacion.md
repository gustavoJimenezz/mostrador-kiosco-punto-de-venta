# Flujo de Compilación — Kiosco POS

El proceso transforma el código fuente Python en un instalador `.exe` listo para entregar al cliente. Involucra **3 herramientas**: Poetry, Nuitka e Inno Setup.

---

## Visión general

```
Código fuente (Python)
        │
        ▼
[Paso 1] scripts\prepare_vendor.bat
        │  Descarga y prepara MariaDB Portable en vendor\mariadb\
        │
        ▼
[Paso 2] build.bat
        │  Lee build_config.py → construye flags → ejecuta Nuitka
        │  Salida: dist\POS.dist\ (carpeta con POS.exe + dependencias)
        │
        ▼
[Paso 3] iscc installer\installer.iss
        │  Empaqueta todo con Inno Setup
        │
        ▼
dist\Instalar_Kiosco_POS.exe  ← entregable final
```

---

## Paso 1 — `prepare_vendor.bat` (se ejecuta una sola vez)

Prepara MariaDB Portable en `vendor\mariadb\`. El script hace 5 sub-pasos:

| Sub-paso | Qué hace |
|---|---|
| 1/5 | Descarga `mariadb-11.4.5-winx64.zip` (~500 MB) vía PowerShell |
| 2/5 | Extrae el ZIP en `vendor\` y mueve los binarios a `vendor\mariadb\` |
| 3/5 | Elimina archivos innecesarios (tests, PDFs, símbolos `.pdb`, idiomas) para reducir de ~500 MB a ~100 MB |
| 4/5 | Verifica que `my.ini` esté presente en `vendor\mariadb\` |
| 5/5 | Inicializa el directorio de datos con `mysql_install_db.exe` |

**Es idempotente:** si `.extracted` ya existe, saltea la descarga y extracción.

---

## Paso 2 — `build.bat` (se repite con cada cambio de código)

El script `.bat` delega toda la configuración a `build_config.py` y ejecuta Nuitka en 5 sub-pasos:

### Sub-paso 1/5 — Leer `build_config.py`

```python
APP_NAME = "POS"
APP_VERSION = "1.0.0"
BUILD_MODE = "standalone"   # "standalone" = carpeta | "onefile" = .exe único
ENTRY_POINT = "src/main.py"
OUTPUT_DIR = "dist"
ENABLE_PYSIDE6_PLUGIN = True
WINDOWS_UAC_ADMIN = True
OPTIMIZATION_LEVEL = 2      # activa --lto=yes (Link Time Optimization)
DISABLE_CONSOLE = True      # suprime la ventana CMD (app GUI pura)
```

### Sub-paso 2/5 — Verificar Nuitka

```bat
poetry run python -m nuitka --version
```

Puede tardar 1-2 minutos la primera vez mientras Poetry inicializa el entorno virtual.

### Sub-paso 3/5 — Crear `dist\`

Crea el directorio de salida si no existe.

### Sub-paso 4/5 — Construir los flags de Nuitka

El `.bat` ensambla dinámicamente el comando según los valores leídos de `build_config.py`:

```
--standalone
--output-dir=dist
--output-filename=POS.exe
--enable-plugin=pyside6        ← obligatorio para Qt/PySide6
--windows-uac-admin            ← solicita UAC al iniciar
--python-flag=no_asserts       ← elimina asserts de Python
--lto=yes                      ← optimización en tiempo de enlace (C++)
--windows-console-mode=disable ← sin ventana CMD
--product-name="POS" --product-version=1.0.0 ...
```

### Sub-paso 5/5 — Ejecutar Nuitka

```bat
poetry run python -m nuitka [flags] src/main.py
```

Nuitka transpila `src/main.py` (y todas sus importaciones) a **C++**, luego llama al compilador MSVC (Visual Studio Build Tools) para generar el `.exe`. Es el paso más largo: **5 a 20 minutos**.

Salida en modo `standalone`:

```
dist\
└── POS.dist\
    ├── POS.exe
    ├── PySide6\ (DLLs de Qt)
    └── ... (todas las dependencias Python compiladas)
```

---

## Paso 3 — `iscc installer\installer.iss` (Inno Setup)

Toma los artefactos generados y produce el instalador final.

### Validaciones previas (`InitializeSetup`)

- Verifica que exista `dist\POS.dist\` o `dist\POS.exe`
- Verifica que exista `vendor\mariadb\`
- Si falta alguno, muestra error y aborta

### Contenido empaquetado en el instalador

| Origen | Destino en instalación |
|---|---|
| `dist\POS.dist\` | `C:\Program Files\Kiosco POS\` |
| `vendor\mariadb\` | `{app}\vendor\mariadb\` |
| `config\database.ini` | `{app}\config\` (solo si no existe) |
| `installer\scripts\backup_daily.bat` | `{app}\scripts\` |

### Acciones post-instalación

- Crea acceso directo en escritorio y menú Inicio
- Crea tarea programada `Kiosco POS - Backup Diario` (02:00 AM, SYSTEM)
- Opcionalmente: regla de firewall para puerto 3306 (multi-caja, desactivado por defecto con `MultiCajaEnabled = 0`)

### Desinstalación segura

- Elimina logs, pero **no elimina `data\` ni `backups\`** para proteger los datos del cliente
- Advierte al usuario si hay datos antes de proceder

---

## Resumen de tiempos estimados

| Paso | Frecuencia | Tiempo estimado |
|---|---|---|
| `prepare_vendor.bat` | Una sola vez por PC | 10-30 min (depende de la descarga) |
| `build.bat` | Cada cambio de código | 5-20 min |
| `iscc installer.iss` | Cada cambio de código o instalador | < 2 min |

---

## Cuándo repetir cada paso

| Situación | Pasos a repetir |
|---|---|
| Primera vez en la PC | Prerequisitos → Pasos 1, 2 y 3 |
| Se modificó código fuente | Paso 2 → Paso 3 |
| Se agregó una dependencia Python | `poetry install` → Paso 2 → Paso 3 |
| Solo cambió `installer.iss` | Paso 3 |
| PC nueva sin `vendor\mariadb\` | Paso 1 → Paso 2 → Paso 3 |
