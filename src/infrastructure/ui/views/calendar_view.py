"""Vista del calendario mensual (PySide6).

Muestra una cuadrícula de 7 columnas (Lunes–Domingo) con celdas editables
por día. Las notas persisten vía ``CalendarPresenter`` en un archivo JSON local.

El componente usa la misma paleta de colores clara que el resto de la aplicación
(índigo como acento principal, fondos blancos/grises suaves).
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.infrastructure.ui.theme import (
    CAL_BG_BASE,
    CAL_BTN_NAV_BG,
    CAL_BTN_NAV_FG,
    CAL_BTN_NAV_HOVER,
    CAL_HEADER_BG,
    CAL_MONTH_LABEL,
    CAL_TEXT_WEEKDAY,
    CAL_BORDER_CELL,
)
from src.infrastructure.ui.widgets.calendar_day_cell import CalendarDayCell

if TYPE_CHECKING:
    from src.infrastructure.ui.presenters.calendar_presenter import CalendarPresenter

_WEEKDAY_NAMES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

_MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

_NAV_BTN_STYLE = (
    f"QPushButton {{"
    f"  background: {CAL_BTN_NAV_BG}; color: {CAL_BTN_NAV_FG};"
    f"  border: none; border-radius: 4px;"
    f"  font-size: 14px; font-weight: bold;"
    f"  padding: 4px 12px;"
    f"}}"
    f"QPushButton:hover {{ background: {CAL_BTN_NAV_HOVER}; color: #ffffff; }}"
)

_DEBOUNCE_MS = 800


class CalendarView(QWidget):
    """Vista del calendario de mes completo con notas editables por día.

    Args:
        parent: QWidget padre (opcional).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        today = date.today()
        self._current_year = today.year
        self._current_month = today.month
        self._today = today
        self._presenter: CalendarPresenter | None = None
        self._cells: list[CalendarDayCell] = []
        self._pending_saves: dict[str, str] = {}
        self._grid_container: QWidget | None = None
        self._scroll_area: QScrollArea | None = None
        self._month_label: QLabel | None = None

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._flush_pending_saves)

        self._build_ui()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout principal: cabecera + nombres de días + grid."""
        self.setStyleSheet(f"CalendarView {{ background: {CAL_BG_BASE}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header_bar())
        root.addWidget(self._build_weekday_header())

        # Área de scroll para el grid (meses de 6 semanas pueden ser altos)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet(
            f"QScrollArea {{ border: none; background: {CAL_BG_BASE}; }}"
            f"QScrollBar:vertical {{ width: 6px; background: {CAL_BG_BASE}; }}"
            f"QScrollBar::handle:vertical {{ background: {CAL_BTN_NAV_BG}; border-radius: 3px; }}"
        )
        root.addWidget(self._scroll_area, stretch=1)

        self._rebuild_grid()

    def _build_header_bar(self) -> QWidget:
        """Construye la barra de navegación (◀ Mes Año ▶).

        Returns:
            QWidget con la barra de encabezado.
        """
        bar = QWidget()
        bar.setStyleSheet(f"background: {CAL_HEADER_BG};")
        bar.setFixedHeight(44)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        btn_prev = QPushButton("◀")
        btn_prev.setStyleSheet(_NAV_BTN_STYLE)
        btn_prev.setFixedWidth(40)
        btn_prev.clicked.connect(self._on_prev_month)

        self._month_label = QLabel()
        self._month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._month_label.setStyleSheet(
            f"color: {CAL_MONTH_LABEL}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        self._update_month_label()

        btn_next = QPushButton("▶")
        btn_next.setStyleSheet(_NAV_BTN_STYLE)
        btn_next.setFixedWidth(40)
        btn_next.clicked.connect(self._on_next_month)

        layout.addWidget(btn_prev)
        layout.addWidget(self._month_label, stretch=1)
        layout.addWidget(btn_next)

        return bar

    def _build_weekday_header(self) -> QWidget:
        """Construye la fila de encabezados de día de semana (Lun–Dom).

        Returns:
            QWidget con los 7 labels.
        """
        row = QWidget()
        row.setStyleSheet(f"background: {CAL_HEADER_BG}; border-bottom: 1px solid {CAL_BORDER_CELL};")
        row.setFixedHeight(28)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for name in _WEEKDAY_NAMES:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {CAL_TEXT_WEEKDAY}; font-size: 11px; font-weight: bold;"
                f" background: transparent;"
            )
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(lbl)

        return row

    # ------------------------------------------------------------------
    # Construcción del grid mensual
    # ------------------------------------------------------------------

    def _rebuild_grid(self) -> None:
        """Elimina el grid actual y construye uno nuevo para el mes vigente.

        Usa ``calendar.monthcalendar`` de la stdlib para obtener la matriz
        de semanas. Los días ``0`` son días fuera del mes (relleno).
        Crea un ``QWidget`` contenedor nuevo cada vez para evitar el bug de
        ``setLayout`` doble (Qt ignora silenciosamente la segunda llamada).
        """
        self._cells.clear()

        new_container = QWidget()
        new_container.setStyleSheet(f"background: {CAL_BG_BASE};")

        grid = QGridLayout(new_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        weeks = calendar.monthcalendar(self._current_year, self._current_month)

        for row_idx, week in enumerate(weeks):
            for col_idx, day in enumerate(week):
                is_filler = day == 0
                is_today = (
                    not is_filler
                    and self._today.year == self._current_year
                    and self._today.month == self._current_month
                    and self._today.day == day
                )
                cell = CalendarDayCell(
                    year=self._current_year,
                    month=self._current_month,
                    day_number=day if not is_filler else 0,
                    is_today=is_today,
                    is_current_month=not is_filler,
                )
                cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                if not is_filler:
                    cell.text_changed.connect(self._on_cell_text_changed)
                    self._cells.append(cell)
                grid.addWidget(cell, row_idx, col_idx)

        # Distribuir filas uniformemente
        for i in range(len(weeks)):
            grid.setRowStretch(i, 1)
        for j in range(7):
            grid.setColumnStretch(j, 1)

        # Reemplazar el contenedor en el scroll area
        if self._grid_container is not None:
            self._grid_container.deleteLater()
        self._grid_container = new_container
        self._scroll_area.setWidget(new_container)

        self._update_month_label()

        # Cargar notas desde el presenter si está disponible
        if self._presenter is not None:
            self._presenter.on_view_activated()

    # ------------------------------------------------------------------
    # Navegación de mes
    # ------------------------------------------------------------------

    def _on_prev_month(self) -> None:
        """Retrocede un mes y reconstruye el grid."""
        if self._current_month == 1:
            self._current_month = 12
            self._current_year -= 1
        else:
            self._current_month -= 1
        self._rebuild_grid()

    def _on_next_month(self) -> None:
        """Avanza un mes y reconstruye el grid."""
        if self._current_month == 12:
            self._current_month = 1
            self._current_year += 1
        else:
            self._current_month += 1
        self._rebuild_grid()

    def _update_month_label(self) -> None:
        """Actualiza el texto del label con el mes y año actuales."""
        if self._month_label is not None:
            name = _MONTH_NAMES[self._current_month - 1]
            self._month_label.setText(f"{name}  {self._current_year}")

    # ------------------------------------------------------------------
    # Auto-save con debounce
    # ------------------------------------------------------------------

    def _on_cell_text_changed(self, date_key: str, text: str) -> None:
        """Registra el cambio pendiente y reinicia el temporizador de guardado.

        Args:
            date_key: Clave ``YYYY-MM-DD`` de la celda modificada.
            text: Texto actual del editor.
        """
        self._pending_saves[date_key] = text
        self._autosave_timer.start(_DEBOUNCE_MS)

    def _flush_pending_saves(self) -> None:
        """Delega todos los cambios pendientes al presenter y limpia el buffer."""
        if self._presenter is None:
            self._pending_saves.clear()
            return
        for date_key, text in self._pending_saves.items():
            self._presenter.on_note_changed(date_key, text)
        self._pending_saves.clear()

    # ------------------------------------------------------------------
    # ICalendarView — interfaz pública requerida por el presenter
    # ------------------------------------------------------------------

    def load_notes(self, notes: dict[str, str]) -> None:
        """Carga el diccionario de notas en las celdas del grid actual.

        Args:
            notes: Mapa ``{YYYY-MM-DD: texto}`` con todas las notas guardadas.
        """
        for cell in self._cells:
            text = notes.get(cell.date_key, "")
            cell.set_text(text)

    def show_status(self, message: str) -> None:
        """Muestra un mensaje de estado (reservado para uso futuro).

        Args:
            message: Texto informativo.
        """
        # Actualmente no hay un label de estado en la vista del calendario.
        pass

    # ------------------------------------------------------------------
    # Ciclo de vida (hook de MainWindow)
    # ------------------------------------------------------------------

    def set_presenter(self, presenter: CalendarPresenter) -> None:
        """Inyecta el presenter y carga las notas del mes actual.

        Args:
            presenter: Instancia de ``CalendarPresenter`` ya configurada.
        """
        self._presenter = presenter
        presenter.on_view_activated()

    def on_view_activated(self) -> None:
        """Carga las notas del mes visible. Llamado por ``MainWindow._on_tab_changed``."""
        if self._presenter is not None:
            self._presenter.on_view_activated()
