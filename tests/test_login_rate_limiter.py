
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import auth_routes
from sqlalchemy.orm import Session

from config import settings
from login_rate_limiter import (
    create_bucket_hash,
    enforce_login_rate_limit,
    increment_rate_limit_bucket,
)
from models import LoginRateLimit


def test_bucket_hash_is_stable_and_scope_specific():
    first = create_bucket_hash("ip", "192.0.2.10")
    repeated = create_bucket_hash("ip", "192.0.2.10")
    different_ip = create_bucket_hash("ip", "192.0.2.11")
    username_bucket = create_bucket_hash(
        "ip_username",
        "192.0.2.10",
        "testuser",
    )

    assert first == repeated
    assert len(first) == 64
    assert first != different_ip
    assert first != username_bucket
    assert "192.0.2.10" not in first


def test_expired_bucket_resets_window(test_engine, test_api_setup):
    bucket_hash = "a" * 64
    now = datetime.now(timezone.utc)
    window_seconds = settings.login_rate_limit_window_seconds
    old_start = now - timedelta(seconds=window_seconds + 10)
    cutoff = now - timedelta(seconds=window_seconds)

    with Session(test_engine) as db:
        db.add(
            LoginRateLimit(
                bucket_hash=bucket_hash,
                window_started_at=old_start,
                request_count=8,
            )
        )
        db.commit()

        new_start, count = increment_rate_limit_bucket(
            db,
            bucket_hash,
            now,
            cutoff,
        )
        db.commit()

    assert new_start == now
    assert count == 1


def test_concurrent_bucket_updates_are_atomic(
    test_engine,
    test_api_setup,
):
    bucket_hash = "b" * 64
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(
        seconds=settings.login_rate_limit_window_seconds
    )

    def increment_once(_):
        with Session(test_engine) as db:
            result = increment_rate_limit_bucket(
                db,
                bucket_hash,
                now,
                cutoff,
            )
            db.commit()
            return result[1]

    request_count = 24

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(increment_once, range(request_count))
        )

    with Session(test_engine) as db:
        bucket = db.get(LoginRateLimit, bucket_hash)

    assert bucket is not None
    assert bucket.request_count == request_count
    assert sorted(results) == list(range(1, request_count + 1))


def test_login_rate_limit_blocks_ip_username_bucket(
    anonymous_client,
    monkeypatch,
):
    monkeypatch.setattr(
        auth_routes,
        "verify_password",
        lambda password, password_hash: False,
    )

    payload = {
        "username": "unknown-rate-user",
        "password": "Test-Password-2026!",
    }

    for _ in range(settings.login_rate_limit_ip_username_max_attempts):
        response = anonymous_client.post("/auth/login", json=payload)
        assert response.status_code == 401

    blocked = anonymous_client.post("/auth/login", json=payload)

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == (
        "Too many login attempts. Please try again later."
    )
    assert int(blocked.headers["Retry-After"]) > 0


def test_login_rate_limit_blocks_ip_bucket(
    anonymous_client,
    monkeypatch,
):
    monkeypatch.setattr(
        auth_routes,
        "verify_password",
        lambda password, password_hash: False,
    )

    for index in range(settings.login_rate_limit_ip_max_attempts):
        response = anonymous_client.post(
            "/auth/login",
            json={
                "username": f"unknown-user-{index}",
                "password": "Test-Password-2026!",
            },
        )

        assert response.status_code == 401

    blocked = anonymous_client.post(
        "/auth/login",
        json={
            "username": "another-unknown-user",
            "password": "Test-Password-2026!",
        },
    )

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
