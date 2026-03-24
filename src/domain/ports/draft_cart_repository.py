"""Puerto para la persistencia del carrito borrador.

Define el contrato que cualquier implementación de almacenamiento de borrador
debe satisfacer. Permite recuperar la venta en progreso tras un cierre
inesperado (corte de luz, fallo del sistema).
"""

from __future__ import annotations

from typing import Protocol


class DraftCartRepository(Protocol):
    """Contrato para persistir y restaurar el carrito borrador.

    El carrito borrador almacena únicamente ``{product_id: quantity}``
    (sin precios ni nombres). Los datos completos del producto se obtienen
    de la base de datos al restaurar.

    La implementación debe garantizar escritura atómica para evitar
    corrupción del archivo ante cortes de luz durante la operación de guardado.
    """

    def save(self, cart: dict[int, int]) -> None:
        """Persiste el estado actual del carrito.

        Args:
            cart: Diccionario ``{product_id: quantity}`` con los ítems actuales.
                  Un dict vacío indica que el carrito está limpio.
        """
        ...

    def load(self) -> dict[int, int]:
        """Carga el borrador guardado.

        Returns:
            Diccionario ``{product_id: quantity}``. Retorna ``{}`` si no existe
            ningún borrador o si el archivo está corrupto.
        """
        ...

    def clear(self) -> None:
        """Elimina el borrador guardado.

        Debe llamarse al completar o cancelar una venta para evitar
        restauraciones involuntarias en la próxima sesión.
        """
        ...

    def has_draft(self) -> bool:
        """Indica si existe un borrador guardado con al menos un ítem.

        Returns:
            True si hay un borrador válido con ítems pendientes.
        """
        ...
