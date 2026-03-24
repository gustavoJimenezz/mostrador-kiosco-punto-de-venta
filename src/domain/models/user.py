"""Entidad User: representa un operador o administrador del sistema POS."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class UserRole(Enum):
    """Roles disponibles en el sistema POS.

    Attributes:
        ADMIN: Acceso completo (configuración, productos, importación).
        OPERATOR: Acceso restringido (solo ventas).
    """

    ADMIN = "admin"
    OPERATOR = "operator"


@dataclass
class User:
    """Representa un usuario del sistema POS.

    Args:
        name: Nombre para mostrar en la UI de login.
        role: Rol que determina el acceso a funcionalidades.
        pin_hash: Hash bcrypt del PIN numérico. Nunca almacenar en texto plano.
        is_active: Si es False, el usuario no puede iniciar sesión.
        id: Identificador único asignado por la DB (0 = no persistido aún).
    """

    name: str
    role: UserRole
    pin_hash: str
    is_active: bool = True
    id: int = field(default=0)
