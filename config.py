"""
config.py — Application configuration and database connection pool.

Credentials are loaded from environment variables.
Locally: set them in .env (loaded by app.py via python-dotenv).
On Render: set them in the Environment tab of your service.
"""

import os
import psycopg2
from psycopg2 import pool
from urllib.parse import urlparse

# ── Database credentials ───────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Render (and some other platforms) still issue postgres:// URLs.
    # psycopg2 requires postgresql:// — fix it silently.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    parsed  = urlparse(DATABASE_URL)
    DB_NAME = parsed.path.lstrip("/")
    DB_USER = parsed.username
    DB_PASSWORD = parsed.password
    DB_HOST = parsed.hostname
    DB_PORT = str(parsed.port) if parsed.port else "5432"
else:
    # Individual env vars — used locally when no DATABASE_URL is set
    DB_NAME     = os.getenv("DB_NAME",     "clinic_booking")
    DB_USER     = os.getenv("DB_USER",     "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST     = os.getenv("DB_HOST",     "localhost")
    DB_PORT     = os.getenv("DB_PORT",     "5432")

# ── Flask secret key ───────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-key-change-in-production")

# ── Connection pool (module-level singleton) ───────────────────────────────────
_pool: psycopg2.pool.SimpleConnectionPool | None = None


def init_db_pool(app) -> None:
    """
    Creates the psycopg2 connection pool.
    Called once at startup from app.py.
    """
    global _pool
    _pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    app.logger.info("PostgreSQL connection pool initialised (min=1, max=10).")


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
