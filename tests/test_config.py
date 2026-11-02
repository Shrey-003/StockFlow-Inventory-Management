import pytest

from config import Settings, get_cors_origins


def set_valid_database_environment(monkeypatch):
    monkeypatch.setenv(
	"LOGIN_RATE_LIMIT_SECRET",
	"test-login-rate-limit-secret-that-is-long-enough-012345",
    )
    monkeypatch.setenv("APP_ENV", "development")
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


def test_settings_load_valid_configuration(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:4200,https://stockflow.example.com",
    )
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "45")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "900")
    monkeypatch.setenv(
        "LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS", "10"
    )
    monkeypatch.setenv("LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS", "60")

    settings = Settings.from_environment()

    assert settings.db_host == "127.0.0.1"
    assert settings.db_port == 5432
    assert settings.db_name == "stockflow_test"
    assert settings.db_user == "test_user"
    assert settings.db_password == "test_password"
    assert settings.cors_origins == (
        "http://localhost:4200",
        "https://stockflow.example.com",
    )
    assert settings.jwt_secret_key.startswith("test-jwt-secret")
    assert settings.worker_api_token.startswith("test-worker-token")
    assert settings.access_token_expire_minutes == 45
    assert settings.login_rate_limit_window_seconds == 900
    assert settings.login_rate_limit_ip_username_max_attempts == 10
    assert settings.login_rate_limit_ip_max_attempts == 60


def test_settings_reject_missing_database_setting(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.delenv("DB_HOST")

    with pytest.raises(RuntimeError, match="DB_HOST"):
        Settings.from_environment()


@pytest.mark.parametrize(
    "port",
    ["not-a-port", "0", "65536"],
)
def test_settings_reject_invalid_database_port(monkeypatch, port):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("DB_PORT", port)

    with pytest.raises(RuntimeError, match="DB_PORT"):
        Settings.from_environment()


def test_cors_origins_normalize_and_remove_duplicates(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        " https://stockflow.example.com/ , "
        "http://localhost:4200, https://stockflow.example.com/ ",
    )

    assert get_cors_origins() == (
        "https://stockflow.example.com",
        "http://localhost:4200",
    )


@pytest.mark.parametrize(
    "origin",
    [
        "https://stockflow.example.com/dashboard",
        "ftp://stockflow.example.com",
        "not-a-valid-origin",
        "https://stockflow.example.com:abc",
        "https://stockflow.example.com:65536",
    ],
)
def test_cors_rejects_invalid_origins(monkeypatch, origin):
    monkeypatch.setenv("CORS_ORIGINS", origin)

    with pytest.raises(RuntimeError, match="Invalid CORS origin"):
        get_cors_origins()


def test_cors_uses_local_defaults_when_not_configured(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert get_cors_origins() == (
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    )


def test_settings_reject_missing_database_password(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.delenv("DB_PASSWORD")

    with pytest.raises(RuntimeError, match="DB_PASSWORD"):
        Settings.from_environment()


@pytest.mark.parametrize(
    "setting",
    ["JWT_SECRET_KEY", "WORKER_API_TOKEN"],
)
def test_settings_reject_missing_authentication_secrets(
    monkeypatch,
    setting,
):
    set_valid_database_environment(monkeypatch)
    monkeypatch.delenv(setting)

    with pytest.raises(RuntimeError, match=setting):
        Settings.from_environment()


@pytest.mark.parametrize(
    "setting",
    ["JWT_SECRET_KEY", "WORKER_API_TOKEN"],
)
def test_settings_reject_short_authentication_secrets(
    monkeypatch,
    setting,
):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv(setting, "too-short")

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        Settings.from_environment()


@pytest.mark.parametrize(
    "expiry",
    ["not-a-number", "0", "1441"],
)
def test_settings_reject_invalid_token_expiry(monkeypatch, expiry):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", expiry)

    with pytest.raises(RuntimeError, match="ACCESS_TOKEN_EXPIRE_MINUTES"):
        Settings.from_environment()


def test_settings_default_token_expiry(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)

    settings = Settings.from_environment()

    assert settings.access_token_expire_minutes == 30

@pytest.mark.parametrize(
    "setting",
    [
        "LOGIN_RATE_LIMIT_SECRET",
    ],
)
def test_settings_reject_missing_rate_limit_secret(monkeypatch, setting):
    set_valid_database_environment(monkeypatch)
    monkeypatch.delenv(setting)

    with pytest.raises(RuntimeError, match=setting):
        Settings.from_environment()


def test_settings_reject_short_rate_limit_secret(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("LOGIN_RATE_LIMIT_SECRET", "too-short")

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        Settings.from_environment()


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "not-a-number"),
        ("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "59"),
        ("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "86401"),
        ("LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS", "0"),
        ("LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS", "101"),
        ("LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS", "0"),
        ("LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS", "1001"),
    ],
)
def test_settings_reject_invalid_rate_limit_values(
    monkeypatch,
    setting,
    value,
):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv(setting, value)

    with pytest.raises(RuntimeError, match=setting):
        Settings.from_environment()


def test_settings_reject_ip_limit_lower_than_username_limit(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv(
        "LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS", "20"
    )
    monkeypatch.setenv("LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS", "10")

    with pytest.raises(RuntimeError, match="IP_MAX_ATTEMPTS"):
        Settings.from_environment()

def test_settings_default_login_rate_limits(monkeypatch):
    set_valid_database_environment(monkeypatch)

    monkeypatch.delenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv(
        "LOGIN_RATE_LIMIT_IP_USERNAME_MAX_ATTEMPTS",
        raising=False,
    )
    monkeypatch.delenv(
        "LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS",
        raising=False,
    )

    settings = Settings.from_environment()

    assert settings.login_rate_limit_window_seconds == 900
    assert settings.login_rate_limit_ip_username_max_attempts == 10
    assert settings.login_rate_limit_ip_max_attempts == 60


def test_settings_default_to_development(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings.from_environment()

    assert settings.app_env == "development"
    assert settings.api_docs_enabled is True
    assert settings.cors_origins == (
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    )


@pytest.mark.parametrize("environment", ["staging", "testing", ""])
def test_settings_reject_invalid_environment(monkeypatch, environment):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", environment)

    with pytest.raises(RuntimeError, match="APP_ENV"):
        Settings.from_environment()


def test_production_requires_explicit_cors_origins(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="explicitly configured"):
        Settings.from_environment()


@pytest.mark.parametrize(
    "origin",
    [
        "http://stockflow.example.com",
        "http://localhost:4200",
    ],
)
def test_production_rejects_http_cors_origins(monkeypatch, origin):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", origin)

    with pytest.raises(RuntimeError, match="must use HTTPS"):
        Settings.from_environment()


@pytest.mark.parametrize(
    "origin",
    [
        "https://localhost:4200",
        "https://127.0.0.1:4200",
        "https://sub.localhost:4200",
        "https://[::1]:4200",
    ],
)
def test_production_rejects_loopback_cors_origins(monkeypatch, origin):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", origin)

    with pytest.raises(RuntimeError, match="localhost or loopback"):
        Settings.from_environment()


def test_production_accepts_https_frontend_origin(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://stockflow.example.com",
    )

    settings = Settings.from_environment()

    assert settings.app_env == "production"
    assert settings.cors_origins == (
        "https://stockflow.example.com",
    )
    assert settings.api_docs_enabled is False


def test_production_rejects_empty_cors_list(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", ", , ")

    with pytest.raises(RuntimeError, match="at least one valid"):
        Settings.from_environment()
