"""Adaptador de infraestructura: implementación MariaDB del puerto CategoryRepository.

Implementa el protocolo ``CategoryRepository`` del dominio usando SQLAlchemy 2.0
Core (sin ORM mapeado). Consistente con el estilo de ``mariadb_product_repository.py``.

La gestión del ciclo de vida de la sesión (commit, rollback, close) es
responsabilidad del caso de uso o del composition root.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domain.models.category import Category
from src.infrastructure.persistence.tables import categories_table


class MariaDbCategoryRepository:
    """Implementación de ``CategoryRepository`` sobre MariaDB + SQLAlchemy 2.0.

    Usa SQLAlchemy Core directamente (sin mapeo imperativo ORM) para mantener
    el ciclo INSERT/SELECT simple y explícito.

    Args:
        session: Sesión SQLAlchemy activa. El repositorio NO hace commit ni
            rollback; solo opera dentro de la transacción abierta.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_name(self, name: str) -> Optional[Category]:
        """Busca una categoría por nombre (case-insensitive, con trim).

        Args:
            name: Nombre a buscar. Se normaliza a ``strip().lower()`` antes
                de comparar contra la DB.

        Returns:
            ``Category`` si existe, ``None`` si no se encuentra.
        """
        normalized = name.strip().lower()
        stmt = select(categories_table).where(
            func.lower(categories_table.c.name) == normalized
        )
        row = self._session.execute(stmt).first()
        if row is None:
            return None
        return Category(name=row.name, id=row.id)

    def save(self, category: Category) -> Category:
        """Persiste una categoría nueva (INSERT) o actualiza una existente (UPDATE).

        Args:
            category: Entidad a persistir. Si ``category.id`` es None se hace
                INSERT; si tiene id se hace UPDATE.

        Returns:
            La misma entidad con el ``id`` asignado o actualizado.
        """
        if category.id is None:
            result = self._session.execute(
                categories_table.insert().values(name=category.name)
            )
            category.id = result.inserted_primary_key[0]
        else:
            self._session.execute(
                categories_table.update()
                .where(categories_table.c.id == category.id)
                .values(name=category.name)
            )
        return category

    def list_all(self) -> list[Category]:
        """Retorna todas las categorías ordenadas por nombre.

        Returns:
            Lista de ``Category`` (puede ser vacía).
        """
        stmt = select(categories_table).order_by(categories_table.c.name)
        rows = self._session.execute(stmt).all()
        return [Category(name=row.name, id=row.id) for row in rows]
