#!/usr/bin/env bash
# build_deb.sh — Genera el paquete .deb para Ubuntu 22.04 (kiosco Pentium E5700)
#
# Prerequisitos en la PC de build (Ubuntu 22.04):
#   sudo apt install python3-dev python3-venv build-essential dpkg-dev
#   curl -sSL https://install.python-poetry.org | python3 -
#   node >= 18 y npm (para el build del frontend React)
#
# Uso:
#   bash packaging/build_deb.sh
#   → genera dist/kiosco-pos_<version>_amd64.deb

set -euo pipefail

VERSION=$(grep '^version' pyproject.toml | head -1 | grep -oP '[\d.]+')
PKG_NAME="kiosco-pos"
ARCH="amd64"
DEB_NAME="${PKG_NAME}_${VERSION}_${ARCH}"
BUILD_DIR="/tmp/build_deb_${DEB_NAME}"
INSTALL_DIR="${BUILD_DIR}/usr/lib/kiosco-pos"

echo "=== Build .deb v${VERSION} ==="

# --- 1. Limpiar directorio de build anterior ---
rm -rf "${BUILD_DIR}"
mkdir -p "${INSTALL_DIR}"
mkdir -p "${BUILD_DIR}/etc/kiosco-pos"
mkdir -p "${BUILD_DIR}/lib/systemd/system"
mkdir -p "${BUILD_DIR}/etc/xdg/autostart"
mkdir -p "${BUILD_DIR}/usr/share/kiosco-pos"
mkdir -p "${BUILD_DIR}/DEBIAN"

# --- 2. Build del frontend React ---
echo "→ Build frontend React..."
cd frontend
npm install
npm ci --silent
npm run build
cd ..
echo "→ Frontend listo en frontend/dist/"

# --- 3. Instalar dependencias Python en venv ---
echo "→ Instalando dependencias Python..."
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install --quiet fastapi "uvicorn[standard]" python-multipart itsdangerous sqlalchemy alembic pymysql pydantic bcrypt polars cryptography python-dotenv psutil

# --- 4. Copiar código fuente ---
echo "→ Copiando código fuente..."
cp -r src "${INSTALL_DIR}/"
cp -r alembic "${INSTALL_DIR}/"
cp alembic.ini "${INSTALL_DIR}/"
cp web_main.py "${INSTALL_DIR}/"
cp pyproject.toml "${INSTALL_DIR}/"

# Copiar frontend compilado
mkdir -p "${INSTALL_DIR}/frontend"
cp -r frontend/dist "${INSTALL_DIR}/frontend/"

# Logo
cp src/infrastructure/ui/assets/logo.png "${BUILD_DIR}/usr/share/kiosco-pos/" 2>/dev/null || true

# --- 5. Archivos de configuración y servicio ---
cp packaging/config.env.example "${BUILD_DIR}/etc/kiosco-pos/config.env"
cp packaging/kiosco-pos.service "${BUILD_DIR}/lib/systemd/system/"
cp packaging/kiosco-chromium.desktop "${BUILD_DIR}/etc/xdg/autostart/"

# --- 6. Scripts DEBIAN ---
cat > "${BUILD_DIR}/DEBIAN/control" << EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: gustavoJimenezz
Depends: python3 (>= 3.12), sqlite3, libgl1, libglib2.0-0
Description: Sistema POS para kioscos (v2.0 — web)
 Sistema punto de venta offline-first basado en FastAPI + React.
 Opera localmente en localhost sin necesidad de internet.
EOF

cat > "${BUILD_DIR}/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

# Crear usuario kiosco si no existe
if ! id -u kiosco &>/dev/null; then
    useradd -r -m -s /bin/bash -d /home/kiosco kiosco
fi

# Ajustar permisos
chown -R kiosco:kiosco /usr/lib/kiosco-pos
chown -R kiosco:kiosco /etc/kiosco-pos

# Generar SECRET_KEY si el archivo es el template
if grep -q "cambiar-esta-clave" /etc/kiosco-pos/config.env 2>/dev/null; then
    NEW_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/cambiar-esta-clave-en-produccion/${NEW_KEY}/" /etc/kiosco-pos/config.env
fi

# Habilitar e iniciar el servicio
systemctl daemon-reload
systemctl enable kiosco-pos.service
systemctl start kiosco-pos.service

echo "Kiosco POS instalado. Accedé en http://localhost:8000"
EOF

cat > "${BUILD_DIR}/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e
systemctl stop kiosco-pos.service 2>/dev/null || true
systemctl disable kiosco-pos.service 2>/dev/null || true
EOF

chmod 755 "${BUILD_DIR}/DEBIAN/postinst" "${BUILD_DIR}/DEBIAN/prerm"

# --- 7. Calcular tamaño instalado ---
INSTALLED_SIZE=$(du -sk "${BUILD_DIR}" | cut -f1)
echo "Installed-Size: ${INSTALLED_SIZE}" >> "${BUILD_DIR}/DEBIAN/control"

# --- 8. Generar .deb ---
mkdir -p dist
dpkg-deb --build --root-owner-group "${BUILD_DIR}" "dist/${DEB_NAME}.deb"

echo ""
echo "=== ✓ Paquete generado: dist/${DEB_NAME}.deb ==="
echo "    Instalar en el kiosco: sudo dpkg -i dist/${DEB_NAME}.deb"
