
from dataclasses import dataclass
import os
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    encoding="utf-8-sig",
)


DEFAULT_CORS_ORIGINS = (
    "http://localhost:4200",
    "http://127.0.0.1:4200",
)

DEFAULT_EXPIRY_WORKER_API_URL = "http://127.0.0.1:8000"


def get_app_environment() -> str:
    environment = os.getenv("APP_ENV", "development").strip().lower()

    if environment not in {"development", "production"}:
        raise RuntimeError(
            "APP_ENV must be either 'development' or 'production'."
        )

    return environment


def get_required_setting(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"Missing required environment setting: {name}"
        )

    return value.strip()


def get_required_secret(name: str) -> str:
    value = get_required_setting(name)

    if len(value) < 32:
        raise RuntimeError(
            f"{name} must contain at least 32 characters."
        )

    return value


def get_integer_setting(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be a valid integer."
        ) from exc


def get_expiry_worker_api_url() -> str:
    raw_url = os.getenv(
        "EXPIRY_WORKER_API_URL",
        DEFAULT_EXPIRY_WORKER_API_URL,
    ).strip().rstrip("/")

    parsed = urlsplit(raw_url)

    try:
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("Invalid port")
    except ValueError as exc:
        raise RuntimeError(
            "EXPIRY_WORKER_API_URL must contain a valid port."
        ) from exc

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise RuntimeError(
            "EXPIRY_WORKER_API_URL must be an HTTP or HTTPS base URL "
            "without a path, query, fragment or credentials."
        )

    return raw_url


def get_cors_origins(
    app_environment: str | None = None,
) -> tuple[str, ...]:
    environment = app_environment or get_app_environment()

    configured_origins = os.getenv("CORS_ORIGINS")

    if environment == "production":
        if not configured_origins or not configured_origins.strip():
            raise RuntimeError(
                "CORS_ORIGINS must be explicitly configured in production."
            )

        raw_origins = configured_origins
    else:
        raw_origins = (
            configured_origins
            if configured_origins is not None
            else ",".join(DEFAULT_CORS_ORIGINS)
        )

    origins = []

    for raw_origin in raw_origins.split(","):
        origin = raw_origin.strip().rstrip("/")

        if not origin:
            continue

        parsed = urlsplit(origin)

        try:
            port = parsed.port
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid CORS origin: {origin}. "
                "Provide a valid port between 1 and 65535."
            ) from exc

        if port is not None and not 1 <= port <= 65535:
            raise RuntimeError(
                f"Invalid CORS origin: {origin}. "
                "Port must be between 1 and 65535."
            )

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise RuntimeError(
                f"Invalid CORS origin: {origin}. "
                "Provide an origin such as https://example.com "
                "without a path."
            )

        if environment == "production":
            if parsed.scheme != "https":
                raise RuntimeError(
                    "Production CORS origins must use HTTPS."
                )

            hostname = parsed.hostname or ""
            is_loopback = (
                hostname.lower() == "localhost"
                or hostname.lower().endswith(".localhost")
            )

            try:
                is_loopback = (
                    is_loopback or ipaddress.ip_address(hostname).is_loopback
                )
            except ValueError:
                pass

            if is_loopback:
                raise RuntimeError(
                    "Production CORS origins cannot use localhost "
                    "or loopback addresses."
                )

        if origin not in origins:
            origins.append(origin)

    if environment == "production" and not origins:
        raise RuntimeError(
            "CORS_ORIGINS must contain at least one valid production origin."
        )

    return tuple(origins)


@dataclass(frozen=True)
class Settings:
    app_env: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    cors_origins: tuple[str, ...]

    jwt_secret_key: str
    worker_api_token: str
    access_token_expire_minutes: int

    login_rate_limit_secret: str
    login_rate_limit_window_seconds: int
    login_rate_limit_ip_username_max_attempts: int
    login_rate_limit_ip_max_attempts: int

    expiry_worker_api_url: str
    expiry_worker_interval_seconds: int
    expiry_worker_request_timeout_seconds: int
    expiry_worker_max_backoff_seconds: int

    @property
    def api_docs_enabled(self) -> bool:
        return self.app_env == "development"

    @classmethod
    def from_environment(cls) -> "Settings":
        app_env = get_app_environment()
        # PostgreSQL configuration.
        try:
            db_port = int(get_required_setting("DB_PORT"))
        except ValueError as exc:
            raise RuntimeError(
                "DB_PORT must be a valid integer."
            ) from exc

        if not 1 <= db_port <= 65535:
            raise RuntimeError(
                "DB_PORT must be between 1 and 65535."
            )

        # Authentication configuration.
        token_expiry = get_integer_setting(
            "ACCESS_TOKEN_EXPIRE_MINUTES", 30
        )

        if not 1 <= token_expiry <= 1440:
            raise RuntimeError(
                "ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440."
            )

        jwt_secret = get_required_secret("JWT_SECRET_KEY")
        worker_token = get_required_secret("WORKER_API_TOKEN")

        # Login rate-limit configuration.
        login_rate_limit_secret = get_required_secret(
            "LOGIN_RATE_LIMIT_SECRET"
        )

        rate_limit_window = get_integer_setting(
            "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 900
        )

        ip_username_max_attempts = get_integer_setting(
            "LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS", 10
        )

        ip_max_attempts = get_integer_setting(
            "LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS", 60
        )

        if not 60 <= rate_limit_window <= 86400:
            raise RuntimeError(
                "LOGIN_RATE_LIMIT_WINDOW_SECONDS must be between 60 and 86400."
            )

        if not 1 <= ip_username_max_attempts <= 100:
            raise RuntimeError(
                "LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS must be between 1 and 100."
            )

        if not 1 <= ip_max_attempts <= 1000:
            raise RuntimeError(
                "LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS must be between 1 and 1000."
            )

        if ip_max_attempts < ip_username_max_attempts:
            raise RuntimeError(
                "LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS must be greater than "
                "or equal to LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS."
            )

        # Expiry worker configuration.
        expiry_worker_api_url = get_expiry_worker_api_url()

        expiry_worker_interval = get_integer_setting(
            "EXPIRY_WORKER_INTERVAL_SECONDS", 30
        )

        expiry_worker_timeout = get_integer_setting(
            "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS", 10
        )

        expiry_worker_max_backoff = get_integer_setting(
            "EXPIRY_WORKER_MAX_BACKOFF_SECONDS", 300
        )

        if not 5 <= expiry_worker_interval <= 3600:
            raise RuntimeError(
                "EXPIRY_WORKER_INTERVAL_SECONDS must be between 5 and 3600."
            )

        if not 1 <= expiry_worker_timeout <= 120:
            raise RuntimeError(
                "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS must be between 1 and 120."
            )

        if not expiry_worker_interval <= expiry_worker_max_backoff <= 3600:
            raise RuntimeError(
                "EXPIRY_WORKER_MAX_BACKOFF_SECONDS must be greater than "
                "or equal to EXPIRY_WORKER_INTERVAL_SECONDS and no greater "
                "than 3600."
            )

        return cls(
            app_env=app_env,
            db_host=get_required_setting("DB_HOST"),
            db_port=db_port,
            db_name=get_required_setting("DB_NAME"),
            db_user=get_required_setting("DB_USER"),
            db_password=get_required_setting("DB_PASSWORD"),
            cors_origins=get_cors_origins(app_env),

            jwt_secret_key=jwt_secret,
            worker_api_token=worker_token,
            access_token_expire_minutes=token_expiry,

            login_rate_limit_secret=login_rate_limit_secret,
            login_rate_limit_window_seconds=rate_limit_window,
            login_rate_limit_ip_username_max_attempts=ip_username_max_attempts,
            login_rate_limit_ip_max_attempts=ip_max_attempts,

            expiry_worker_api_url=expiry_worker_api_url,
            expiry_worker_interval_seconds=expiry_worker_interval,
            expiry_worker_request_timeout_seconds=expiry_worker_timeout,
            expiry_worker_max_backoff_seconds=expiry_worker_max_backoff,
        )


settings = Settings.from_environment()
