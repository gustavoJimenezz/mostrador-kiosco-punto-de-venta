"""Mock in-memory de CategoryRepository para tests unitarios.

No requiere base de datos. Implementa el protocolo ``CategoryRepository``
usando un diccionario en memoria.
"""

from __future__ import annotations

from typing import Optional

from src.domain.models.category import Category


class InMemoryCategoryRepository:
    """Implementación en memoria de CategoryRepository para tests.

    Almacena categorías en un dict ``{id: Category}``. El id se autoincrementa
    internamente. La búsqueda por nombre es case-insensitive con strip().
    """

    def __init__(self) -> None:
        self._store: dict[int, Category] = {}
        self._next_id: int = 1

    def get_by_name(self, name: str) -> Optional[Category]:
        """Busca una categoría por nombre (case-insensitive, con trim).

        Args:
            name: Nombre a buscar.

        Returns:
            ``Category`` si existe, ``None`` si no se encuentra.
        """
        normalized = name.strip().lower()
        for cat in self._store.values():
            if cat.name.strip().lower() == normalized:
                return cat
        return None

    def save(self, category: Category) -> Category:
        """Persiste una categoría nueva (INSERT) o actualiza una existente (UPDATE).

        Args:
            category: Entidad a persistir.

        Returns:
            La misma entidad con el ``id`` asignado.
        """
        if category.id is None:
            category.id = self._next_id
            self._next_id += 1
        self._store[category.id] = category
        return category

    def list_all(self) -> list[Category]:
        """Retorna todas las categorías ordenadas por nombre.

        Returns:
            Lista de ``Category`` (puede ser vacía).
        """
        return sorted(self._store.values(), key=lambda c: c.name)
