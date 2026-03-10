"""Implementación en memoria de ProductRepository para tests unitarios.

No requiere base de datos. Cumple el contrato definido en el puerto
ProductRepository. Usada en todos los tests de dominio que necesiten
un repositorio de productos.
"""

from __future__ import annotations

from typing import Optional

from src.domain.models.product import Product


class InMemoryProductRepository:
    """Repositorio de productos en memoria que implementa ProductRepository.

    Almacena productos en un dict indexado por ID. Asigna IDs secuenciales
    al persistir productos nuevos (sin ID).

    Examples:
        >>> from decimal import Decimal
        >>> repo = InMemoryProductRepository()
        >>> p = Product(barcode="001", name="Test", current_cost=Decimal("100"), margin_percent=Decimal("30"))
        >>> saved = repo.save(p)
        >>> saved.id
        1
    """

    def __init__(self) -> None:
        self._store: dict[int, Product] = {}
        self._next_id: int = 1

    def get_by_barcode(self, barcode: str) -> Optional[Product]:
        """Busca un producto por código de barras.

        Args:
            barcode: Código de barras del producto.

        Returns:
            Product si existe, None si no se encuentra.
        """
        for product in self._store.values():
            if product.barcode == barcode:
                return product
        return None

    def get_by_id(self, product_id: int) -> Optional[Product]:
        """Busca un producto por su ID.

        Args:
            product_id: Identificador primario del producto.

        Returns:
            Product si existe, None si no se encuentra.
        """
        return self._store.get(product_id)

    def save(self, product: Product) -> Product:
        """Persiste un producto nuevo o actualiza uno existente.

        Args:
            product: Entidad Product a guardar.

        Returns:
            Product con el ID asignado (muta el objeto recibido).
        """
        if product.id is None:
            product.id = self._next_id
            self._next_id += 1
        self._store[product.id] = product
        return product

    def search_by_name(self, query: str) -> list[Product]:
        """Busca productos por nombre (parcial, case-insensitive).

        Args:
            query: Texto parcial del nombre a buscar.

        Returns:
            Lista de productos cuyo nombre contiene el query.
        """
        query_lower = query.lower()
        return [p for p in self._store.values() if query_lower in p.name.lower()]

    def list_all(self) -> list[Product]:
        """Retorna todos los productos almacenados.

        Returns:
            Lista de todos los productos (puede ser vacía).
        """
        return list(self._store.values())

    def delete(self, product_id: int) -> None:
        """Elimina un producto por su ID.

        Si el producto no existe, la operación es silenciosa.

        Args:
            product_id: Identificador primario del producto a eliminar.
        """
        self._store.pop(product_id, None)
