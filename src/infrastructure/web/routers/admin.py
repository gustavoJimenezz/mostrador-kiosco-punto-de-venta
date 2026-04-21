"""Router del panel de administración.

Endpoints:
    GET    /api/products           — listar todos los productos
    POST   /api/products           — crear producto
    PUT    /api/products/{id}      — actualizar producto
    DELETE /api/products/{id}      — eliminar producto
    GET    /api/categories         — listar categorías
    POST   /api/categories         — crear categoría
    DELETE /api/categories/{id}    — eliminar categoría
    GET    /api/users              — listar usuarios (solo admin)
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from uuid import UUID

from src.domain.models.product import Product
from src.domain.models.category import Category
from src.infrastructure.persistence.sqlite_product_repository import SqliteProductRepository
from src.infrastructure.persistence.mariadb_category_repository import MariaDbCategoryRepository
from src.infrastructure.persistence.mariadb_sale_repository import MariadbSaleRepository
from src.infrastructure.persistence.mariadb_user_repository import MariadbUserRepository
from src.infrastructure.web.dependencies import (
    get_category_repo,
    get_product_repo,
    get_sale_repo,
    get_session,
    get_user_repo,
    require_admin,
    require_auth,
)

router = APIRouter(prefix="/api", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProductResponse(BaseModel):
    id: int
    barcode: str
    name: str
    current_cost: str
    margin_percent: str
    current_price: str
    stock: int
    min_stock: int
    category_id: Optional[int]


class ProductCreateRequest(BaseModel):
    barcode: str
    name: str
    current_cost: str
    margin_percent: str = "30.00"
    final_price: Optional[str] = None  # si se envía, tiene prioridad sobre margin_percent
    stock: int = 0
    min_stock: int = 0
    category_id: Optional[int] = None


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    current_cost: Optional[str] = None
    margin_percent: Optional[str] = None
    final_price: Optional[str] = None  # si se envía, tiene prioridad sobre margin_percent
    stock: Optional[int] = None
    min_stock: Optional[int] = None
    category_id: Optional[int] = None


class CategoryResponse(BaseModel):
    id: int
    name: str


class CategoryCreateRequest(BaseModel):
    name: str


class CategoryUpdateRequest(BaseModel):
    name: str


class UserResponse(BaseModel):
    id: int
    name: str
    role: str
    is_active: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _margin_from_price(cost: Decimal, price: Decimal) -> Decimal:
    """Calcula el margen exacto que produce ``price`` dado ``cost``.

    Usa aritmética Decimal de alta precisión y redondea a 4 decimales
    (Numeric(15,4)) para garantizar que ``cost * (1 + margin/100)``
    vuelva al mismo centavo via ROUND_HALF_UP.

    Args:
        cost: Costo del producto.
        price: Precio final deseado.

    Returns:
        Margen en porcentaje redondeado a 4 decimales.
    """
    if cost == Decimal("0"):
        return Decimal("0.0000")
    margin = ((price / cost) - Decimal("1")) * Decimal("100")
    return margin.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _product_to_response(p: Product) -> ProductResponse:
    return ProductResponse(
        id=p.id,
        barcode=p.barcode,
        name=p.name,
        current_cost=str(p.current_cost),
        margin_percent=str(p.margin_percent),
        current_price=str(p.current_price.amount),
        stock=p.stock,
        min_stock=p.min_stock,
        category_id=p.category_id,
    )


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------

@router.get("/products", response_model=list[ProductResponse])
def list_products(
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    _auth: dict = Depends(require_auth),
):
    """Lista todos los productos del catálogo ordenados por nombre."""
    return [_product_to_response(p) for p in product_repo.list_all()]


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreateRequest,
    session: Session = Depends(get_session),
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    _auth: dict = Depends(require_admin),
):
    """Crea un nuevo producto en el catálogo."""
    try:
        cost = Decimal(body.current_cost)
        if body.final_price is not None:
            margin = _margin_from_price(cost, Decimal(body.final_price))
        else:
            margin = Decimal(body.margin_percent)
        product = Product(
            barcode=body.barcode,
            name=body.name,
            current_cost=cost,
            margin_percent=margin,
            stock=body.stock,
            min_stock=body.min_stock,
            category_id=body.category_id,
        )
        saved = product_repo.save(product)
        session.commit()
    except (ValueError, Exception) as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _product_to_response(saved)


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    body: ProductUpdateRequest,
    session: Session = Depends(get_session),
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    _auth: dict = Depends(require_admin),
):
    """Actualiza campos de un producto existente."""
    product = product_repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto id={product_id} no encontrado.",
        )

    try:
        if body.name is not None:
            product.name = body.name
        if body.current_cost is not None:
            product.update_cost(Decimal(body.current_cost))
        # final_price tiene prioridad sobre margin_percent
        if body.final_price is not None:
            new_cost = Decimal(body.current_cost) if body.current_cost is not None else product.current_cost
            product.update_margin(_margin_from_price(new_cost, Decimal(body.final_price)))
        elif body.margin_percent is not None:
            product.update_margin(Decimal(body.margin_percent))
        if body.stock is not None:
            product.stock = body.stock
        if body.min_stock is not None:
            product.min_stock = body.min_stock
        if body.category_id is not None:
            product.category_id = body.category_id

        saved = product_repo.save(product)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _product_to_response(saved)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    session: Session = Depends(get_session),
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    _auth: dict = Depends(require_admin),
):
    """Elimina un producto del catálogo."""
    product_repo.delete(product_id)
    session.commit()


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    category_repo: MariaDbCategoryRepository = Depends(get_category_repo),
    _auth: dict = Depends(require_auth),
):
    """Lista todas las categorías disponibles."""
    return [CategoryResponse(id=c.id, name=c.name) for c in category_repo.list_all()]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreateRequest,
    session: Session = Depends(get_session),
    category_repo: MariaDbCategoryRepository = Depends(get_category_repo),
    _auth: dict = Depends(require_admin),
):
    """Crea una nueva categoría."""
    try:
        category = Category(name=body.name.strip())
        saved = category_repo.save(category)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CategoryResponse(id=saved.id, name=saved.name)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    body: CategoryUpdateRequest,
    session: Session = Depends(get_session),
    category_repo: MariaDbCategoryRepository = Depends(get_category_repo),
    _auth: dict = Depends(require_admin),
):
    """Actualiza el nombre de una categoría existente."""
    try:
        category = Category(name=body.name.strip(), id=category_id)
        saved = category_repo.save(category)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CategoryResponse(id=saved.id, name=saved.name)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
    category_repo: MariaDbCategoryRepository = Depends(get_category_repo),
    _auth: dict = Depends(require_admin),
):
    """Elimina una categoría. Los productos asociados quedan sin categoría (SET NULL)."""
    category_repo.delete(category_id)
    session.commit()


# ---------------------------------------------------------------------------
# Ventas — cancelación
# ---------------------------------------------------------------------------

@router.delete("/sales/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_sale(
    sale_id: str,
    sale_repo: MariadbSaleRepository = Depends(get_sale_repo),
    _auth: dict = Depends(require_admin),
):
    """Cancela una venta y restaura el stock de sus ítems.

    Operación de soft delete: marca la venta como cancelada y revierte
    el stock. Solo accesible por ADMIN.

    Raises:
        HTTPException 404: Si la venta no existe.
        HTTPException 409: Si la venta ya está cancelada.
    """
    try:
        sale_repo.cancel_sale(UUID(sale_id))
    except ValueError as exc:
        msg = str(exc)
        if "no encontrada" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from exc


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserResponse])
def list_users(
    user_repo: MariadbUserRepository = Depends(get_user_repo),
    _auth: dict = Depends(require_admin),
):
    """Lista todos los usuarios del sistema (solo accesible por ADMIN)."""
    users = user_repo.list_active()
    return [
        UserResponse(id=u.id, name=u.name, role=u.role.value, is_active=u.is_active)
        for u in users
    ]
