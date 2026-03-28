"""
routes/doctor.py — Doctor-only routes.

Blueprint prefix: /doctor  (set in app.py)

Routes
------
GET       /doctor/dashboard               — today's appointments + stats
GET/POST  /doctor/slots/add               — add a new available time slot
GET       /doctor/bookings                — full booking history
POST      /doctor/booking/<id>/confirm    — confirm a pending booking
POST      /doctor/booking/<id>/reject     — reject (cancel) a pending booking
POST      /doctor/booking/<id>/complete   — mark a confirmed booking as completed
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from config import get_db, release_db
from routes import login_required
from datetime import date, datetime

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.route("/dashboard")
@login_required("doctor")
def dashboard():
    """
    Doctor's home screen.

    Fetches:
      - All bookings scheduled for today (with patient name and time).
      - Count of all pending bookings (awaiting confirmation).
      - Count of all confirmed upcoming bookings.

    Returns: rendered doctor_dashboard.html.
    """
    doctor_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()

        # Today's appointments for this doctor
        cur.execute(
            """SELECT b.id, p.name AS patient_name,
                      ts.start_time, ts.end_time,
                      b.status, b.reason
               FROM bookings b
               JOIN users      p  ON b.patient_id   = p.id
               JOIN time_slots ts ON b.time_slot_id = ts.id
               WHERE b.doctor_id = %s
                 AND ts.date = CURRENT_DATE
               ORDER BY ts.start_time""",
            (doctor_id,)
        )
        today_bookings = cur.fetchall()

        # Total pending bookings (all dates)
        cur.execute(
            "SELECT COUNT(*) FROM bookings WHERE doctor_id = %s AND status = 'pending'",
            (doctor_id,)
        )
        pending_count = cur.fetchone()[0]

        # Total confirmed bookings (all dates)
        cur.execute(
            "SELECT COUNT(*) FROM bookings WHERE doctor_id = %s AND status = 'confirmed'",
            (doctor_id,)
        )
        confirmed_count = cur.fetchone()[0]

        cur.close()
    finally:
        release_db(conn)

    return render_template(
        "doctor_dashboard.html",
        today_bookings=today_bookings,
        pending_count=pending_count,
        confirmed_count=confirmed_count,
        today=date.today()
    )


@doctor_bp.route("/slots/add", methods=["GET", "POST"])
@login_required("doctor")
def add_slot():
    """
    Allows the logged-in doctor to add an available time slot.

    GET  → renders the add-slot form.
    POST → validates date (must not be in the past), start time, end time,
           then inserts a new row into time_slots with is_available=TRUE.
           Redirects to dashboard on success.
    """
    if request.method == "POST":
        slot_date  = request.form.get("date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time   = request.form.get("end_time", "").strip()
        doctor_id  = session["user_id"]

        if not all([slot_date, start_time, end_time]):
            flash("All fields are required.", "error")
            return render_template("add_slot.html")

        # Validate the date is today or in the future
        try:
            slot_date_obj = datetime.strptime(slot_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format.", "error")
            return render_template("add_slot.html")

        if slot_date_obj < date.today():
            flash("Cannot add slots for past dates.", "error")
            return render_template("add_slot.html")

        # Validate start < end
        try:
            start_obj = datetime.strptime(start_time, "%H:%M").time()
            end_obj   = datetime.strptime(end_time,   "%H:%M").time()
        except ValueError:
            flash("Invalid time format.", "error")
            return render_template("add_slot.html")

        if start_obj >= end_obj:
            flash("Start time must be before end time.", "error")
            return render_template("add_slot.html")

        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO time_slots (doctor_id, date, start_time, end_time, is_available)
                   VALUES (%s, %s, %s, %s, TRUE)""",
                (doctor_id, slot_date, start_time, end_time)
            )
            conn.commit()
            cur.close()
            flash("Time slot added successfully.", "success")
            return redirect(url_for("doctor.dashboard"))

        except Exception:
            conn.rollback()
            flash("Failed to add time slot. Please try again.", "error")
        finally:
            release_db(conn)

    return render_template("add_slot.html")


@doctor_bp.route("/bookings")
@login_required("doctor")
def bookings():
    """
    Full booking history for the logged-in doctor.

    Returns all bookings (all statuses, all dates) ordered by most recent.
    Returns: rendered doctor_bookings.html.
    """
    doctor_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT b.id,
                      p.name  AS patient_name,
                      ts.date,
                      ts.start_time,
                      ts.end_time,
                      b.status,
                      b.reason,
                      b.created_at
               FROM bookings b
               JOIN users      p  ON b.patient_id   = p.id
               JOIN time_slots ts ON b.time_slot_id = ts.id
               WHERE b.doctor_id = %s
               ORDER BY ts.date DESC, ts.start_time DESC""",
            (doctor_id,)
        )
        all_bookings = cur.fetchall()
        cur.close()
    finally:
        release_db(conn)

    return render_template("doctor_bookings.html", bookings=all_bookings)


@doctor_bp.route("/booking/<int:booking_id>/confirm", methods=["POST"])
@login_required("doctor")
def confirm_booking(booking_id):
    """
    Confirms a pending booking.

    Only the doctor who owns the booking can confirm it.
    Transitions status: pending → confirmed.

    Receives: booking_id from URL path.
    Redirects: back to doctor.bookings.
    """
    doctor_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE bookings
               SET status = 'confirmed'
               WHERE id = %s AND doctor_id = %s AND status = 'pending'""",
            (booking_id, doctor_id)
        )
        if cur.rowcount == 0:
            flash("Booking not found or already processed.", "error")
        else:
            conn.commit()
            flash("Booking confirmed successfully.", "success")
        cur.close()
    except Exception:
        conn.rollback()
        flash("Failed to confirm booking.", "error")
    finally:
        release_db(conn)

    return redirect(url_for("doctor.bookings"))


@doctor_bp.route("/booking/<int:booking_id>/reject", methods=["POST"])
@login_required("doctor")
def reject_booking(booking_id):
    """
    Rejects a pending booking and restores the time slot.

    Transitions status: pending → cancelled.
    Also sets time_slots.is_available = TRUE so the slot becomes bookable again.

    Receives: booking_id from URL path.
    Redirects: back to doctor.bookings.
    """
    doctor_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()

        # Fetch the time_slot_id so we can restore it
        cur.execute(
            """SELECT time_slot_id FROM bookings
               WHERE id = %s AND doctor_id = %s AND status = 'pending'""",
            (booking_id, doctor_id)
        )
        row = cur.fetchone()

        if not row:
            flash("Booking not found or already processed.", "error")
        else:
            time_slot_id = row[0]
            # Cancel booking and restore slot availability in one transaction
            cur.execute(
                "UPDATE bookings   SET status = 'cancelled' WHERE id = %s",
                (booking_id,)
            )
            cur.execute(
                "UPDATE time_slots SET is_available = TRUE  WHERE id = %s",
                (time_slot_id,)
            )
            conn.commit()
            flash("Booking rejected and time slot restored.", "success")

        cur.close()
    except Exception:
        conn.rollback()
        flash("Failed to reject booking.", "error")
    finally:
        release_db(conn)

    return redirect(url_for("doctor.bookings"))


@doctor_bp.route("/booking/<int:booking_id>/complete", methods=["POST"])
@login_required("doctor")
def complete_booking(booking_id):
    """
    Marks a confirmed booking as completed.

    Transitions status: confirmed → completed.
    Only confirmed bookings can be completed (not pending/cancelled).

    Receives: booking_id from URL path.
    Redirects: back to doctor.bookings.
    """
    doctor_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE bookings
               SET status = 'completed'
               WHERE id = %s AND doctor_id = %s AND status = 'confirmed'""",
            (booking_id, doctor_id)
        )
        if cur.rowcount == 0:
            flash("Booking not found or not in confirmed state.", "error")
        else:
            conn.commit()
            flash("Booking marked as completed.", "success")
        cur.close()
    except Exception:
        conn.rollback()
        flash("Failed to mark booking as completed.", "error")
    finally:
        release_db(conn)

    return redirect(url_for("doctor.bookings"))
