"""Tests unitarios de visibilidad del Panel Administrador en MainWindow.

Verifica que la pestaña "Panel Administrador" (índice 3) solo se muestre
al presionar el botón administrador, y que las pestañas visibles para todos
(Movimientos de caja, Calendario) nunca sean ocultadas por ese mecanismo.

Criterios de aceptación:
- _ADMIN_TAB_INDICES apunta al índice 3 (Panel Administrador), nunca al 2 (Calendario).
- _lock_admin_tabs() oculta el índice 3 y no toca el índice 2.
- _unlock_admin_tabs() muestra el índice 3 y no toca el índice 2.
- Si el panel ya está visible y se presiona el botón, se bloquea (toggle).
- Si el panel está oculto y se presiona el botón, se muestra el diálogo de PIN.
- Los atajos F5/F6/F7/F9 navegan al índice 3 (no al 2).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, call, patch

import pytest
from PySide6.QtWidgets import QApplication

from src.infrastructure.ui.windows.main_window import MainWindow

# ---------------------------------------------------------------------------
# Fixture: QApplication singleton
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    """Retorna la instancia de QApplication necesaria para los widgets Qt."""
    return QApplication.instance() or QApplication(sys.argv)


# ---------------------------------------------------------------------------
# Fixture: MainWindow sin UI cargada, con _tab_widget mockeado
# ---------------------------------------------------------------------------


@pytest.fixture
def window(qapp):
    """MainWindow con _load_ui y _setup_shortcuts parcheados.

    Se sustituyen los atributos Qt por mocks para probar la lógica de
    visibilidad de tabs sin necesitar el archivo .ui ni widgets reales.

    Returns:
        MainWindow lista para testear el mecanismo de lock/unlock de admin.
    """
    with (
        patch.object(MainWindow, "_load_ui"),
        patch.object(MainWindow, "_setup_shortcuts"),
    ):
        w = MainWindow(session_factory=MagicMock())

    # Atributos que usan _lock_admin_tabs / _unlock_admin_tabs
    w._tab_widget = MagicMock()
    w._admin_btn = MagicMock()

    # Atributos que usan los handlers de atajos (F5–F9)
    w._admin_panel_view = MagicMock()
    w._barcode_input = MagicMock()

    return w


# ---------------------------------------------------------------------------
# Constante _ADMIN_TAB_INDICES
# ---------------------------------------------------------------------------


def test_admin_tab_indices_apunta_a_indice_3():
    """_ADMIN_TAB_INDICES debe ser [3]: Panel Administrador, no Calendario."""
    assert MainWindow._ADMIN_TAB_INDICES == [3]


def test_admin_tab_indices_no_incluye_indice_2():
    """El índice 2 (Calendario) no debe estar en _ADMIN_TAB_INDICES."""
    assert 2 not in MainWindow._ADMIN_TAB_INDICES


# ---------------------------------------------------------------------------
# _lock_admin_tabs
# ---------------------------------------------------------------------------


def test_lock_oculta_panel_administrador(window):
    """_lock_admin_tabs() debe llamar setTabVisible(3, False)."""
    window._lock_admin_tabs()
    window._tab_widget.setTabVisible.assert_any_call(3, False)


def test_lock_no_oculta_calendario(window):
    """_lock_admin_tabs() no debe tocar el índice 2 (Calendario)."""
    window._lock_admin_tabs()
    for call_args in window._tab_widget.setTabVisible.call_args_list:
        assert call_args.args[0] != 2, (
            "setTabVisible fue llamado con índice 2 (Calendario) — "
            "solo el índice 3 debe ocultarse."
        )


def test_lock_actualiza_texto_boton(window):
    """_lock_admin_tabs() debe mostrar el candado en el botón."""
    window._lock_admin_tabs()
    window._admin_btn.setText.assert_called_once()
    texto = window._admin_btn.setText.call_args[0][0]
    assert "🔒" in texto


# ---------------------------------------------------------------------------
# _unlock_admin_tabs
# ---------------------------------------------------------------------------


def test_unlock_muestra_panel_administrador(window):
    """_unlock_admin_tabs() debe llamar setTabVisible(3, True)."""
    window._unlock_admin_tabs()
    window._tab_widget.setTabVisible.assert_any_call(3, True)


def test_unlock_no_afecta_calendario(window):
    """_unlock_admin_tabs() no debe tocar el índice 2 (Calendario)."""
    window._unlock_admin_tabs()
    for call_args in window._tab_widget.setTabVisible.call_args_list:
        assert call_args.args[0] != 2, (
            "setTabVisible fue llamado con índice 2 (Calendario) — "
            "unlock solo debe afectar el índice 3."
        )


def test_unlock_actualiza_texto_boton(window):
    """_unlock_admin_tabs() debe cambiar el texto del botón a 'ocultar'."""
    window._unlock_admin_tabs()
    window._admin_btn.setText.assert_called_once()
    texto = window._admin_btn.setText.call_args[0][0]
    assert "Ocultar" in texto or "ocultar" in texto


# ---------------------------------------------------------------------------
# Toggle: _on_admin_access_requested
# ---------------------------------------------------------------------------


def test_boton_admin_bloquea_si_panel_ya_visible(window):
    """Si el panel ya está visible, el botón debe bloquearlo (toggle off)."""
    # Simular que el primer índice admin ya es visible
    window._tab_widget.isTabVisible.return_value = True

    with patch.object(window, "_lock_admin_tabs") as mock_lock:
        window._on_admin_access_requested()

    mock_lock.assert_called_once()


def test_boton_admin_muestra_dialogo_pin_si_panel_oculto(window):
    """Si el panel está oculto, el botón debe abrir el diálogo de PIN."""
    window._tab_widget.isTabVisible.return_value = False
    window._elevate_use_case = None  # evitar la lógica post-PIN

    # AdminPinDialog se importa lazy dentro del método; se parchea en su módulo origen.
    with patch("src.infrastructure.ui.dialogs.admin_pin_dialog.AdminPinDialog") as mock_dialog:
        mock_dialog.return_value.exec.return_value = 0  # Cancelled
        window._on_admin_access_requested()

    mock_dialog.assert_called_once()


def test_boton_admin_desbloquea_con_pin_correcto(window):
    """PIN correcto → _unlock_admin_tabs() debe ser llamado."""
    from PySide6.QtWidgets import QDialog

    window._tab_widget.isTabVisible.return_value = False

    mock_use_case = MagicMock()
    mock_use_case.execute.return_value = True
    window._elevate_use_case = mock_use_case

    with (
        patch("src.infrastructure.ui.dialogs.admin_pin_dialog.AdminPinDialog") as mock_dialog_cls,
        patch.object(window, "_unlock_admin_tabs") as mock_unlock,
    ):
        instance = mock_dialog_cls.return_value
        instance.exec.return_value = QDialog.DialogCode.Accepted
        instance.pin = "1234"
        window._on_admin_access_requested()

    mock_unlock.assert_called_once()


def test_boton_admin_no_desbloquea_con_pin_incorrecto(window):
    """PIN incorrecto → _unlock_admin_tabs() NO debe ser llamado."""
    from PySide6.QtWidgets import QDialog

    window._tab_widget.isTabVisible.return_value = False

    mock_use_case = MagicMock()
    mock_use_case.execute.return_value = False
    window._elevate_use_case = mock_use_case

    with (
        patch("src.infrastructure.ui.dialogs.admin_pin_dialog.AdminPinDialog") as mock_dialog_cls,
        patch.object(window, "_unlock_admin_tabs") as mock_unlock,
    ):
        instance = mock_dialog_cls.return_value
        # Primer intento: PIN incorrecto → exec retorna Accepted
        # Segundo intento: usuario cancela → exec retorna Rejected
        instance.exec.side_effect = [
            QDialog.DialogCode.Accepted,
            QDialog.DialogCode.Rejected,
        ]
        instance.pin = "0000"
        window._on_admin_access_requested()

    mock_unlock.assert_not_called()


# ---------------------------------------------------------------------------
# Atajos de teclado F5–F9: deben navegar al índice 3
# ---------------------------------------------------------------------------


def _make_admin_session():
    """Patcher que simula sesión de administrador activa."""
    return patch(
        "src.infrastructure.ui.session.AppSession.is_admin",
        return_value=True,
    )


def test_f5_navega_a_indice_3(window):
    """F5 (_on_open_products) debe llamar setCurrentIndex(3), no 2."""
    with _make_admin_session():
        window._on_open_products()
    window._tab_widget.setCurrentIndex.assert_called_with(3)


def test_f6_navega_a_indice_3(window):
    """F6 (_on_open_stock_edit) debe llamar setCurrentIndex(3), no 2."""
    with _make_admin_session():
        window._on_open_stock_edit()
    window._tab_widget.setCurrentIndex.assert_called_with(3)


def test_f7_navega_a_indice_3(window):
    """F7 (_on_open_stock_inject) debe llamar setCurrentIndex(3), no 2."""
    with _make_admin_session():
        window._on_open_stock_inject()
    window._tab_widget.setCurrentIndex.assert_called_with(3)


def test_f9_navega_a_indice_3(window):
    """F9 (_on_open_import) debe llamar setCurrentIndex(3), no 2."""
    with _make_admin_session():
        window._on_open_import()
    window._tab_widget.setCurrentIndex.assert_called_with(3)


def test_f5_no_navega_sin_ser_admin(window):
    """F5 sin rol admin no debe cambiar de pestaña."""
    with patch(
        "src.infrastructure.ui.session.AppSession.is_admin",
        return_value=False,
    ):
        window._on_open_products()
    window._tab_widget.setCurrentIndex.assert_not_called()
