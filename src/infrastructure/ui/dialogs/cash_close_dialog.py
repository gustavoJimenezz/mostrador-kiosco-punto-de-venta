"""Diálogo modal de cierre de caja (arqueo diario).

Envuelve CashCloseView en un QDialog modal grande, accesible desde el
botón "Cierre de caja" del corner widget o con el atajo F10.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)

from src.infrastructure.ui.views.cash_close_view import CashCloseView


class CashCloseDialog(QDialog):
    """Diálogo modal que contiene la vista de arqueo de caja.

    Se instancia una sola vez en MainWindow y se reutiliza en cada apertura,
    preservando el presenter y el estado entre usos.

    Args:
        session_factory: Callable que retorna una nueva sesión SQLAlchemy.
        parent: QWidget padre (opcional).
    """

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cierre de Caja")
        self.setModal(True)
        self.resize(720, 600)
        self.setMinimumSize(640, 520)

        self._cash_close_view = CashCloseView(session_factory=session_factory)

        from src.infrastructure.ui.theme import setup_rounded_modal
        container = setup_rounded_modal(self)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.addWidget(self._cash_close_view)

        from src.infrastructure.ui.theme import get_btn_secondary_stylesheet

        row = QHBoxLayout()
        row.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.setStyleSheet(get_btn_secondary_stylesheet())
        btn_close.clicked.connect(self.close)
        row.addWidget(btn_close)
        row.setContentsMargins(0, 0, 12, 0)
        layout.addLayout(row)

    @property
    def cash_close_view(self) -> CashCloseView:
        """Retorna la instancia interna de CashCloseView.

        Returns:
            CashCloseView contenida en este diálogo.
        """
        return self._cash_close_view

    def open_and_activate(self) -> None:
        """Carga el estado actual del arqueo y abre el diálogo modal."""
        self._cash_close_view.on_view_activated()
        self.exec()
