"""Configuración centralizada para la compilación con Nuitka.

Este módulo define todos los parámetros usados por ``build.bat`` para generar
el ejecutable ``POS.exe``.  Editar aquí antes de compilar; no se requiere
modificar el script ``.bat``.

Notas sobre ``--onefile`` vs ``--standalone``
---------------------------------------------
- ``--onefile``   : genera un único ``POS.exe`` autodescomprimible.  Simple para
  el cliente, pero el arranque es más lento porque extrae archivos a un
  directorio temporal en cada ejecución.  Recomendado para PCs con SSD.
- ``--standalone`` : genera una *carpeta* ``POS.dist/`` con el ejecutable y
  todas sus dependencias.  El arranque es notablemente más rápido en discos
  mecánicos (HDD) o CPUs antiguas porque no hay descompresión al iniciar.
  Recomendado para el hardware típico de un kiosco argentino.

El valor de ``BUILD_MODE`` controla cuál de los dos se usa.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Metadatos del ejecutable
# ---------------------------------------------------------------------------

#: Nombre del ejecutable de salida (sin extensión .exe).
APP_NAME: str = "POS"

#: Versión del ejecutable (visible en Propiedades → Detalles en Windows).
APP_VERSION: str = "1.0.0"

#: Nombre de la empresa que aparece en los metadatos del ejecutable.
COMPANY_NAME: str = "Mostrador Kiosco"

#: Descripción del producto en los metadatos del ejecutable.
PRODUCT_DESCRIPTION: str = "Sistema POS para kioscos"

# ---------------------------------------------------------------------------
# Modo de compilación
# ---------------------------------------------------------------------------

#: ``"onefile"``   → ejecutable único (más simple, arranque lento en HDD).
#: ``"standalone"`` → carpeta de distribución (arranque rápido en HDD/CPUs viejas).
BUILD_MODE: str = "standalone"

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

#: Punto de entrada de la aplicación, relativo a la raíz del proyecto.
ENTRY_POINT: str = "src/main.py"

#: Directorio de salida de la compilación.
OUTPUT_DIR: str = "dist"

#: Ruta al ícono del ejecutable (.ico).  Dejar en blanco para omitir.
ICON_PATH: str = "src/infrastructure/ui/resources/icon.ico"

# ---------------------------------------------------------------------------
# Flags adicionales de Nuitka
# ---------------------------------------------------------------------------

#: Habilitar el plugin de PySide6 (obligatorio para la UI Qt).
ENABLE_PYSIDE6_PLUGIN: bool = True

#: Solicitar privilegios de administrador al iniciar (UAC en Windows).
WINDOWS_UAC_ADMIN: bool = True

#: Mostrar estadísticas de memoria durante la compilación.
SHOW_MEMORY: bool = True

#: Nivel de optimización de Nuitka (``0`` = sin optimización, ``2`` = máxima con LTO).
#: NOTA: Nivel 2 activa --lto=yes (Link Time Optimization), lo que puede causar
#: "LLVM ERROR: out of memory" al linkear cientos de objetos (ej: PySide6).
#: Usar nivel 1 para compilación normal sin LTO.
OPTIMIZATION_LEVEL: int = 1

#: Deshabilitar la consola de Windows (la app es GUI pura; no se necesita CMD).
DISABLE_CONSOLE: bool = True
