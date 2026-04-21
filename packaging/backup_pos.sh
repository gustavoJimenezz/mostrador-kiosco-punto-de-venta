#!/bin/bash
# backup_pos.sh — Genera un backup completo del kiosco POS instalado.
#
# Respalda:
#   - /var/lib/kiosco-pos/   → base de datos SQLite (productos, ventas, historial)
#   - /etc/kiosco-pos/       → configuración (DATABASE_URL, SECRET_KEY)
#
# El archivo resultante se guarda en el home del usuario con fecha y hora.
#
# Uso:
#   bash packaging/backup_pos.sh
#
# Restaurar:
#   sudo systemctl stop kiosco-pos.service
#   sudo tar -xzf ~/backup_pos_YYYYMMDD_HHMMSS.tar.gz -C /
#   sudo systemctl start kiosco-pos.service

set -euo pipefail

FECHA=$(date +%Y%m%d_%H%M%S)
DESTINO="$HOME/backup_pos_${FECHA}.tar.gz"

echo "=== Backup POS — ${FECHA} ==="

sudo tar -czf "${DESTINO}" \
    /var/lib/kiosco-pos/ \
    /etc/kiosco-pos/ \
    2>/dev/null

sudo chown "$USER":"$USER" "${DESTINO}"

echo "✓ Backup guardado en: ${DESTINO}"
echo "  Tamaño: $(du -sh "${DESTINO}" | cut -f1)"
echo ""
echo "  Para verificar el contenido:"
echo "    tar -tzf ${DESTINO}"
