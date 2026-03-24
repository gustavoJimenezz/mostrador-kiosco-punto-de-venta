"""Tests unitarios del caso de uso ProcessSale.

Verifica las reglas de negocio: validación de carrito vacío, stock
insuficiente, construcción correcta de SaleItems con price_at_sale
inmutable, y delegación atómica al SaleRepository.

No requiere base de datos. Usa InMemorySaleRepository y
InMemoryProductRepository.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.use_cases.process_sale import ProcessSale
from src.domain.models.product import Product
from src.domain.models.sale import PaymentMethod, Sale
from tests.unit.domain.mocks.in_memory_product_repository import (
    InMemoryProductRepository,
)
from tests.unit.domain.mocks.in_memory_sale_repository import InMemorySaleRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(
    product_id: int = 1,
    barcode: str = "7790001000001",
    name: str = "Alfajor Jorgito",
    cost: str = "250.00",
    margin: str = "35.00",
    stock: int = 10,
) -> Product:
    """Crea un Product de prueba con ID y stock asignados."""
    p = Product(
        barcode=barcode,
        name=name,
        current_cost=Decimal(cost),
        margin_percent=Decimal(margin),
        stock=stock,
    )
    p.id = product_id
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sale_repo() -> InMemorySaleRepository:
    return InMemorySaleRepository()


@pytest.fixture
def product_repo() -> InMemoryProductRepository:
    return InMemoryProductRepository()


@pytest.fixture
def use_case(
    sale_repo: InMemorySaleRepository,
    product_repo: InMemoryProductRepository,
) -> ProcessSale:
    return ProcessSale(sale_repo=sale_repo, product_repo=product_repo)


@pytest.fixture
def product() -> Product:
    return _make_product()


# ---------------------------------------------------------------------------
# Tests: validaciones de entrada
# ---------------------------------------------------------------------------


class TestProcessSaleValidation:
    def test_empty_cart_raises_value_error(self, use_case: ProcessSale) -> None:
        with pytest.raises(ValueError, match="vacío"):
            use_case.execute({}, PaymentMethod.CASH)

    def test_empty_cart_does_not_call_sale_repo(
        self,
        use_case: ProcessSale,
        sale_repo: InMemorySaleRepository,
    ) -> None:
        with pytest.raises(ValueError):
            use_case.execute({}, PaymentMethod.CASH)
        assert len(sale_repo.saved) == 0

    def test_insufficient_stock_raises_value_error(
        self, use_case: ProcessSale
    ) -> None:
        product = _make_product(stock=2)
        cart = {product.id: (product, 5)}

        with pytest.raises(ValueError, match="Stock insuficiente"):
            use_case.execute(cart, PaymentMethod.CASH)

    def test_insufficient_stock_error_includes_product_name(
        self, use_case: ProcessSale
    ) -> None:
        product = _make_product(name="Coca Cola", stock=1)
        cart = {product.id: (product, 3)}

        with pytest.raises(ValueError, match="Coca Cola"):
            use_case.execute(cart, PaymentMethod.CASH)

    def test_insufficient_stock_includes_available_and_required(
        self, use_case: ProcessSale
    ) -> None:
        product = _make_product(stock=2)
        cart = {product.id: (product, 4)}

        with pytest.raises(ValueError, match="disponible=2"):
            use_case.execute(cart, PaymentMethod.CASH)

    def test_exact_stock_quantity_is_allowed(
        self, use_case: ProcessSale, product: Product
    ) -> None:
        """Vender exactamente el stock disponible no debe lanzar error."""
        cart = {product.id: (product, product.stock)}
        sale = use_case.execute(cart, PaymentMethod.CASH)
        assert isinstance(sale, Sale)

    def test_insufficient_stock_does_not_persist_sale(
        self,
        use_case: ProcessSale,
        sale_repo: InMemorySaleRepository,
    ) -> None:
        product = _make_product(stock=1)
        cart = {product.id: (product, 2)}

        with pytest.raises(ValueError):
            use_case.execute(cart, PaymentMethod.CASH)
        assert len(sale_repo.saved) == 0


# ---------------------------------------------------------------------------
# Tests: construcción de la venta
# ---------------------------------------------------------------------------


class TestProcessSaleExecution:
    def test_returns_sale_instance(
        self, use_case: ProcessSale, product: Product
    ) -> None:
        cart = {product.id: (product, 1)}
        result = use_case.execute(cart, PaymentMethod.CASH)
        assert isinstance(result, Sale)

    def test_sale_has_correct_payment_method(
        self, use_case: ProcessSale, product: Product
    ) -> None:
        cart = {product.id: (product, 1)}
        sale = use_case.execute(cart, PaymentMethod.TRANSFER)
        assert sale.payment_method == PaymentMethod.TRANSFER

    def test_sale_items_count_matches_cart(
        self, use_case: ProcessSale
    ) -> None:
        p1 = _make_product(product_id=1, barcode="001")
        p2 = _make_product(product_id=2, barcode="002")
        cart = {p1.id: (p1, 1), p2.id: (p2, 2)}
        sale = use_case.execute(cart, PaymentMethod.CASH)
        assert len(sale.items) == 2

    def test_price_at_sale_matches_current_price(
        self, use_case: ProcessSale, product: Product
    ) -> None:
        """price_at_sale debe ser el snapshot del precio actual, no recalculado."""
        expected_price = product.current_price.amount
        cart = {product.id: (product, 1)}
        sale = use_case.execute(cart, PaymentMethod.CASH)
        assert sale.items[0].price_at_sale == expected_price

    def test_sale_item_quantity_matches_cart(
        self, use_case: ProcessSale, product: Product
    ) -> None:
        cart = {product.id: (product, 3)}
        sale = use_case.execute(cart, PaymentMethod.CASH)
        assert sale.items[0].quantity == 3

    def test_total_amount_correct_for_single_item(
        self, use_case: ProcessSale
    ) -> None:
        product = _make_product(cost="100.00", margin="0.00")
        cart = {product.id: (product, 2)}
        sale = use_case.execute(cart, PaymentMethod.CASH)
        assert sale.total_amount.amount == Decimal("200.00")

    def test_total_amount_correct_for_multiple_products(
        self, use_case: ProcessSale
    ) -> None:
        p1 = _make_product(product_id=1, barcode="001", cost="100.00", margin="0.00")
        p2 = _make_product(product_id=2, barcode="002", cost="200.00", margin="0.00")
        cart = {p1.id: (p1, 1), p2.id: (p2, 1)}
        sale = use_case.execute(cart, PaymentMethod.CASH)
        assert sale.total_amount.amount == Decimal("300.00")

    def test_sale_is_delegated_to_repository(
        self,
        use_case: ProcessSale,
        sale_repo: InMemorySaleRepository,
        product: Product,
    ) -> None:
        cart = {product.id: (product, 1)}
        sale = use_case.execute(cart, PaymentMethod.CASH)
        assert len(sale_repo.saved) == 1
        assert sale_repo.saved[0] is sale

    def test_sale_repo_called_exactly_once(
        self,
        use_case: ProcessSale,
        sale_repo: InMemorySaleRepository,
        product: Product,
    ) -> None:
        cart = {product.id: (product, 1)}
        use_case.execute(cart, PaymentMethod.CASH)
        assert len(sale_repo.saved) == 1

    def test_repository_error_propagates(
        self,
        use_case: ProcessSale,
        sale_repo: InMemorySaleRepository,
        product: Product,
    ) -> None:
        """Si el repositorio falla, la excepción se propaga al caller."""
        sale_repo.fail_with = RuntimeError("DB connection lost")
        cart = {product.id: (product, 1)}

        with pytest.raises(RuntimeError, match="DB connection lost"):
            use_case.execute(cart, PaymentMethod.CASH)
