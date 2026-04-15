"""
app.py — Application entry point.

On every startup (local or Railway), create_app() ensures all database
tables exist before the first request is served.
"""

import os
import logging

from dotenv import load_dotenv
load_dotenv()  # must be before importing config

from flask import Flask, redirect, url_for
from config import SECRET_KEY, init_db_pool, get_db, release_db
from routes.auth    import auth_bp
from routes.admin   import admin_bp
from routes.doctor  import doctor_bp
from routes.patient import patient_bp

log = logging.getLogger(__name__)


def ensure_tables(app):
    """
    Creates all database tables if they don't already exist.
    Runs inside create_app() on every startup — safe to call repeatedly
    because every statement uses CREATE TABLE IF NOT EXISTS.
    """
    sql_statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            name          VARCHAR(100)  NOT NULL,
            email         VARCHAR(150)  UNIQUE NOT NULL,
            password_hash VARCHAR(255)  NOT NULL,
            role          VARCHAR(20)   NOT NULL CHECK (role IN ('admin','doctor','patient')),
            specialty     VARCHAR(100)  NULL,
            created_at    TIMESTAMP     DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS time_slots (
            id           SERIAL PRIMARY KEY,
            doctor_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date         DATE    NOT NULL,
            start_time   TIME    NOT NULL,
            end_time     TIME    NOT NULL,
            is_available BOOLEAN DEFAULT TRUE,
            created_at   TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id           SERIAL PRIMARY KEY,
            patient_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            doctor_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            time_slot_id INTEGER NOT NULL REFERENCES time_slots(id) ON DELETE CASCADE,
            status       VARCHAR(20) DEFAULT 'pending'
                             CHECK (status IN ('pending','confirmed','cancelled','completed')),
            reason       TEXT,
            created_at   TIMESTAMP DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_bookings_patient ON bookings(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_doctor  ON bookings(doctor_id)",
        "CREATE INDEX IF NOT EXISTS idx_slots_doctor     ON time_slots(doctor_id)",
        "CREATE INDEX IF NOT EXISTS idx_slots_date       ON time_slots(date)",
    ]

    conn = get_db()
    try:
        cur = conn.cursor()
        for stmt in sql_statements:
            cur.execute(stmt)
        conn.commit()
        cur.close()
        app.logger.info("Database tables verified / created.")
    except Exception as exc:
        conn.rollback()
        app.logger.error("FATAL: could not create tables — %s", exc)
        raise   # crash loudly so Railway shows the real error
    finally:
        release_db(conn)


def create_app() -> Flask:
    """Factory function that builds and configures the Flask application."""
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    logging.basicConfig(level=logging.INFO)

    # Initialise DB connection pool
    init_db_pool(app)

    # Guarantee tables exist on every deploy / restart
    ensure_tables(app)

    # Register role-based blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,   url_prefix="/admin")
    app.register_blueprint(doctor_bp,  url_prefix="/doctor")
    app.register_blueprint(patient_bp, url_prefix="/patient")

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
