"""Fábrica de adaptadores de hardware de impresión (cross-platform).

Provee ``get_printer_adapter()`` que selecciona el adaptador correcto
según la plataforma detectada en runtime via ``sys.platform``.

Los imports son lazy (dentro de cada branch) para que Nuitka no intente
compilar el módulo CUPS al compilar para Windows, evitando warnings de
módulos inalcanzables.
"""

from __future__ import annotations

import sys

from src.domain.ports.printer_base import PrinterBase


def get_printer_adapter() -> PrinterBase:
    """Retorna el adaptador de impresora adecuado para la plataforma actual.

    - ``win32``  → ``NullPrinterAdapter`` (adaptador real Windows en Epic 4).
    - ``linux``  → ``CupsPrinterAdapter`` (CUPS via comando ``lp``).
    - otros      → ``NullPrinterAdapter`` (macOS, etc.).

    Returns:
        Instancia que implementa ``PrinterBase``.

    Examples:
        >>> adapter = get_printer_adapter()
        >>> hasattr(adapter, "print_ticket")
        True
    """
    if sys.platform == "win32":
        from src.infrastructure.hardware.null_printer_adapter import NullPrinterAdapter
        return NullPrinterAdapter()
    elif sys.platform.startswith("linux"):
        from src.infrastructure.hardware.cups_printer_adapter import CupsPrinterAdapter
        return CupsPrinterAdapter()
    else:
        from src.infrastructure.hardware.null_printer_adapter import NullPrinterAdapter
        return NullPrinterAdapter()
