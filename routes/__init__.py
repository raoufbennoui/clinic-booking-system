"""
routes/__init__.py — Shared utilities for all route blueprints.

Exports:
  login_required(role)  — decorator that guards routes behind authentication
                          and optional role enforcement.
"""

from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(role: str | None = None):
    """
    Decorator factory that protects a route behind login and an optional role check.

    Usage
    -----
    @login_required()            # any logged-in user
    @login_required('admin')     # only admins
    @login_required('doctor')    # only doctors
    @login_required('patient')   # only patients

    Behaviour
    ---------
    1. If the user is NOT logged in → flash error, redirect to login.
    2. If a role is specified and the session role does NOT match → flash error,
       redirect to login.
    3. Otherwise → call the original view function normally.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Step 1: check login state
            if "user_id" not in session:
                flash("Please log in to access this page.", "error")
                return redirect(url_for("auth.login"))

            # Step 2: check role if specified
            if role is not None and session.get("role") != role:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("auth.login"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
