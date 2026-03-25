"""Tests unitarios para el módulo de tema centralizado (theme.py).

Validan tokens de paleta y que todas las funciones get_*_stylesheet()
retornen strings QSS coherentes con la paleta definida.
Estos tests NO requieren QApplication — operan sobre strings Python puras.
"""

from __future__ import annotations

import pytest

from src.infrastructure.ui.theme import (
    DANGER_COLOR,
    INFO_COLOR,
    PALETTE,
    SUCCESS_COLOR,
    TEXT_PRIMARY_COLOR,
    TEXT_SECONDARY_COLOR,
    WARNING_COLOR,
    get_btn_corner_primary_stylesheet,
    get_btn_corner_secondary_stylesheet,
    get_btn_corner_teal_stylesheet,
    get_btn_danger_stylesheet,
    get_btn_primary_stylesheet,
    get_btn_secondary_stylesheet,
    get_btn_success_stylesheet,
    get_btn_warning_stylesheet,
    get_cash_status_badge_stylesheet,
    get_dialog_stylesheet,
    get_global_stylesheet,
    get_pin_input_stylesheet,
)


class TestPaletteTokens:
    """Verifica valores concretos de tokens críticos de la paleta."""

    def test_primary_is_indigo(self) -> None:
        assert PALETTE.primary == "#4f46e5"

    def test_success_is_emerald(self) -> None:
        assert PALETTE.success == "#059669"

    def test_danger_is_red(self) -> None:
        assert PALETTE.danger == "#dc2626"

    def test_surface_is_light_gray(self) -> None:
        assert PALETTE.surface == "#f9fafb"

    def test_surface_card_is_white(self) -> None:
        assert PALETTE.surface_card == "#ffffff"

    def test_border_is_light(self) -> None:
        assert PALETTE.border == "#e5e7eb"

    def test_text_primary_is_dark_gray(self) -> None:
        assert PALETTE.text_primary == "#374151"

    def test_text_secondary_is_medium_gray(self) -> None:
        assert PALETTE.text_secondary == "#6b7280"

    def test_palette_is_immutable(self) -> None:
        with pytest.raises((AttributeError, TypeError)):
            PALETTE.primary = "#000000"  # type: ignore[misc]


class TestSemanticColorConstants:
    """Verifica que las constantes semánticas apuntan a los tokens correctos."""

    def test_success_color_matches_palette(self) -> None:
        assert SUCCESS_COLOR == PALETTE.success

    def test_danger_color_matches_palette(self) -> None:
        assert DANGER_COLOR == PALETTE.danger

    def test_warning_color_matches_palette(self) -> None:
        assert WARNING_COLOR == PALETTE.warning

    def test_info_color_matches_palette(self) -> None:
        assert INFO_COLOR == PALETTE.info

    def test_text_primary_matches_palette(self) -> None:
        assert TEXT_PRIMARY_COLOR == PALETTE.text_primary

    def test_text_secondary_matches_palette(self) -> None:
        assert TEXT_SECONDARY_COLOR == PALETTE.text_secondary


class TestGlobalStylesheet:
    """Verifica el contenido del stylesheet global de MainWindow."""

    def test_returns_non_empty_string(self) -> None:
        css = get_global_stylesheet()
        assert isinstance(css, str)
        assert len(css) > 100

    def test_contains_primary_color(self) -> None:
        css = get_global_stylesheet()
        assert PALETTE.primary in css

    def test_contains_surface_color(self) -> None:
        css = get_global_stylesheet()
        assert PALETTE.surface in css

    def test_contains_success_color(self) -> None:
        css = get_global_stylesheet()
        assert PALETTE.success in css

    def test_contains_danger_color(self) -> None:
        css = get_global_stylesheet()
        assert PALETTE.danger in css

    def test_contains_sale_tab_selectors(self) -> None:
        """Verifica que los selectores del tab de venta fueron migrados del .ui."""
        css = get_global_stylesheet()
        assert "barcode_input" in css
        assert "cart_table" in css
        assert "total_label" in css
        assert "btn_confirm" in css

    def test_contains_tab_bar_styles(self) -> None:
        css = get_global_stylesheet()
        assert "QTabBar" in css

    def test_contains_table_styles(self) -> None:
        css = get_global_stylesheet()
        assert "QTableWidget" in css
        assert "QHeaderView" in css

    def test_contains_scrollbar_styles(self) -> None:
        css = get_global_stylesheet()
        assert "QScrollBar" in css


class TestDialogStylesheet:
    """Verifica el stylesheet de diálogos independientes."""

    def test_returns_non_empty_string(self) -> None:
        css = get_dialog_stylesheet()
        assert isinstance(css, str)
        assert len(css) > 50

    def test_contains_surface_background(self) -> None:
        css = get_dialog_stylesheet()
        assert PALETTE.surface in css

    def test_contains_input_styles(self) -> None:
        css = get_dialog_stylesheet()
        assert "QLineEdit" in css


class TestButtonStylesheets:
    """Verifica que cada función de botón retorna QSS con el color correcto."""

    def test_primary_contains_primary_color(self) -> None:
        css = get_btn_primary_stylesheet()
        assert PALETTE.primary in css
        assert PALETTE.primary_hover in css

    def test_secondary_contains_secondary_bg(self) -> None:
        css = get_btn_secondary_stylesheet()
        assert PALETTE.btn_secondary_bg in css

    def test_success_contains_success_color(self) -> None:
        css = get_btn_success_stylesheet()
        assert PALETTE.success in css

    def test_danger_contains_danger_color(self) -> None:
        css = get_btn_danger_stylesheet()
        assert PALETTE.danger in css

    def test_warning_contains_warning_amber(self) -> None:
        css = get_btn_warning_stylesheet()
        assert PALETTE.warning_amber in css

    def test_corner_teal_contains_teal(self) -> None:
        css = get_btn_corner_teal_stylesheet()
        assert PALETTE.teal in css

    def test_corner_primary_contains_primary(self) -> None:
        css = get_btn_corner_primary_stylesheet()
        assert PALETTE.primary in css

    def test_corner_secondary_contains_secondary_bg(self) -> None:
        css = get_btn_corner_secondary_stylesheet()
        assert PALETTE.btn_secondary_bg in css

    def test_all_btn_functions_return_non_empty_strings(self) -> None:
        fns = [
            get_btn_primary_stylesheet,
            get_btn_secondary_stylesheet,
            get_btn_success_stylesheet,
            get_btn_danger_stylesheet,
            get_btn_warning_stylesheet,
            get_btn_corner_teal_stylesheet,
            get_btn_corner_primary_stylesheet,
            get_btn_corner_secondary_stylesheet,
        ]
        for fn in fns:
            result = fn()
            assert isinstance(result, str), f"{fn.__name__} debe retornar str"
            assert len(result) > 10, f"{fn.__name__} no debe retornar string vacío"


class TestPinInputStylesheet:
    """Verifica el stylesheet del campo de PIN."""

    def test_contains_primary_border(self) -> None:
        css = get_pin_input_stylesheet()
        assert PALETTE.primary in css

    def test_contains_large_font_size(self) -> None:
        css = get_pin_input_stylesheet()
        assert "22px" in css


class TestCashStatusBadge:
    """Verifica el stylesheet del badge de estado de caja."""

    def test_contains_success_color(self) -> None:
        css = get_cash_status_badge_stylesheet()
        assert PALETTE.success in css
        assert PALETTE.success_light in css
