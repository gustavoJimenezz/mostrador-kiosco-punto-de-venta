#!/usr/bin/env bash
# =============================================================================
#  build_linux.sh — Compilación del sistema POS con Nuitka para Linux/Ubuntu
#  Entorno requerido: Ubuntu 22.04+ / Debian 12+ + Python 3.12 + Poetry
#
#  Uso:
#    ./scripts/build_linux.sh              → compila en modo standalone (default)
#    ./scripts/build_linux.sh --onefile    → genera binario único (más simple)
#    ./scripts/build_linux.sh --standalone → genera carpeta dist/ (arranque rápido)
#    ./scripts/build_linux.sh --help       → muestra esta ayuda
#
#  Salida:
#    standalone: dist/main.dist/POS   (distribuir toda la carpeta)
#    onefile:    dist/POS             (binario ELF único)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Ayuda
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--help" ]]; then
    echo "Uso: $0 [--onefile | --standalone]"
    echo ""
    echo "  --onefile     Genera un binario ELF único. Arranque más lento (extrae temp)."
    echo "  --standalone  Genera carpeta dist/. Arranque rápido en HDD/CPUs viejas."
    echo "  Sin argumento usa el modo definido en build_config.py (BUILD_MODE)."
    echo ""
    echo "  Editar build_config.py para cambiar versión, nombre, ícono, etc."
    exit 0
fi

# ---------------------------------------------------------------------------
# Leer configuración desde build_config.py
# ---------------------------------------------------------------------------
echo "[1/5] Leyendo configuración desde build_config.py..."

APP_NAME=$(poetry run python3 -c "import build_config as c; print(c.APP_NAME)")
APP_VERSION=$(poetry run python3 -c "import build_config as c; print(c.APP_VERSION)")
ENTRY_POINT=$(poetry run python3 -c "import build_config as c; print(c.ENTRY_POINT)")
OUTPUT_DIR=$(poetry run python3 -c "import build_config as c; print(c.OUTPUT_DIR)")
BUILD_MODE=$(poetry run python3 -c "import build_config as c; print(c.BUILD_MODE)")
ENABLE_PYSIDE6=$(poetry run python3 -c "import build_config as c; print(str(c.ENABLE_PYSIDE6_PLUGIN).lower())")
SHOW_MEM=$(poetry run python3 -c "import build_config as c; print(str(c.SHOW_MEMORY).lower())")
OPT_LEVEL=$(poetry run python3 -c "import build_config as c; print(c.OPTIMIZATION_LEVEL)")
DISABLE_CONSOLE=$(poetry run python3 -c "import build_config as c; print(str(c.DISABLE_CONSOLE).lower())")

# Argumento CLI sobreescribe BUILD_MODE
if [[ "${1:-}" == "--onefile" ]];    then BUILD_MODE="onefile"; fi
if [[ "${1:-}" == "--standalone" ]]; then BUILD_MODE="standalone"; fi

# Nuitka nombra la carpeta según el script de entrada (main.py → main.dist)
ENTRY_BASENAME=$(basename "${ENTRY_POINT}" .py)
DIST_FOLDER="${ENTRY_BASENAME}.dist"
DIST_PATH="${OUTPUT_DIR}/${DIST_FOLDER}"

echo "    APP_NAME    : ${APP_NAME}"
echo "    VERSION     : ${APP_VERSION}"
echo "    ENTRY_POINT : ${ENTRY_POINT}"
echo "    OUTPUT_DIR  : ${OUTPUT_DIR}"
echo "    BUILD_MODE  : ${BUILD_MODE}"
echo ""

# ---------------------------------------------------------------------------
# Verificar Nuitka
# ---------------------------------------------------------------------------
echo "[2/5] Verificando Nuitka..."
if ! poetry run python3 -m nuitka --version &>/dev/null; then
    echo "ERROR: Nuitka no encontrado. Ejecutar: poetry add nuitka --group dev"
    exit 1
fi
echo "    OK"
echo ""

# ---------------------------------------------------------------------------
# Verificar dependencias del sistema
# ---------------------------------------------------------------------------
echo "[2b/5] Verificando dependencias del sistema..."

MISSING_DEPS=()
for dep in patchelf ccache; do
    if ! command -v "${dep}" &>/dev/null; then
        MISSING_DEPS+=("${dep}")
    fi
done

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    echo "ADVERTENCIA: Dependencias recomendadas no encontradas: ${MISSING_DEPS[*]}"
    echo "    Instalar con: sudo apt install ${MISSING_DEPS[*]}"
    echo "    La compilación continuará pero puede ser más lenta o producir advertencias."
fi
echo "    OK"
echo ""

# ---------------------------------------------------------------------------
# Preparar directorio de salida
# ---------------------------------------------------------------------------
echo "[3/5] Preparando directorio de salida: ${OUTPUT_DIR}/..."
mkdir -p "${OUTPUT_DIR}"

if [[ "${BUILD_MODE}" == "standalone" && -d "${DIST_PATH}" ]]; then
    echo "    Limpiando build anterior: ${DIST_PATH}/..."
    rm -rf "${DIST_PATH}"
fi
echo "    OK"
echo ""

# ---------------------------------------------------------------------------
# Construir flags de Nuitka
# ---------------------------------------------------------------------------
echo "[4/5] Construyendo comando Nuitka..."

NUITKA_FLAGS=(
    "--standalone"
    "--output-dir=${OUTPUT_DIR}"
    "--output-filename=${APP_NAME}"
)

# Modo onefile (binario único)
if [[ "${BUILD_MODE}" == "onefile" ]]; then
    NUITKA_FLAGS+=("--onefile")
fi

# Plugin PySide6 (obligatorio para Qt)
if [[ "${ENABLE_PYSIDE6}" == "true" ]]; then
    NUITKA_FLAGS+=("--enable-plugin=pyside6")
fi

# Estadísticas de memoria durante la compilación
if [[ "${SHOW_MEM}" == "true" ]]; then
    NUITKA_FLAGS+=("--show-memory")
fi

# Nivel de optimización
NUITKA_FLAGS+=("--python-flag=no_asserts")
if [[ "${OPT_LEVEL}" == "2" ]]; then
    NUITKA_FLAGS+=("--lto=yes")
else
    NUITKA_FLAGS+=("--lto=no")
fi

# En Linux la app es GUI pero no hay flag --windows-console-mode
# Usar --linux-onefile-icon si se dispone de un .png
ICON_PNG="src/infrastructure/ui/resources/icon.png"
if [[ "${BUILD_MODE}" == "onefile" && -f "${ICON_PNG}" ]]; then
    NUITKA_FLAGS+=("--linux-onefile-icon=${ICON_PNG}")
fi

# SQLAlchemy y pymysql tienen imports dinámicos que Nuitka no puede rastrear
# estáticamente. En standalone se excluyen y se copian en el post-build.
# En onefile se incluyen explícitamente para que queden dentro del binario.
if [[ "${BUILD_MODE}" == "onefile" ]]; then
    NUITKA_FLAGS+=(
        "--include-package=sqlalchemy"
        "--include-package=pymysql"
    )
else
    NUITKA_FLAGS+=(
        "--nofollow-import-to=sqlalchemy"
        "--nofollow-import-to=pymysql"
        "--no-deployment-flag=excluded-module-usage"
    )
fi

# Incluir archivos de recursos no-Python (Qt Designer .ui, assets)
NUITKA_FLAGS+=(
    "--include-data-files=src/infrastructure/ui/windows/main_window.ui=src/infrastructure/ui/windows/main_window.ui"
    "--include-data-dir=src/infrastructure/ui/assets=src/infrastructure/ui/assets"
)

# Paquetes con extensiones C/Rust (.so) que Nuitka no rastrea estáticamente
NUITKA_FLAGS+=(
    "--include-package=bcrypt"
    "--include-package=psutil"
    "--include-package=polars"
    "--include-package=dotenv"
)

# Metadatos del producto (nombre visible en /proc y ps)
NUITKA_FLAGS+=(
    "--product-name=${APP_NAME}"
    "--product-version=${APP_VERSION}"
)

echo "    Flags: ${NUITKA_FLAGS[*]}"
echo ""

# ---------------------------------------------------------------------------
# Compilar
# ---------------------------------------------------------------------------
echo "[5/5] Compilando con Nuitka..."
echo "      Esto puede tardar varios minutos. No interrumpir."
echo ""

START_TIME=$(date +%s)

poetry run python3 -m nuitka "${NUITKA_FLAGS[@]}" "${ENTRY_POINT}"

if [[ $? -ne 0 ]]; then
    echo ""
    echo "ERROR: La compilación falló. Revisar la salida anterior."
    exit 1
fi

END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))

# ---------------------------------------------------------------------------
# Post-build: copiar recursos (solo en modo standalone)
# ---------------------------------------------------------------------------
if [[ "${BUILD_MODE}" == "standalone" ]]; then
    echo ""
    echo "[Post-build] Copiando recursos a ${DIST_PATH}/..."

    # config/database.ini
    if [[ -f "config/database.ini" ]]; then
        mkdir -p "${DIST_PATH}/config"
        cp "config/database.ini" "${DIST_PATH}/config/database.ini"
        echo "    OK — config/database.ini copiado."
    else
        echo "ADVERTENCIA: config/database.ini no encontrado."
    fi

    # .env (variables de entorno opcionales)
    if [[ -f ".env" ]]; then
        cp ".env" "${DIST_PATH}/.env"
        echo "    OK — .env copiado."
    fi

    # Archivos .ui de Qt Designer (QUiLoader los carga en runtime)
    UI_SOURCE="src/infrastructure/ui/windows/main_window.ui"
    UI_DEST="${DIST_PATH}/src/infrastructure/ui/windows"
    if [[ -f "${UI_SOURCE}" ]]; then
        mkdir -p "${UI_DEST}"
        cp "${UI_SOURCE}" "${UI_DEST}/main_window.ui"
        echo "    OK — main_window.ui copiado."
    else
        echo "ADVERTENCIA: ${UI_SOURCE} no encontrado."
    fi

    # Assets (iconos, logo)
    ASSETS_SOURCE="src/infrastructure/ui/assets"
    if [[ -d "${ASSETS_SOURCE}" ]]; then
        cp -r "${ASSETS_SOURCE}" "${DIST_PATH}/src/infrastructure/ui/assets"
        echo "    OK — assets/ copiado."
    else
        echo "ADVERTENCIA: ${ASSETS_SOURCE} no encontrado, la app correrá sin ícono."
    fi

    # sqlalchemy y pymysql desde el venv
    VENV_SITEPACKAGES=$(poetry env info --path)/lib/python*/site-packages
    # Expandir el glob manualmente
    VENV_SITEPACKAGES_DIR=$(ls -d ${VENV_SITEPACKAGES} 2>/dev/null | head -1)

    if [[ -z "${VENV_SITEPACKAGES_DIR}" ]]; then
        echo "ERROR: No se encontró el directorio site-packages del venv."
        exit 1
    fi

    if [[ -d "${VENV_SITEPACKAGES_DIR}/sqlalchemy" ]]; then
        cp -r "${VENV_SITEPACKAGES_DIR}/sqlalchemy" "${DIST_PATH}/sqlalchemy"
        echo "    OK — sqlalchemy copiado desde venv."
    else
        echo "ERROR: sqlalchemy no encontrado en ${VENV_SITEPACKAGES_DIR}."
        exit 1
    fi

    if [[ -d "${VENV_SITEPACKAGES_DIR}/pymysql" ]]; then
        cp -r "${VENV_SITEPACKAGES_DIR}/pymysql" "${DIST_PATH}/pymysql"
        echo "    OK — pymysql copiado desde venv."
    else
        echo "ERROR: pymysql no encontrado en ${VENV_SITEPACKAGES_DIR}."
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Resumen final
# ---------------------------------------------------------------------------
echo ""
echo "============================================================================="
echo " Compilación exitosa"
echo " Modo    : ${BUILD_MODE}"
echo " Duración: ${ELAPSED}s"
if [[ "${BUILD_MODE}" == "onefile" ]]; then
    echo " Salida  : ${OUTPUT_DIR}/${APP_NAME}"
else
    echo " Salida  : ${DIST_PATH}/"
    echo " Nota    : distribuir toda la carpeta ${DIST_FOLDER}/, no solo el binario"
fi
echo "============================================================================="
echo ""
