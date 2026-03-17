"""Puerto de dominio: repositorio de categorías.

Define el contrato que deben implementar los adaptadores de infraestructura
para persistir y recuperar categorías.
"""

from __future__ import annotations

from typing import Optional
from typing import runtime_checkable, Protocol

from src.domain.models.category import Category


@runtime_checkable
class CategoryRepository(Protocol):
    """Protocolo de repositorio para la entidad Category.

    Cualquier implementación (MariaDB, InMemory, etc.) debe satisfacer
    esta interfaz para ser usada en los casos de uso.
    """

    def get_by_name(self, name: str) -> Optional[Category]:
        """Busca una categoría por nombre (búsqueda normalizada, case-insensitive).

        Args:
            name: Nombre de la categoría a buscar.

        Returns:
            ``Category`` si existe, ``None`` si no se encuentra.
        """
        ...

    def save(self, category: Category) -> Category:
        """Persiste una categoría nueva o actualiza una existente.

        Si ``category.id`` es None, se realiza un INSERT y se asigna el id
        generado. Si tiene id, se hace UPDATE.

        Args:
            category: Entidad a persistir.

        Returns:
            La misma entidad con el ``id`` asignado por la DB.
        """
        ...

    def list_all(self) -> list[Category]:
        """Retorna todas las categorías persistidas.

        Returns:
            Lista de categorías (puede ser vacía).
        """
        ...
