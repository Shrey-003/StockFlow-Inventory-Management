# StockFlow

StockFlow is a full-stack inventory management and reservation application built to demonstrate reliable inventory operations, transactional data integrity, concurrent request handling, and role-based access control.

The application consists of an Angular dashboard, a FastAPI backend, and a PostgreSQL database.

## Features

### Inventory Management

- Create, read, update, and delete products.
- Unique SKU enforcement.
- Product input validation.
- Inventory quantity and value summaries.
- Low-stock indicators.

### Reservations

- Reserve inventory for a configurable duration.
- Atomic stock deduction during reservation creation.
- Prevent reservations exceeding available inventory.
- Cancel active reservations and restore stock.
- Automatically expire overdue reservations.
- Restore inventory when reservations expire.
- Reservation history and pagination.
- Reservation ownership linked to authenticated users.
- Admin access to all reservation records.
- Staff access restricted to their own reservations.

### Authentication and Authorization

- Username and password authentication.
- Argon2 password hashing using pwdlib.
- JWT bearer-token authentication using PyJWT.
- Configurable access-token expiration.
- Admin and staff role-based permissions.
- Backend-enforced authorization.
- Protected product and reservation operations.
- Secure initial administrator creation.
- Staff account creation through a local setup utility.
- Dedicated worker-token authentication.
- Angular login and logout functionality.
- Session restoration and authenticated HTTP requests.
- User-specific reservation visibility.

### Engineering and Reliability

- PostgreSQL persistence with SQLAlchemy.
- Database migrations managed by Alembic.
- Dedicated integration-test database.
- Automated backend tests.
- Concurrent reservation demonstration.
- Background reservation-expiry worker.
- Environment-based application configuration.
- Interactive API documentation.

## Technology Stack

| Area | Technology |
|---|---|
| Frontend | Angular, TypeScript, HTML, CSS |
| Backend | Python, FastAPI, Uvicorn |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Authentication | PyJWT, pwdlib, Argon2 |
| Migrations | Alembic |
| Testing | pytest, HTTPX, HTTPX2 |
| Version Control | Git |

## Architecture

```text
Angular Dashboard
       |
       | HTTP requests with JWT bearer token
       v
FastAPI Backend
       |
       | SQLAlchemy
       v
PostgreSQL Database

Expiry Worker
       |
       | Periodic API requests with X-Worker-Token
       v
FastAPI Reservation Expiry Endpoint
```

## Local Development Setup

### 1. Prerequisites

Install the following:

- Python 3.14
- PostgreSQL 18
- Node.js
- npm
- Git

### 2. Clone the Repository

```powershell
git clone <repository-url>
Set-Location StockFlow
```

### 3. Create PostgreSQL Databases

Create two databases:

- `stockflow` for application development.
- `stockflow_test` for automated integration tests.

The PostgreSQL user must have permission to manage the test schema.

Keep the development and test databases separate.

### 4. Configure Environment Variables

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Configure the following settings in `.env`:

| Variable | Description |
|---|---|
| `DB_HOST` | PostgreSQL server hostname |
| `DB_PORT` | PostgreSQL server port |
| `DB_NAME` | Development database name |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `JWT_SECRET_KEY` | Secret used to sign JWT access tokens |
| `WORKER_API_TOKEN` | Separate authentication token for the expiry worker |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access-token lifetime in minutes |

#### Generate Authentication Secrets

Generate two independent random secrets by running this command twice:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use one generated value for `JWT_SECRET_KEY` and the other for `WORKER_API_TOKEN`.

Both secrets must contain at least 32 characters. Never reuse the same secret for both purposes.

The default access-token lifetime is 30 minutes. The configured value must be between 1 and 1440 minutes.

The authentication settings are required. The application validates the configuration during startup.

**Security precautions:**

- Never commit real credentials or the `.env` file.
- Never include actual secret values in source code or documentation.
- Keep the worker token separate from user authentication tokens.
- Use `.env.example` only as a template containing placeholders.

### 5. Set Up Python

From the project root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Use the project's virtual environment when executing Python, Alembic, and pytest commands.

### 6. Initialize the Database

For a fresh database:

```powershell
python init_db.py
```

This applies pending Alembic migrations and verifies the required application tables.

#### Existing Database Created Before Alembic

For an existing database containing the original inventory schema:

1. Create and verify a database backup.
2. Confirm that the existing schema matches the original migration revision `f49feedbdf32`.
3. Record the original migration revision.
4. Apply subsequent migrations.

```powershell
python -m alembic stamp f49feedbdf32
python -m alembic upgrade head
```

If the database is already recorded at `f49feedbdf32`, only run:

```powershell
python -m alembic upgrade head
```

**Important:** Do not stamp a pre-authentication database directly at `head`. Doing so would skip the authentication and reservation-ownership migration.

The authentication migration creates the `users` table and adds a nullable `user_id` foreign key to reservations. Existing historical reservations are preserved without assigning fictitious owners.

Verify the resulting migration:

```powershell
python -m alembic current
python -m alembic check
```

### 7. Create the Initial Administrator

There is no public signup endpoint or default administrator password.

After initializing the database, create the first administrator:

```powershell
python create_admin.py
```

Enter the administrator username and password when prompted.

Password entry is hidden. Passwords are stored as Argon2 password hashes.

The initial administrator utility prevents creation of an additional administrator if one already exists.

New passwords must contain between 12 and 128 characters.

### 8. Create Staff Accounts

An active administrator must already exist.

Run:

```powershell
python create_staff.py
```

Enter the staff username and password when prompted.

The utility creates a staff account in the configured development database.

### 9. Start the Backend

Open a terminal in the project root:

```powershell
.\.venv\Scripts\Activate.ps1

python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The backend runs at:

http://127.0.0.1:8000

Swagger API documentation:

http://127.0.0.1:8000/docs

### 10. Start the Expiry Worker

Open a separate terminal in the project root:

```powershell
.\.venv\Scripts\Activate.ps1

python expiry_worker.py
```

The worker checks for overdue reservations every 30 seconds.

It authenticates with the backend using the `X-Worker-Token` HTTP header and the configured `WORKER_API_TOKEN`.

Run one worker instance during local development.

The worker token must never be exposed to the Angular frontend.

### 11. Start the Angular Frontend

Open another terminal:

```powershell
Set-Location .\frontend

npm ci
npm start
```

The Angular dashboard runs at:

http://localhost:4200

Sign in using an administrator or staff account created through the local setup utilities.

The Angular application stores the access token in browser session storage and attaches it to protected API requests through its HTTP interceptor.

### 12. Build the Frontend

From the `frontend` directory:

```powershell
npm run build
```

The production build is generated in:

`frontend/dist/frontend`

## Authentication and API Permissions

### Authentication Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/login` | Authenticate using username and password |
| GET | `/auth/me` | Retrieve the authenticated user's information |
| GET | `/health` | Application health check |
| GET | `/health/db` | Database health check |

Successful authentication returns a JWT bearer access token.

Protected API requests must include:

```text
Authorization: Bearer <access-token>
```

The access-token lifetime is controlled through `ACCESS_TOKEN_EXPIRE_MINUTES`.

### Role-Based Permissions

| Operation | Admin | Staff |
|---|---|---|
| View products | Yes | Yes |
| Create products | Yes | No |
| Update products | Yes | No |
| Delete products | Yes | No |
| Create reservations | Yes | Yes |
| View all reservations | Yes | No |
| View own reservations | Yes | Yes |
| Cancel any reservation | Yes | No |
| Cancel own reservations | Yes | Yes |

Authorization is enforced by the FastAPI backend, independently of the Angular interface.

Hiding a button in the frontend does not replace backend permission checks.

### Reservation Ownership

- Newly created reservations are associated with the authenticated user.
- Staff users can view and cancel their own reservations.
- Staff users cannot access another user's reservation records.
- Administrators can view and manage all reservations.
- Historical reservations created before ownership tracking retain a nullable `user_id` and remain accessible to administrators.

### Background Worker Authorization

The reservation-expiry endpoint is protected separately from normal user authentication.

The expiry worker must provide:

```text
X-Worker-Token: <worker-api-token>
```

The token is configured through `WORKER_API_TOKEN`.

An administrator or staff JWT cannot substitute for this service credential.

## Database Migrations

Check the current migration:

```powershell
python -m alembic current
```

Check database schema consistency:

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

The test fixtures reset the isolated test schema through Alembic migrations and verify database identity before performing database operations.

The automated tests cover:

- Configuration validation.
- Authentication and token handling.
- Authorization and role restrictions.
- Reservation ownership.
- Inventory operations.
- Reservation creation and cancellation.
- Reservation expiry.
- API behavior.

Never configure the test database to point to a database containing important development or production data.

### Concurrency Demonstration

```powershell
python test_concurrency.py
```

This manual demonstration requires product ID 6 to be the dedicated concurrency test product with exactly 10 units available.

It tests concurrent reservations and verifies inventory restoration.

## Production Readiness

StockFlow is currently a development-stage project.

### Implemented

- Username and password authentication.
- Argon2 password hashing.
- JWT bearer-token validation and expiration.
- Admin and staff role-based access control.
- Protected product and reservation operations.
- Reservation ownership enforcement.
- Dedicated worker authentication.
- Environment-based authentication secret configuration.
- Alembic migrations for users and reservation ownership.
- Angular login and logout functionality.
- Authenticated HTTP requests through an Angular interceptor.
- Automated backend authentication and authorization tests.

### Remaining Before Production Deployment

- HTTPS/TLS and production reverse-proxy configuration.
- Production secret management and secret rotation.
- Login rate limiting and brute-force protection.
- Stronger frontend session protection against XSS.
- Password reset and account-management workflows.
- Structured logging, monitoring, alerting, and audit trails.
- Automated Angular frontend and end-to-end tests.
- Production deployment configuration and process supervision.
- Docker-based deployment.
- Continuous integration and continuous delivery.
- Verified backup, restore, and disaster-recovery procedures.
- Database least-privilege configuration.
- A suitable project license.

Do not expose the current development configuration publicly as a production service.

## License

No project license is currently specified. Select and add an appropriate license before distributing the project.
