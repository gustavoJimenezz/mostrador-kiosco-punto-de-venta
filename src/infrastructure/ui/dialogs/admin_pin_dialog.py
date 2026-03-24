"""Diálogo modal para ingresar el PIN de administrador."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AdminPinDialog(QDialog):
    """Solicita el PIN de administrador para desbloquear funciones restringidas.

    Muestra un campo de PIN enmascarado con botones Confirmar/Cancelar.
    No verifica el PIN internamente: devuelve el valor ingresado para que
    el caso de uso ``ElevateToAdmin`` realice la verificación.

    Args:
        parent: Widget padre (MainWindow).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Acceso de administrador")
        self.setMinimumWidth(320)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._pin: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        """Construye el layout del diálogo."""
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        icon_label = QLabel("🔒")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 28px;")
        root.addWidget(icon_label)

        hint = QLabel("Ingresá el PIN de administrador")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 13px; color: #475569;")
        root.addWidget(hint)

        self._pin_input = QLineEdit()
        self._pin_input.setEchoMode(QLineEdit.Password)
        self._pin_input.setAlignment(Qt.AlignCenter)
        self._pin_input.setMaxLength(8)
        self._pin_input.setPlaceholderText("••••")
        self._pin_input.setStyleSheet(
            "font-size: 22px; letter-spacing: 6px; padding: 10px;"
            "border: 2px solid #4f46e5; border-radius: 8px;"
        )
        self._pin_input.returnPressed.connect(self._on_confirm)
        root.addWidget(self._pin_input)

        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet("color: #dc2626; font-size: 12px;")
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            "QPushButton { padding: 8px 18px; border-radius: 6px;"
            "background: #e2e8f0; color: #334155; border: none; }"
            "QPushButton:hover { background: #cbd5e1; }"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton("Confirmar")
        btn_confirm.setDefault(True)
        btn_confirm.setStyleSheet(
            "QPushButton { padding: 8px 18px; border-radius: 6px;"
            "background: #4f46e5; color: white; font-weight: bold; border: none; }"
            "QPushButton:hover { background: #4338ca; }"
        )
        btn_confirm.clicked.connect(self._on_confirm)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_confirm)
        root.addLayout(btn_row)

    def _on_confirm(self) -> None:
        """Guarda el PIN y cierra el diálogo con Accepted."""
        pin = self._pin_input.text()
        if not pin:
            self._error_label.setText("Ingresá el PIN.")
            self._error_label.setVisible(True)
            return
        self._pin = pin
        self.accept()

    def show_error(self, message: str) -> None:
        """Muestra un error y limpia el campo para reintentar.

        Args:
            message: Texto del error a mostrar.
        """
        self._pin_input.clear()
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._pin_input.setFocus()

    @property
    def pin(self) -> str:
        """PIN ingresado por el usuario (disponible tras accept()).

        Returns:
            El PIN en texto plano.
        """
        return self._pin
