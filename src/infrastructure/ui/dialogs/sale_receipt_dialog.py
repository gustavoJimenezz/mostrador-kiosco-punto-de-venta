"""Diálogo modal de comprobante de venta (ticket de caja).

Se muestra automáticamente tras confirmar el cobro en efectivo.
Presenta el detalle de la venta en formato de factura/ticket y
se cierra con Enter o Escape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.sale import Sale

if TYPE_CHECKING:
    from src.domain.models.product import Product

_DIALOG_QSS = """
QDialog {
    background-color: #111111;
}
QLabel#lbl_title {
    color: #ffffff;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 3px;
}
QLabel#lbl_subtitle {
    color: #888888;
    font-size: 13px;
    letter-spacing: 1px;
}
QLabel#lbl_meta {
    color: #aaaaaa;
    font-size: 13px;
}
QFrame#separator {
    color: #444444;
}
QTableWidget {
    background-color: #1a1a1a;
    color: #dddddd;
    font-size: 14px;
    border: none;
    gridline-color: #333333;
}
QTableWidget::item {
    padding: 6px 8px;
}
QHeaderView::section {
    background-color: #222222;
    color: #888888;
    font-size: 12px;
    font-weight: bold;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #444444;
}
QLabel#lbl_total_label {
    color: #888888;
    font-size: 18px;
}
QLabel#lbl_total_amount {
    color: #00FF00;
    font-size: 36px;
    font-weight: bold;
}
QLabel#lbl_payment {
    color: #aaaaaa;
    font-size: 14px;
}
QLabel#lbl_thanks {
    color: #555555;
    font-size: 13px;
    letter-spacing: 2px;
}
QPushButton#btn_close {
    font-size: 16px;
    font-weight: bold;
    color: #111111;
    background-color: #00CC00;
    border-radius: 6px;
    padding: 10px 48px;
}
"""


class SaleReceiptDialog(QDialog):
    """Diálogo modal de comprobante de venta estilo ticket de caja.

    Muestra el detalle completo de la venta (ítems, subtotales, total,
    método de pago) y se cierra con Enter o Escape.

    Args:
        sale: Venta confirmada con ítems y total.
        cart: Carrito al momento de la venta ``{product_id: (Product, qty)}``.
              Se usa para resolver los nombres de productos.
        parent: Widget padre para centrar el diálogo.
    """

    def __init__(
        self,
        sale: Sale,
        cart: dict[int, tuple[Product, int]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sale = sale
        self._cart = cart

        self.setWindowTitle("Comprobante de Venta")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(_DIALOG_QSS)

        self._build_ui()

        # Cerrar con Enter o Escape
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(self.accept)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self).activated.connect(self.accept)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.accept)

        if parent:
            ps = parent.size()
            self.resize(ps.width() * 3 // 4, ps.height() * 4 // 5)

        self._btn_close.setFocus()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @classmethod
    def show_receipt(
        cls,
        sale: Sale,
        cart: dict[int, tuple[Product, int]],
        parent: QWidget | None = None,
    ) -> None:
        """Muestra el comprobante de venta de forma modal.

        Args:
            sale: Venta confirmada.
            cart: Carrito al momento del cobro (para resolver nombres).
            parent: Widget padre.
        """
        dialog = cls(sale, cart, parent)
        dialog.exec()

    # ------------------------------------------------------------------
    # Construcción de UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout del comprobante."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # Encabezado
        lbl_title = QLabel("COMPROBANTE DE VENTA")
        lbl_title.setObjectName("lbl_title")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_subtitle = QLabel("MOSTRADOR KIOSCO — PUNTO DE VENTA")
        lbl_subtitle.setObjectName("lbl_subtitle")
        lbl_subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_subtitle)

        layout.addWidget(self._make_separator())

        # Metadata: número de venta y fecha/hora
        sale_id_short = str(self._sale.id)[:8].upper()
        meta_row = QHBoxLayout()
        lbl_id = QLabel(f"Nro: #{sale_id_short}")
        lbl_id.setObjectName("lbl_meta")
        lbl_date = QLabel(self._sale.timestamp.strftime("%d/%m/%Y  %H:%M:%S"))
        lbl_date.setObjectName("lbl_meta")
        lbl_date.setAlignment(Qt.AlignRight)
        meta_row.addWidget(lbl_id)
        meta_row.addStretch()
        meta_row.addWidget(lbl_date)
        layout.addLayout(meta_row)

        layout.addWidget(self._make_separator())

        # Tabla de ítems
        table = self._build_items_table()
        layout.addWidget(table)

        layout.addWidget(self._make_separator())

        # Total
        total_row = QHBoxLayout()
        lbl_total_label = QLabel("TOTAL")
        lbl_total_label.setObjectName("lbl_total_label")
        lbl_total_amount = QLabel(f"${self._sale.total_amount.amount:,.2f}")
        lbl_total_amount.setObjectName("lbl_total_amount")
        lbl_total_amount.setAlignment(Qt.AlignRight)
        total_row.addWidget(lbl_total_label, alignment=Qt.AlignVCenter)
        total_row.addStretch()
        total_row.addWidget(lbl_total_amount, alignment=Qt.AlignVCenter)
        layout.addLayout(total_row)

        # Método de pago
        lbl_payment = QLabel(f"Método de pago: {self._sale.payment_method.value}")
        lbl_payment.setObjectName("lbl_payment")
        lbl_payment.setAlignment(Qt.AlignRight)
        layout.addWidget(lbl_payment)

        layout.addWidget(self._make_separator())

        # Pie de página
        lbl_thanks = QLabel("¡GRACIAS POR SU COMPRA!")
        lbl_thanks.setObjectName("lbl_thanks")
        lbl_thanks.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_thanks)

        layout.addSpacing(8)

        # Botón cerrar
        self._btn_close = QPushButton("Cerrar  [Enter]")
        self._btn_close.setObjectName("btn_close")
        self._btn_close.setDefault(True)
        self._btn_close.clicked.connect(self.accept)
        layout.addWidget(self._btn_close, alignment=Qt.AlignCenter)

    def _build_items_table(self) -> QTableWidget:
        """Construye la tabla de ítems de la venta.

        Returns:
            QTableWidget configurado con los ítems de la venta.
        """
        headers = ["Cant.", "Descripción", "P. Unit.", "Subtotal"]
        table = QTableWidget(len(self._sale.items), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.horizontalHeader().setStretchLastSection(True)

        # Anchos de columna: Cant. | Descripción | P.Unit | Subtotal
        table.setColumnWidth(0, 60)
        table.setColumnWidth(1, 240)
        table.setColumnWidth(2, 100)

        for row, item in enumerate(self._sale.items):
            product_name = self._resolve_name(item.product_id)
            subtotal = item.subtotal

            qty_cell = QTableWidgetItem(str(item.quantity))
            qty_cell.setTextAlignment(Qt.AlignCenter)

            name_cell = QTableWidgetItem(product_name)

            price_cell = QTableWidgetItem(f"${item.price_at_sale:,.2f}")
            price_cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            subtotal_cell = QTableWidgetItem(f"${subtotal.amount:,.2f}")
            subtotal_cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            font = QFont()
            font.setBold(True)
            subtotal_cell.setFont(font)

            table.setItem(row, 0, qty_cell)
            table.setItem(row, 1, name_cell)
            table.setItem(row, 2, price_cell)
            table.setItem(row, 3, subtotal_cell)

        table.resizeRowsToContents()
        return table

    def _resolve_name(self, product_id: int) -> str:
        """Resuelve el nombre del producto desde el carrito.

        Args:
            product_id: ID del producto a buscar.

        Returns:
            Nombre del producto, o '(producto #ID)' si no se encontró.
        """
        if product_id in self._cart:
            product, _ = self._cart[product_id]
            return product.name
        return f"(producto #{product_id})"

    def _make_separator(self) -> QFrame:
        """Crea una línea horizontal separadora.

        Returns:
            QFrame configurado como separador horizontal.
        """
        line = QFrame()
        line.setObjectName("separator")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line
