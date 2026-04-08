"""Adaptador SQLite de ProductRepository.

Hereda de MariadbProductRepository y sobreescribe únicamente la búsqueda
FullText (MATCH...AGAINST), que no existe en SQLite, por una búsqueda ILIKE.
Todo el resto de la lógica (get_by_barcode, save, list_all, delete) es
idéntica y se reutiliza sin cambios.
"""

from __future__ import annotations

from src.infrastructure.persistence.mariadb_product_repository import (
    MariadbProductRepository,
)
from src.domain.models.product import Product


class SqliteProductRepository(MariadbProductRepository):
    """Implementación de ``ProductRepository`` sobre SQLite.

    La única diferencia con ``MariadbProductRepository`` es la búsqueda
    por nombre: SQLite no tiene FullText index, se usa ILIKE en su lugar.
    El rendimiento es aceptable para catálogos de hasta ~5,000 SKUs en
    hardware modesto (Pentium E5700 con 8 GB RAM).
    """

    def _search_by_name_fulltext(self, query: str) -> list[Product]:
        """Sobreescribe MATCH...AGAINST con ILIKE para compatibilidad SQLite.

        En MariaDB este método usa el índice FullText. En SQLite no existe ese
        índice, por lo que se delega directamente a ``_search_by_name_ilike``.

        Args:
            query: Texto de búsqueda (>= 3 caracteres por contrato del padre).

        Returns:
            Lista de hasta 50 productos cuyo nombre contiene ``query``.
        """
        return self._search_by_name_ilike(query)
