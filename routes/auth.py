"""
routes/auth.py — Authentication routes (login, register, logout).

Blueprint prefix: none (routes are at the app root level).
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from config import get_db, release_db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles user login for all roles.

    GET  → renders the login form.
    POST → reads email + password from the form, looks up the user in `users`,
           verifies the password hash, populates the session, then redirects
           to the role-appropriate dashboard.
           On failure → re-renders the form with a flash error message.
    """
    # Already logged in? Send to dashboard.
    if "user_id" in session:
        return _redirect_by_role(session["role"])

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        try:
            cur = conn.cursor()
            # Parameterised query — prevents SQL injection
            cur.execute(
                "SELECT id, name, email, password_hash, role FROM users WHERE email = %s",
                (email,)
            )
            user = cur.fetchone()
            cur.close()
        finally:
            release_db(conn)

        if user and check_password_hash(user[3], password):
            # Populate session with the minimum required data
            session["user_id"] = user[0]
            session["name"]    = user[1]
            session["email"]   = user[2]
            session["role"]    = user[4]
            flash(f"Welcome back, {user[1]}!", "success")
            return _redirect_by_role(user[4])

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Self-registration for patients only.
    Admins create doctor accounts; patients register themselves here.

    GET  → renders the registration form.
    POST → validates all fields, checks for duplicate email, hashes the
           password, inserts a new patient row, then redirects to login.
    """
    if "user_id" in session:
        return _redirect_by_role(session["role"])

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        # ── Server-side validation ─────────────────────────────────────────
        if not all([name, email, password, confirm]):
            flash("All fields are required.", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        conn = get_db()
        try:
            cur = conn.cursor()

            # Check for duplicate email
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("That email address is already registered.", "error")
                cur.close()
                return render_template("register.html")

            cur.execute(
                """INSERT INTO users (name, email, password_hash, role)
                   VALUES (%s, %s, %s, 'patient')""",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
            cur.close()
            flash("Account created! You can now log in.", "success")
            return redirect(url_for("auth.login"))

        except Exception:
            conn.rollback()
            flash("Registration failed. Please try again.", "error")
        finally:
            release_db(conn)

    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    """
    Clears the session and redirects to the login page.
    Works for all roles.
    """
    name = session.get("name", "")
    session.clear()
    flash(f"You have been logged out{', ' + name if name else ''}.", "success")
    return redirect(url_for("auth.login"))


# ── Helper ────────────────────────────────────────────────────────────────────

def _redirect_by_role(role: str):
    """Returns a redirect response to the correct dashboard for the given role."""
    destinations = {
        "admin":   "admin.dashboard",
        "doctor":  "doctor.dashboard",
        "patient": "patient.dashboard",
    }
    return redirect(url_for(destinations.get(role, "auth.login")))
