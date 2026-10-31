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

        # End the read transaction before handing the connection to Alembic.
        connection.commit()

        config.attributes["connection"] = connection

        try:
            operation(config, revision)

            # Ensure any remaining migration transaction is committed.
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

        print(
            f"\nIntegration tests use database: {TEST_DATABASE_NAME}"
        )

        yield engine

    finally:
        try:
            verify_test_database(engine)
            reset_test_schema(engine)
        finally:
            engine.dispose()


@pytest.fixture
def client(test_engine):
    reset_test_schema(test_engine)

    from main import app, get_db

    def override_get_db():
        with Session(test_engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
