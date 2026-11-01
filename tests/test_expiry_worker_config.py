
import pytest

from config import Settings


def set_valid_environment(monkeypatch):
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "stockflow_test")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")

    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "test-jwt-secret-key-that-is-long-enough-0123456789",
    )
    monkeypatch.setenv(
        "WORKER_API_TOKEN",
        "test-worker-token-that-is-long-enough-0123456789",
    )
    monkeypatch.setenv(
        "LOGIN_RATE_LIMIT_SECRET",
        "test-login-rate-limit-secret-that-is-long-enough-012345",
    )


def test_expiry_worker_default_configuration(monkeypatch):
    set_valid_environment(monkeypatch)

    worker_settings = [
        "EXPIRY_WORKER_API_URL",
        "EXPIRY_WORKER_INTERVAL_SECONDS",
        "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS",
        "EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
    ]

    for setting in worker_settings:
        monkeypatch.delenv(setting, raising=False)

    settings = Settings.from_environment()

    assert (
        settings.expiry_worker_api_url
        == "http://127.0.0.1:8000"
    )
    assert settings.expiry_worker_interval_seconds == 30
    assert settings.expiry_worker_request_timeout_seconds == 10
    assert settings.expiry_worker_max_backoff_seconds == 300


def test_expiry_worker_loads_custom_configuration(monkeypatch):
    set_valid_environment(monkeypatch)

    monkeypatch.setenv(
        "EXPIRY_WORKER_API_URL",
        "https://stockflow-internal.example.com:8443/",
    )
    monkeypatch.setenv("EXPIRY_WORKER_INTERVAL_SECONDS", "60")
    monkeypatch.setenv(
        "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS", "15"
    )
    monkeypatch.setenv("EXPIRY_WORKER_MAX_BACKOFF_SECONDS", "600")

    settings = Settings.from_environment()

    assert (
        settings.expiry_worker_api_url
        == "https://stockflow-internal.example.com:8443"
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
def test_expiry_worker_rejects_invalid_api_urls(
    monkeypatch,
    url,
):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv("EXPIRY_WORKER_API_URL", url)

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_API_URL",
    ):
        Settings.from_environment()


@pytest.mark.parametrize(
    "interval",
    [
        "not-a-number",
        "4",
        "3601",
    ],
)
def test_expiry_worker_rejects_invalid_intervals(
    monkeypatch,
    interval,
):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv(
        "EXPIRY_WORKER_INTERVAL_SECONDS",
        interval,
    )

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_INTERVAL_SECONDS",
    ):
        Settings.from_environment()


@pytest.mark.parametrize(
    "timeout",
    [
        "not-a-number",
        "0",
        "121",
    ],
)
def test_expiry_worker_rejects_invalid_request_timeouts(
    monkeypatch,
    timeout,
):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv(
        "EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS",
        timeout,
    )

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_REQUEST_TIMEOUT_SECONDS",
    ):
        Settings.from_environment()


@pytest.mark.parametrize(
    "backoff",
    [
        "not-a-number",
        "29",
        "3601",
    ],
)
def test_expiry_worker_rejects_invalid_maximum_backoff(
    monkeypatch,
    backoff,
):
    set_valid_environment(monkeypatch)
    monkeypatch.setenv(
        "EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
        backoff,
    )

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
    ):
        Settings.from_environment()


def test_expiry_worker_backoff_must_cover_polling_interval(
    monkeypatch,
):
    set_valid_environment(monkeypatch)

    monkeypatch.setenv(
        "EXPIRY_WORKER_INTERVAL_SECONDS",
        "60",
    )
    monkeypatch.setenv(
        "EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
        "59",
    )

    with pytest.raises(
        RuntimeError,
        match="EXPIRY_WORKER_MAX_BACKOFF_SECONDS",
    ):
        Settings.from_environment()
