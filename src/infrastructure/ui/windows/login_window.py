"""Ventana de inicio de sesión con selección de usuario y PIN numérico."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.user import User


class LoginWindow(QDialog):
    """Pantalla de selección de usuario e ingreso de PIN.

    Flujo:
        1. Muestra botones con los nombres de usuarios activos.
        2. Al seleccionar un usuario, aparece el campo de PIN.
        3. Al confirmar (Enter o botón), el Presenter verifica el PIN.
        4. Si es correcto, llama a ``self.accept()`` para que ``main.py``
           continúe con la apertura de MainWindow.

    Args:
        presenter: LoginPresenter ya configurado con sus dependencias.
        parent: Widget padre (None al inicio de la app).
    """

    def __init__(self, presenter, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._presenter = presenter
        self._presenter.set_view(self)
        self._selected_user: User | None = None
        self._needs_opening: bool = presenter.needs_opening_amount()

        self.setWindowTitle("Mostrador POS — Iniciar sesión")
        self.setMinimumSize(420, 340)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)

        self._build_ui()
        self._load_users()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout principal de la ventana."""
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 60, 40, 60)
        root.setSpacing(10)

        title = QLabel("Selecciona tu usuario")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #ffffff;"
        )
        root.addWidget(title)

        # Contenedor de botones de usuario
        self._users_frame = QWidget()
        self._users_layout = QVBoxLayout(self._users_frame)
        self._users_layout.setSpacing(8)
        root.addWidget(self._users_frame)

        # Sección de PIN (oculta hasta seleccionar un usuario)
        self._pin_frame = QFrame()
        self._pin_frame.setFrameShape(QFrame.StyledPanel)
        self._pin_frame.setStyleSheet(
            "QFrame { background: #f8fafc; border-radius: 8px; }"
        )
        pin_layout = QVBoxLayout(self._pin_frame)
        pin_layout.setContentsMargins(20, 16, 20, 16)
        pin_layout.setSpacing(10)

        self._user_label = QLabel()
        self._user_label.setAlignment(Qt.AlignCenter)
        self._user_label.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #4f46e5;"
        )
        pin_layout.addWidget(self._user_label)

        pin_hint = QLabel("Ingresá tu PIN")
        pin_hint.setAlignment(Qt.AlignCenter)
        pin_hint.setStyleSheet("color: #64748b; font-size: 13px;")
        pin_layout.addWidget(pin_hint)

        # Monto inicial de caja (visible solo cuando no hay sesión abierta)
        self._row_initial = QWidget()
        row_initial_layout = QHBoxLayout(self._row_initial)
        row_initial_layout.setContentsMargins(0, 0, 0, 0)
        lbl_initial = QLabel("Monto inicial de caja ($):")
        lbl_initial.setStyleSheet("color: #374151; font-size: 13px;")
        row_initial_layout.addWidget(lbl_initial)
        self._spin_initial = QDoubleSpinBox()
        self._spin_initial.setRange(0, 999999.99)
        self._spin_initial.setDecimals(2)
        self._spin_initial.setSingleStep(100)
        self._spin_initial.setStyleSheet(
            "font-size: 13px; padding: 4px; color: #1e293b;"
            "border: 1px solid #d1d5db; border-radius: 6px; background: white;"
        )
        row_initial_layout.addWidget(self._spin_initial)
        pin_layout.addWidget(self._row_initial)
        self._row_initial.setVisible(self._needs_opening)

        self._pin_input = QLineEdit()
        self._pin_input.setEchoMode(QLineEdit.Password)
        self._pin_input.setAlignment(Qt.AlignCenter)
        self._pin_input.setMaxLength(8)
        self._pin_input.setPlaceholderText("••••")
        self._pin_input.setStyleSheet(
            "font-size: 24px; letter-spacing: 8px; padding: 10px;"
            "border: 2px solid #4f46e5; border-radius: 8px;"
            "background: white; color: #1e293b;"
        )
        self._pin_input.returnPressed.connect(self._on_confirm)
        pin_layout.addWidget(self._pin_input)

        btn_row = QHBoxLayout()
        btn_back = QPushButton("← Volver")
        btn_back.setStyleSheet(
            "QPushButton { padding: 8px 18px; border-radius: 6px;"
            "background: #e2e8f0; color: #334155; font-size: 13px; border: none; }"
            "QPushButton:hover { background: #cbd5e1; }"
        )
        btn_back.clicked.connect(self._on_back)

        btn_confirm = QPushButton("Ingresar →")
        btn_confirm.setDefault(True)
        btn_confirm.setStyleSheet(
            "QPushButton { padding: 8px 18px; border-radius: 6px;"
            "background: #4f46e5; color: white; font-size: 13px;"
            "font-weight: bold; border: none; }"
            "QPushButton:hover { background: #4338ca; }"
        )
        btn_confirm.clicked.connect(self._on_confirm)

        btn_row.addWidget(btn_back)
        btn_row.addStretch()
        btn_row.addWidget(btn_confirm)
        pin_layout.addLayout(btn_row)

        root.addWidget(self._pin_frame)
        self._pin_frame.setVisible(False)

        # Mensaje de error (oculto por defecto)
        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet("color: #dc2626; font-size: 12px;")
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_back)

    def _load_users(self) -> None:
        """Obtiene los usuarios activos del Presenter y crea un botón por cada uno."""
        for i in reversed(range(self._users_layout.count())):
            widget = self._users_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        users = self._presenter.get_active_users()
        for user in users:
            btn = QPushButton(user.name)
            btn.setMinimumHeight(46)
            btn.setStyleSheet(
                "QPushButton { background: #4f46e5; color: white; font-size: 14px;"
                "font-weight: bold; border-radius: 8px; padding: 8px; border: none; }"
                "QPushButton:hover { background: #4338ca; }"
            )
            btn.clicked.connect(lambda checked, u=user: self._on_user_selected(u))
            self._users_layout.addWidget(btn)

    # ------------------------------------------------------------------
    # Handlers de eventos
    # ------------------------------------------------------------------

    def _on_user_selected(self, user: User) -> None:
        """Muestra el campo de PIN para el usuario seleccionado.

        Args:
            user: Usuario cuyo botón fue pulsado.
        """
        self._selected_user = user
        self._user_label.setText(f"Hola, {user.name}")
        self._pin_input.clear()
        self._error_label.setVisible(False)
        self._users_frame.setVisible(False)
        self._pin_frame.setVisible(True)
        self._pin_input.setFocus()

    def _on_back(self) -> None:
        """Vuelve a la pantalla de selección de usuario."""
        self._selected_user = None
        self._pin_frame.setVisible(False)
        self._users_frame.setVisible(True)
        self._error_label.setVisible(False)

    def _on_confirm(self) -> None:
        """Valida el PIN ingresado contra el Presenter."""
        if self._selected_user is None:
            return
        pin = self._pin_input.text()
        if not pin:
            self.show_error("Ingresá tu PIN.")
            return
        opening_amount = (
            Decimal(str(self._spin_initial.value())) if self._needs_opening else None
        )
        success = self._presenter.on_pin_submitted(
            self._selected_user.id, pin, opening_amount
        )
        if success:
            self.accept()

    # ------------------------------------------------------------------
    # Interfaz para el Presenter
    # ------------------------------------------------------------------

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error y limpia el campo de PIN.

        Args:
            message: Texto del error a mostrar bajo el input.
        """
        self._pin_input.clear()
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._pin_input.setFocus()
