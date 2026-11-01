from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from config import settings


password_hasher = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"
VALID_ROLES = {"admin", "staff"}


def hash_password(password: str) -> str:
    """Hash a password using the recommended Argon2 configuration."""

    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError(
            "Password must contain between 12 and 128 characters."
        )

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain-text password against its stored hash."""

    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False

    if not password_hash:
        return False

    return password_hasher.verify(password, password_hash)


def create_access_token(*, subject: str, role: str) -> str:
    """Create a signed JWT access token."""

    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Token subject must be a non-empty string.")

    if role not in VALID_ROLES:
        raise ValueError("Invalid user role.")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": subject,
        "role": role,
        "token_type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Validate a JWT and return its claims, or None if invalid."""

    if not isinstance(token, str) or not token.strip():
        return None

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
        options={
            "require": [
                    "exp",
                    "iat",
                    "sub",
                    "role",
                    "token_type",
            ],
            },
        )
    except InvalidTokenError:
        return None

    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        return None

    if payload.get("role") not in VALID_ROLES:
        return None

    if payload.get("token_type") != "access":
        return None

    return payload
