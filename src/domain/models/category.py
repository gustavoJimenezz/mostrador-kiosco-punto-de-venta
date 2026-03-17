"""Entidad de dominio Category.

Representa una categoría del catálogo de productos (ej: "Golosinas", "Bebidas").
Python puro, sin dependencias externas. El mapeo ORM vive en infrastructure/persistence/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Category:
    """Entidad que representa una categoría de productos.

    Attributes:
        name: Nombre de la categoría (único, max 100 caracteres).
        id: Identificador único (asignado por la DB; None antes de persistir).

    Examples:
        >>> c = Category(name="Golosinas")
        >>> c.name
        'Golosinas'
    """

    name: str
    id: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Valida invariantes de la entidad tras la inicialización.

        Raises:
            ValueError: Si el nombre está vacío o supera 100 caracteres.
        """
        if not self.name or not self.name.strip():
            raise ValueError("El nombre de la categoría no puede estar vacío.")
        if len(self.name) > 100:
            raise ValueError(
                "El nombre de la categoría no puede superar 100 caracteres."
            )
