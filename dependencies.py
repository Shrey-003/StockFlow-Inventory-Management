
from collections.abc import Generator
import hmac
from typing import Any, Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from models import RevokedToken, User
from security import decode_access_token, hash_token_identifier


bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Validate the JWT and reject revoked tokens."""

    if credentials is None:
        raise authentication_error()

    claims = decode_access_token(credentials.credentials)

    if claims is None:
        raise authentication_error()

    jti_hash = hash_token_identifier(claims["jti"])

    revoked_token = db.get(RevokedToken, jti_hash)

    if revoked_token is not None:
        raise authentication_error()

    return claims


def get_current_user(
    claims: dict[str, Any] = Depends(get_current_token_claims),
    db: Session = Depends(get_db),
) -> User:
    """Load the authenticated user after validating the JWT."""

    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError):
        raise authentication_error()

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise authentication_error()

    return user


def require_roles(*allowed_roles: str) -> Callable:
    if not allowed_roles or not set(allowed_roles).issubset(
        {"admin", "staff"}
    ):
        raise ValueError("At least one valid role must be specified.")

    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_dependency


def verify_worker_token(
    x_worker_token: str | None = Header(
        default=None,
        alias="X-Worker-Token",
    ),
) -> None:
    if x_worker_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker authentication required.",
        )

    provided = x_worker_token.encode("utf-8")
    expected = settings.worker_api_token.encode("utf-8")

    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker credentials.",
        )
