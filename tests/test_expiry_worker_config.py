import pytest

from worker_config import WorkerSettings


VALID_TOKEN = "test-worker-token-that-is-long-enough-0123456789"


def set_valid_environment(monkeypatch):
    monkeypatch.setenv("WORKER_API_TOKEN", VALID_TOKEN)


def test_worker_configuration_needs_no_database_or_api_secrets(monkeypatch):
    set_valid_environment(monkeypatch)

    for name in (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "JWT_SECRET_KEY",
        "LOGIN_RATE_LIMIT_SECRET",
        "CORS_ORIGINS",
        "APP_ENV",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = WorkerSettings.from_environment()

    assert settings.worker_api_token == VALID_TOKEN
    assert settings.expiry_worker_api_url == "http://127.0.0.1:8000"
    assert settings.expiry_worker_interval_seconds == 30
    assert settings.expiry_worker_request_timeout_seconds == 10
    assert settings.expiry_worker_max_backoff_seconds == 300


def test_worker_rejects_missing_token(monkeypatch):
    monkeypatch.delenv("WORKER_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="WORKER_API_TOKEN"):
        WorkerSettings.from_environment()


def test_worker_rejects_short_token(monkeypatch):
    monkeypatch.setenv("WORKER_API_TOKEN", "too-short")

    with pytest.raises(RuntimeError, match="32 characters"):
        WorkerSettings.from_environment()


def test_worker_default_configuration(monkeypatch):
    set_valid_environment(monkeypatch)

    for name in (
        "EXPIRY_WORKER_API_URL",
        "EXPIRY_WORKER_INTERVAL_SECONDS",
        "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS",
        "EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = WorkerSettings.from_environment()

    assert settings.expiry_worker_api_url == "http://127.0.0.1:8000"
    assert settings.expiry_worker_interval_seconds == 30
    assert settings.expiry_worker_request_timeout_seconds == 10
    assert settings.expiry_worker_max_backoff_seconds == 300


def test_worker_custom_configuration(monkeypatch):
    set_valid_environment(monkeypatch)

    monkeypatch.setenv(
        "EXPIRY_WORKER_API_URL",
        "https://stockflow-internal.example.com:8443/",
    )
    monkeypatch.setenv("EXPIRY_WORKER_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("EXPIRY_WORKER_MAX_BACKOFF_SECONDS", "600")

    settings = WorkerSettings.from_environment()

    assert settings.expiry_worker_api_url == (
        "https://stockflow-internal.example.com:8443"
    )
    assert settings.expiry_worker_interval_seconds == 60
    assert settings.expiry_worker_request_timeout_seconds == 15
    assert settings.expiry_worker_max_backoff_seconds == 600


@pytest.mark.parametrize(
    "url",
    [
        "not-a-valid-url",
        "ftp://localhost:8000",
        "http://localhost:8000/health",
        "https://user:password@example.com",
        "https://example.com?token=value",
        "https://example.com#fragment",
        "http://localhost:99999",
    ],
)
def test_worker_rejects_invalid_api_urls(monkeypatch, url):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv("EXPIRY_WORKER_API_URL", url)

    with pytest.raises(RuntimeError, match="EXPIRY_WORKER_API_URL"):
        WorkerSettings.from_environment()


@pytest.mark.parametrize(
    "interval",
    ["not-a-number", "4", "3601"],
)
def test_worker_rejects_invalid_intervals(monkeypatch, interval):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv("EXPIRY_WORKER_INTERVAL_SECONDS", interval)

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_INTERVAL_SECONDS",
    ):
        WorkerSettings.from_environment()


@pytest.mark.parametrize(
    "timeout",
    ["not-a-number", "0", "121"],
)
def test_worker_rejects_invalid_timeouts(monkeypatch, timeout):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv(
        "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS",
        timeout,
    )

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS",
    ):
        WorkerSettings.from_environment()


@pytest.mark.parametrize(
    "backoff",
    ["not-a-number", "29", "3601"],
)
def test_worker_rejects_invalid_backoff(monkeypatch, backoff):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv(
        "EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
        backoff,
    )

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
    ):
        WorkerSettings.from_environment()


def test_worker_backoff_must_cover_interval(monkeypatch):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv("EXPIRY_WORKER_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("EXPIRY_WORKER_MAX_BACKOFF_SECONDS", "59")

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
    ):
        WorkerSettings.from_environment()