# StockFlow

StockFlow is a backend inventory management and reservation system built to demonstrate software engineering fundamentals, data integrity, and concurrent request handling.

## Features

- Product CRUD APIs backed by PostgreSQL
- Unique SKU enforcement and input validation
- Atomic inventory reservations
- Reservation cancellation and stock restoration
- Reservation expiry processing
- Background expiry worker
- Concurrent reservation test script
- Automated validation tests
- Interactive API documentation

## Technology Stack

- Python, FastAPI, Uvicorn
- PostgreSQL, SQLAlchemy, Psycopg
- Pydantic
- pytest
- Git

## Local Development

1. Install Python 3.14 and PostgreSQL 18.
2. Create the PostgreSQL database named `stockflow`.
3. Create a local `.env` file with your database connection settings.
4. Install dependencies:

   `python -m pip install -r requirements.txt`

5. Initialize the database:

   `python init_db.py`

6. Start the API:

   `python -m uvicorn main:app --reload`

7. Open Swagger UI:

   http://127.0.0.1:8000/docs

Run the expiry worker in a separate terminal:

`python expiry_worker.py`

## Testing

Run automated validation tests:

`python -m pytest -q`

Run the concurrency demonstration only when product ID 6 is the dedicated concurrency test product with exactly 10 units available:

`python test_concurrency.py`

The concurrency script cancels the reservations it creates and checks that inventory returns to its initial quantity.

## Production Hardening Roadmap

Before production deployment, add authentication and authorization, database migrations, protected operational endpoints, managed secrets, structured monitoring, deployment automation, and broader integration and failure-recovery tests.
