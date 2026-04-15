"""
app.py — Application entry point.

Creates the Flask app, registers blueprints, initialises the DB pool,
then starts the development server.
"""

import os

# Load .env file BEFORE importing config, so env vars are available
# when config.py reads them at import time.
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, redirect, url_for
from config import SECRET_KEY, init_db_pool
from routes.auth    import auth_bp
from routes.admin   import admin_bp
from routes.doctor  import doctor_bp
from routes.patient import patient_bp


def create_app() -> Flask:
    """Factory function that builds and configures the Flask application."""
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    # Initialise the PostgreSQL connection pool
    init_db_pool(app)

    # Register role-based blueprints with URL prefixes
    app.register_blueprint(auth_bp)                           # /login, /register, /logout
    app.register_blueprint(admin_bp,   url_prefix="/admin")   # /admin/...
    app.register_blueprint(doctor_bp,  url_prefix="/doctor")  # /doctor/...
    app.register_blueprint(patient_bp, url_prefix="/patient") # /patient/...

    @app.route("/")
    def index():
        """Root URL redirects to the login page."""
        return redirect(url_for("auth.login"))

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
