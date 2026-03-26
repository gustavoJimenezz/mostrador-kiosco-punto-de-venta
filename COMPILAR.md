# Guía de Compilación y Distribución (Windows 11)

Este documento explica cómo generar el instalador `Instalar_Kiosco_POS.exe` desde cero en Windows 11.

---

## Prerequisitos

Instalar todo esto una sola vez antes de comenzar.

| Herramienta | Para qué sirve | Descarga |
|---|---|---|
| **Python 3.12** | Lenguaje base del proyecto | [python.org/downloads](https://python.org/downloads) |
| **Poetry** | Gestiona dependencias y entorno virtual | Ver comando abajo |
| **Git** | Clonar el repositorio | [git-scm.com](https://git-scm.com) |
| **Inno Setup 6.3+** | Genera el instalador `.exe` desde `installer.iss` | [jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php) |
| **Visual Studio Build Tools** | Nuitka compila Python a C++ y necesita MSVC para enlazar | [visualstudio.microsoft.com/downloads](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) |

> **Nota sobre Git:** si copiás la carpeta del proyecto por ZIP o USB, Git no es necesario.

### Instalar Poetry (ejecutar en PowerShell)

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

Cerrar y reabrir PowerShell después de instalar para que el PATH se actualice.

### Instalar Visual Studio Build Tools

1. Descargar **Build Tools for Visual Studio** desde el link de la tabla.
2. En el instalador, seleccionar únicamente: **"Desarrollo de escritorio con C++"**.
3. Instalar y reiniciar si se solicita.

---

## Paso a paso

### Paso 1 — Clonar el repositorio

```bat
git clone <url-del-repositorio>
cd mostrador-kiosco-punto-de-venta
```

Si ya tenés la carpeta del proyecto (por ZIP o USB), ir directamente al Paso 2.

---

### Paso 2 — Instalar dependencias Python

```bat
poetry install
```

Crea el entorno virtual con todas las dependencias: PySide6, SQLAlchemy, Nuitka, Polars, etc.

**Solo necesario la primera vez**, o cuando se agregan nuevas dependencias al proyecto.

---

### Paso 3 — Preparar MariaDB Portable

Abrir CMD **como Administrador** y ejecutar:

```bat
scripts\prepare_vendor.bat
```

Este script:
- Descarga MariaDB 11.4.5 para Windows x64 (~500 MB, requiere internet)
- Elimina archivos innecesarios para reducir el tamaño a ~100 MB
- Inicializa el directorio de datos (`vendor\mariadb\data\`)

**Solo necesario la primera vez.** Si `vendor\mariadb\` ya existe y tiene el marcador `.extracted`, el script omite la descarga y extracción automáticamente.

---

### Paso 4 — Compilar el ejecutable

```bat
build.bat
```

Compila `src/main.py` con Nuitka y genera `dist\POS.dist\` (carpeta con el ejecutable y todas sus dependencias).

**Este paso hay que repetirlo cada vez que se modifique el código fuente.**

Opciones disponibles:

```bat
build.bat              # Modo por defecto (standalone: carpeta, arranque rápido en HDD)
build.bat --standalone # Igual al anterior
build.bat --onefile    # Ejecutable único (más simple, pero arranque lento en HDD)
build.bat --help       # Ver ayuda
```

> **Tiempo estimado:** entre 5 y 20 minutos según la PC. No cerrar la ventana.

---

### Paso 5 — Generar el instalador

```bat
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer\installer.iss
```

> Si `iscc` está en el PATH podés usar simplemente `iscc installer\installer.iss`.

Genera el archivo final en:

```
dist\Instalar_Kiosco_POS.exe
```

---

## Resultado

```
dist\
├── POS.dist\                  ← generado por build.bat (Paso 4)
│   ├── POS.exe
│   └── ... (dependencias)
└── Instalar_Kiosco_POS.exe    ← instalador final (Paso 5)
```

El archivo `Instalar_Kiosco_POS.exe` es lo que se entrega al cliente. No necesita Python ni ningún prerequisito adicional.

---

## Cuándo repetir cada paso

| Situación | Pasos a repetir |
|---|---|
| Primera vez en la PC | Prerequisitos → Pasos 1 al 5 |
| Se modificó código fuente | Paso 4 → Paso 5 |
| Se agregó una dependencia Python | Paso 2 → Paso 4 → Paso 5 |
| Solo cambió `installer.iss` | Paso 5 |
| PC nueva sin MariaDB en vendor/ | Paso 3 → Paso 4 → Paso 5 |

---

## Errores comunes

| Error | Causa probable | Solución |
|---|---|---|
| `'poetry' no se reconoce` | Poetry no está en el PATH | Reiniciar CMD/PowerShell después de instalar Poetry |
| `Nuitka no encontrado` | Dependencias no instaladas | Ejecutar `poetry install` |
| Error de compilador C durante Nuitka | Visual Studio Build Tools no instalado | Instalar "Desarrollo de escritorio con C++" |
| `No se encontró dist\POS.dist` al ejecutar `iscc` | `build.bat` no se ejecutó antes | Ejecutar el Paso 4 primero |
| `No se encontró vendor\mariadb` al ejecutar `iscc` | `prepare_vendor.bat` no se ejecutó | Ejecutar el Paso 3 primero (como Administrador) |
| `'iscc' no se reconoce` | Inno Setup no está en el PATH | Usar la ruta completa: `"C:\Program Files (x86)\Inno Setup 6\iscc.exe"` |
| Error de descarga en `prepare_vendor.bat` | Sin conexión a internet | Verificar conexión; la descarga es solo la primera vez |
