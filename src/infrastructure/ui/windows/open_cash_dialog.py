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
        from src.infrastructure.ui.theme import get_dialog_stylesheet
        self.setStyleSheet(get_dialog_stylesheet())
        self._build_ui()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout del diálogo."""
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(16)

        from src.infrastructure.ui.theme import (
            TEXT_PRIMARY_COLOR,
            get_btn_primary_stylesheet,
            get_btn_secondary_stylesheet,
        )

        title = QLabel("Ingresá el monto inicial de caja")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_PRIMARY_COLOR};")
        root.addWidget(title)

        row = QHBoxLayout()
        lbl = QLabel("Monto inicial ($):")
        lbl.setStyleSheet(f"color: {TEXT_PRIMARY_COLOR}; font-size: 13px;")
        row.addWidget(lbl)

        self._spin = QDoubleSpinBox()
        self._spin.setRange(0, 999999.99)
        self._spin.setDecimals(2)
        self._spin.setSingleStep(100)
        row.addWidget(self._spin)
        root.addLayout(row)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(get_btn_secondary_stylesheet())
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton("Confirmar")
        btn_confirm.setDefault(True)
        btn_confirm.setStyleSheet(get_btn_primary_stylesheet())
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
