"""
config.py — Application configuration and database connection pool.

Database credentials and secrets are now loaded from environment variables.
Set these in your environment or deployment platform (e.g., Render).
"""

import os
import psycopg2
from psycopg2 import pool
from urllib.parse import urlparse

# ── Database credentials ───────────────────────────────────────────────────────
# Use DATABASE_URL if available (common in cloud deployments like Render)
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Parse DATABASE_URL for PostgreSQL
    parsed = urlparse(DATABASE_URL)
    DB_NAME = parsed.path.lstrip('/')
    DB_USER = parsed.username
    DB_PASSWORD = parsed.password
    DB_HOST = parsed.hostname
    DB_PORT = str(parsed.port) if parsed.port else '5432'
else:
    # Fallback to individual environment variables
    DB_NAME = os.getenv('DB_NAME', 'clinic_booking')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')

# ── Flask secret key (used to sign session cookies) ───────────────────────────
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required. Please set it to a long random string.")

# ── Connection pool (module-level singleton) ───────────────────────────────────
_pool: psycopg2.pool.SimpleConnectionPool | None = None


def init_db_pool(app) -> None:
    """
    Creates the psycopg2 connection pool and attaches it to the app.
    Called once at startup from app.py.

    minconn=1  — always keeps one live connection ready.
    maxconn=10 — caps concurrent connections at 10.
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
    """
    Borrows a connection from the pool.
    Always pair with release_db() in a try/finally block so the
    connection is returned even if an exception is raised.
    """
    global _pool
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db_pool() first.")
    return _pool.getconn()


def release_db(conn: psycopg2.extensions.connection) -> None:
    """
    Returns a connection to the pool.
    The connection must have been committed or rolled back before calling this.
    """
    global _pool
    if _pool and conn:
        _pool.putconn(conn)
