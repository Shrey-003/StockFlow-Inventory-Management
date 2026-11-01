
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth_schemas import LoginRequest, TokenResponse, UserRead
from config import settings
from dependencies import (
    get_current_token_claims,
    get_current_user,
    get_db,
)
from login_rate_limiter import enforce_login_rate_limit
from models import RevokedToken, User
from security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_token_identifier,
    verify_password,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    # Use the direct client address. Do not trust arbitrary forwarded
    # headers unless the deployment explicitly configures trusted proxies.
    client_ip = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    # Apply rate limits before checking credentials.
    enforce_login_rate_limit(
        db,
        client_ip,
        payload.username,
    )

    user = db.scalar(
        select(User).where(User.username == payload.username)
    )

    if user is None or not user.is_active:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=str(user.id),
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def logout(
    claims: dict[str, Any] = Depends(get_current_token_claims),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke the current access token."""

    try:
        now = datetime.now(timezone.utc)

        db.execute(
            delete(RevokedToken).where(
                RevokedToken.expires_at <= now
            )
        )

        jti_hash = hash_token_identifier(claims["jti"])

        expires_at = datetime.fromtimestamp(
            claims["exp"],
            tz=timezone.utc,
        )

        statement = (
            pg_insert(RevokedToken)
            .values(
                jti_hash=jti_hash,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(
                index_elements=[RevokedToken.jti_hash]
            )
        )

        db.execute(statement)
        db.commit()

    except (SQLAlchemyError, ValueError, TypeError, KeyError) as exc:
        db.rollback()
        logger.exception("Token revocation failed")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not complete logout.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserRead,
)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user

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
