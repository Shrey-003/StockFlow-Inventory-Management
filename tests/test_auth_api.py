from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from models import Reservation, RevokedToken, User
from security import decode_access_token, hash_token_identifier


def create_test_product(client, sku="AUTH-TEST-001"):
    response = client.post(
        "/products",
        json={
            "name": "Authentication Test Product",
            "sku": sku,
            "price": "20.00",
            "stock_quantity": 20,
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def test_login_returns_access_token_and_current_user(
    anonymous_client,
    test_api_setup,
):
    response = anonymous_client.post(
        "/auth/login",
        json={
            "username": "testadmin",
            "password": test_api_setup["passwords"]["admin"],
        },
    )

    assert response.status_code == 200, response.text
    token_data = response.json()

    assert token_data["token_type"] == "bearer"
    assert token_data["access_token"]
    assert token_data["expires_in"] == 1800

    me_response = anonymous_client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token_data['access_token']}"
        },
    )

    assert me_response.status_code == 200
    user_data = me_response.json()

    assert user_data["username"] == "testadmin"
    assert user_data["role"] == "admin"
    assert "password_hash" not in user_data


def test_login_rejects_invalid_credentials(
    anonymous_client,
    test_api_setup,
):
    response = anonymous_client.post(
        "/auth/login",
        json={
            "username": "testadmin",
            "password": "Incorrect-Password-2026!",
        },
    )

    assert response.status_code == 401


def test_login_rejects_unknown_user(anonymous_client):
    response = anonymous_client.post(
        "/auth/login",
        json={
            "username": "unknownuser",
            "password": "Unknown-Password-2026!",
        },
    )

    assert response.status_code == 401


def test_anonymous_users_cannot_access_protected_routes(
    anonymous_client,
):
    assert anonymous_client.get("/health").status_code == 200
    assert anonymous_client.get("/products").status_code == 401
    assert anonymous_client.get("/reservations").status_code == 401
    assert anonymous_client.get("/auth/me").status_code == 401

    response = anonymous_client.post(
        "/products",
        json={
            "name": "Unauthorized Product",
            "sku": "AUTH-UNAUTH-001",
            "price": "10.00",
            "stock_quantity": 1,
        },
    )

    assert response.status_code == 401


def test_staff_can_view_products_but_cannot_manage_them(
    client,
    staff_client,
):
    product = create_test_product(client, sku="AUTH-ROLE-001")
    product_id = product["id"]

    assert staff_client.get("/products").status_code == 200
    assert staff_client.get(
        f"/products/{product_id}"
    ).status_code == 200

    response = staff_client.post(
        "/products",
        json={
            "name": "Staff Product",
            "sku": "AUTH-ROLE-002",
            "price": "10.00",
            "stock_quantity": 1,
        },
    )
    assert response.status_code == 403

    response = staff_client.patch(
        f"/products/{product_id}",
        json={"price": "25.00"},
    )
    assert response.status_code == 403

    response = staff_client.delete(f"/products/{product_id}")
    assert response.status_code == 403

    assert client.get(f"/products/{product_id}").status_code == 200


def test_staff_can_only_view_and_cancel_own_reservations(
    client,
    staff_client,
    other_staff_client,
    test_engine,
    test_api_setup,
):
    product = create_test_product(client, sku="AUTH-OWNER-001")

    response = staff_client.post(
        f"/products/{product['id']}/reservations",
        json={"quantity": 2, "ttl_minutes": 15},
    )

    assert response.status_code == 201, response.text
    reservation_id = response.json()["id"]

    with Session(test_engine) as db:
        reservation = db.get(Reservation, reservation_id)
        assert reservation is not None
        assert reservation.user_id == test_api_setup["user_ids"]["staff"]

    own_list = staff_client.get("/reservations")
    assert own_list.status_code == 200
    assert [r["id"] for r in own_list.json()] == [reservation_id]

    other_list = other_staff_client.get("/reservations")
    assert other_list.status_code == 200
    assert other_list.json() == []

    assert staff_client.get(
        f"/reservations/{reservation_id}"
    ).status_code == 200

    assert other_staff_client.get(
        f"/reservations/{reservation_id}"
    ).status_code == 404

    assert other_staff_client.post(
        f"/reservations/{reservation_id}/cancel"
    ).status_code == 404

    own_cancel = staff_client.post(
        f"/reservations/{reservation_id}/cancel"
    )
    assert own_cancel.status_code == 200
    assert own_cancel.json()["status"] == "cancelled"

    assert client.get(
        f"/reservations/{reservation_id}"
    ).status_code == 200

    admin_list = client.get("/reservations")
    assert reservation_id in [
        item["id"] for item in admin_list.json()
    ]


def test_admin_can_cancel_another_users_reservation(
    client,
    staff_client,
):
    product = create_test_product(
        client,
        sku="AUTH-ADMIN-CANCEL-001",
    )

    response = staff_client.post(
        f"/products/{product['id']}/reservations",
        json={"quantity": 1, "ttl_minutes": 15},
    )

    assert response.status_code == 201
    reservation_id = response.json()["id"]

    response = client.post(
        f"/reservations/{reservation_id}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_inactive_user_cannot_use_existing_token(
    staff_client,
    test_engine,
    test_api_setup,
):
    user_id = test_api_setup["user_ids"]["staff"]

    with Session(test_engine) as db:
        user = db.get(User, user_id)
        assert user is not None
        user.is_active = False
        db.commit()

    response = staff_client.get("/products")
    assert response.status_code == 401


def test_worker_endpoint_rejects_missing_and_invalid_tokens(
    anonymous_client,
    worker_client,
):
    response = anonymous_client.post("/reservations/expire-due")
    assert response.status_code == 401

    response = anonymous_client.post(
        "/reservations/expire-due",
        headers={"X-Worker-Token": "incorrect-worker-token"},
    )
    assert response.status_code == 401

    response = worker_client.post("/reservations/expire-due")
    assert response.status_code == 200
    assert response.json() == {"expired_count": 0}


def test_admin_jwt_cannot_replace_worker_token(client):
    response = client.post("/reservations/expire-due")
    assert response.status_code == 401

def test_login_rejects_short_wrong_password_as_unauthorized(
    anonymous_client,
    test_api_setup,
):
    response = anonymous_client.post(
        "/auth/login",
        json={
            "username": "testadmin",
            "password": "wrong",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."

def test_unknown_user_login_still_verifies_password(
    anonymous_client,
    monkeypatch,
):
    import auth_routes

    verification_calls = 0
    original_verify_password = auth_routes.verify_password

    def tracked_verify_password(password, password_hash):
        nonlocal verification_calls
        verification_calls += 1
        return original_verify_password(password, password_hash)

    monkeypatch.setattr(
        auth_routes,
        "verify_password",
        tracked_verify_password,
    )

    response = anonymous_client.post(
        "/auth/login",
        json={
            "username": "nonexistent_user",
            "password": "Unknown-Password-2026!",
        },
    )

    assert response.status_code == 401
    assert verification_calls == 1

def test_inactive_user_login_still_verifies_dummy_password(
    anonymous_client,
    monkeypatch,
    test_engine,
    test_api_setup,
):
    import auth_routes

    user_id = test_api_setup["user_ids"]["staff"]

    with Session(test_engine) as db:
        user = db.get(User, user_id)
        assert user is not None
        user.is_active = False
        db.commit()

    verification_hashes = []
    original_verify_password = auth_routes.verify_password

    def tracked_verify_password(password, password_hash):
        verification_hashes.append(password_hash)
        return original_verify_password(password, password_hash)

    monkeypatch.setattr(
        auth_routes,
        "verify_password",
        tracked_verify_password,
    )

    response = anonymous_client.post(
        "/auth/login",
        json={
            "username": "teststaff",
            "password": "Inactive-Password-2026!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."
    assert verification_hashes == [auth_routes.DUMMY_PASSWORD_HASH]

def test_logout_revokes_current_token(client):
    logout_response = client.post("/auth/logout")

    assert logout_response.status_code == 204

    protected_response = client.get("/products")

    assert protected_response.status_code == 401


def test_logout_revokes_only_current_session(
    anonymous_client,
    test_api_setup,
):
    credentials = {
        "username": "testadmin",
        "password": test_api_setup["passwords"]["admin"],
    }

    first_login = anonymous_client.post(
        "/auth/login",
        json=credentials,
    )
    second_login = anonymous_client.post(
        "/auth/login",
        json=credentials,
    )

    assert first_login.status_code == 200
    assert second_login.status_code == 200

    first_token = first_login.json()["access_token"]
    second_token = second_login.json()["access_token"]

    assert first_token != second_token

    logout_response = anonymous_client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert logout_response.status_code == 204

    first_session = anonymous_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    second_session = anonymous_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert first_session.status_code == 401
    assert second_session.status_code == 200


def test_logout_requires_authentication(anonymous_client):
    response = anonymous_client.post("/auth/logout")

    assert response.status_code == 401

def test_logout_stores_only_hashed_jti(client, test_engine):
    authorization = client.headers["Authorization"]
    token = authorization.removeprefix("Bearer ")

    claims = decode_access_token(token)

    assert claims is not None
    assert claims["jti"]

    response = client.post("/auth/logout")

    assert response.status_code == 204

    expected_hash = hash_token_identifier(claims["jti"])

    with Session(test_engine) as db:
        revoked_token = db.get(RevokedToken, expected_hash)

        assert revoked_token is not None
        assert revoked_token.jti_hash == expected_hash
        assert revoked_token.jti_hash != claims["jti"]

def test_logout_cleans_expired_revocation_records(
    client,
    test_engine,
):
    expired_hash = "f" * 64
    now = datetime.now(timezone.utc)

    with Session(test_engine) as db:
        db.add(
            RevokedToken(
                jti_hash=expired_hash,
                expires_at=now - timedelta(seconds=10),
            )
        )
        db.commit()

    response = client.post("/auth/logout")

    assert response.status_code == 204

    with Session(test_engine) as db:
        expired_record = db.get(RevokedToken, expired_hash)

    assert expired_record is None