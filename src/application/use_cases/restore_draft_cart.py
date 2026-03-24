"""Caso de uso: restaurar carrito borrador desde persistencia.

Carga el borrador guardado, busca cada producto en la base de datos y
retorna la lista de ítems listos para poblar el carrito del presenter.
"""

from __future__ import annotations

from src.domain.models.product import Product
from src.domain.ports.draft_cart_repository import DraftCartRepository
from src.domain.ports.product_repository import ProductRepository


class RestoreDraftCart:
    """Restaura el carrito en progreso desde el borrador persistido.

    Consulta cada ``product_id`` en la base de datos para obtener el
    producto actualizado (precio y stock vigentes). Si un producto fue
    eliminado del catálogo, se omite silenciosamente. Si la cantidad
    guardada supera el stock actual, se recorta al máximo disponible.

    Args:
        draft_repo: Repositorio que provee el borrador ``{product_id: quantity}``.
        product_repo: Repositorio de productos para obtener datos actualizados.
    """

    def __init__(
        self,
        draft_repo: DraftCartRepository,
        product_repo: ProductRepository,
    ) -> None:
        """Inicializa el caso de uso con sus dependencias.

        Args:
            draft_repo: Implementación del repositorio de borrador.
            product_repo: Implementación del repositorio de productos.
        """
        self._draft_repo = draft_repo
        self._product_repo = product_repo

    def execute(self) -> list[tuple[Product, int]]:
        """Ejecuta la restauración del carrito borrador.

        Returns:
            Lista de tuplas ``(Product, quantity)`` validadas contra el stock
            actual. Puede ser vacía si el borrador estaba vacío, todos los
            productos fueron eliminados o no había stock disponible.
        """
        cart = self._draft_repo.load()
        if not cart:
            return []

        result: list[tuple[Product, int]] = []

        for product_id, saved_qty in cart.items():
            product = self._product_repo.get_by_id(product_id)
            if product is None:
                # Producto eliminado del catálogo entre sesiones
                continue

            capped_qty = min(saved_qty, product.stock)
            if capped_qty > 0:
                result.append((product, capped_qty))

        return result
