"""Tests unitarios para las entidades Sale, SaleItem y el enum PaymentMethod."""

import pytest
from decimal import Decimal
from uuid import UUID

from src.domain.models.sale import Sale, SaleItem, PaymentMethod
from src.domain.models.price import Price


def make_item(**kwargs) -> SaleItem:
    defaults = dict(product_id=1, quantity=1, price_at_sale=Decimal("100.00"))
    defaults.update(kwargs)
    return SaleItem(**defaults)


class TestSaleItem:

    def test_create_sale_item(self):
        item = make_item()
        assert item.product_id == 1
        assert item.quantity == 1
        assert item.price_at_sale == Decimal("100.00")

    def test_subtotal_single_unit(self):
        item = make_item(quantity=1, price_at_sale=Decimal("337.50"))
        assert item.subtotal.amount == Decimal("337.50")

    def test_subtotal_multiple_units(self):
        item = make_item(quantity=3, price_at_sale=Decimal("337.50"))
        assert item.subtotal.amount == Decimal("1012.50")

    def test_subtotal_returns_price_instance(self):
        item = make_item()
        assert isinstance(item.subtotal, Price)

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="mayor a cero"):
            make_item(quantity=0)

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError, match="mayor a cero"):
            make_item(quantity=-1)

    def test_negative_price_at_sale_raises(self):
        with pytest.raises(ValueError, match="negativo"):
            make_item(price_at_sale=Decimal("-0.01"))

    def test_zero_price_at_sale_allowed(self):
        """Precio cero es válido (ej: regalo, promoción)."""
        item = make_item(price_at_sale=Decimal("0"))
        assert item.subtotal.amount == Decimal("0.00")

    def test_is_immutable(self):
        item = make_item()
        with pytest.raises(Exception):
            item.quantity = 10


class TestPaymentMethod:

    def test_cash_value(self):
        assert PaymentMethod.CASH.value == "EFECTIVO"

    def test_debit_value(self):
        assert PaymentMethod.DEBIT.value == "DEBITO"

    def test_transfer_value(self):
        assert PaymentMethod.TRANSFER.value == "TRANSFERENCIA"

    def test_is_string_enum(self):
        assert isinstance(PaymentMethod.CASH, str)


class TestSale:

    def test_create_sale_with_one_item(self):
        item = make_item(price_at_sale=Decimal("200.00"))
        sale = Sale(payment_method=PaymentMethod.CASH, items=[item])
        assert sale.total_amount.amount == Decimal("200.00")

    def test_sale_id_is_uuid(self):
        item = make_item()
        sale = Sale(payment_method=PaymentMethod.CASH, items=[item])
        assert isinstance(sale.id, UUID)

    def test_sale_ids_are_unique(self):
        item = make_item()
        sale1 = Sale(payment_method=PaymentMethod.CASH, items=[item])
        sale2 = Sale(payment_method=PaymentMethod.CASH, items=[item])
        assert sale1.id != sale2.id

    def test_empty_items_raises(self):
        with pytest.raises(ValueError, match="al menos un ítem"):
            Sale(payment_method=PaymentMethod.CASH, items=[])

    def test_total_amount_sums_all_items(self):
        items = [
            make_item(quantity=2, price_at_sale=Decimal("100.00")),
            make_item(product_id=2, quantity=1, price_at_sale=Decimal("50.00")),
        ]
        sale = Sale(payment_method=PaymentMethod.DEBIT, items=items)
        assert sale.total_amount.amount == Decimal("250.00")

    def test_total_amount_returns_price_instance(self):
        item = make_item()
        sale = Sale(payment_method=PaymentMethod.CASH, items=[item])
        assert isinstance(sale.total_amount, Price)

    def test_item_count(self):
        items = [
            make_item(quantity=3),
            make_item(product_id=2, quantity=2),
        ]
        sale = Sale(payment_method=PaymentMethod.CASH, items=items)
        assert sale.item_count == 5

    def test_add_item(self):
        item1 = make_item(price_at_sale=Decimal("100.00"))
        sale = Sale(payment_method=PaymentMethod.CASH, items=[item1])
        item2 = make_item(product_id=2, quantity=2, price_at_sale=Decimal("50.00"))
        sale.add_item(item2)
        assert sale.total_amount.amount == Decimal("200.00")
        assert sale.item_count == 3

    def test_cash_close_id_default_none(self):
        item = make_item()
        sale = Sale(payment_method=PaymentMethod.TRANSFER, items=[item])
        assert sale.cash_close_id is None

    def test_total_with_rounding(self):
        """Prueba que el total acumulado se redondea correctamente."""
        items = [
            make_item(quantity=1, price_at_sale=Decimal("33.33")),
            make_item(product_id=2, quantity=1, price_at_sale=Decimal("33.34")),
            make_item(product_id=3, quantity=1, price_at_sale=Decimal("33.33")),
        ]
        sale = Sale(payment_method=PaymentMethod.CASH, items=items)
        assert sale.total_amount.amount == Decimal("100.00")
