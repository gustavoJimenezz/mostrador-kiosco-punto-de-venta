"""Adaptador de impresora nulo (no-op) para desarrollo y fallback.

Útil en entornos sin impresora física (desarrollo en Linux/Windows antes del
Epic 4) y como fallback en plataformas no soportadas.
"""

from __future__ import annotations

from src.domain.models.sale import Sale
from src.domain.ports.printer_base import PrinterBase


class NullPrinterAdapter:
    """Adaptador de impresora nulo: registra en stdout y no hace nada más.

    Implementa ``PrinterBase`` para poder ser inyectado en cualquier caso de uso
    que requiera un adaptador de impresora, sin hardware real.

    Examples:
        >>> adapter = NullPrinterAdapter()
        >>> isinstance(adapter, PrinterBase)
        True
    """

    def print_ticket(self, sale: Sale) -> None:
        """Simula la impresión de un ticket mostrando info en stdout.

        Args:
            sale: Venta completada (solo se usa su id y total para el log).
        """
        print(  # noqa: T201
            f"[NullPrinter] Ticket venta {sale.id} | "
            f"Total: {sale.total_amount} | "
            f"Pago: {sale.payment_method.value}"
        )
