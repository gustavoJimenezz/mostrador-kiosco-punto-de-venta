"""Widget de celda de día para el calendario mensual (PySide6).

Cada instancia representa un cuadrado del grid del calendario. Internamente
contiene un ``QPlainTextEdit`` para notas de texto libre y un ``paintEvent``
que dibuja renglones horizontales alineados con la métrica de fuente del editor.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

from src.infrastructure.ui.theme import (
    CAL_BG_CELL,
    CAL_BG_CELL_OTHER,
    CAL_BORDER_CELL,
    CAL_LINE_RULES,
    CAL_TEXT_DAY_NUM,
    CAL_TEXT_NOTES,
    CAL_TEXT_OTHER,
    CAL_TODAY_BORDER,
    CAL_TODAY_NUM_BG,
    CAL_TODAY_NUM_FG,
)


class CalendarDayCell(QFrame):
    """Celda de un día en el grid del calendario mensual.

    Muestra el número de día en la esquina superior derecha y un área de texto
    libre con renglones horizontales dibujados mediante ``paintEvent``.

    Args:
        year: Año de la celda.
        month: Mes de la celda.
        day_number: Número de día a mostrar. 0 si es un relleno de mes adyacente.
        is_today: True si esta celda representa el día actual.
        is_current_month: False si el día pertenece a un mes adyacente (relleno).
        notes_text: Texto inicial cargado desde el almacenamiento.
        parent: QWidget padre (opcional).
    """

    text_changed = Signal(str, str)  # (date_key, text)

    def __init__(
        self,
        year: int,
        month: int,
        day_number: int,
        *,
        is_today: bool = False,
        is_current_month: bool = True,
        notes_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._year = year
        self._month = month
        self._day_number = day_number
        self._is_today = is_today
        self._is_current_month = is_current_month
        self._date_key = f"{year:04d}-{month:02d}-{day_number:02d}" if day_number else ""
        self._text_edit: QPlainTextEdit | None = None
        self._build_ui(notes_text)

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _build_ui(self, notes_text: str) -> None:
        """Construye el layout interno de la celda.

        Args:
            notes_text: Texto inicial para el editor de notas.
        """
        bg = CAL_BG_CELL if self._is_current_month else CAL_BG_CELL_OTHER

        # Borde izquierdo cian para el día actual; borde normal para el resto
        border_left = f"3px solid {CAL_TODAY_BORDER}" if self._is_today else f"1px solid {CAL_BORDER_CELL}"
        self.setStyleSheet(
            f"CalendarDayCell {{"
            f"  background: {bg};"
            f"  border: 1px solid {CAL_BORDER_CELL};"
            f"  border-left: {border_left};"
            f"}}"
        )
        self.setMinimumHeight(130)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Encabezado: número de día (alineado a la derecha) ──────────
        header = QWidget()
        header.setFixedHeight(22)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 6, 0)
        header_layout.addStretch()

        self._day_label = QLabel()
        if self._day_number:
            self._day_label.setText(str(self._day_number))
        self._day_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if self._is_today:
            self._day_label.setStyleSheet(
                f"background: {CAL_TODAY_NUM_BG};"
                f"color: {CAL_TODAY_NUM_FG};"
                f"font-size: 11px; font-weight: bold;"
                f"padding: 1px 5px; border-radius: 9px;"
            )
        else:
            color = CAL_TEXT_DAY_NUM if self._is_current_month else CAL_TEXT_OTHER
            self._day_label.setStyleSheet(
                f"background: transparent; color: {color};"
                f"font-size: 11px; font-weight: normal;"
            )

        header_layout.addWidget(self._day_label)
        layout.addWidget(header)

        # ── Editor de notas (fondo transparente, sin borde) ────────────
        self._text_edit = QPlainTextEdit()
        self._text_edit.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background: transparent;"
            f"  color: {CAL_TEXT_NOTES};"
            f"  border: none;"
            f"  padding: 2px 6px 2px 6px;"
            f"  font-size: 14px;"
            f"  line-height: 1.4;"
            f"}}"
            f"QScrollBar {{ width: 0px; height: 0px; }}"
        )
        self._text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        if not self._is_current_month or not self._day_number:
            self._text_edit.setEnabled(False)
            self._text_edit.setPlaceholderText("")
        else:
            self._text_edit.setPlainText(notes_text)
            self._text_edit.textChanged.connect(self._on_text_changed)

        layout.addWidget(self._text_edit, stretch=1)

    # ------------------------------------------------------------------
    # paintEvent: dibuja renglones horizontales alineados con la fuente
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """Dibuja renglones horizontales sutiles sobre el área del editor.

        Las líneas se calculan en runtime a partir de ``QFontMetrics.lineSpacing()``
        para alinearse exactamente con el texto del ``QPlainTextEdit``.

        Args:
            event: QPaintEvent recibido de Qt.
        """
        super().paintEvent(event)

        if self._text_edit is None or not self._is_current_month or not self._day_number:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        pen = QPen(QColor(CAL_LINE_RULES))
        pen.setWidth(1)
        painter.setPen(pen)

        edit_rect = self._text_edit.geometry()
        fm = self._text_edit.fontMetrics()
        line_height = fm.lineSpacing()

        if line_height <= 0:
            painter.end()
            return

        margins = self._text_edit.contentsMargins()
        # Primera línea base: parte superior del editor + margen top + ascenso de fuente
        y = edit_rect.top() + margins.top() + fm.ascent() + 2

        left = edit_rect.left() + 6
        right = edit_rect.right() - 6

        while y < edit_rect.bottom() - 4:
            painter.drawLine(left, y, right, y)
            y += line_height

        painter.end()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @property
    def date_key(self) -> str:
        """Clave de fecha en formato ``YYYY-MM-DD`` para identificar la celda.

        Returns:
            Cadena con la fecha o cadena vacía si es una celda de relleno.
        """
        return self._date_key

    def get_text(self) -> str:
        """Retorna el texto actual del editor de notas.

        Returns:
            Texto plano del editor.
        """
        if self._text_edit is None:
            return ""
        return self._text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        """Establece el texto del editor sin disparar la señal ``text_changed``.

        Args:
            text: Texto a cargar en el editor.
        """
        if self._text_edit is None:
            return
        self._text_edit.blockSignals(True)
        self._text_edit.setPlainText(text)
        self._text_edit.blockSignals(False)

    # ------------------------------------------------------------------
    # Slots privados
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        """Propaga el cambio de texto con la clave de fecha asociada."""
        if self._date_key:
            self.text_changed.emit(self._date_key, self._text_edit.toPlainText())
