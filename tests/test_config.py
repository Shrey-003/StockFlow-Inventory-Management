import pytest

from config import Settings, get_cors_origins


def set_valid_database_environment(monkeypatch):
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "stockflow_test")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")


def test_settings_load_valid_configuration(monkeypatch):
    set_valid_database_environment(monkeypatch)
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:4200,https://stockflow.example.com",
    )

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
