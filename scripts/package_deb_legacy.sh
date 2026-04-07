#!/usr/bin/env bash
# =============================================================================
#  package_deb_legacy.sh — Genera el paquete .deb legacy para Pentium E5700
#
#  Prerequisito: haber compilado el binario con build_linux_legacy.sh.
#  El paquete generado es compatible con Ubuntu 22.04 / GLIBC 2.35.
#
#  Uso:
#    ./scripts/package_deb_legacy.sh [--onefile | --standalone]
#
#  Modos:
#    --onefile    El binario es dist/POS (generado con --onefile en Nuitka).
#    --standalone El binario es dist/main.dist/POS. Default.
#
#  Salida:
#    dist/kiosco-pos-legacy_<VERSION>_amd64.deb
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Leer metadatos desde build_config.py
# ---------------------------------------------------------------------------
echo "[1/6] Leyendo configuración..."
APP_NAME=$(poetry run python3 -c "import build_config as c; print(c.APP_NAME)")
APP_VERSION=$(poetry run python3 -c "import build_config as c; print(c.APP_VERSION)")
OUTPUT_DIR=$(poetry run python3 -c "import build_config as c; print(c.OUTPUT_DIR)")

PACKAGE_NAME="kiosco-pos-legacy"
ARCH="amd64"
DEB_FILENAME="${PACKAGE_NAME}_${APP_VERSION}_${ARCH}.deb"
DEB_OUT="${OUTPUT_DIR}/${DEB_FILENAME}"

echo "    Paquete : ${DEB_FILENAME}"
echo "    Versión : ${APP_VERSION}"
echo ""

# ---------------------------------------------------------------------------
# Detectar modo de compilación (onefile vs standalone)
# ---------------------------------------------------------------------------
BUILD_MODE="${1:---standalone}"
if [[ "${BUILD_MODE}" == "--onefile" ]]; then
    BINARY_SRC="${OUTPUT_DIR}/${APP_NAME}"
else
    BINARY_SRC="${OUTPUT_DIR}/main.dist/${APP_NAME}"
fi

if [[ ! -f "${BINARY_SRC}" ]]; then
    echo "ERROR: Binario no encontrado en '${BINARY_SRC}'."
    echo "       Ejecutar primero: bash scripts/build_linux_legacy.sh ${BUILD_MODE}"
    exit 1
fi

echo "[2/6] Binario encontrado: ${BINARY_SRC} ($(du -sh "${BINARY_SRC}" | cut -f1))"
echo ""

# ---------------------------------------------------------------------------
# Preparar árbol del paquete en un directorio temporal
# ---------------------------------------------------------------------------
echo "[3/6] Preparando árbol del paquete..."
PKG_TREE=$(mktemp -d)
trap 'rm -rf "${PKG_TREE}"' EXIT

# Copiar estructura DEBIAN del paquete normal como base
cp -r packaging/deb/. "${PKG_TREE}/"

# Actualizar nombre, versión y descripción en el control file
sed -i "s/^Package: .*/Package: ${PACKAGE_NAME}/" "${PKG_TREE}/DEBIAN/control"
sed -i "s/^Version: .*/Version: ${APP_VERSION}/" "${PKG_TREE}/DEBIAN/control"
sed -i "s/^Description: .*/Description: Kiosco POS (legacy — compatible E5700\/Ubuntu 22.04)/" \
    "${PKG_TREE}/DEBIAN/control"

# Calcular tamaño instalado (en KB) y actualizar control file
INSTALLED_SIZE=$(du -sk "${BINARY_SRC}" | cut -f1)
sed -i "s/^Installed-Size: .*/Installed-Size: ${INSTALLED_SIZE}/" "${PKG_TREE}/DEBIAN/control"

# Crear directorios del árbol de instalación
install -d "${PKG_TREE}/usr/bin"
install -d "${PKG_TREE}/usr/lib/kiosco-pos"

# En modo standalone, copiar toda la carpeta dist
if [[ "${BUILD_MODE}" == "--standalone" ]]; then
    cp -r "${OUTPUT_DIR}/main.dist/." "${PKG_TREE}/usr/lib/kiosco-pos/"
    cat > "${PKG_TREE}/usr/bin/POS" <<'WRAPPER'
#!/bin/sh
exec /usr/lib/kiosco-pos/POS "$@"
WRAPPER
    chmod 755 "${PKG_TREE}/usr/bin/POS"
else
    install -m 755 "${BINARY_SRC}" "${PKG_TREE}/usr/lib/kiosco-pos/POS"
    if [[ -f "config/database.ini" ]]; then
        install -d "${PKG_TREE}/usr/lib/kiosco-pos/config"
        cp "config/database.ini" "${PKG_TREE}/usr/lib/kiosco-pos/config/database.ini"
    fi
    cat > "${PKG_TREE}/usr/bin/POS" <<'WRAPPER'
#!/bin/sh
export DATABASE_URL="mysql+pymysql://pos:pos_password@localhost:3306/kiosco_pos"
exec /usr/lib/kiosco-pos/POS "$@"
WRAPPER
    chmod 755 "${PKG_TREE}/usr/bin/POS"
fi

# Generar schema.sql desde las migraciones Alembic
install -d "${PKG_TREE}/usr/share/kiosco-pos"
if [[ -f "alembic.ini" ]]; then
    echo "    Generando schema.sql desde migraciones Alembic..."
    DATABASE_URL="mysql+pymysql://pos:pos_password@localhost:3306/kiosco_pos" \
        poetry run alembic upgrade --sql head > "${PKG_TREE}/usr/share/kiosco-pos/schema.sql" 2>/dev/null || {
        echo "ADVERTENCIA: No se pudo generar schema.sql. El postinst omitirá las migraciones."
        rm -f "${PKG_TREE}/usr/share/kiosco-pos/schema.sql"
    }
    echo "    OK"
fi

# Ícono (si existe)
ICON_PNG="src/infrastructure/ui/resources/icon.png"
if [[ -f "${ICON_PNG}" ]]; then
    install -d "${PKG_TREE}/usr/share/icons/hicolor/256x256/apps"
    install -m 644 "${ICON_PNG}" \
        "${PKG_TREE}/usr/share/icons/hicolor/256x256/apps/kiosco-pos.png"
fi

echo "    OK"
echo ""

# ---------------------------------------------------------------------------
# Permisos obligatorios para los scripts DEBIAN
# ---------------------------------------------------------------------------
echo "[4/6] Ajustando permisos de scripts DEBIAN..."
chmod 755 "${PKG_TREE}/DEBIAN/postinst"
chmod 755 "${PKG_TREE}/DEBIAN/prerm"
echo "    OK"
echo ""

# ---------------------------------------------------------------------------
# Construir el .deb
# ---------------------------------------------------------------------------
echo "[5/6] Construyendo paquete con dpkg-deb..."
mkdir -p "${OUTPUT_DIR}"
dpkg-deb --build --root-owner-group "${PKG_TREE}" "${DEB_OUT}"
echo "    OK"
echo ""

# ---------------------------------------------------------------------------
# Validar con lintian
# ---------------------------------------------------------------------------
echo "[6/6] Validando con lintian..."
if command -v lintian > /dev/null 2>&1; then
    lintian --no-tag-display-limit "${DEB_OUT}" || {
        echo "ADVERTENCIA: lintian reportó problemas. Revisar antes de distribuir."
    }
else
    echo "    lintian no instalado. Omitiendo validación."
    echo "    Instalar con: sudo apt install lintian"
fi
echo ""

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
echo "============================================================================="
echo " Paquete legacy generado exitosamente"
echo " Archivo : ${DEB_OUT}"
echo " Tamaño  : $(du -sh "${DEB_OUT}" | cut -f1)"
echo " Target  : Ubuntu 22.04 / Pentium E5700 / GLIBC 2.35"
echo ""
echo " Instalar en el kiosco:"
echo "   sudo dpkg -i ${DEB_OUT}"
echo "   sudo apt-get install -f   # si hay dependencias faltantes"
echo "============================================================================="
