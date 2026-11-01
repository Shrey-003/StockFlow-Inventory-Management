
from datetime import datetime, timedelta, timezone
import hmac
import logging
import math

from fastapi import HTTPException, status
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import settings
from models import LoginRateLimit


logger = logging.getLogger(__name__)


def create_bucket_hash(
    scope: str,
    client_ip: str,
    username: str | None = None,
) -> str:
    """Create a keyed hash without storing raw IP or username values."""

    parts = [scope, client_ip]

    if username is not None:
        parts.append(username)

    message = "\0".join(parts).encode("utf-8")

    return hmac.new(
        settings.login_rate_limit_secret.encode("utf-8"),
        message,
        digestmod="sha256",
    ).hexdigest()


def increment_rate_limit_bucket(
    db: Session,
    bucket_hash: str,
    now: datetime,
    cutoff: datetime,
) -> tuple[datetime, int]:
    """Atomically increment a bucket or reset its expired window."""

    expired = LoginRateLimit.window_started_at <= cutoff

    statement = (
        pg_insert(LoginRateLimit)
        .values(
            bucket_hash=bucket_hash,
            window_started_at=now,
            request_count=1,
        )
        .on_conflict_do_update(
            index_elements=[LoginRateLimit.bucket_hash],
            set_={
                "window_started_at": case(
                    (expired, now),
                    else_=LoginRateLimit.window_started_at,
                ),
                "request_count": case(
                    (expired, 1),
                    else_=LoginRateLimit.request_count + 1,
                ),
            },
        )
        .returning(
            LoginRateLimit.window_started_at,
            LoginRateLimit.request_count,
        )
    )

    row = db.execute(statement).one()

    return row[0], row[1]


def calculate_retry_after(
    window_started_at: datetime,
    now: datetime,
    window_seconds: int,
) -> int:
    """Calculate remaining seconds in a rate-limit window."""

    window_end = window_started_at + timedelta(
        seconds=window_seconds
    )

    return max(
        1,
        math.ceil((window_end - now).total_seconds()),
    )


def enforce_login_rate_limit(
    db: Session,
    client_ip: str,
    username: str,
) -> None:
    """
    Apply IP and IP-plus-username limits.

    Every valid login submission consumes one request from both buckets,
    regardless of whether authentication eventually succeeds.
    """

    client_ip = client_ip.strip() if client_ip else "unknown"

    now = datetime.now(timezone.utc)
    window_seconds = settings.login_rate_limit_window_seconds
    cutoff = now - timedelta(seconds=window_seconds)

    ip_bucket = create_bucket_hash(
        scope="ip",
        client_ip=client_ip,
    )

    ip_username_bucket = create_bucket_hash(
        scope="ip_username",
        client_ip=client_ip,
        username=username,
    )

    try:
        ip_window_started, ip_count = increment_rate_limit_bucket(
            db,
            ip_bucket,
            now,
            cutoff,
        )

        username_window_started, username_count = (
            increment_rate_limit_bucket(
                db,
                ip_username_bucket,
                now,
                cutoff,
            )
        )

        # Periodically remove sufficiently old bucket records.
        # Only the first request in an IP window performs this cleanup.
        if ip_count == 1:
            cleanup_cutoff = now - timedelta(
                seconds=window_seconds * 2
            )

            db.execute(
                delete(LoginRateLimit).where(
                    LoginRateLimit.window_started_at < cleanup_cutoff
                )
            )

        # Persist counters even when this request is subsequently blocked.
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Login rate-limit database operation failed")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ) from exc

    retry_after_values = []

    if username_count > settings.login_rate_limit_ip_username_max_attempts:
        retry_after_values.append(
            calculate_retry_after(
                username_window_started,
                now,
                window_seconds,
            )
        )

    if ip_count > settings.login_rate_limit_ip_max_attempts:
        retry_after_values.append(
            calculate_retry_after(
                ip_window_started,
                now,
                window_seconds,
            )
        )

    if retry_after_values:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={
                "Retry-After": str(max(retry_after_values))
            },
        )
