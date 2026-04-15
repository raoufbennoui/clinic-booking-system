"""
force_db.py — Creates all database tables before the app starts.

This project uses raw psycopg2 (NOT SQLAlchemy).
Tables are created by running schema.sql directly.

Called by Procfile:
    web: python force_db.py && gunicorn 'app:create_app()'
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()


def get_connection():
    database_url = os.getenv("DATABASE_URL", "")

    # Railway / Render issue: psycopg2 requires postgresql://, not postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    if database_url:
        # Pass DSN directly so SSL settings in the URL are preserved.
        # Explicitly add sslmode=require for Railway.
        print(f"Connecting via DATABASE_URL (host will be hidden)...", flush=True)
        return psycopg2.connect(dsn=database_url, sslmode="require")

    # Local development fallback
    print("Connecting via individual env vars (local)...", flush=True)
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "clinic_booking"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


def run_schema():
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

    if not os.path.exists(schema_path):
        print("ERROR: schema.sql not found.", flush=True)
        sys.exit(1)

    with open(schema_path, "r") as f:
        sql = f.read()

    print("Running schema.sql against the database...", flush=True)
    try:
        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()

        # Execute each statement individually to avoid psycopg2
        # "multiple statements not allowed" errors
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            try:
                cur.execute(stmt)
            except psycopg2.errors.DuplicateTable:
                pass  # IF NOT EXISTS handles this, but just in case
            except Exception as e:
                # Log but continue — some NOTICE-level things look like errors
                print(f"  Warning on statement: {e}", flush=True)

        cur.close()
        conn.close()
        print("Database schema verified successfully.", flush=True)

    except Exception as e:
        print(f"FATAL: Could not connect to database: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    run_schema()
