from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent

# Load local environment settings.
# Existing operating-system environment variables take precedence.
load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    encoding="utf-8-sig",
)


DEFAULT_CORS_ORIGINS = (
    "http://localhost:4200",
    "http://127.0.0.1:4200",
)


def get_required_setting(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"Missing required environment setting: {name}"
        )

    return value.strip()


def get_cors_origins() -> tuple[str, ...]:
    raw_origins = os.getenv(
        "CORS_ORIGINS",
        ",".join(DEFAULT_CORS_ORIGINS),
    )

    origins = []

    for raw_origin in raw_origins.split(","):
        origin = raw_origin.strip().rstrip("/")

        if not origin:
            continue

        parsed = urlsplit(origin)

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

        if origin not in origins:
            origins.append(origin)

    return tuple(origins)


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    cors_origins: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "Settings":
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

        return cls(
            db_host=get_required_setting("DB_HOST"),
            db_port=db_port,
            db_name=get_required_setting("DB_NAME"),
            db_user=get_required_setting("DB_USER"),
            db_password=get_required_setting("DB_PASSWORD"),
            cors_origins=get_cors_origins(),
        )


settings = Settings.from_environment()
