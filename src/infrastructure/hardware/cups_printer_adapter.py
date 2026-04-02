"""Adaptador de impresora térmica para Linux usando CUPS.

Implementa el puerto ``PrinterBase`` enviando tickets formateados en texto
plano al demonio CUPS mediante el comando ``lp`` (sin dependencias externas).

Configuración via variables de entorno:
- ``CUPS_PRINTER``: Nombre de la impresora CUPS (ej: ``Ticketera``). Si no
  está definida, se autodetecta la primera impresora disponible con ``lpstat -e``.
- ``CUPS_LINE_WIDTH``: Ancho de línea del ticket en caracteres (default: 40).
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime
from decimal import Decimal

from src.domain.models.sale import Sale
from src.domain.ports.printer_base import PrinterBase

logger = logging.getLogger(__name__)

_DEFAULT_LINE_WIDTH = 40


class CupsPrinterAdapter:
    """Adaptador de impresora térmica para Linux via CUPS.

    Envía tickets formateados al demonio CUPS usando ``lp -d <printer> -``.
    No propaga excepciones al caller: todos los errores se registran en el log.

    Examples:
        >>> adapter = CupsPrinterAdapter()
        >>> isinstance(adapter, PrinterBase)
        True
    """

    def __init__(self) -> None:
        """Inicializa el adaptador resolviendo el nombre de impresora."""
        self._line_width: int = int(os.environ.get("CUPS_LINE_WIDTH", _DEFAULT_LINE_WIDTH))
        self._printer_name: str | None = self._resolve_printer_name()

    def _resolve_printer_name(self) -> str | None:
        """Resuelve el nombre de la impresora CUPS a usar.

        Primero lee la variable de entorno ``CUPS_PRINTER``. Si no está
        definida, consulta ``lpstat -e`` y usa la primera impresora disponible.

        Returns:
            Nombre de la impresora, o ``None`` si no hay ninguna disponible.
        """
        env_printer = os.environ.get("CUPS_PRINTER")
        if env_printer:
            return env_printer.strip()

        try:
            result = subprocess.run(
                ["lpstat", "-e"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.decode("utf-8").strip().splitlines()
                if lines:
                    return lines[0].strip()
        except FileNotFoundError:
            logger.warning(
                "cups_printer: comando 'lpstat' no encontrado. "
                "Instalar CUPS con: sudo apt install cups"
            )
        except subprocess.TimeoutExpired:
            logger.warning("cups_printer: timeout al consultar lpstat -e")
        except OSError as exc:
            logger.warning("cups_printer: error al consultar lpstat -e: %s", exc)

        logger.warning(
            "cups_printer: no se encontró ninguna impresora CUPS disponible. "
            "Definir la variable de entorno CUPS_PRINTER con el nombre de la impresora."
        )
        return None

    def _format_ticket(self, sale: Sale) -> bytes:
        """Formatea el ticket de venta como texto plano UTF-8.

        Args:
            sale: Venta completada cuyos datos se imprimen en el ticket.

        Returns:
            Bytes UTF-8 listos para enviar a ``lp`` via stdin.
        """
        w = self._line_width
        sep = "-" * w
        lines: list[str] = []

        # --- Cabecera ---
        lines.append("KIOSCO POS".center(w))
        lines.append(sep)
        lines.append(f"Fecha : {sale.timestamp.strftime('%d/%m/%Y %H:%M')}")
        lines.append(f"Venta : {str(sale.id)[:8].upper()}")
        lines.append(f"Pago  : {sale.payment_method.value}")
        lines.append(sep)

        # --- Detalle de ítems ---
        if sale.items:
            lines.append(f"{'Prod':<10} {'Cant':>4} {'P.Unit':>10} {'Subt':>10}")
            lines.append(sep)
            for item in sale.items:
                prod_id = f"#{item.product_id}"
                qty = str(item.quantity)
                unit = f"${item.price_at_sale:,.2f}"
                sub = f"${item.subtotal.amount:,.2f}"
                lines.append(f"{prod_id:<10} {qty:>4} {unit:>10} {sub:>10}")

        # --- Total ---
        lines.append(sep)
        total_str = f"$ {sale.total_amount.amount:,.2f}"
        lines.append(f"TOTAL: {total_str:>{w - 7}}")
        lines.append(sep)
        lines.append("")
        lines.append("¡Gracias por su compra!".center(w))
        lines.append("")
        # Avance de papel para corte
        lines.append("\n" * 3)

        return "\n".join(lines).encode("utf-8")

    def print_ticket(self, sale: Sale) -> None:
        """Imprime el ticket de una venta via CUPS.

        Formatea el ticket y lo envía a la impresora usando ``lp -d <printer> -``.
        Si la impresora no está disponible o ``lp`` falla, registra el error
        en el log sin propagar la excepción.

        Args:
            sale: Venta completada cuyos datos se imprimen en el ticket.
        """
        if self._printer_name is None:
            logger.error(
                "cups_printer: no hay impresora configurada. "
                "Ticket de venta %s no impreso.", sale.id
            )
            return

        ticket_bytes = self._format_ticket(sale)

        try:
            result = subprocess.run(
                ["lp", "-d", self._printer_name, "-"],
                input=ticket_bytes,
                capture_output=True,
                timeout=15,
            )
            if result.returncode != 0:
                logger.error(
                    "cups_printer: lp retornó código %d al imprimir venta %s. "
                    "Stderr: %s",
                    result.returncode,
                    sale.id,
                    result.stderr.decode("utf-8", errors="replace"),
                )
        except FileNotFoundError:
            logger.error(
                "cups_printer: comando 'lp' no encontrado. "
                "Instalar CUPS con: sudo apt install cups"
            )
        except subprocess.TimeoutExpired:
            logger.error(
                "cups_printer: timeout al enviar ticket de venta %s a CUPS.", sale.id
            )
        except OSError as exc:
            logger.error(
                "cups_printer: error de OS al imprimir venta %s: %s", sale.id, exc
            )
