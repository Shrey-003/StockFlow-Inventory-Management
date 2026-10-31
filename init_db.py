from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from database import engine


PROJECT_ROOT = Path(__file__).resolve().parent


def initialize_database() -> None:
    """Apply pending database migrations and verify the schema."""

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))

    print("Applying database migrations...")
    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = inspector.get_table_names()

        for table_name in ("products", "reservations"):
            if table_name not in tables:
                raise RuntimeError(
                    f"Required table is missing: {table_name}"
                )

            columns = [
                column["name"]
                for column in inspector.get_columns(table_name)
            ]

            print(f"Table verified: {table_name}")
            print(f"Columns: {', '.join(columns)}")

        if "alembic_version" not in tables:
            raise RuntimeError(
                "Alembic version table is missing after migration."
            )

        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()

        if not revision:
            raise RuntimeError(
                "No Alembic migration revision is recorded."
            )

        print(f"Current migration revision: {revision}")

    print("Database initialization successful.")


if __name__ == "__main__":
    initialize_database()
