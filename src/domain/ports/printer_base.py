"""Puerto de salida: contrato para adaptadores de impresora térmica.

Define la interfaz que los adaptadores de hardware deben implementar.
La implementación concreta (ESC/POS via pywin32) vive en
infrastructure/hardware/ y se desarrolla en el Epic 4.

El dominio solo conoce este Protocol; nunca importa pywin32 ni drivers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models.sale import Sale


@runtime_checkable
class PrinterBase(Protocol):
    """Puerto de salida para impresoras térmicas de tickets.

    Cualquier adaptador de impresora (ESC/POS, PDF, mock, etc.)
    debe implementar esta interfaz para ser inyectado en los casos de uso.

    Examples:
        >>> class MockPrinter:
        ...     def print_ticket(self, sale: Sale) -> None: ...
        >>> isinstance(MockPrinter(), PrinterBase)
        True
    """

    def print_ticket(self, sale: Sale) -> None:
        """Imprime el ticket de una venta.

        Args:
            sale: Venta completada cuyos datos se imprimen en el ticket.
        """
        ...
