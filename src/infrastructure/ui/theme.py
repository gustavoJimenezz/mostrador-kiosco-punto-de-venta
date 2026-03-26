"""Sistema centralizado de paleta de colores y estilos QSS (modo claro).

Provee tokens de color y funciones ``get_*_stylesheet()`` para unificar
el diseño visual de todas las vistas y modales del sistema POS.

Uso:
    from src.infrastructure.ui.theme import (
        PALETTE,
        SUCCESS_COLOR, DANGER_COLOR, WARNING_COLOR,
        get_global_stylesheet, get_dialog_stylesheet,
        get_btn_primary_stylesheet, ...
    )
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _Palette:
    """Tokens de color del tema claro del sistema POS.

    Todos los valores son strings de color CSS (#rrggbb).
    El objeto es inmutable (frozen=True) para garantizar consistencia en runtime.
    """

    # ------------------------------------------------------------------ Fondos
    surface: str = "#f9fafb"          # Fondo base de vistas y QWidget raíz
    surface_card: str = "#ffffff"      # Tarjetas, QGroupBox interior, tablas
    surface_input: str = "#ffffff"     # QLineEdit, QSpinBox, QComboBox
    surface_hover: str = "#eef2ff"    # Hover sobre items de lista/tabla

    # ---------------------------------------------------------- Primario índigo
    primary: str = "#4f46e5"
    primary_hover: str = "#4338ca"
    primary_light: str = "#eef2ff"     # Fondo sutil para highlights primarios

    # -------------------------------------------------------------------  Texto
    text_primary: str = "#374151"
    text_secondary: str = "#6b7280"
    text_hint: str = "#9ca3af"
    text_on_primary: str = "#ffffff"   # Texto sobre fondos primario/success/danger

    # ------------------------------------------------------------------ Bordes
    border: str = "#e5e7eb"
    border_focus: str = "#4f46e5"      # = primary; borde de input al recibir foco

    # ---------------------------------------------------------------- Semántico
    success: str = "#059669"
    success_hover: str = "#047857"
    success_light: str = "#d1fae5"     # Fondo badge "Caja abierta", banners OK
    danger: str = "#dc2626"
    danger_hover: str = "#b91c1c"
    danger_light: str = "#fee2e2"      # Hover btn_cash_close, banners de error
    warning: str = "#d97706"           # Estado "Abierta" en historial de caja
    warning_hover: str = "#b45309"
    warning_amber: str = "#ca8a04"     # Botón "Abrir caja" (tono más oscuro)
    warning_amber_hover: str = "#a16207"
    warning_light: str = "#fef9c3"     # Fondo banner de campos requeridos
    info: str = "#1d4ed8"              # Totales destacados en tablas de informe
    info_surface: str = "#f0f9ff"      # Fondo del info-box de formato en ImportView
    info_border: str = "#bae6fd"       # Borde del info-box
    info_text: str = "#0c4a6e"         # Texto del info-box

    # ------------------------------------------------------- Teal (corner btn)
    teal: str = "#0f766e"              # Botón "Cierre de caja" en corner widget
    teal_hover: str = "#0d9488"

    # ------------------------------------------------- Botón secundario / gris
    btn_secondary_bg: str = "#e2e8f0"
    btn_secondary_text: str = "#334155"
    btn_secondary_hover: str = "#cbd5e1"


PALETTE = _Palette()

# Constantes de color semántico para uso dinámico con f-strings en vistas.
# Ejemplo: self._lbl.setStyleSheet(f"color: {SUCCESS_COLOR}; font-weight: bold;")
SUCCESS_COLOR: str = PALETTE.success
DANGER_COLOR: str = PALETTE.danger
WARNING_COLOR: str = PALETTE.warning
INFO_COLOR: str = PALETTE.info
TEXT_PRIMARY_COLOR: str = PALETTE.text_primary
TEXT_SECONDARY_COLOR: str = PALETTE.text_secondary
TEXT_HINT_COLOR: str = PALETTE.text_hint


# ==============================================================================
# Stylesheets
# ==============================================================================

def get_global_stylesheet() -> str:
    """QSS completo para aplicar en MainWindow (propaga a todos sus hijos).

    Incluye:
    - Base QWidget, QGroupBox, inputs, botones genéricos
    - QTabWidget y QTabBar
    - QTableWidget genérico (reemplaza setStretchLastSection en .ui)
    - QScrollBar vertical
    - Selectores específicos del tab de venta (migrados de main_window.ui)

    Returns:
        String QSS listo para pasarse a ``QMainWindow.setStyleSheet()``.
    """
    p = PALETTE
    return f"""
/* ---- BASE ---- */
QWidget {{
    background-color: {p.surface};
    color: {p.text_primary};
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 14px;
}}

/* ---- GROUPBOX ---- */
QGroupBox {{
    border: 1px solid {p.border};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: {p.text_primary};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 10px;
    color: {p.primary};
}}

/* ---- INPUTS ---- */
QLineEdit {{
    background-color: {p.surface_input};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 6px 10px;
    color: {p.text_primary};
}}
QLineEdit:focus {{
    border: 2px solid {p.border_focus};
    padding: 5px 9px;
}}
QLineEdit:disabled {{
    background-color: {p.surface};
    color: {p.text_hint};
}}
QLineEdit:read-only {{
    background-color: {p.surface};
}}
QDoubleSpinBox, QSpinBox {{
    background-color: {p.surface_input};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 4px 8px;
    color: {p.text_primary};
}}
QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 2px solid {p.border_focus};
}}
QDoubleSpinBox:disabled, QSpinBox:disabled {{
    background-color: {p.surface};
    color: {p.text_hint};
}}
QDateEdit {{
    background-color: {p.surface_input};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 4px 8px;
    color: {p.text_primary};
}}
QDateEdit:focus {{
    border: 2px solid {p.border_focus};
}}
QComboBox {{
    background-color: {p.surface_input};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 4px 8px;
    color: {p.text_primary};
}}
QComboBox:focus {{
    border: 2px solid {p.border_focus};
}}
QComboBox::drop-down {{
    border: none;
}}
QCheckBox {{
    color: {p.text_primary};
    spacing: 6px;
}}

/* ---- TABS ---- */
QTabWidget::pane {{
    border: none;
    background-color: {p.surface};
}}
QTabBar::tab {{
    background-color: {p.surface};
    color: {p.text_secondary};
    padding: 8px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background-color: {p.surface_card};
    color: {p.primary};
    font-weight: bold;
    border-bottom: 2px solid {p.primary};
}}
QTabBar::tab:hover:!selected {{
    background-color: {p.surface_hover};
    color: {p.text_primary};
}}

/* ---- TABLE genérica ---- */
QTableWidget {{
    background-color: {p.surface_card};
    border: 1px solid {p.border};
    border-radius: 8px;
    gridline-color: {p.surface};
    outline: none;
}}
QTableWidget QHeaderView::section {{
    background-color: {p.surface};
    color: {p.text_secondary};
    font-weight: bold;
    font-size: 11px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {p.border};
}}
QTableWidget::item {{
    padding: 8px 10px;
}}
QTableWidget::item:selected {{
    background-color: {p.primary_light};
    color: {p.primary};
}}
QTableWidget::item:alternate {{
    background-color: {p.surface};
}}
QTableView {{
    background-color: {p.surface_card};
    border: 1px solid {p.border};
    border-radius: 8px;
    gridline-color: {p.surface};
    outline: none;
    alternate-background-color: {p.surface};
}}
QTableView QHeaderView::section {{
    background-color: {p.surface};
    color: {p.text_secondary};
    font-weight: bold;
    font-size: 11px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {p.border};
}}
QTableView::item:selected {{
    background-color: {p.primary_light};
    color: {p.primary};
}}
QListWidget {{
    background-color: {p.surface_card};
    border: 1px solid {p.border};
    border-radius: 8px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background-color: {p.surface_hover};
    color: {p.primary};
}}
QListWidget::item:selected {{
    background-color: {p.primary};
    color: {p.text_on_primary};
}}

/* ---- SCROLLBAR ---- */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p.btn_secondary_hover};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {p.btn_secondary_hover};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---- LABEL INDICATIVO (tab venta) ---- */
QLabel#barcode_label {{
    color: {p.text_secondary};
    font-size: 13px;
    font-weight: 600;
    padding: 0 4px;
}}
QLabel#barcode_hint_label {{
    color: {p.text_secondary};
    font-size: 11px;
    padding: 0 4px;
}}
QLabel#hint_delete_label {{
    color: {p.text_primary};
    font-size: 11px;
}}

/* ---- BARCODE INPUT (tab venta) ---- */
QLineEdit#barcode_input {{
    background-color: {p.surface_card};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 16px;
    color: {p.text_primary};
}}
QLineEdit#barcode_input:focus {{
    border: 2px solid {p.primary};
    padding: 11px 15px;
}}

/* ---- SEARCH RESULTS (tab venta) ---- */
QListWidget#search_results {{
    background-color: {p.surface_card};
    border: 1px solid {p.border};
    border-radius: 8px;
    outline: none;
}}
QListWidget#search_results::item {{
    padding: 8px 12px;
    border-radius: 6px;
}}
QListWidget#search_results::item:hover {{
    background-color: {p.surface_hover};
    color: {p.primary};
}}
QListWidget#search_results::item:selected {{
    background-color: {p.primary};
    color: {p.text_on_primary};
}}

/* ---- CART TABLE (tab venta) ---- */
QTableWidget#cart_table {{
    background-color: {p.surface_card};
    border: 1px solid {p.border};
    border-radius: 12px;
    gridline-color: {p.surface};
    outline: none;
}}
QTableWidget#cart_table QHeaderView::section {{
    background-color: {p.surface};
    color: {p.text_secondary};
    font-weight: bold;
    font-size: 11px;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {p.border};
}}
QTableWidget#cart_table::item {{
    padding: 10px 12px;
    border: none;
}}
QTableWidget#cart_table::item:selected {{
    background-color: {p.primary_light};
    color: {p.primary};
}}

/* ---- TOTAL LABEL (tab venta) ---- */
QLabel#total_label {{
    background-color: {p.primary};
    color: {p.text_on_primary};
    border-radius: 16px;
    padding: 24px 16px;
    font-size: 40px;
    font-weight: 900;
    min-height: 100px;
}}

/* ---- BOTONES F1 / F10 (tab venta) ---- */
QPushButton#btn_new_sale,
QPushButton#btn_cash_close {{
    background-color: {p.surface_card};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 12px;
    padding: 20px 16px;
    font-size: 13px;
    font-weight: 600;
    min-height: 72px;
}}
QPushButton#btn_new_sale:hover {{
    background-color: {p.primary_light};
    border-color: {p.primary};
    color: {p.primary};
}}
QPushButton#btn_cash_close:hover {{
    background-color: {p.danger_light};
    border-color: #fca5a5;
    color: {p.danger};
}}

/* ---- BOTÓN COBRAR F4 (tab venta) ---- */
QPushButton#btn_confirm {{
    background-color: {p.success};
    color: {p.text_on_primary};
    border: none;
    border-radius: 12px;
    padding: 20px 16px;
    font-size: 15px;
    font-weight: 800;
    min-height: 72px;
}}
QPushButton#btn_confirm:hover {{ background-color: {p.success_hover}; }}
QPushButton#btn_confirm:pressed {{ background-color: #047857; }}

/* ---- BOTÓN BORRAR ÍTEM (tab venta) ---- */
QPushButton#btn_delete_item {{
    background-color: {p.surface_card};
    color: {p.danger};
    border: 1px solid #fca5a5;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#btn_delete_item:hover {{
    background-color: {p.danger_light};
    border-color: {p.danger};
}}
QPushButton#btn_delete_item:disabled {{
    color: {p.text_hint};
    border-color: {p.border};
}}
"""


def get_dialog_stylesheet() -> str:
    """QSS base para diálogos independientes (sin parent en MainWindow).

    Aplicar en ``LoginWindow``, ``OpenCashDialog``, ``AdminPinDialog``.
    Se aplica sobre el container de ``setup_rounded_modal``, no sobre el QDialog.

    Returns:
        String QSS que establece fondo claro e inputs coherentes con el global.
    """
    p = PALETTE
    return f"""
QWidget {{
    background-color: {p.surface};
    color: {p.text_primary};
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 14px;
}}
QFrame {{
    background-color: {p.surface_card};
    border-radius: 8px;
}}
QLineEdit {{
    background-color: {p.surface_input};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 6px 10px;
    color: {p.text_primary};
}}
QLineEdit:focus {{
    border: 2px solid {p.border_focus};
    padding: 5px 9px;
}}
QDoubleSpinBox, QSpinBox {{
    background-color: {p.surface_input};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 4px 8px;
    color: {p.text_primary};
}}
QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 2px solid {p.border_focus};
}}
"""


def setup_rounded_modal(dialog, radius: int = 12) -> "QWidget":
    """Configura un diálogo modal usando la barra de título nativa del OS.

    Mantiene la API original (retorna un QWidget sobre el que los diálogos
    construyen su layout), pero usa el marco estándar del sistema operativo
    en lugar de un marco personalizado sin bordes.

    Uso::

        self._container = setup_rounded_modal(self)
        root = QVBoxLayout(self._container)

    Args:
        dialog: El QDialog (o subclase) a configurar.
        radius: Conservado por compatibilidad de firma; no tiene efecto.

    Returns:
        QWidget área de contenido sobre el que se debe construir el layout.
    """
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    content_area = QWidget()
    content_area.setObjectName("modal_content")
    outer.addWidget(content_area)

    return content_area


def get_btn_primary_stylesheet() -> str:
    """Botón de acción principal (fondo índigo).

    Returns:
        QSS string para botones primarios (Confirmar, Guardar, Cerrar caja, etc.).
    """
    p = PALETTE
    return (
        f"QPushButton {{ background-color: {p.primary}; color: {p.text_on_primary};"
        f" border: none; border-radius: 6px; padding: 8px 18px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {p.primary_hover}; }}"
        f"QPushButton:pressed {{ background-color: {p.primary_hover}; }}"
        f"QPushButton:disabled {{ background-color: #a5b4fc; color: {p.text_on_primary}; }}"
    )


def get_btn_secondary_stylesheet() -> str:
    """Botón de acción secundaria (fondo gris, texto oscuro).

    Returns:
        QSS string para botones Cancelar, Volver, Cerrar.
    """
    p = PALETTE
    return (
        f"QPushButton {{ background-color: {p.btn_secondary_bg}; color: {p.btn_secondary_text};"
        f" border: none; border-radius: 6px; padding: 8px 18px; }}"
        f"QPushButton:hover {{ background-color: {p.btn_secondary_hover}; }}"
        f"QPushButton:pressed {{ background-color: {p.btn_secondary_hover}; }}"
    )


def get_btn_success_stylesheet() -> str:
    """Botón de acción positiva / ingreso (fondo verde).

    Returns:
        QSS string para botones de ingreso y confirmación de pago.
    """
    p = PALETTE
    return (
        f"QPushButton {{ background-color: {p.success}; color: {p.text_on_primary};"
        f" padding: 6px 14px; border-radius: 4px; border: none; }}"
        f"QPushButton:hover {{ background-color: {p.success_hover}; }}"
        f"QPushButton:disabled {{ background-color: #a7f3d0; color: {p.text_secondary}; }}"
    )


def get_btn_danger_stylesheet() -> str:
    """Botón de acción destructiva / egreso (fondo rojo).

    Returns:
        QSS string para botones de egreso, eliminar, etc.
    """
    p = PALETTE
    return (
        f"QPushButton {{ background-color: {p.danger}; color: {p.text_on_primary};"
        f" padding: 6px 14px; border-radius: 4px; border: none; }}"
        f"QPushButton:hover {{ background-color: {p.danger_hover}; }}"
        f"QPushButton:disabled {{ background-color: #fecaca; color: {p.text_secondary}; }}"
    )


def get_btn_warning_stylesheet() -> str:
    """Botón de alerta / apertura de caja (fondo ámbar oscuro).

    Returns:
        QSS string para el botón "Abrir caja" del corner widget.
    """
    p = PALETTE
    return (
        f"QPushButton {{ padding: 4px 12px; border-radius: 5px;"
        f" background: {p.warning_amber}; color: {p.text_on_primary};"
        f" border: none; font-size: 12px; }}"
        f"QPushButton:hover {{ background: {p.warning_amber_hover}; }}"
    )


def get_btn_corner_teal_stylesheet() -> str:
    """Botón teal para "Cierre de caja" en el corner widget.

    Returns:
        QSS string con padding pequeño específico del corner widget.
    """
    p = PALETTE
    return (
        f"QPushButton {{ padding: 4px 12px; border-radius: 5px;"
        f" background: {p.teal}; color: {p.text_on_primary};"
        f" border: none; font-size: 12px; }}"
        f"QPushButton:hover {{ background: {p.teal_hover}; }}"
    )


def get_btn_corner_primary_stylesheet() -> str:
    """Botón primario pequeño para el corner widget (estado Administrador activo).

    Returns:
        QSS string con padding pequeño específico del corner widget.
    """
    p = PALETTE
    return (
        f"QPushButton {{ padding: 4px 12px; border-radius: 5px;"
        f" background: {p.primary}; color: {p.text_on_primary};"
        f" border: none; font-size: 12px; }}"
        f"QPushButton:hover {{ background: {p.primary_hover}; }}"
    )


def get_btn_corner_secondary_stylesheet() -> str:
    """Botón secundario pequeño para el corner widget (estado Administrador inactivo).

    Returns:
        QSS string con padding pequeño específico del corner widget.
    """
    p = PALETTE
    return (
        f"QPushButton {{ padding: 4px 12px; border-radius: 5px;"
        f" background: {p.btn_secondary_bg}; color: {p.btn_secondary_text};"
        f" border: none; font-size: 12px; }}"
        f"QPushButton:hover {{ background: {p.btn_secondary_hover}; }}"
    )


def get_pin_input_stylesheet() -> str:
    """Campo de entrada de PIN con fuente grande y letter-spacing.

    Returns:
        QSS string para QLineEdit de PIN (login y admin dialogs).
    """
    p = PALETTE
    return (
        f"font-size: 22px; letter-spacing: 6px; padding: 10px;"
        f" border: 2px solid {p.primary}; border-radius: 8px;"
        f" background: {p.surface_card}; color: {p.text_primary};"
    )


def get_cash_status_badge_stylesheet() -> str:
    """Badge verde "Caja abierta" en el corner widget de MainWindow.

    Returns:
        QSS string para el QLabel de estado de caja abierta.
    """
    p = PALETTE
    return (
        f"color: {p.success}; font-size: 12px; font-weight: bold;"
        f" padding: 4px 8px; background: {p.success_light}; border-radius: 5px;"
    )


# ── Paleta del Calendario (coherente con tema claro global) ──────────────────
# Estas constantes se usan exclusivamente en CalendarView y CalendarDayCell.
# Usan los mismos tokens de color que el resto de la aplicación.

CAL_BG_BASE       = PALETTE.surface         # Fondo del widget raíz del calendario
CAL_BG_CELL       = PALETTE.surface_card    # Fondo de cada celda de día
CAL_BG_CELL_OTHER = PALETTE.surface         # Celda de día fuera del mes actual
CAL_BORDER_CELL   = PALETTE.border          # Borde entre celdas (#e5e7eb)
CAL_LINE_RULES    = "#d1d5db"               # Renglones horizontales (gris muy sutil)

CAL_TEXT_DAY_NUM  = PALETTE.text_secondary  # Número de día (esquina superior derecha)
CAL_TEXT_OTHER    = PALETTE.text_hint       # Número de día fuera del mes actual
CAL_TEXT_NOTES    = PALETTE.text_primary    # Texto de notas dentro de cada celda
CAL_TEXT_WEEKDAY  = PALETTE.text_secondary  # Encabezados Lu Ma Mi Ju Vi Sa Do

CAL_TODAY_NUM_BG  = PALETTE.primary         # Fondo pastilla del número del día actual
CAL_TODAY_NUM_FG  = PALETTE.text_on_primary # Texto del número del día actual
CAL_TODAY_BORDER  = PALETTE.primary         # Borde izquierdo (3px) de la celda de hoy

CAL_BTN_NAV_BG    = PALETTE.btn_secondary_bg    # Fondo botones ◀ ▶
CAL_BTN_NAV_HOVER = PALETTE.primary             # Hover botones ◀ ▶
CAL_BTN_NAV_FG    = PALETTE.btn_secondary_text  # Icono/texto botones ◀ ▶
CAL_HEADER_BG     = PALETTE.surface_card        # Barra de encabezado (mes/año)
CAL_MONTH_LABEL   = PALETTE.text_primary        # Texto del label de mes y año
