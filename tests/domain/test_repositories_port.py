"""Tests del puerto ProductRepository mediante un MockRepository en memoria.

Verifica que el contrato (Protocol) sea correcto y ejercita
todos los métodos definidos en la interfaz.
Ticket 1.1 / 1.2: MockRepository como implementación de referencia para tests de dominio.
"""

from __future__ import annotations

import pytest
from decimal import Decimal
from typing import Optional

from src.domain.models.product import Product
from src.domain.ports.repositories import ProductRepository


class InMemoryProductRepository:
    """Implementación en memoria de ProductRepository para tests unitarios.

    No requiere base de datos. Cumple el contrato definido en el puerto.
    """

    def __init__(self) -> None:
        self._store: dict[int, Product] = {}
        self._next_id: int = 1

    def get_by_barcode(self, barcode: str) -> Optional[Product]:
        for product in self._store.values():
            if product.barcode == barcode:
                return product
        return None

    def get_by_id(self, product_id: int) -> Optional[Product]:
        return self._store.get(product_id)

    def save(self, product: Product) -> Product:
        if product.id is None:
            product.id = self._next_id
            self._next_id += 1
        self._store[product.id] = product
        return product

    def search_by_name(self, query: str) -> list[Product]:
        query_lower = query.lower()
        return [p for p in self._store.values() if query_lower in p.name.lower()]

    def list_all(self) -> list[Product]:
        return list(self._store.values())


def make_product(barcode: str = "7790895000115", name: str = "Alfajor Jorgito") -> Product:
    return Product(
        barcode=barcode,
        name=name,
        current_cost=Decimal("250.00"),
        margin_percent=Decimal("35.00"),
    )


class TestProductRepositoryProtocol:

    def test_mock_implements_protocol(self):
        """Verifica que InMemoryProductRepository satisface el Protocol."""
        assert isinstance(InMemoryProductRepository(), ProductRepository)

    def test_class_without_methods_does_not_implement_protocol(self):
        class Incomplete:
            pass
        assert not isinstance(Incomplete(), ProductRepository)


class TestInMemoryProductRepository:

    def setup_method(self):
        self.repo = InMemoryProductRepository()

    def test_save_assigns_id(self):
        product = make_product()
        assert product.id is None
        saved = self.repo.save(product)
        assert saved.id == 1

    def test_save_increments_id(self):
        p1 = self.repo.save(make_product(barcode="001", name="Prod A"))
        p2 = self.repo.save(make_product(barcode="002", name="Prod B"))
        assert p1.id == 1
        assert p2.id == 2

    def test_save_existing_product_updates(self):
        product = make_product()
        self.repo.save(product)
        product.update_cost(Decimal("300.00"))
        self.repo.save(product)
        retrieved = self.repo.get_by_id(product.id)
        assert retrieved.current_cost == Decimal("300.00")

    def test_get_by_barcode_found(self):
        product = make_product(barcode="7790895000115")
        self.repo.save(product)
        found = self.repo.get_by_barcode("7790895000115")
        assert found is not None
        assert found.barcode == "7790895000115"

    def test_get_by_barcode_not_found(self):
        found = self.repo.get_by_barcode("0000000000000")
        assert found is None

    def test_get_by_id_found(self):
        product = make_product()
        self.repo.save(product)
        found = self.repo.get_by_id(1)
        assert found is not None
        assert found.name == "Alfajor Jorgito"

    def test_get_by_id_not_found(self):
        found = self.repo.get_by_id(999)
        assert found is None

    def test_search_by_name_exact(self):
        self.repo.save(make_product(barcode="001", name="Alfajor Jorgito"))
        results = self.repo.search_by_name("Alfajor Jorgito")
        assert len(results) == 1

    def test_search_by_name_partial(self):
        self.repo.save(make_product(barcode="001", name="Alfajor Jorgito"))
        self.repo.save(make_product(barcode="002", name="Alfajor Marinela"))
        results = self.repo.search_by_name("alfajor")
        assert len(results) == 2

    def test_search_by_name_case_insensitive(self):
        self.repo.save(make_product(barcode="001", name="Coca Cola"))
        results = self.repo.search_by_name("coca")
        assert len(results) == 1

    def test_search_by_name_no_match(self):
        self.repo.save(make_product(barcode="001", name="Alfajor"))
        results = self.repo.search_by_name("Pepsi")
        assert len(results) == 0

    def test_list_all_empty(self):
        assert self.repo.list_all() == []

    def test_list_all_returns_all_products(self):
        self.repo.save(make_product(barcode="001", name="Prod A"))
        self.repo.save(make_product(barcode="002", name="Prod B"))
        self.repo.save(make_product(barcode="003", name="Prod C"))
        assert len(self.repo.list_all()) == 3
