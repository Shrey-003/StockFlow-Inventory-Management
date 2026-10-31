# StockFlow

StockFlow is a full-stack inventory management and reservation application built to demonstrate reliable inventory operations, transactional data integrity, and concurrent request handling.

The application consists of an Angular dashboard, a FastAPI backend, and a PostgreSQL database.

## Features

### Inventory management
- Create, read, update, and delete products
- Unique SKU enforcement
- Product input validation
- Inventory quantity and value summaries
- Low-stock indicators

### Reservations
- Reserve inventory for a configurable duration
- Atomic stock deduction during reservation creation
- Prevent reservations exceeding available inventory
- Cancel active reservations and restore stock
- Automatically expire overdue reservations
- Restore inventory when reservations expire
- Reservation history and pagination

### Engineering and reliability
- PostgreSQL persistence with SQLAlchemy
- Database migrations managed by Alembic
- Dedicated integration-test database
- Automated backend tests
- Concurrent reservation demonstration
- Background reservation-expiry worker
- Interactive API documentation

## Technology Stack

| Area | Technology |
|---|---|
| Frontend | Angular, TypeScript, HTML, CSS |
| Backend | Python, FastAPI, Uvicorn |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Migrations | Alembic |
| Testing | pytest, HTTPX, HTTPX2 |
| Version control | Git |

## Architecture

```text
Angular Dashboard
       |
       | HTTP requests
       v
FastAPI Backend
       |
       | SQLAlchemy
       v
PostgreSQL Database

Expiry Worker
       |
       | Periodic API requests
       v
FastAPI Reservation Expiry Endpoint

## Local Development Setup

### 1. Prerequisites

Install Python 3.14, PostgreSQL 18, Node.js, npm, and Git.

### 2. Clone the repository

```powershell
git clone <repository-url>
Set-Location StockFlow
```

### 3. Create PostgreSQL databases

Create two databases:

- `stockflow` for application development.
- `stockflow_test` for automated integration tests.

The PostgreSQL user must have permission to manage the test schema.

### 4. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Configure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `CORS_ORIGINS` in `.env`.

Never commit real credentials or `.env`.

### 5. Set up Python

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

### 6. Initialize the database

```powershell
python init_db.py
```

This applies pending Alembic migrations and verifies the application tables.

For an existing database created before Alembic, verify schema equivalence before recording the initial migration:

```powershell
python -m alembic check
python -m alembic stamp head
```

Only stamp an existing database after confirming that its schema matches the migration.

### 7. Start the backend

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Swagger documentation: http://127.0.0.1:8000/docs

### 8. Start the expiry worker

In a separate terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python expiry_worker.py
```

Run one worker instance during local development.

### 9. Start the Angular frontend

In another terminal:

```powershell
Set-Location .\frontend
npm ci
npm start
```

Dashboard: http://localhost:4200

### 10. Build the frontend

From the `frontend` directory:

```powershell
npm run build
```

## Database Migrations

Check the current migration:

```powershell
python -m alembic current
```

Check schema consistency:

```powershell
python -m alembic check
```

Generate a migration after changing SQLAlchemy models:

```powershell
python -m alembic revision --autogenerate -m "Describe schema change"
```

Review generated migrations before applying them.

Apply migrations:

```powershell
python -m alembic upgrade head
```

## Automated Testing

Integration tests use the dedicated `stockflow_test` database.

Run the backend test suite:

```powershell
python -m pytest -v
```

The test fixtures reset the isolated test schema using Alembic migrations. Never configure the test database to point to a database containing important development or production data.

### Concurrency demonstration

```powershell
python test_concurrency.py
```

This manual demonstration requires product ID 6 to be the dedicated concurrency test product with exactly 10 units available. It tests concurrent reservations and verifies inventory restoration.

## Production Readiness

StockFlow is currently a development-stage project.

Before production deployment, implement:

- Authentication and authorization.
- Protection of operational endpoints.
- Production secret management.
- Structured logging and monitoring.
- Frontend automated testing.
- Rate limiting and additional security controls.
- Docker-based deployment.
- Continuous integration and delivery.
- Backup, restore, and recovery verification.
- A suitable project license.

Do not expose the current application publicly as a production service without these controls.

## License

No project license is currently specified. Select and add an appropriate license before distributing the project.