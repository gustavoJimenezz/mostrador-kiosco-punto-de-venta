"""Tests unitarios del closeEvent de MainWindow.

Verifica los dos flujos de cierre (confirmado y cancelado) con y sin venta
en curso, sin necesitar la UI completa de Qt Designer. Se parchean
``_load_ui`` y ``_setup_shortcuts`` para instanciar MainWindow sin el
archivo .ui, y ``QMessageBox`` para controlar la elección del usuario.

Cubre los criterios de aceptación del Ticket 23:
- Cierre confirmado sin venta en curso → event.accept().
- Cierre cancelado sin venta en curso → event.ignore() + foco al barcode.
- Cierre confirmado con venta en curso → event.accept() (mensaje distinto).
- Cierre cancelado con venta en curso → event.ignore() + foco al barcode.
- Sin presenter inyectado → se trata como sin venta en curso.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# PySide6 requiere una QApplication activa para instanciar QMainWindow.
from PySide6.QtWidgets import QApplication

from src.infrastructure.ui.windows.main_window import MainWindow

# ---------------------------------------------------------------------------
# Fixture: QApplication singleton (scope session para que no se recree)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    """Retorna la instancia de QApplication necesaria para los widgets Qt."""
    app = QApplication.instance() or QApplication(sys.argv)
    return app


# ---------------------------------------------------------------------------
# Fixture: MainWindow con _load_ui y _setup_shortcuts parcheados
# ---------------------------------------------------------------------------


@pytest.fixture
def window(qapp):
    """MainWindow sin UI cargada, con barcode_input y presenter mockeados.

    Parchea los métodos de inicialización de Qt para aislar closeEvent
    de la existencia del archivo .ui y del árbol de widgets real.

    Returns:
        MainWindow lista para testear closeEvent en aislamiento.
    """
    with (
        patch.object(MainWindow, "_load_ui"),
        patch.object(MainWindow, "_setup_shortcuts"),
    ):
        w = MainWindow(session_factory=MagicMock())

    # Sustituir widgets reales por mocks para _restore_barcode_focus
    w._barcode_input = MagicMock()
    w._presenter = MagicMock()
    return w


# ---------------------------------------------------------------------------
# Helper: construye el mock de QMessageBox según el botón que "pulsó" el usuario
# ---------------------------------------------------------------------------


def _mock_msgbox(clicked_button_index: int):
    """Retorna un patcher de QMessageBox que simula clic en el botón indicado.

    Args:
        clicked_button_index: 0 → "Salir" (AcceptRole), 1 → "Cancelar" (RejectRole).

    Returns:
        context manager de ``patch`` listo para usar en ``with``.
    """
    mock_cls = MagicMock()
    instance = mock_cls.return_value

    buttons: list[MagicMock] = []

    def _add_button(text, role):
        btn = MagicMock(name=f"btn_{text}")
        buttons.append(btn)
        return btn

    instance.addButton.side_effect = _add_button
    instance.clickedButton.side_effect = lambda: buttons[clicked_button_index]

    return patch("src.infrastructure.ui.windows.main_window.QMessageBox", mock_cls)


# ---------------------------------------------------------------------------
# Tests: cierre confirmado (sin venta en curso)
# ---------------------------------------------------------------------------


def test_close_confirmed_no_sale(window):
    """Aceptar sin venta → event.accept() y sin llamada a event.ignore()."""
    window._presenter.has_active_sale_items.return_value = False
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=0):
        window.closeEvent(event)

    event.accept.assert_called_once()
    event.ignore.assert_not_called()


def test_close_confirmed_no_sale_calls_shutdown(window):
    """Aceptar sin venta → se invoca _shutdown_database."""
    window._presenter.has_active_sale_items.return_value = False
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=0):
        with patch.object(window, "_shutdown_database") as mock_shutdown:
            window.closeEvent(event)

    mock_shutdown.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: cierre cancelado (sin venta en curso)
# ---------------------------------------------------------------------------


def test_close_cancelled_no_sale(window):
    """Cancelar sin venta → event.ignore() y sin llamada a event.accept()."""
    window._presenter.has_active_sale_items.return_value = False
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=1):
        window.closeEvent(event)

    event.ignore.assert_called_once()
    event.accept.assert_not_called()


def test_close_cancelled_restores_barcode_focus(window):
    """Cancelar → foco devuelto al barcode_input."""
    window._presenter.has_active_sale_items.return_value = False
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=1):
        window.closeEvent(event)

    window._barcode_input.setFocus.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: cierre confirmado (con venta en curso)
# ---------------------------------------------------------------------------


def test_close_confirmed_with_sale(window):
    """Aceptar con venta en curso → event.accept()."""
    window._presenter.has_active_sale_items.return_value = True
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=0):
        window.closeEvent(event)

    event.accept.assert_called_once()
    event.ignore.assert_not_called()


def test_close_confirmed_with_sale_shows_warning_message(window):
    """Con venta en curso el mensaje debe mencionar pérdida de datos."""
    window._presenter.has_active_sale_items.return_value = True
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=0) as mock_cls:
        window.closeEvent(event)

    instance = mock_cls.return_value
    call_args = instance.setText.call_args[0][0]
    assert "venta en curso" in call_args.lower()
    assert "perderán" in call_args


# ---------------------------------------------------------------------------
# Tests: cierre cancelado (con venta en curso)
# ---------------------------------------------------------------------------


def test_close_cancelled_with_sale(window):
    """Cancelar con venta en curso → event.ignore() y foco al barcode."""
    window._presenter.has_active_sale_items.return_value = True
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=1):
        window.closeEvent(event)

    event.ignore.assert_called_once()
    event.accept.assert_not_called()
    window._barcode_input.setFocus.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: sin presenter inyectado
# ---------------------------------------------------------------------------


def test_close_without_presenter_treats_as_no_sale(window):
    """Sin presenter, closeEvent no falla y trata como sin venta en curso."""
    window._presenter = None
    event = MagicMock()

    with _mock_msgbox(clicked_button_index=0):
        window.closeEvent(event)

    event.accept.assert_called_once()
