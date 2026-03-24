"""Diálogo para ingresar el monto inicial al abrir la caja."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class OpenCashDialog(QDialog):
    """Solicita el monto inicial de caja antes de abrir la sesión.

    Args:
        parent: Widget padre (tipicamente MainWindow).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Abrir caja")
        self.setMinimumWidth(320)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout del diálogo."""
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(16)

        title = QLabel("Ingresá el monto inicial de caja")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        root.addWidget(title)

        row = QHBoxLayout()
        lbl = QLabel("Monto inicial ($):")
        lbl.setStyleSheet("color: #ffffff; font-size: 13px;")
        row.addWidget(lbl)

        self._spin = QDoubleSpinBox()
        self._spin.setRange(0, 999999.99)
        self._spin.setDecimals(2)
        self._spin.setSingleStep(100)
        self._spin.setStyleSheet(
            "font-size: 13px; padding: 4px; color: #1e293b;"
            "border: 1px solid #d1d5db; border-radius: 6px; background: white;"
        )
        row.addWidget(self._spin)
        root.addLayout(row)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            "QPushButton { padding: 8px 18px; border-radius: 6px;"
            "background: #e2e8f0; color: #334155; font-size: 13px; border: none; }"
            "QPushButton:hover { background: #cbd5e1; }"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton("Confirmar")
        btn_confirm.setDefault(True)
        btn_confirm.setStyleSheet(
            "QPushButton { padding: 8px 18px; border-radius: 6px;"
            "background: #4f46e5; color: white; font-size: 13px;"
            "font-weight: bold; border: none; }"
            "QPushButton:hover { background: #4338ca; }"
        )
        btn_confirm.clicked.connect(self.accept)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_confirm)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Interfaz pública
    # ------------------------------------------------------------------

    def opening_amount(self) -> Decimal:
        """Retorna el monto ingresado en el spinbox.

        Returns:
            Monto inicial de caja como Decimal.
        """
        return Decimal(str(self._spin.value()))
