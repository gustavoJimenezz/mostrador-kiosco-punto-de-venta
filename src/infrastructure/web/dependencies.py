"""Dependency injection para FastAPI.

Provee sesiones SQLAlchemy, repositorios y validación de autenticación
como dependencias inyectables en los routers.
"""

from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.infrastructure.persistence.sqlite_product_repository import (
    SqliteProductRepository,
)
from src.infrastructure.persistence.mariadb_cash_repository import (
    MariadbCashRepository,
)
from src.infrastructure.persistence.mariadb_sale_repository import (
    MariadbSaleRepository,
)
from src.infrastructure.persistence.mariadb_user_repository import (
    MariadbUserRepository,
)
from src.infrastructure.persistence.mariadb_category_repository import (
    MariaDbCategoryRepository,
)


def get_session(request: Request) -> Generator[Session, None, None]:
    """Provee una sesión SQLAlchemy por request.

    Obtiene la ``session_factory`` del estado de la app (inicializado en el
    lifespan de ``app.py``). La sesión se cierra automáticamente al finalizar
    el request, con rollback si ocurre una excepción no manejada.

    Yields:
        Session SQLAlchemy activa para el request.
    """
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def require_auth(request: Request) -> dict:
    """Verifica que el request tenga una sesión de usuario autenticada.

    Lee la sesión HTTP (cookie firmada por SessionMiddleware). Si no hay
    sesión activa, retorna 401.

    Args:
        request: Request HTTP de FastAPI/Starlette.

    Returns:
        Dict con ``user_id``, ``user_name`` y ``user_role``.

    Raises:
        HTTPException 401: Si no hay sesión activa.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Inicie sesión primero.",
        )
    return {
        "user_id": user_id,
        "user_name": request.session.get("user_name"),
        "user_role": request.session.get("user_role"),
    }


def require_admin(auth: dict = Depends(require_auth)) -> dict:
    """Verifica que el usuario autenticado tenga rol ADMIN.

    Args:
        auth: Dict de sesión provisto por ``require_auth``.

    Returns:
        El mismo dict de sesión si el rol es admin.

    Raises:
        HTTPException 403: Si el usuario no es ADMIN.
    """
    if auth.get("user_role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol ADMIN para esta operación.",
        )
    return auth


def get_product_repo(session: Session = Depends(get_session)) -> SqliteProductRepository:
    """Provee el repositorio de productos para la sesión actual."""
    return SqliteProductRepository(session)


def get_cash_repo(session: Session = Depends(get_session)) -> MariadbCashRepository:
    """Provee el repositorio de arqueos de caja."""
    return MariadbCashRepository(session)


def get_sale_repo(session: Session = Depends(get_session)) -> MariadbSaleRepository:
    """Provee el repositorio de ventas."""
    return MariadbSaleRepository(session)


def get_user_repo(session: Session = Depends(get_session)) -> MariadbUserRepository:
    """Provee el repositorio de usuarios."""
    return MariadbUserRepository(session)


def get_category_repo(session: Session = Depends(get_session)) -> MariaDbCategoryRepository:
    """Provee el repositorio de categorías."""
    return MariaDbCategoryRepository(session)
