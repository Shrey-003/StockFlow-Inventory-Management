from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas import ProductUpdate, ProductWrite, ReservationCreate


def test_product_write_normalizes_sku_and_whitespace():
    product = ProductWrite(
        name=" Mechanical Keyboard ",
        sku="sf-keyboard-001",
        description="Office keyboard",
        price=Decimal("79.99"),
        stock_quantity=25,
    )

    assert product.name == "Mechanical Keyboard"
    assert product.sku == "SF-KEYBOARD-001"
    assert product.price == Decimal("79.99")
    assert product.stock_quantity == 25


@pytest.mark.parametrize("price", ["-0.01", "-10.00"])
def test_product_rejects_negative_price(price):
    with pytest.raises(ValidationError):
        ProductWrite(
            name="Test Product",
            sku="SF-TEST-001",
            price=Decimal(price),
            stock_quantity=1,
        )


def test_product_rejects_negative_stock():
    with pytest.raises(ValidationError):
        ProductWrite(
            name="Test Product",
            sku="SF-TEST-002",
            price=Decimal("10.00"),
            stock_quantity=-1,
        )


def test_product_update_changes_only_supplied_fields():
    update = ProductUpdate(
        description=" Updated description "
    )

    assert update.model_dump(exclude_unset=True) == {
        "description": "Updated description"
    }


def test_product_update_rejects_empty_payload():
    with pytest.raises(ValidationError):
        ProductUpdate()


def test_product_update_rejects_null_price():
    with pytest.raises(ValidationError):
        ProductUpdate(price=None)


def test_reservation_defaults_to_15_minutes():
    reservation = ReservationCreate(quantity=1)

    assert reservation.quantity == 1
    assert reservation.ttl_minutes == 15


@pytest.mark.parametrize("quantity", [0, -1])
def test_reservation_rejects_nonpositive_quantity(quantity):
    with pytest.raises(ValidationError):
        ReservationCreate(quantity=quantity)


@pytest.mark.parametrize("ttl", [0, 121])
def test_reservation_rejects_invalid_expiry_duration(ttl):
    with pytest.raises(ValidationError):
        ReservationCreate(quantity=1, ttl_minutes=ttl)
