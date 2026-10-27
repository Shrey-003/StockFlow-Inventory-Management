from sqlalchemy import inspect

from database import engine
from models import Base

Base.metadata.create_all(bind=engine)

inspector = inspect(engine)
tables = inspector.get_table_names()

for table_name in ("products", "reservations"):
    if table_name not in tables:
        raise RuntimeError(
            f"Required table was not created: {table_name}"
        )

    columns = [
        column["name"]
        for column in inspector.get_columns(table_name)
    ]

    print(f"Table verified: {table_name}")
    print(f"Columns: {', '.join(columns)}")

print("Database schema verification successful.")
