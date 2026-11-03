from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    encoding="utf-8-sig",
)

DEFAULT_API_URL = "http://127.0.0.1:8000"


def get_required_worker_token() -> str:
    token = os.getenv("WORKER_API_TOKEN", "").strip()

    if not token:
        raise RuntimeError("WORKER_API_TOKEN is required.")

    if len(token) < 32:
        raise RuntimeError(
            "WORKER_API_TOKEN must contain at least 32 characters."
        )

    return token


def get_worker_api_url() -> str:
    raw_url = os.getenv(
        "EXPIRY_WORKER_API_URL",
        DEFAULT_API_URL,
    ).strip().rstrip("/")

    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError(
            "EXPIRY_WORKER_API_URL must contain a valid URL and port."
        ) from exc

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise RuntimeError(
            "EXPIRY_WORKER_API_URL must be an HTTP or HTTPS base URL "
            "without a path, query, fragment or credentials."
        )

    return raw_url


def get_integer_setting(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be a valid integer."
        ) from exc


@dataclass(frozen=True)
class WorkerSettings:
    worker_api_token: str
    expiry_worker_api_url: str
    expiry_worker_interval_seconds: int
    expiry_worker_request_timeout_seconds: int
    expiry_worker_max_backoff_seconds: int

    @classmethod
    def from_environment(cls) -> "WorkerSettings":
        interval = get_integer_setting(
            "EXPIRY_WORKER_INTERVAL_SECONDS", 30
        )
        timeout = get_integer_setting(
            "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS", 10
        )
        max_backoff = get_integer_setting(
            "EXPIRY_WORKER_MAX_BACKOFF_SECONDS", 300
        )

        if not 5 <= interval <= 3600:
            raise RuntimeError(
                "EXPIRY_WORKER_INTERVAL_SECONDS must be between 5 and 3600."
            )

        if not 1 <= timeout <= 120:
            raise RuntimeError(
                "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS must be between 1 and 120."
            )

        if not interval <= max_backoff <= 3600:
            raise RuntimeError(
                "EXPIRY_WORKER_MAX_BACKOFF_SECONDS must be greater than "
                "or equal to EXPIRY_WORKER_INTERVAL_SECONDS and no greater "
                "than 3600."
            )

        return cls(
            worker_api_token=get_required_worker_token(),
            expiry_worker_api_url=get_worker_api_url(),
            expiry_worker_interval_seconds=interval,
            expiry_worker_request_timeout_seconds=timeout,
            expiry_worker_max_backoff_seconds=max_backoff,
        )


worker_settings = WorkerSettings.from_environment()