from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import Reservation


def get_stock(client, product_id):
    response = client.get(f"/products/{product_id}")
    assert response.status_code == 200, response.text
    return response.json()["stock_quantity"]


def create_reservation(client, product_id, quantity, ttl_minutes=15):
    response = client.post(
        f"/products/{product_id}/reservations",
        json={
            "quantity": quantity,
            "ttl_minutes": ttl_minutes,
        },
    )
    return response


def test_reservation_creation_deducts_stock(client):
    product_response = client.post(
        "/products",
        json={
            "name": "Reservation Test Product",
            "sku": "SF-TEST-CREATE-001",
            "description": "Integration test",
            "price": "12.50",
            "stock_quantity": 10,
        },
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()

    response = create_reservation(client, product["id"], quantity=3)

    assert response.status_code == 201, response.text
    reservation = response.json()

    assert reservation["product_id"] == product["id"]
    assert reservation["quantity"] == 3
    assert reservation["status"] == "active"
    assert get_stock(client, product["id"]) == 7


def test_insufficient_stock_does_not_change_inventory(client):
    product_response = client.post(
        "/products",
        json={
            "name": "Insufficient Stock Test",
            "sku": "SF-TEST-STOCK-001",
            "price": "10.00",
            "stock_quantity": 10,
        },
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()

    response = create_reservation(client, product["id"], quantity=11)

    assert response.status_code == 409, response.text
    assert get_stock(client, product["id"]) == 10

    reservations_response = client.get("/reservations")
    assert reservations_response.status_code == 200
    assert reservations_response.json() == []


def test_cancellation_restores_inventory(client):
    product_response = client.post(
        "/products",
        json={
            "name": "Cancellation Test Product",
            "sku": "SF-TEST-CANCEL-001",
            "price": "15.00",
            "stock_quantity": 10,
        },
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()

    create_response = create_reservation(
        client, product["id"], quantity=4
    )
    assert create_response.status_code == 201, create_response.text
    reservation = create_response.json()

    assert get_stock(client, product["id"]) == 6

    cancel_response = client.post(
        f"/reservations/{reservation['id']}/cancel"
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"
    assert get_stock(client, product["id"]) == 10


def test_repeated_cancellation_does_not_restore_stock_twice(client):
    product_response = client.post(
        "/products",
        json={
            "name": "Repeated Cancellation Test",
            "sku": "SF-TEST-CANCEL-002",
            "price": "20.00",
            "stock_quantity": 10,
        },
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()

    create_response = create_reservation(
        client, product["id"], quantity=2
    )
    assert create_response.status_code == 201, create_response.text
    reservation_id = create_response.json()["id"]

    first_cancel = client.post(
        f"/reservations/{reservation_id}/cancel"
    )
    assert first_cancel.status_code == 200, first_cancel.text
    assert get_stock(client, product["id"]) == 10

    second_cancel = client.post(
        f"/reservations/{reservation_id}/cancel"
    )
    assert second_cancel.status_code == 409, second_cancel.text
    assert get_stock(client, product["id"]) == 10


def test_expiration_restores_inventory(client, worker_client, test_engine):
    product_response = client.post(
        "/products",
        json={
            "name": "Expiration Test Product",
            "sku": "SF-TEST-EXPIRY-001",
            "price": "25.00",
            "stock_quantity": 10,
        },
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()

    create_response = create_reservation(
        client, product["id"], quantity=3
    )
    assert create_response.status_code == 201, create_response.text
    reservation_id = create_response.json()["id"]

    assert get_stock(client, product["id"]) == 7

    # Make this test reservation overdue without waiting for the TTL.
    with Session(test_engine) as db:
        reservation = db.get(Reservation, reservation_id)
        assert reservation is not None

        reservation.expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.commit()

    expiry_response = worker_client.post("/reservations/expire-due")
    assert expiry_response.status_code == 200, expiry_response.text

    detail_response = client.get(f"/reservations/{reservation_id}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "expired"
    assert get_stock(client, product["id"]) == 10

def test_list_reservations_returns_newest_first(client):
    product_response = client.post(
        "/products",
        json={
            "name": "Reservation Listing Test",
            "sku": "SF-TEST-LIST-001",
            "price": "10.00",
            "stock_quantity": 5,
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    created_ids = []

    for _ in range(3):
        response = create_reservation(client, product_id, quantity=1)
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])

    response = client.get("/reservations")
    assert response.status_code == 200, response.text

    listed_ids = [item["id"] for item in response.json()]
    assert listed_ids == list(reversed(created_ids))


def test_list_reservations_supports_pagination(client):
    product_response = client.post(
        "/products",
        json={
            "name": "Reservation Pagination Test",
            "sku": "SF-TEST-PAGE-001",
            "price": "10.00",
            "stock_quantity": 5,
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    created_ids = []

    for _ in range(3):
        response = create_reservation(client, product_id, quantity=1)
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])

    response = client.get(
        "/reservations",
        params={"skip": 1, "limit": 1},
    )
    assert response.status_code == 200, response.text

    listed = response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == list(reversed(created_ids))[1]
