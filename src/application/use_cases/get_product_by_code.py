"""Caso de uso: obtener un producto por su código de barras.

Encapsula la búsqueda por EAN-13 (u otro código) delegando al
ProductRepository sin exponer detalles de infraestructura.
"""

from __future__ import annotations

from typing import Optional

from src.domain.models.product import Product
from src.domain.ports.product_repository import ProductRepository


class GetProductByCode:
    """Caso de uso: busca un producto por su código de barras.

    Args:
        product_repo: Repositorio de productos (ProductRepository protocol).

    Examples:
        >>> repo = InMemoryProductRepository()
        >>> uc = GetProductByCode(repo)
        >>> product = uc.execute("7790895000115")  # None si no existe en el catálogo
    """

    def __init__(self, product_repo: ProductRepository) -> None:
        """Inicializa el caso de uso con el repositorio inyectado.

        Args:
            product_repo: Implementación de ProductRepository a usar.
        """
        self._repo = product_repo

    def execute(self, barcode: str) -> Optional[Product]:
        """Busca un producto por su código de barras.

        Args:
            barcode: Código EAN-13 u otro código del producto.

        Returns:
            Product si se encuentra en el catálogo, None si no existe.

        Raises:
            ValueError: Si el barcode está vacío o contiene solo espacios.
        """
        if not barcode or not barcode.strip():
            raise ValueError("El código de barras no puede estar vacío.")
        return self._repo.get_by_barcode(barcode.strip())
