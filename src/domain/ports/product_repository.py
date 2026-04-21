"""Puerto de salida: contrato de persistencia para productos.

Define la interfaz que cualquier adaptador de infraestructura (MariaDB,
repositorio en memoria, etc.) debe implementar para ser inyectado en
los casos de uso del dominio.

El dominio solo conoce este Protocol; nunca importa SQLAlchemy ni MariaDB.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.domain.models.product import Product


@runtime_checkable
class ProductRepository(Protocol):
    """Puerto de salida para persistencia de productos.

    Cualquier adaptador de infraestructura (MariaDB, memoria, etc.)
    debe implementar esta interfaz para ser inyectado en los casos de uso.

    Examples:
        >>> class MockRepo:
        ...     def get_by_barcode(self, barcode: str) -> Optional[Product]: ...
        ...     def get_by_id(self, product_id: int) -> Optional[Product]: ...
        ...     def save(self, product: Product) -> Product: ...
        ...     def search_by_name(self, query: str) -> list[Product]: ...
        ...     def list_all(self) -> list[Product]: ...
        ...     def delete(self, product_id: int) -> None: ...
        >>> isinstance(MockRepo(), ProductRepository)
        True
    """

    def get_by_barcode(self, barcode: str) -> Optional[Product]:
        """Busca un producto por su código de barras (EAN-13).

        Args:
            barcode: Código de barras del producto.

        Returns:
            Product si existe, None si no se encuentra.
        """
        ...

    def get_by_id(self, product_id: int) -> Optional[Product]:
        """Busca un producto por su ID de base de datos.

        Args:
            product_id: Identificador primario del producto.

        Returns:
            Product si existe, None si no se encuentra.
        """
        ...

    def save(self, product: Product) -> Product:
        """Persiste un producto nuevo o actualiza uno existente.

        Args:
            product: Entidad Product a guardar.

        Returns:
            Product con el ID asignado por la DB (en caso de inserción nueva).
        """
        ...

    def search_by_name(self, query: str) -> list[Product]:
        """Busca productos por nombre (búsqueda fuzzy/parcial).

        La implementación debe cumplir: < 50ms con 5,000 registros.

        Args:
            query: Texto parcial del nombre a buscar.

        Returns:
            Lista de productos cuyo nombre contiene el query (puede ser vacía).
        """
        ...

    def search_by_barcode(self, query: str) -> list[Product]:
        """Busca productos por coincidencia parcial de código de barras.

        Args:
            query: Secuencia parcial de dígitos a buscar en el barcode.

        Returns:
            Lista de hasta 50 productos cuyo barcode contiene el query.
        """
        ...

    def list_all(self) -> list[Product]:
        """Retorna todos los productos del catálogo.

        Returns:
            Lista de todos los productos (puede ser vacía).
        """
        ...

    def delete(self, product_id: int) -> None:
        """Elimina un producto por su ID.

        Si el producto no existe, la operación es silenciosa (no lanza excepción).

        Args:
            product_id: Identificador primario del producto a eliminar.
        """
        ...
