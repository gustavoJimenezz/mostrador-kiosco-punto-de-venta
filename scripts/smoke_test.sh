#!/usr/bin/env bash
# =============================================================================
#  smoke_test.sh — Verificaciones post-instalación dentro del contenedor Docker
#
#  Se ejecuta como CMD del Dockerfile.test.
#  Retorna código 0 si todo pasa, != 0 si alguna verificación falla.
# =============================================================================

set -euo pipefail

PASS=0
FAIL=0

ok()   { echo "  [OK]  $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "============================================================"
echo " Smoke Test — Kiosco POS"
echo "============================================================"

# ---------------------------------------------------------------------------
# 1. Binario instalado en /usr/bin/POS
# ---------------------------------------------------------------------------
echo ""
echo "[1] Verificando binario..."
if [ -f "/usr/bin/POS" ] && [ -x "/usr/bin/POS" ]; then
    ok "/usr/bin/POS existe y es ejecutable"
else
    fail "/usr/bin/POS no encontrado o no es ejecutable"
fi

# ---------------------------------------------------------------------------
# 2. Archivo de configuración creado por postinst
# ---------------------------------------------------------------------------
echo ""
echo "[2] Verificando archivo de configuración..."
if [ -f "/etc/pos/config.ini" ]; then
    ok "/etc/pos/config.ini existe"
else
    fail "/etc/pos/config.ini no encontrado (falló postinst)"
fi

# ---------------------------------------------------------------------------
# 3. MariaDB activa y accesible
# ---------------------------------------------------------------------------
echo ""
echo "[3] Verificando MariaDB..."
# En Docker iniciamos mysqld_safe en background; comprobamos con mysqladmin
if mysqladmin -u root ping --silent 2>/dev/null; then
    ok "MariaDB responde a ping"
else
    # Intentar arrancar para el smoke test
    mysqld_safe --skip-networking=0 &
    sleep 5
    if mysqladmin -u root ping --silent 2>/dev/null; then
        ok "MariaDB responde a ping (iniciada manualmente)"
    else
        fail "MariaDB no responde — verificar instalación"
    fi
fi

# ---------------------------------------------------------------------------
# 4. Base de datos kiosco_pos existe
# ---------------------------------------------------------------------------
echo ""
echo "[4] Verificando base de datos..."
if mysql -u root -e "USE kiosco_pos;" 2>/dev/null; then
    ok "Base de datos 'kiosco_pos' existe"
else
    fail "Base de datos 'kiosco_pos' no encontrada (falló postinst)"
fi

# ---------------------------------------------------------------------------
# 5. SELECT 1 — conectividad básica con el usuario de la app
# ---------------------------------------------------------------------------
echo ""
echo "[5] Verificando conectividad con usuario 'pos'..."
RESULT=$(mysql -u pos -ppos_password kiosco_pos -sNe "SELECT 1;" 2>/dev/null || echo "ERROR")
if [ "${RESULT}" = "1" ]; then
    ok "Conexión con usuario 'pos' exitosa (SELECT 1 = 1)"
else
    fail "No se pudo conectar con usuario 'pos' a kiosco_pos"
fi

# ---------------------------------------------------------------------------
# 6. Entrada en el menú de escritorio
# ---------------------------------------------------------------------------
echo ""
echo "[6] Verificando entrada de escritorio..."
if [ -f "/usr/share/applications/pos.desktop" ]; then
    ok "/usr/share/applications/pos.desktop existe"
else
    fail "/usr/share/applications/pos.desktop no encontrado"
fi

# ---------------------------------------------------------------------------
# 7. Arranque de la UI con Xvfb (verifica que no hay segfault)
# ---------------------------------------------------------------------------
echo ""
echo "[7] Verificando arranque de la UI con Xvfb..."
if command -v xvfb-run > /dev/null 2>&1; then
    # Timeout de 5 segundos: la app abrirá la ventana de login y la matamos.
    # Si sale con señal de segfault (código 139) → falla.
    DATABASE_URL="mysql+pymysql://pos:pos_password@localhost:3306/kiosco_pos" \
        timeout 5 xvfb-run --auto-servernum /usr/bin/POS 2>/dev/null || EXIT_CODE=$?
    # timeout retorna 124 al expirar (normal), 139 = segfault
    if [ "${EXIT_CODE:-0}" -eq 139 ]; then
        fail "La app terminó con segfault (código 139)"
    else
        ok "La app arrancó sin segfault (código de salida: ${EXIT_CODE:-0})"
    fi
else
    echo "  [SKIP] xvfb-run no disponible — omitiendo test de UI"
fi

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " Resultados: ${PASS} OK  |  ${FAIL} FAIL"
echo "============================================================"
echo ""

if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi
exit 0
