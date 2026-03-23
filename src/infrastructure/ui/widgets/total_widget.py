"""Widget de total de venta con escalado dinámico de fuente.

Subclase de QLabel que reduce automáticamente el tamaño de la fuente
cuando el texto (monto total) no entra en el ancho disponible. Diseñado
para reemplazar el ``total_label`` fijo del .ui en la ventana principal.
"""

from __future__ import annotations

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel

from src.domain.models.price import Price


class TotalWidget(QLabel):
    """QLabel con font scaling dinámico para montos de venta grandes.

    Mantiene el tamaño de fuente base (52pt) y lo reduce en pasos de 2pt
    hasta que el texto entre en el ancho disponible, con un mínimo de 24pt.
    El reescalado ocurre también al redimensionar la ventana.

    Ejemplo de uso::

        widget = TotalWidget()
        widget.set_total(Price("1234567.89"))
    """

    _BASE_FONT_SIZE = 52
    _MIN_FONT_SIZE = 24

    def set_total(self, total: Price) -> None:
        """Actualiza el texto del total y ajusta el tamaño de fuente.

        Args:
            total: Precio total a mostrar.
        """
        self.setText(f"TOTAL: ${total.amount:,.2f}")
        self._adjust_font_size()

    def resizeEvent(self, event) -> None:
        """Reajusta la fuente cuando cambia el tamaño del widget.

        Args:
            event: Evento de redimensionado Qt.
        """
        super().resizeEvent(event)
        self._adjust_font_size()

    def _adjust_font_size(self) -> None:
        """Reduce el font-size hasta que el texto entre en el ancho disponible.

        Itera desde ``_BASE_FONT_SIZE`` hacia abajo en pasos de 2pt hasta
        ``_MIN_FONT_SIZE``. Aplica el primer tamaño donde el texto cabe.
        Si el widget aún no tiene ancho asignado (width == 0), no actúa.
        """
        if self.width() == 0 or not self.text():
            return

        font = self.font()
        for size in range(self._BASE_FONT_SIZE, self._MIN_FONT_SIZE - 1, -2):
            font.setPointSize(size)
            metrics = QFontMetrics(font)
            if metrics.horizontalAdvance(self.text()) <= self.width() - 48:
                break
        self.setFont(font)
