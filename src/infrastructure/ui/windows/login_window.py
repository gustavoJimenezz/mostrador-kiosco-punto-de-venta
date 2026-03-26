"""Ventana de inicio de sesión con selección de usuario y PIN numérico."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.user import User
from src.infrastructure.ui.app_config import get_app_icon


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

        self.setWindowTitle("Mostrador POS — Iniciar sesión")
        self.setMinimumSize(420, 460)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        from src.infrastructure.ui.theme import get_dialog_stylesheet, setup_rounded_modal
        self._container = setup_rounded_modal(self)
        self._container.setStyleSheet(
            self._container.styleSheet() + get_dialog_stylesheet()
        )

        self._build_ui()
        self._load_users()

    # ------------------------------------------------------------------
    # Eventos de ciclo de vida
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Centra la ventana en pantalla al mostrarse."""
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout principal de la ventana."""
        root = QVBoxLayout(self._container)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(10)

        logo_label = QLabel()
        logo_label.setPixmap(get_app_icon().pixmap(120, 120))
        logo_label.setAlignment(Qt.AlignCenter)
        root.addWidget(logo_label)

        from src.infrastructure.ui.theme import (
            DANGER_COLOR,
            TEXT_SECONDARY_COLOR,
            get_btn_primary_stylesheet,
            get_btn_secondary_stylesheet,
            get_pin_input_stylesheet,
            PALETTE,
        )

        title = QLabel("Selecciona tu usuario")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {PALETTE.text_primary};"
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
        pin_layout = QVBoxLayout(self._pin_frame)
        pin_layout.setContentsMargins(20, 16, 20, 16)
        pin_layout.setSpacing(10)

        self._user_label = QLabel()
        self._user_label.setAlignment(Qt.AlignCenter)
        self._user_label.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {PALETTE.primary};"
        )
        pin_layout.addWidget(self._user_label)

        pin_hint = QLabel("Ingresá tu PIN")
        pin_hint.setAlignment(Qt.AlignCenter)
        pin_hint.setStyleSheet(f"color: {TEXT_SECONDARY_COLOR}; font-size: 13px;")
        pin_layout.addWidget(pin_hint)

        self._pin_input = QLineEdit()
        self._pin_input.setEchoMode(QLineEdit.Password)
        self._pin_input.setAlignment(Qt.AlignCenter)
        self._pin_input.setMaxLength(8)
        self._pin_input.setPlaceholderText("••••")
        self._pin_input.setStyleSheet(
            f"font-size: 24px; letter-spacing: 8px; padding: 10px;"
            f" border: 2px solid {PALETTE.primary}; border-radius: 8px;"
            f" background: {PALETTE.surface_card}; color: {PALETTE.text_primary};"
        )
        self._pin_input.returnPressed.connect(self._on_confirm)
        pin_layout.addWidget(self._pin_input)

        btn_row = QHBoxLayout()
        btn_back = QPushButton("← Volver")
        btn_back.setStyleSheet(get_btn_secondary_stylesheet())
        btn_back.clicked.connect(self._on_back)

        btn_confirm = QPushButton("Ingresar →")
        btn_confirm.setDefault(True)
        btn_confirm.setStyleSheet(get_btn_primary_stylesheet())
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
        self._error_label.setStyleSheet(f"color: {DANGER_COLOR}; font-size: 12px;")
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_back)

    def _load_users(self) -> None:
        """Obtiene los usuarios activos del Presenter y crea un botón por cada uno."""
        for i in reversed(range(self._users_layout.count())):
            widget = self._users_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        from src.infrastructure.ui.theme import PALETTE

        users = self._presenter.get_active_users()
        for user in users:
            btn = QPushButton(user.name)
            btn.setMinimumHeight(46)
            btn.setStyleSheet(
                f"QPushButton {{ background: {PALETTE.primary}; color: {PALETTE.text_on_primary};"
                f" font-size: 14px; font-weight: bold; border-radius: 8px; padding: 8px; border: none; }}"
                f"QPushButton:hover {{ background: {PALETTE.primary_hover}; }}"
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
        success = self._presenter.on_pin_submitted(self._selected_user.id, pin)
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
