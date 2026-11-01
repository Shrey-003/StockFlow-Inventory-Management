from datetime import datetime, timedelta, timezone

import jwt
import pytest

from config import settings
from security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verification():
    password = "StockFlow-Strong-Password-2026"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("Wrong-Password-2026", hashed)


@pytest.mark.parametrize(
    "password",
    [
        "",
        "short",
        "a" * 129,
    ],
)
def test_hash_password_rejects_invalid_length(password):
    with pytest.raises(ValueError):
        hash_password(password)


def test_access_token_creation_and_validation():
    token = create_access_token(
        subject="42",
        role="admin",
    )

    claims = decode_access_token(token)

    assert claims is not None
    assert claims["sub"] == "42"
    assert claims["role"] == "admin"
    assert claims["token_type"] == "access"
    assert claims["exp"] > claims["iat"]
    assert claims["jti"]


def test_access_token_rejects_tampering():
    token = create_access_token(
        subject="42",
        role="staff",
    )

    tampered_token = token[:-1] + (
        "A" if token[-1] != "A" else "B"
    )

    assert decode_access_token(tampered_token) is None


def test_access_token_rejects_expired_token():
    now = datetime.now(timezone.utc)

    expired_token = jwt.encode(
        {
            "sub": "42",
            "role": "staff",
            "token_type": "access",
            "jti": "expired-token-id",
            "iat": int((now - timedelta(minutes=10)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(expired_token) is None


def test_access_token_rejects_invalid_role():
    now = datetime.now(timezone.utc)

    invalid_role_token = jwt.encode(
        {
            "sub": "42",
            "role": "superuser",
            "token_type": "access",
            "jti": "invalid-role-token-id",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(invalid_role_token) is None


def test_access_token_rejects_wrong_token_type():
    now = datetime.now(timezone.utc)

    wrong_type_token = jwt.encode(
        {
            "sub": "42",
            "role": "staff",
            "token_type": "refresh",
            "jti": "wrong-type-token-id",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(wrong_type_token) is None


def test_access_token_rejects_empty_token():
    assert decode_access_token("") is None


@pytest.mark.parametrize(
    ("subject", "role"),
    [
        ("", "admin"),
        ("42", "superuser"),
    ],
)
def test_access_token_rejects_invalid_claims(subject, role):
    with pytest.raises(ValueError):
        create_access_token(subject=subject, role=role)


@pytest.mark.parametrize(
    "missing_claim",
    ["sub", "role", "token_type", "iat", "exp", "jti"],
)
def test_access_token_rejects_missing_required_claims(missing_claim):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": "42",
        "role": "staff",
        "token_type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": "test-token-identifier",
    }

    payload.pop(missing_claim)

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(token) is None


def test_access_tokens_have_unique_jti():
    first_token = create_access_token(
        subject="42",
        role="admin",
    )

    second_token = create_access_token(
        subject="42",
        role="admin",
    )

    first_claims = decode_access_token(first_token)
    second_claims = decode_access_token(second_token)

    assert first_claims is not None
    assert second_claims is not None
    assert first_claims["jti"] != second_claims["jti"]