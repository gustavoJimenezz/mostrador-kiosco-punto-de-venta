"""Presenter del calendario mensual (MVP).

Gestiona la carga y persistencia de notas diarias en un archivo JSON local.
No interactúa con la base de datos ni con Qt directamente.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ICalendarView(Protocol):
    """Contrato que debe cumplir la vista del calendario.

    El presenter depende de esta interfaz, no de la clase concreta,
    siguiendo el principio de inversión de dependencias.
    """

    def load_notes(self, notes: dict[str, str]) -> None:
        """Carga el diccionario completo de notas en la vista.

        Args:
            notes: Mapa ``{YYYY-MM-DD: texto}`` con todas las notas guardadas.
        """
        ...

    def show_status(self, message: str) -> None:
        """Muestra un mensaje de estado informativo en la vista.

        Args:
            message: Texto a mostrar.
        """
        ...


class CalendarPresenter:
    """Presenter del calendario de mes completo.

    Carga y persiste notas diarias en ``notes_file_path`` (JSON).
    La escritura es sincrónica dado que el archivo es pequeño (< 50 KB
    para varios años de notas) y la operación tarda < 1 ms.

    Args:
        view: Vista que implementa ``ICalendarView``.
        notes_file_path: Ruta al archivo JSON de notas.
    """

    def __init__(self, view: ICalendarView, notes_file_path: Path) -> None:
        self._view = view
        self._notes_file = notes_file_path
        self._notes: dict[str, str] = self._load_from_disk()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def on_view_activated(self) -> None:
        """Carga las notas guardadas en la vista activa.

        Llamado por ``CalendarView.on_view_activated()`` cada vez que
        el usuario navega a la pestaña Calendario.
        """
        self._view.load_notes(self._notes)

    # ------------------------------------------------------------------
    # Persistencia de notas
    # ------------------------------------------------------------------

    def on_note_changed(self, date_key: str, text: str) -> None:
        """Actualiza la nota de una fecha y persiste el estado en disco.

        Args:
            date_key: Clave de fecha en formato ``YYYY-MM-DD``.
            text: Texto nuevo. Si está vacío se elimina la entrada del dict.
        """
        if text.strip():
            self._notes[date_key] = text
        else:
            self._notes.pop(date_key, None)

        self._persist_to_disk()

    # ------------------------------------------------------------------
    # Helpers de I/O
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> dict[str, str]:
        """Lee el archivo JSON de notas.

        Returns:
            Dict ``{YYYY-MM-DD: texto}`` o ``{}`` si el archivo no existe
            o está corrupto.
        """
        if not self._notes_file.exists():
            return {}
        try:
            with self._notes_file.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo leer %s: %s", self._notes_file, exc)
        return {}

    def _persist_to_disk(self) -> None:
        """Escribe el estado actual de notas en el archivo JSON.

        Crea el directorio padre si no existe.
        """
        try:
            self._notes_file.parent.mkdir(parents=True, exist_ok=True)
            with self._notes_file.open("w", encoding="utf-8") as fh:
                json.dump(self._notes, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error("No se pudo guardar %s: %s", self._notes_file, exc)
