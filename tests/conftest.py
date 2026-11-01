import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from config import settings
from models import Base, User
from security import create_access_token, hash_password


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_NAME = "stockflow_test"


def verify_test_database(engine) -> None:
    """Ensure operations target only the dedicated test database."""

    if engine.url.database != TEST_DATABASE_NAME:
        raise RuntimeError(
            f"Refusing database operation on {engine.url.database}."
        )

    with engine.connect() as connection:
        actual_database = connection.scalar(
            text("SELECT current_database()")
        )

    if actual_database != TEST_DATABASE_NAME:
        raise RuntimeError(
            f"Expected {TEST_DATABASE_NAME}, connected to {actual_database}."
        )


def run_test_migration(engine, operation, revision: str) -> None:
    """Execute an Alembic migration against the verified test database."""

    verify_test_database(engine)
    config = Config(str(PROJECT_ROOT / "alembic.ini"))

    with engine.connect() as connection:
        actual_database = connection.scalar(
            text("SELECT current_database()")
        )

        if actual_database != TEST_DATABASE_NAME:
            raise RuntimeError(
                "Database identity changed. Migration cancelled."
            )

        connection.commit()
        config.attributes["connection"] = connection

        try:
            operation(config, revision)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            config.attributes.pop("connection", None)


def reset_test_schema(engine) -> None:
    """Recreate the test schema through Alembic migrations."""

    verify_test_database(engine)
    print("\nResetting isolated test database through Alembic...")

    run_test_migration(engine, command.downgrade, "base")
    run_test_migration(engine, command.upgrade, "head")

    print("Test database migration reset completed.")


@pytest.fixture(scope="session")
def test_engine():
    load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8-sig")

    required = (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    )

    missing = [key for key in required if not os.getenv(key)]

    if missing:
        raise RuntimeError(
            f"Missing database settings: {', '.join(missing)}"
        )

    development_database = os.environ["DB_NAME"]

    if development_database.casefold() == TEST_DATABASE_NAME.casefold():
        raise RuntimeError(
            "Safety check failed: DB_NAME points to the test database. "
            "Keep development and test databases separate."
        )

    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=TEST_DATABASE_NAME,
    )

    if url.database != TEST_DATABASE_NAME:
        raise RuntimeError("Refusing to use an unexpected database.")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )

    try:
        verify_test_database(engine)
        print(f"\nIntegration tests use database: {TEST_DATABASE_NAME}")
        yield engine

    finally:
        try:
            verify_test_database(engine)
            reset_test_schema(engine)
        finally:
            engine.dispose()


@pytest.fixture
def test_api_setup(test_engine):
    """Reset the test DB, override DB sessions and seed test identities."""

    reset_test_schema(test_engine)

    from main import app
    from dependencies import get_db

    def override_get_db():
        with Session(test_engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    passwords = {
        "admin": "TestAdmin-Password-2026!",
        "staff": "TestStaff-Password-2026!",
        "other_staff": "OtherStaff-Password-2026!",
    }

    users = {
        "admin": User(
            username="testadmin",
            password_hash=hash_password(passwords["admin"]),
            role="admin",
            is_active=True,
        ),
        "staff": User(
            username="teststaff",
            password_hash=hash_password(passwords["staff"]),
            role="staff",
            is_active=True,
        ),
        "other_staff": User(
            username="otherstaff",
            password_hash=hash_password(passwords["other_staff"]),
            role="staff",
            is_active=True,
        ),
    }

    try:
        with Session(test_engine) as db:
            db.add_all(users.values())
            db.commit()

            user_ids = {
                key: user.id
                for key, user in users.items()
            }

        tokens = {
            key: create_access_token(
                subject=str(user_ids[key]),
                role=users[key].role,
            )
            for key in users
        }

        headers = {
            key: {"Authorization": f"Bearer {token}"}
            for key, token in tokens.items()
        }

        yield {
            "app": app,
            "passwords": passwords,
            "user_ids": user_ids,
            "headers": headers,
        }

    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(test_api_setup):
    """Default authenticated admin client for existing API tests."""

    with TestClient(test_api_setup["app"]) as test_client:
        test_client.headers.update(
            test_api_setup["headers"]["admin"]
        )
        yield test_client


@pytest.fixture
def staff_client(test_api_setup):
    with TestClient(test_api_setup["app"]) as test_client:
        test_client.headers.update(
            test_api_setup["headers"]["staff"]
        )
        yield test_client


@pytest.fixture
def other_staff_client(test_api_setup):
    with TestClient(test_api_setup["app"]) as test_client:
        test_client.headers.update(
            test_api_setup["headers"]["other_staff"]
        )
        yield test_client


@pytest.fixture
def anonymous_client(test_api_setup):
    with TestClient(test_api_setup["app"]) as test_client:
        yield test_client


@pytest.fixture
def worker_client(test_api_setup):
    with TestClient(test_api_setup["app"]) as test_client:
        test_client.headers.update(
            {"X-Worker-Token": settings.worker_api_token}
        )
        yield test_client
