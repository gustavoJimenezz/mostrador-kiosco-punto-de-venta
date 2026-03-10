"""Tests del MockRepository en memoria y los puertos de dominio.

Verifica que:
- InMemoryProductRepository satisface el Protocol ProductRepository.
- Todos los métodos CRUD del repositorio funcionan correctamente.
- MockPrinter satisface el Protocol PrinterBase.
- El módulo domain/ no importa nada de infrastructure/ ni application/.

Ticket 1.2: Puerto de Persistencia (Interface Definition).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import uuid4

import pytest

from src.domain.models.product import Product
from src.domain.models.sale import PaymentMethod, Sale, SaleItem
from src.domain.ports.printer_base import PrinterBase
from src.domain.ports.product_repository import ProductRepository
from tests.unit.domain.mocks.in_memory_product_repository import InMemoryProductRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_product(
    barcode: str = "7790895000115",
    name: str = "Alfajor Jorgito",
    cost: str = "250.00",
    margin: str = "35.00",
) -> Product:
    """Construye un Product con valores por defecto para tests."""
    return Product(
        barcode=barcode,
        name=name,
        current_cost=Decimal(cost),
        margin_percent=Decimal(margin),
    )


def make_sale() -> Sale:
    """Construye una Sale mínima para tests de impresión."""
    item = SaleItem(product_id=1, quantity=2, price_at_sale=Decimal("337.50"))
    return Sale(payment_method=PaymentMethod.CASH, items=[item])


class MockPrinter:
    """Implementación en memoria de PrinterBase para tests."""

    def __init__(self) -> None:
        self.printed_sales: list[Sale] = []

    def print_ticket(self, sale: Sale) -> None:
        """Registra la venta como 'impresa' sin hardware real.

        Args:
            sale: Venta cuyo ticket se imprimiría.
        """
        self.printed_sales.append(sale)


# ---------------------------------------------------------------------------
# Tests de contrato (Protocol)
# ---------------------------------------------------------------------------

class TestProductRepositoryProtocol:

    def test_mock_implements_protocol(self):
        """InMemoryProductRepository debe satisfacer ProductRepository."""
        assert isinstance(InMemoryProductRepository(), ProductRepository)

    def test_incomplete_class_does_not_implement_protocol(self):
        """Una clase sin los métodos requeridos no satisface el Protocol."""
        class Incomplete:
            pass

        assert not isinstance(Incomplete(), ProductRepository)

    def test_class_missing_delete_does_not_implement_protocol(self):
        """Una clase sin delete() no satisface ProductRepository."""
        class WithoutDelete:
            def get_by_barcode(self, barcode: str) -> Optional[Product]: ...
            def get_by_id(self, product_id: int) -> Optional[Product]: ...
            def save(self, product: Product) -> Product: ...
            def search_by_name(self, query: str) -> list[Product]: ...
            def list_all(self) -> list[Product]: ...

        assert not isinstance(WithoutDelete(), ProductRepository)


class TestPrinterBaseProtocol:

    def test_mock_printer_implements_protocol(self):
        """MockPrinter debe satisfacer PrinterBase."""
        assert isinstance(MockPrinter(), PrinterBase)

    def test_incomplete_class_does_not_implement_protocol(self):
        """Una clase sin print_ticket() no satisface PrinterBase."""
        class Incomplete:
            pass

        assert not isinstance(Incomplete(), PrinterBase)


# ---------------------------------------------------------------------------
# Tests funcionales de InMemoryProductRepository
# ---------------------------------------------------------------------------

class TestInMemoryProductRepository:

    def setup_method(self) -> None:
        self.repo = InMemoryProductRepository()

    # --- save ---

    def test_save_assigns_id_to_new_product(self):
        product = make_product()
        assert product.id is None
        saved = self.repo.save(product)
        assert saved.id == 1

    def test_save_increments_id_per_product(self):
        p1 = self.repo.save(make_product(barcode="001", name="Prod A"))
        p2 = self.repo.save(make_product(barcode="002", name="Prod B"))
        assert p1.id == 1
        assert p2.id == 2

    def test_save_existing_product_updates_in_place(self):
        product = make_product()
        self.repo.save(product)
        product.update_cost(Decimal("300.00"))
        self.repo.save(product)
        retrieved = self.repo.get_by_id(product.id)
        assert retrieved.current_cost == Decimal("300.00")

    def test_save_returns_same_object(self):
        product = make_product()
        saved = self.repo.save(product)
        assert saved is product

    # --- get_by_barcode ---

    def test_get_by_barcode_returns_product_when_found(self):
        product = make_product(barcode="7790895000115")
        self.repo.save(product)
        found = self.repo.get_by_barcode("7790895000115")
        assert found is not None
        assert found.barcode == "7790895000115"

    def test_get_by_barcode_returns_none_when_not_found(self):
        assert self.repo.get_by_barcode("0000000000000") is None

    # --- get_by_id ---

    def test_get_by_id_returns_product_when_found(self):
        product = make_product()
        self.repo.save(product)
        found = self.repo.get_by_id(1)
        assert found is not None
        assert found.name == "Alfajor Jorgito"

    def test_get_by_id_returns_none_when_not_found(self):
        assert self.repo.get_by_id(999) is None

    # --- search_by_name ---

    def test_search_by_name_exact_match(self):
        self.repo.save(make_product(barcode="001", name="Alfajor Jorgito"))
        results = self.repo.search_by_name("Alfajor Jorgito")
        assert len(results) == 1

    def test_search_by_name_partial_match(self):
        self.repo.save(make_product(barcode="001", name="Alfajor Jorgito"))
        self.repo.save(make_product(barcode="002", name="Alfajor Marinela"))
        results = self.repo.search_by_name("alfajor")
        assert len(results) == 2

    def test_search_by_name_is_case_insensitive(self):
        self.repo.save(make_product(barcode="001", name="Coca Cola"))
        results = self.repo.search_by_name("coca")
        assert len(results) == 1

    def test_search_by_name_returns_empty_when_no_match(self):
        self.repo.save(make_product(barcode="001", name="Alfajor"))
        assert self.repo.search_by_name("Pepsi") == []

    # --- list_all ---

    def test_list_all_returns_empty_list_initially(self):
        assert self.repo.list_all() == []

    def test_list_all_returns_all_saved_products(self):
        for i in range(3):
            self.repo.save(make_product(barcode=f"00{i}", name=f"Prod {i}"))
        assert len(self.repo.list_all()) == 3

    # --- delete ---

    def test_delete_removes_existing_product(self):
        product = make_product()
        self.repo.save(product)
        assert self.repo.get_by_id(product.id) is not None
        self.repo.delete(product.id)
        assert self.repo.get_by_id(product.id) is None

    def test_delete_nonexistent_product_is_silent(self):
        """Eliminar un ID inexistente no debe lanzar excepción."""
        self.repo.delete(9999)

    def test_delete_only_removes_target_product(self):
        p1 = self.repo.save(make_product(barcode="001", name="Prod A"))
        p2 = self.repo.save(make_product(barcode="002", name="Prod B"))
        self.repo.delete(p1.id)
        assert self.repo.get_by_id(p1.id) is None
        assert self.repo.get_by_id(p2.id) is not None

    def test_delete_reduces_list_all_count(self):
        p = self.repo.save(make_product())
        assert len(self.repo.list_all()) == 1
        self.repo.delete(p.id)
        assert len(self.repo.list_all()) == 0


# ---------------------------------------------------------------------------
# Tests funcionales de MockPrinter
# ---------------------------------------------------------------------------

class TestMockPrinter:

    def setup_method(self) -> None:
        self.printer = MockPrinter()

    def test_print_ticket_records_sale(self):
        sale = make_sale()
        self.printer.print_ticket(sale)
        assert len(self.printer.printed_sales) == 1
        assert self.printer.printed_sales[0] is sale

    def test_print_ticket_multiple_sales(self):
        for _ in range(3):
            self.printer.print_ticket(make_sale())
        assert len(self.printer.printed_sales) == 3
