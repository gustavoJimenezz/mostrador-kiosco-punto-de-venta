"""Implementación JSON del repositorio de carrito borrador.

Persiste el carrito en progreso en ``~/.kiosco_pos/draft_cart.json``.
Usa escritura atómica (archivo temporal + os.replace) para garantizar que
un corte de luz durante el guardado no deje el archivo corrupto.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class JsonDraftCartRepository:
    """Repositorio de carrito borrador basado en archivo JSON.

    Guarda el estado del carrito en ``~/.kiosco_pos/draft_cart.json``.
    La escritura es atómica: se escribe en un archivo temporal en el mismo
    directorio y luego se reemplaza con ``os.replace``, que es atómico en
    sistemas POSIX y en Windows (NTFS).

    Args:
        path: Ruta opcional al archivo de borrador. Por defecto usa
              ``~/.kiosco_pos/draft_cart.json``.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Inicializa el repositorio con la ruta al archivo de borrador.

        Args:
            path: Ruta al archivo JSON. Si es None, usa el valor por defecto.
        """
        self._path: Path = path or (Path.home() / ".kiosco_pos" / "draft_cart.json")

    def save(self, cart: dict[int, int]) -> None:
        """Persiste el carrito en el archivo JSON de forma atómica.

        Si el directorio padre no existe, lo crea. La escritura usa un archivo
        temporal en el mismo directorio para garantizar atomicidad.

        Args:
            cart: Diccionario ``{product_id: quantity}``.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Convertir claves a string (JSON solo admite strings como claves)
        data = {str(pid): qty for pid, qty in cart.items()}

        tmp_path = self._path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp_path, self._path)
        except OSError:
            # Si falla el reemplazo, limpiar el temporal
            tmp_path.unlink(missing_ok=True)
            raise

    def load(self) -> dict[int, int]:
        """Carga el borrador desde el archivo JSON.

        Returns:
            Diccionario ``{product_id: quantity}``. Retorna ``{}`` si el
            archivo no existe o tiene formato inválido.
        """
        if not self._path.exists():
            return {}

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {int(pid): int(qty) for pid, qty in raw.items() if int(qty) > 0}
        except (json.JSONDecodeError, ValueError, KeyError):
            # Archivo corrupto: tratar como sin borrador
            return {}

    def clear(self) -> None:
        """Elimina el archivo de borrador si existe."""
        self._path.unlink(missing_ok=True)

    def has_draft(self) -> bool:
        """Indica si existe un borrador con al menos un ítem.

        Returns:
            True si el archivo existe y contiene ítems válidos.
        """
        return bool(self.load())
