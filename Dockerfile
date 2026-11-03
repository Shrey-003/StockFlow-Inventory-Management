
# --------------------------------------------------
# StockFlow FastAPI backend
# --------------------------------------------------

FROM python:3.14.10-slim

# Python runtime configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Create an unprivileged application user
RUN groupadd --system --gid 10001 app \
    && useradd --system \
       --uid 10001 \
       --gid app \
       --home-dir /app \
       --no-create-home \
       --shell /usr/sbin/nologin \
       app

# Install pinned Python dependencies
COPY requirements.txt .

RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy application source files
COPY --chown=10001:10001 \
    main.py \
    auth_routes.py \
    auth_schemas.py \
    config.py \
    database.py \
    dependencies.py \
    expiry_worker.py \
    worker_config.py \
    login_rate_limiter.py \
    models.py \
    schemas.py \
    security.py \
    ./

# Include Alembic migration configuration and scripts
COPY --chown=10001:10001 alembic.ini ./alembic.ini
COPY --chown=10001:10001 alembic/ ./alembic/

# Run as a non-root user
USER 10001:10001

EXPOSE 8000

# API liveness check
HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

# Start FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
