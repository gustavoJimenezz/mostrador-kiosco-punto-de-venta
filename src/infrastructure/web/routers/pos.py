"""Router del punto de venta (POS).

Endpoints:
    GET  /api/products/barcode/{barcode} — busca producto por código de barras
    GET  /api/products/search            — busca productos por nombre
    POST /api/sales                      — procesa una venta de forma atómica
    GET  /api/sales                      — lista ventas del día (historial)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.application.use_cases.get_product_by_code import GetProductByCode
from src.application.use_cases.process_sale import ProcessSale
from src.domain.models.sale import PaymentMethod
from src.infrastructure.persistence.mariadb_sale_repository import MariadbSaleRepository
from src.infrastructure.persistence.sqlite_product_repository import SqliteProductRepository
from src.infrastructure.web.dependencies import (
    get_cash_repo,
    get_product_repo,
    get_sale_repo,
    get_session,
    require_auth,
)

router = APIRouter(prefix="/api", tags=["pos"])


# ---------------------------------------------------------------------------
# Schemas de respuesta
# ---------------------------------------------------------------------------

class ProductResponse(BaseModel):
    id: int
    barcode: str
    name: str
    current_price: str   # Decimal serializado como str — nunca float
    stock: int
    category_id: Optional[int]


class SaleItemRequest(BaseModel):
    product_id: int
    qty: int


class SaleRequest(BaseModel):
    items: list[SaleItemRequest]
    payment_method: str   # "EFECTIVO" | "DEBITO" | "TRANSFERENCIA"
    cash_close_id: Optional[int] = None


class SaleItemResponse(BaseModel):
    product_id: int
    quantity: int
    price_at_sale: str   # Decimal como str


class SaleResponse(BaseModel):
    id: str
    timestamp: str
    total_amount: str
    payment_method: str
    items: list[SaleItemResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/products/barcode/{barcode}", response_model=ProductResponse)
def get_by_barcode(
    barcode: str,
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    _auth: dict = Depends(require_auth),
):
    """Busca un producto por código de barras (EAN-13).

    Equivalente al ``SearchByBarcodeWorker`` de la UI Qt anterior.

    Raises:
        HTTPException 404: Si el producto no existe en el catálogo.
    """
    try:
        product = GetProductByCode(product_repo).execute(barcode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con código '{barcode}' no encontrado.",
        )

    return ProductResponse(
        id=product.id,
        barcode=product.barcode,
        name=product.name,
        current_price=str(product.current_price.amount),
        stock=product.stock,
        category_id=product.category_id,
    )


@router.get("/products/search", response_model=list[ProductResponse])
def search_products(
    q: str = Query(..., min_length=1, description="Texto a buscar en el nombre"),
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    _auth: dict = Depends(require_auth),
):
    """Busca productos por nombre (ILIKE en SQLite, FullText en MariaDB).

    Equivalente al ``SearchByNameWorker`` de la UI Qt anterior.

    Returns:
        Lista de hasta 50 productos que coinciden con la búsqueda.
    """
    products = product_repo.search_by_name(q)
    return [
        ProductResponse(
            id=p.id,
            barcode=p.barcode,
            name=p.name,
            current_price=str(p.current_price.amount),
            stock=p.stock,
            category_id=p.category_id,
        )
        for p in products
    ]


@router.get("/products/search-barcode", response_model=list[ProductResponse])
def search_products_by_barcode(
    q: str = Query(..., min_length=1, description="Dígitos parciales del código de barras"),
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    _auth: dict = Depends(require_auth),
):
    """Busca productos por coincidencia parcial de código de barras.

    Permite buscar ingresando solo parte del barcode (ej: "7790" retorna
    todos los productos cuyo código contiene esa secuencia).

    Returns:
        Lista de hasta 50 productos cuyo barcode contiene ``q``.
    """
    products = product_repo.search_by_barcode(q)
    return [
        ProductResponse(
            id=p.id,
            barcode=p.barcode,
            name=p.name,
            current_price=str(p.current_price.amount),
            stock=p.stock,
            category_id=p.category_id,
        )
        for p in products
    ]


@router.post("/sales", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def process_sale(
    body: SaleRequest,
    session: Session = Depends(get_session),
    product_repo: SqliteProductRepository = Depends(get_product_repo),
    sale_repo: MariadbSaleRepository = Depends(get_sale_repo),
    _auth: dict = Depends(require_auth),
):
    """Procesa y persiste una venta de forma atómica.

    REGLA CRÍTICA: el ``price_at_sale`` de cada ítem se asigna aquí en el
    servidor desde ``product.current_price.amount``. El cliente solo envía
    ``product_id`` y ``qty`` — nunca el precio.

    La transacción es atómica: INSERT sale + INSERT sale_items + UPDATE stock
    ocurren en una sola operación. Si falla cualquier paso, se hace rollback.

    Raises:
        HTTPException 400: Carrito vacío, stock insuficiente o método de pago inválido.
        HTTPException 404: Algún product_id no existe en el catálogo.
    """
    # Validar método de pago
    try:
        payment_method = PaymentMethod(body.payment_method)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Método de pago inválido: '{body.payment_method}'. "
                   f"Valores válidos: {[m.value for m in PaymentMethod]}",
        )

    # Cargar productos desde DB — el precio lo dicta el servidor, nunca el cliente
    cart: dict[int, tuple] = {}
    for item in body.items:
        product = product_repo.get_by_id(item.product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con id={item.product_id} no encontrado.",
            )
        cart[item.product_id] = (product, item.qty)

    try:
        use_case = ProcessSale(sale_repo, product_repo)
        sale = use_case.execute(cart, payment_method, body.cash_close_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SaleResponse(
        id=str(sale.id),
        timestamp=sale.timestamp.isoformat(),
        total_amount=str(sale.total_amount.amount),
        payment_method=sale.payment_method.value,
        items=[
            SaleItemResponse(
                product_id=it.product_id,
                quantity=it.quantity,
                price_at_sale=str(it.price_at_sale),
            )
            for it in sale.items
        ],
    )


@router.get("/sales")
def list_sales(
    date: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    sale_repo: MariadbSaleRepository = Depends(get_sale_repo),
    _auth: dict = Depends(require_auth),
):
    """Lista ventas de un día con detalle de ítems (historial)."""
    try:
        start = datetime.fromisoformat(date + "T00:00:00")
        end = datetime.fromisoformat(date + "T23:59:59")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")

    sales = sale_repo.list_by_date_range(start, end)
    result = []
    for sale in sales:
        items_with_names = sale_repo.get_sale_items_with_names(sale.id)
        result.append({
            "id": str(sale.id),
            "timestamp": sale.timestamp.isoformat(),
            "total_amount": str(sale.total_amount.amount),
            "payment_method": sale.payment_method.value,
            "is_cancelled": sale.is_cancelled,
            "cancelled_at": sale.cancelled_at.isoformat() if sale.cancelled_at else None,
            "items": [
                {
                    "product_name": row.get("product_name", ""),
                    "quantity": row.get("quantity", 0),
                    "price_at_sale": str(row.get("price_at_sale", "0")),
                    "subtotal": str(row.get("subtotal", "0")),
                }
                for row in items_with_names
            ],
        })
    return result
