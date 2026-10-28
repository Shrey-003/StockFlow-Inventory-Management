import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_NAME = "stockflow_test"


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
            "Keep your development database and test database separate."
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
        with engine.connect() as connection:
            actual_database = connection.scalar(
                text("SELECT current_database()")
            )

        if actual_database != TEST_DATABASE_NAME:
            raise RuntimeError(
                f"Expected {TEST_DATABASE_NAME}, "
                f"connected to {actual_database}."
            )

        print(f"\nIntegration tests use database: {actual_database}")
        yield engine

    finally:
        # Clean up tables only if the database identity is still verified.
        try:
            with engine.connect() as connection:
                actual_database = connection.scalar(
                    text("SELECT current_database()")
                )

            if (
                actual_database == TEST_DATABASE_NAME
                and engine.url.database == TEST_DATABASE_NAME
            ):
                Base.metadata.drop_all(bind=engine)
        finally:
            engine.dispose()


@pytest.fixture
def client(test_engine):
    if test_engine.url.database != TEST_DATABASE_NAME:
        raise RuntimeError("Refusing to reset an unexpected database.")

    with test_engine.connect() as connection:
        actual_database = connection.scalar(
            text("SELECT current_database()")
        )

    if actual_database != TEST_DATABASE_NAME:
        raise RuntimeError(
            f"Refusing to reset database: {actual_database}"
        )

    # Recreate the schema only in the dedicated test database.
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

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
