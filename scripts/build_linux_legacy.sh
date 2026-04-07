#!/usr/bin/env bash
# =============================================================================
#  build_linux_legacy.sh — Build legacy para Pentium E5700 / Ubuntu 22.04
#
#  Problema: PySide6 de pip usa instrucciones SSE4.2 que el E5700 no soporta,
#  causando crash SIGILL. PyQt5 5.15.x usa wheels manylinux2014 sin SSE4.2
#  y fue validado en el hardware objetivo.
#
#  Estrategia: build-time source transformation.
#  El código fuente en src/ NUNCA se modifica. Este script:
#    1. Copia src/ a /tmp/build_legacy/
#    2. Aplica reemplazos sed SOLO sobre src/infrastructure/ui/ en la copia
#    3. Compila desde la copia con Nuitka + PyQt5
#
#  Uso:
#    bash scripts/build_linux_legacy.sh              → standalone (default)
#    bash scripts/build_linux_legacy.sh --onefile    → binario único
#    bash scripts/build_linux_legacy.sh --standalone → carpeta dist/
#    bash scripts/build_linux_legacy.sh --dry-run    → solo transforma, no compila
#    bash scripts/build_linux_legacy.sh --help       → muestra esta ayuda
#
#  Prerequisito: poetry install --with legacy
#
#  Salida:
#    standalone: dist/main.dist/POS
#    onefile:    dist/POS
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

BUILD_TEMP="/tmp/build_legacy"

# ---------------------------------------------------------------------------
# Ayuda
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--help" ]]; then
    echo "Uso: $0 [--onefile | --standalone | --dry-run]"
    echo ""
    echo "  --onefile     Genera un binario ELF único."
    echo "  --standalone  Genera carpeta dist/. Recomendado para HDD/CPUs viejas. (default)"
    echo "  --dry-run     Solo aplica la transformación sed, no compila."
    echo "                Útil para verificar que los reemplazos son correctos."
    echo "                Los archivos transformados quedan en ${BUILD_TEMP}/"
    echo ""
    echo "  Prerequisito: poetry install --with legacy"
    exit 0
fi

# ---------------------------------------------------------------------------
# Leer configuración desde build_config.py
# ---------------------------------------------------------------------------
echo "[1/6] Leyendo configuración desde build_config.py..."

APP_NAME=$(poetry run python3 -c "import build_config as c; print(c.APP_NAME)")
APP_VERSION=$(poetry run python3 -c "import build_config as c; print(c.APP_VERSION)")
ENTRY_POINT=$(poetry run python3 -c "import build_config as c; print(c.ENTRY_POINT)")
OUTPUT_DIR=$(poetry run python3 -c "import build_config as c; print(c.OUTPUT_DIR)")
BUILD_MODE=$(poetry run python3 -c "import build_config as c; print(c.BUILD_MODE)")
SHOW_MEM=$(poetry run python3 -c "import build_config as c; print(str(c.SHOW_MEMORY).lower())")
OPT_LEVEL=$(poetry run python3 -c "import build_config as c; print(c.OPTIMIZATION_LEVEL)")

# Argumento CLI sobreescribe BUILD_MODE
if [[ "${1:-}" == "--onefile" ]];    then BUILD_MODE="onefile"; fi
if [[ "${1:-}" == "--standalone" ]]; then BUILD_MODE="standalone"; fi
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]];    then DRY_RUN=true; fi

ENTRY_BASENAME=$(basename "${ENTRY_POINT}" .py)
DIST_FOLDER="${ENTRY_BASENAME}.dist"
DIST_PATH="${OUTPUT_DIR}/${DIST_FOLDER}"

# Punto de entrada en la copia temporal
LEGACY_ENTRY="${BUILD_TEMP}/${ENTRY_POINT}"

echo "    APP_NAME    : ${APP_NAME}"
echo "    VERSION     : ${APP_VERSION}"
echo "    ENTRY_POINT : ${LEGACY_ENTRY}"
echo "    OUTPUT_DIR  : ${OUTPUT_DIR}"
echo "    BUILD_MODE  : ${BUILD_MODE}"
echo "    DRY_RUN     : ${DRY_RUN}"
echo ""

# ---------------------------------------------------------------------------
# Verificar PyQt5
# ---------------------------------------------------------------------------
echo "[2/6] Verificando PyQt5..."
if ! poetry run python3 -c "from PyQt5.QtWidgets import QApplication" &>/dev/null; then
    echo "ERROR: PyQt5 no encontrado en el entorno."
    echo "       Ejecutar: poetry install --with legacy"
    exit 1
fi
echo "    OK"
echo ""

# ---------------------------------------------------------------------------
# Verificar Nuitka (solo si no es dry-run)
# ---------------------------------------------------------------------------
if [[ "${DRY_RUN}" == "false" ]]; then
    echo "[2b/6] Verificando Nuitka..."
    if ! poetry run python3 -m nuitka --version &>/dev/null; then
        echo "ERROR: Nuitka no encontrado. Ejecutar: poetry add nuitka --group dev"
        exit 1
    fi
    echo "    OK"
    echo ""
fi

# ---------------------------------------------------------------------------
# Preparar directorio temporal — limpiar build anterior
# ---------------------------------------------------------------------------
echo "[3/6] Preparando directorio temporal: ${BUILD_TEMP}/..."
rm -rf "${BUILD_TEMP}"
mkdir -p "${BUILD_TEMP}"

# Garantizar limpieza al salir (solo si no es dry-run, en dry-run dejamos la copia)
if [[ "${DRY_RUN}" == "false" ]]; then
    trap 'echo ""; echo "[Limpieza] Eliminando ${BUILD_TEMP}/..."; rm -rf "${BUILD_TEMP}"' EXIT
fi

# Copiar src/ y archivos necesarios para la compilación
cp -r src/                "${BUILD_TEMP}/src/"
cp -r build_config.py     "${BUILD_TEMP}/build_config.py" 2>/dev/null || true
cp -r main.py             "${BUILD_TEMP}/main.py"         2>/dev/null || true

echo "    OK — src/ copiado a ${BUILD_TEMP}/"
echo ""

# ---------------------------------------------------------------------------
# Transformar imports PySide6 → PyQt5 (SOLO en infrastructure/ui/)
# ---------------------------------------------------------------------------
UI_TARGET="${BUILD_TEMP}/src/infrastructure/ui"

echo "[4/6] Aplicando transformación PySide6 → PyQt5 en ${UI_TARGET}/..."

if [[ ! -d "${UI_TARGET}" ]]; then
    echo "ADVERTENCIA: El directorio ${UI_TARGET} no existe en la copia."
    echo "             No se aplicaron transformaciones."
else
    # Contar archivos .py antes de transformar
    PY_FILES=$(find "${UI_TARGET}" -name "*.py" | wc -l)
    echo "    Archivos .py encontrados: ${PY_FILES}"
    echo ""

    # Reemplazar imports de módulos PySide6
    find "${UI_TARGET}" -name "*.py" -exec \
        sed -i 's/from PySide6\./from PyQt5./g' {} +

    # Signal y Slot con word boundary (\b) para evitar falsos positivos
    # Ejemplo: "SignalName" o "SlotMachine" no deben ser afectados
    find "${UI_TARGET}" -name "*.py" -exec \
        sed -i 's/\bSignal\b/pyqtSignal/g' {} +
    find "${UI_TARGET}" -name "*.py" -exec \
        sed -i 's/\bSlot\b/pyqtSlot/g' {} +

    echo "    Transformaciones aplicadas:"
    echo "      from PySide6.QtXxx  →  from PyQt5.QtXxx"
    echo "      Signal              →  pyqtSignal"
    echo "      Slot                →  pyqtSlot"
    echo ""

    # Verificar que no quedan referencias a PySide6 en ui/
    REMAINING=$(grep -r "PySide6" "${UI_TARGET}" --include="*.py" -l 2>/dev/null || true)
    if [[ -n "${REMAINING}" ]]; then
        echo "ADVERTENCIA: Aún quedan referencias a PySide6 en los siguientes archivos:"
        echo "${REMAINING}"
        echo "             Revisar manualmente antes de distribuir."
    else
        echo "    OK — No quedan referencias a PySide6 en infrastructure/ui/"
    fi
fi

echo ""

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "============================================================================="
    echo " Dry-run completado. Archivos transformados en: ${BUILD_TEMP}/"
    echo " Revisar con: grep -r 'PyQt5' ${UI_TARGET} --include='*.py' | head -20"
    echo "============================================================================="
    exit 0
fi

# ---------------------------------------------------------------------------
# Preparar directorio de salida
# ---------------------------------------------------------------------------
echo "[5/6] Preparando directorio de salida: ${OUTPUT_DIR}/..."
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
echo "[6/6] Compilando con Nuitka + PyQt5..."
echo "      Esto puede tardar varios minutos. No interrumpir."
echo ""

NUITKA_FLAGS=(
    "--standalone"
    "--output-dir=${OUTPUT_DIR}"
    "--output-filename=${APP_NAME}"
    "--enable-plugin=pyqt5"
)

if [[ "${BUILD_MODE}" == "onefile" ]]; then
    NUITKA_FLAGS+=("--onefile")
fi

if [[ "${SHOW_MEM}" == "true" ]]; then
    NUITKA_FLAGS+=("--show-memory")
fi

NUITKA_FLAGS+=("--python-flag=no_asserts")
if [[ "${OPT_LEVEL}" == "2" ]]; then
    NUITKA_FLAGS+=("--lto=yes")
else
    NUITKA_FLAGS+=("--lto=no")
fi

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

NUITKA_FLAGS+=(
    "--include-package=bcrypt"
    "--include-package=psutil"
    "--include-package=polars"
    "--include-package=dotenv"
    "--product-name=${APP_NAME}"
    "--product-version=${APP_VERSION}"
)

# Incluir archivos de recursos .ui y assets desde la copia temporal
NUITKA_FLAGS+=(
    "--include-data-files=${BUILD_TEMP}/src/infrastructure/ui/windows/main_window.ui=src/infrastructure/ui/windows/main_window.ui"
    "--include-data-dir=${BUILD_TEMP}/src/infrastructure/ui/assets=src/infrastructure/ui/assets"
)

echo "    Flags: ${NUITKA_FLAGS[*]}"
echo ""

START_TIME=$(date +%s)

# Compilar desde el directorio temporal para que los imports relativos funcionen
cd "${BUILD_TEMP}"
QT_API=pyqt5 poetry --directory="${PROJECT_ROOT}" run python3 -m nuitka \
    "${NUITKA_FLAGS[@]}" "${LEGACY_ENTRY}"

cd "${PROJECT_ROOT}"

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

    if [[ -f "${PROJECT_ROOT}/config/database.ini" ]]; then
        mkdir -p "${DIST_PATH}/config"
        cp "${PROJECT_ROOT}/config/database.ini" "${DIST_PATH}/config/database.ini"
        echo "    OK — config/database.ini copiado."
    else
        echo "ADVERTENCIA: config/database.ini no encontrado."
    fi

    if [[ -f "${PROJECT_ROOT}/.env" ]]; then
        cp "${PROJECT_ROOT}/.env" "${DIST_PATH}/.env"
        echo "    OK — .env copiado."
    fi

    VENV_SITEPACKAGES=$(poetry env info --path)/lib/python*/site-packages
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
# Resumen
# ---------------------------------------------------------------------------
echo ""
echo "============================================================================="
echo " Build legacy completado (PyQt5 — compatible con E5700)"
echo " Modo    : ${BUILD_MODE}"
echo " Duración: ${ELAPSED}s"
if [[ "${BUILD_MODE}" == "onefile" ]]; then
    echo " Salida  : ${OUTPUT_DIR}/${APP_NAME}"
else
    echo " Salida  : ${DIST_PATH}/"
    echo " Nota    : distribuir toda la carpeta ${DIST_FOLDER}/, no solo el binario"
fi
echo ""
echo " Siguiente paso: bash scripts/package_deb_legacy.sh ${1:-}"
echo "============================================================================="
echo ""
