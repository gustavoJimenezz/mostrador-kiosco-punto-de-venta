#!/usr/bin/env bash
# =============================================================================
#  test_deb.sh — Pipeline de validación del paquete .deb en Docker
#
#  Uso:
#    bash scripts/test_deb.sh [--ubuntu-version 22.04|24.04]
#
#  Prerequisito: haber generado el .deb con scripts/package_deb.sh
#
#  Qué hace:
#    1. Encuentra el .deb más reciente en dist/
#    2. Construye la imagen Docker de test (packaging/Dockerfile.test)
#    3. Ejecuta los smoke tests dentro del contenedor (scripts/smoke_test.sh)
#    4. Reporta el resultado
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

UBUNTU_VERSION="22.04"
if [[ "${1:-}" == "--ubuntu-version" ]]; then
    UBUNTU_VERSION="${2:-22.04}"
fi

IMAGE_TAG="kiosco-pos-test:ubuntu${UBUNTU_VERSION}"

# ---------------------------------------------------------------------------
# Localizar el .deb más reciente
# ---------------------------------------------------------------------------
echo "[1/3] Buscando paquete .deb en dist/..."
DEB_FILE=$(ls -t dist/kiosco-pos_*.deb 2>/dev/null | head -1 || true)

if [[ -z "${DEB_FILE}" ]]; then
    echo "ERROR: No se encontró ningún .deb en dist/."
    echo "       Ejecutar primero: bash scripts/package_deb.sh"
    exit 1
fi
echo "    Encontrado: ${DEB_FILE}"
echo ""

# ---------------------------------------------------------------------------
# Construir imagen Docker
# ---------------------------------------------------------------------------
echo "[2/3] Construyendo imagen Docker '${IMAGE_TAG}'..."
echo "      Ubuntu ${UBUNTU_VERSION} | $(date)"
echo ""

docker build \
    -f packaging/Dockerfile.test \
    --build-arg DEB_FILE="${DEB_FILE}" \
    --build-arg UBUNTU_VERSION="${UBUNTU_VERSION}" \
    -t "${IMAGE_TAG}" \
    --progress=plain \
    .

echo ""
echo "    Imagen construida: ${IMAGE_TAG}"
echo ""

# ---------------------------------------------------------------------------
# Ejecutar smoke tests
# ---------------------------------------------------------------------------
echo "[3/3] Ejecutando smoke tests en contenedor..."
echo ""

if docker run --rm "${IMAGE_TAG}"; then
    echo ""
    echo "============================================================"
    echo " RESULTADO: TODOS LOS TESTS PASARON en Ubuntu ${UBUNTU_VERSION}"
    echo "============================================================"
    exit 0
else
    echo ""
    echo "============================================================"
    echo " RESULTADO: FALLOS DETECTADOS en Ubuntu ${UBUNTU_VERSION}"
    echo " Revisar la salida anterior para diagnóstico."
    echo "============================================================"
    exit 1
fi
