"""
routes/admin.py — Admin-only routes.

Blueprint prefix: /admin  (set in app.py)

Routes
------
GET  /admin/dashboard         — stats + doctor list
GET  /admin/bookings          — all bookings with optional filters
GET/POST /admin/add-doctor    — create a new doctor account
POST /admin/remove-doctor/<id>— delete a doctor account
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from config import get_db, release_db
from routes import login_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@login_required("admin")
def dashboard():
    """
    Admin main dashboard.

    Fetches:
      - Total bookings created today (across all doctors).
      - Total bookings currently in 'pending' status.
      - Total bookings currently in 'confirmed' status.
      - Full list of all doctor accounts (id, name, email, specialty, joined date).

    Returns: rendered admin_dashboard.html with the above data.
    """
    conn = get_db()
    try:
        cur = conn.cursor()

        # Count of bookings created today
        cur.execute(
            "SELECT COUNT(*) FROM bookings WHERE DATE(created_at) = CURRENT_DATE"
        )
        total_today = cur.fetchone()[0]

        # Count of all pending bookings
        cur.execute("SELECT COUNT(*) FROM bookings WHERE status = 'pending'")
        total_pending = cur.fetchone()[0]

        # Count of all confirmed bookings
        cur.execute("SELECT COUNT(*) FROM bookings WHERE status = 'confirmed'")
        total_confirmed = cur.fetchone()[0]

        # All doctor accounts ordered by most recently joined
        cur.execute(
            """SELECT id, name, email, specialty, created_at
               FROM users
               WHERE role = 'doctor'
               ORDER BY created_at DESC"""
        )
        doctors = cur.fetchall()

        cur.close()
    finally:
        release_db(conn)

    return render_template(
        "admin_dashboard.html",
        total_today=total_today,
        total_pending=total_pending,
        total_confirmed=total_confirmed,
        doctors=doctors
    )


@admin_bp.route("/bookings")
@login_required("admin")
def bookings():
    """
    System-wide booking list with optional filters.

    Query params:
      date   (YYYY-MM-DD) — filter by the appointment date
      status              — filter by booking status

    Joins bookings with patient name, doctor name, and time slot details.
    Returns: rendered admin_bookings.html with filtered booking rows.
    """
    filter_date   = request.args.get("date", "").strip()
    filter_status = request.args.get("status", "").strip()

    conn = get_db()
    try:
        cur = conn.cursor()

        # Build the query dynamically; parameterised to prevent SQL injection
        query = """
            SELECT b.id,
                   p.name  AS patient_name,
                   d.name  AS doctor_name,
                   d.specialty,
                   ts.date,
                   ts.start_time,
                   ts.end_time,
                   b.status,
                   b.reason,
                   b.created_at
            FROM bookings b
            JOIN users      p  ON b.patient_id   = p.id
            JOIN users      d  ON b.doctor_id    = d.id
            JOIN time_slots ts ON b.time_slot_id = ts.id
            WHERE 1=1
        """
        params = []

        if filter_date:
            query += " AND ts.date = %s"
            params.append(filter_date)

        if filter_status:
            query += " AND b.status = %s"
            params.append(filter_status)

        query += " ORDER BY ts.date DESC, ts.start_time DESC"

        cur.execute(query, params)
        all_bookings = cur.fetchall()
        cur.close()
    finally:
        release_db(conn)

    return render_template(
        "admin_bookings.html",
        bookings=all_bookings,
        filter_date=filter_date,
        filter_status=filter_status
    )


@admin_bp.route("/add-doctor", methods=["GET", "POST"])
@login_required("admin")
def add_doctor():
    """
    Creates a new doctor account.

    GET  → renders the add-doctor form.
    POST → validates all fields, checks for duplicate email, hashes the
           password, inserts the doctor row, redirects to dashboard on success.

    Receives (form fields): name, email, password, specialty.
    Returns: redirect to admin.dashboard on success; re-renders form on error.
    """
    if request.method == "POST":
        name      = request.form.get("name", "").strip()
        email     = request.form.get("email", "").strip().lower()
        password  = request.form.get("password", "")
        specialty = request.form.get("specialty", "").strip()

        if not all([name, email, password, specialty]):
            flash("All fields are required.", "error")
            return render_template("add_doctor.html")

        conn = get_db()
        try:
            cur = conn.cursor()

            # Prevent duplicate emails
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("A user with that email already exists.", "error")
                cur.close()
                return render_template("add_doctor.html")

            cur.execute(
                """INSERT INTO users (name, email, password_hash, role, specialty)
                   VALUES (%s, %s, %s, 'doctor', %s)""",
                (name, email, generate_password_hash(password), specialty)
            )
            conn.commit()
            cur.close()
            flash(f"Doctor {name} added successfully.", "success")
            return redirect(url_for("admin.dashboard"))

        except Exception:
            conn.rollback()
            flash("Failed to add doctor. Please try again.", "error")
        finally:
            release_db(conn)

    return render_template("add_doctor.html")


@admin_bp.route("/remove-doctor/<int:doctor_id>", methods=["POST"])
@login_required("admin")
def remove_doctor(doctor_id):
    """
    Permanently deletes a doctor account.

    Receives: doctor_id from URL path.
    Cascades: all time_slots and bookings for this doctor are deleted via
              ON DELETE CASCADE defined in the schema.

    POST only — triggered by a form submit (confirm dialog in JS).
    Redirects back to admin.dashboard after deletion.
    """
    conn = get_db()
    try:
        cur = conn.cursor()

        # Fetch name first so we can use it in the flash message
        cur.execute(
            "SELECT name FROM users WHERE id = %s AND role = 'doctor'",
            (doctor_id,)
        )
        doctor = cur.fetchone()

        if not doctor:
            flash("Doctor not found.", "error")
        else:
            cur.execute(
                "DELETE FROM users WHERE id = %s AND role = 'doctor'",
                (doctor_id,)
            )
            conn.commit()
            flash(f"Doctor {doctor[0]} has been removed.", "success")

        cur.close()
    except Exception:
        conn.rollback()
        flash("Failed to remove doctor.", "error")
    finally:
        release_db(conn)

    return redirect(url_for("admin.dashboard"))
