"""Diálogo de vuelto para pago en efectivo (F12).

Presenta un display de cajero de pantalla grande con fondo oscuro donde el
cajero ingresa el monto recibido y ve el vuelto calculado en tiempo real.
Solo habilita la confirmación cuando el monto ingresado cubre el total.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.price import Price
from src.infrastructure.ui.theme import PALETTE


def _build_stylesheet() -> str:
    """Genera el QSS del diálogo de cobro usando la paleta centralizada del tema."""
    p = PALETTE
    return f"""
QWidget {{
    background-color: {p.surface};
    color: {p.text_primary};
    font-family: "Segoe UI", "Ubuntu", sans-serif;
}}
QLabel#lbl_header {{
    color: {p.text_secondary};
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 2px;
}}
QLabel#lbl_total {{
    color: {p.primary};
    font-size: 48px;
    font-weight: bold;
}}
QLabel#lbl_pays_label {{
    color: {p.text_secondary};
    font-size: 18px;
}}
QLabel#lbl_change {{
    color: {p.success};
    font-size: 44px;
    font-weight: bold;
}}
QLabel#lbl_change[insufficient="true"] {{
    color: {p.danger};
}}
QLineEdit#amount_input {{
    font-size: 32px;
    color: {p.text_primary};
    background-color: {p.surface_card};
    border: 2px solid {p.border};
    border-radius: 8px;
    padding: 8px 14px;
}}
QLineEdit#amount_input:focus {{
    border: 2px solid {p.border_focus};
}}
QPushButton#btn_confirm {{
    font-size: 18px;
    font-weight: bold;
    color: {p.text_on_primary};
    background-color: {p.success};
    border-radius: 8px;
    padding: 12px 28px;
    border: none;
}}
QPushButton#btn_confirm:hover {{
    background-color: {p.success_hover};
}}
QPushButton#btn_confirm:disabled {{
    background-color: #a7f3d0;
    color: {p.text_secondary};
}}
QPushButton#btn_cancel {{
    font-size: 16px;
    color: {p.btn_secondary_text};
    background-color: {p.btn_secondary_bg};
    border-radius: 8px;
    padding: 12px 28px;
    border: none;
}}
QPushButton#btn_cancel:hover {{
    background-color: {p.btn_secondary_hover};
}}
"""


class ChangeDialog(QDialog):
    """Diálogo modal de vuelto para pago en efectivo.

    Muestra el total de la venta, permite ingresar el monto entregado por
    el cliente y calcula el vuelto en tiempo real. La confirmación solo se
    habilita cuando el monto cubre el total.

    Args:
        total: Monto total de la venta.
        parent: Widget padre para centrar el diálogo (opcional).
        default_amount: Monto pre-cargado en el input (opcional). Si se omite,
            se pre-carga el total de la venta.
    """

    def __init__(
        self,
        total: Price,
        parent: QWidget | None = None,
        default_amount: Price | None = None,
    ) -> None:
        super().__init__(parent)
        self._total = total
        self._default_amount = default_amount

        self.setWindowTitle("Cobrar — Efectivo")
        self.setModal(True)
        self.setMinimumWidth(540)

        from src.infrastructure.ui.theme import setup_rounded_modal
        self._container = setup_rounded_modal(self)
        self._container.setStyleSheet(
            self._container.styleSheet() + _build_stylesheet()
        )

        self._build_ui()

        # Pre-cargar input con el total (o default_amount si se proveyó)
        fill_value = default_amount if default_amount is not None else total
        self._amount_input.setText(str(fill_value.amount))
        self._amount_input.selectAll()
        self._calculate_change(str(fill_value.amount))

        # Tamaño: 3/4 del padre
        if parent:
            ps = parent.size()
            self.resize(ps.width() * 3 // 4, ps.height() * 3 // 4)

        self._amount_input.setFocus()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @classmethod
    def show_and_confirm(
        cls,
        total: Price,
        parent: QWidget | None = None,
        default_amount: Price | None = None,
    ) -> bool:
        """Muestra el diálogo y retorna si el cajero confirmó el cobro.

        Args:
            total: Monto total de la venta a cobrar.
            parent: Widget padre para centrar el diálogo.
            default_amount: Monto pre-cargado en el input. Si se omite, se
                pre-carga el total de la venta.

        Returns:
            True si el cajero confirmó, False si canceló (Escape / botón).
        """
        dialog = cls(total, parent, default_amount=default_amount)
        return dialog.exec() == QDialog.Accepted

    # ------------------------------------------------------------------
    # Construcción de UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout programático del diálogo."""
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Encabezado
        lbl_header = QLabel("COBRO EN EFECTIVO")
        lbl_header.setObjectName("lbl_header")
        lbl_header.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_header)

        # Total
        self._lbl_total = QLabel(f"TOTAL: ${self._total.amount:,.2f}")
        self._lbl_total.setObjectName("lbl_total")
        self._lbl_total.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_total)

        layout.addSpacing(8)

        # Etiqueta "Paga con:"
        lbl_pays = QLabel("Paga con:")
        lbl_pays.setObjectName("lbl_pays_label")
        lbl_pays.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_pays)

        # Input de monto
        self._amount_input = QLineEdit()
        self._amount_input.setObjectName("amount_input")
        self._amount_input.setAlignment(Qt.AlignCenter)
        self._amount_input.setPlaceholderText("0,00")
        validator = QDoubleValidator(0.0, 9_999_999.99, 2, self)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self._amount_input.setValidator(validator)
        self._amount_input.textChanged.connect(self._calculate_change)
        layout.addWidget(self._amount_input)

        layout.addSpacing(8)

        # Vuelto
        self._lbl_change = QLabel("Vuelto: —")
        self._lbl_change.setObjectName("lbl_change")
        self._lbl_change.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_change)

        layout.addSpacing(16)

        # Botones
        btn_row = QHBoxLayout()
        self._btn_confirm = QPushButton("Confirmar  [Enter]")
        self._btn_confirm.setObjectName("btn_confirm")
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.setDefault(True)
        self._btn_confirm.clicked.connect(self.accept)

        btn_cancel = QPushButton("Cancelar  [Esc]")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_confirm)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Lógica de vuelto
    # ------------------------------------------------------------------

    def _calculate_change(self, text: str) -> None:
        """Calcula el vuelto en tiempo real al cambiar el monto ingresado.

        Habilita el botón de confirmar solo si el monto cubre el total.
        Acepta coma o punto como separador decimal.

        Args:
            text: Texto actual del campo de monto.
        """
        try:
            paid = Decimal(text.replace(",", "."))
            change = paid - self._total.amount
            if change >= 0:
                self._lbl_change.setText(f"Vuelto: ${change:,.2f}")
                self._lbl_change.setProperty("insufficient", "false")
                self._btn_confirm.setEnabled(True)
            else:
                self._lbl_change.setText("Monto insuficiente")
                self._lbl_change.setProperty("insufficient", "true")
                self._btn_confirm.setEnabled(False)
        except (InvalidOperation, ValueError):
            self._lbl_change.setText("Vuelto: —")
            self._lbl_change.setProperty("insufficient", "false")
            self._btn_confirm.setEnabled(False)
        # Refrescar QSS dinámico (propiedad cambiada)
        self._lbl_change.style().unpolish(self._lbl_change)
        self._lbl_change.style().polish(self._lbl_change)
