"""
config.py — Application configuration and database connection pool.

Credentials are loaded from environment variables.
Locally: set them in .env (loaded by app.py via python-dotenv).
On Railway / Render: set DATABASE_URL in the service's environment tab.
"""

import os
import psycopg2
from psycopg2 import pool
from urllib.parse import urlparse

# ── Database credentials ───────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Railway and Render still issue postgres:// URLs.
# psycopg2 requires postgresql:// — fix it here once for the whole app.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Parse individual components (used for local fallback and force_db.py)
if DATABASE_URL:
    _p       = urlparse(DATABASE_URL)
    DB_NAME  = _p.path.lstrip("/")
    DB_USER  = _p.username
    DB_PASSWORD = _p.password
    DB_HOST  = _p.hostname
    DB_PORT  = str(_p.port) if _p.port else "5432"
else:
    DB_NAME     = os.getenv("DB_NAME",     "clinic_booking")
    DB_USER     = os.getenv("DB_USER",     "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST     = os.getenv("DB_HOST",     "localhost")
    DB_PORT     = os.getenv("DB_PORT",     "5432")

# ── Flask secret key ───────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-key-change-in-production")

# ── Connection pool (module-level singleton) ───────────────────────────────────
_pool: psycopg2.pool.SimpleConnectionPool | None = None


def _build_conn_kwargs() -> dict:
    """
    Returns the psycopg2 connection keyword arguments.

    When DATABASE_URL is set (cloud deployment), we pass it as the DSN string
    directly so that all SSL parameters embedded in the URL are preserved.
    Railway requires SSL — passing the DSN directly is the safest approach.
    """
    if DATABASE_URL:
        return {"dsn": DATABASE_URL, "sslmode": "require"}
    # Local development — no SSL needed
    return {
        "dbname":   DB_NAME,
        "user":     DB_USER,
        "password": DB_PASSWORD,
        "host":     DB_HOST,
        "port":     DB_PORT,
    }


def init_db_pool(app) -> None:
    """Creates the psycopg2 connection pool. Called once at startup."""
    global _pool
    kwargs = _build_conn_kwargs()
    _pool = psycopg2.pool.SimpleConnectionPool(minconn=1, maxconn=10, **kwargs)
    app.logger.info(
        "PostgreSQL connection pool initialised (min=1, max=10). "
        f"Host: {DB_HOST or 'from DATABASE_URL'}"
    )


def get_db() -> psycopg2.extensions.connection:
    """Borrows a connection from the pool. Always pair with release_db()."""
    global _pool
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db_pool() first.")
    return _pool.getconn()


def release_db(conn: psycopg2.extensions.connection) -> None:
    """Returns a connection to the pool."""
    global _pool
    if _pool and conn:
        _pool.putconn(conn)
