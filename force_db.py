"""
force_db.py — Ensures all database tables exist before the app starts.

This project uses raw psycopg2 (NOT SQLAlchemy), so tables are created
by running schema.sql directly against the database.

Called by the Procfile before gunicorn:
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
        parsed = urlparse(database_url)
        return psycopg2.connect(
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432,
        )

    # Fallback to individual env vars (local development)
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "clinic_booking"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


def run_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    if not os.path.exists(schema_path):
        print("ERROR: schema.sql not found.", flush=True)
        sys.exit(1)

    with open(schema_path, "r") as f:
        sql = f.read()

    print("Connecting to database...", flush=True)
    try:
        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print("Database tables verified / created successfully.", flush=True)
    except Exception as e:
        print(f"ERROR: Could not initialise database: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    run_schema()
