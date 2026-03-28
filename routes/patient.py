"""
routes/patient.py — Patient-only routes.

Blueprint prefix: /patient  (set in app.py)

Routes
------
GET      /patient/dashboard         — overview + upcoming appointments
GET      /patient/browse            — browse doctors with specialty filter
GET/POST /patient/book/<doctor_id>  — select slot and book appointment
GET      /patient/bookings          — patient's own booking history
POST     /patient/cancel/<id>       — cancel a pending booking
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from config import get_db, release_db
from routes import login_required

patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/dashboard")
@login_required("patient")
def dashboard():
    """
    Patient home screen.

    Fetches:
      - Total number of bookings made by this patient.
      - Count of pending bookings (awaiting doctor confirmation).
      - Next 3 upcoming confirmed appointments (today or later).

    Returns: rendered patient_dashboard.html.
    """
    patient_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()

        # Total bookings ever made by this patient
        cur.execute(
            "SELECT COUNT(*) FROM bookings WHERE patient_id = %s",
            (patient_id,)
        )
        total = cur.fetchone()[0]

        # Pending bookings waiting for doctor confirmation
        cur.execute(
            "SELECT COUNT(*) FROM bookings WHERE patient_id = %s AND status = 'pending'",
            (patient_id,)
        )
        pending = cur.fetchone()[0]

        # Upcoming confirmed appointments (today onwards), limit 3
        cur.execute(
            """SELECT b.id, d.name, d.specialty, ts.date, ts.start_time, b.status
               FROM bookings b
               JOIN users      d  ON b.doctor_id    = d.id
               JOIN time_slots ts ON b.time_slot_id = ts.id
               WHERE b.patient_id = %s
                 AND b.status = 'confirmed'
                 AND ts.date >= CURRENT_DATE
               ORDER BY ts.date, ts.start_time
               LIMIT 3""",
            (patient_id,)
        )
        upcoming = cur.fetchall()
        cur.close()
    finally:
        release_db(conn)

    return render_template(
        "patient_dashboard.html",
        total=total,
        pending=pending,
        upcoming=upcoming
    )


@patient_bp.route("/browse")
@login_required("patient")
def browse_doctors():
    """
    Browse all doctors with an optional specialty filter.

    Query param: specialty — if supplied, only doctors with that specialty are shown.

    Also fetches all distinct specialties to populate the filter dropdown.
    Returns: rendered browse_doctors.html.
    """
    specialty_filter = request.args.get("specialty", "").strip()

    conn = get_db()
    try:
        cur = conn.cursor()

        # All distinct specialties for the filter dropdown
        cur.execute(
            "SELECT DISTINCT specialty FROM users WHERE role = 'doctor' ORDER BY specialty"
        )
        specialties = [row[0] for row in cur.fetchall()]

        # Doctor list — filtered or full
        if specialty_filter:
            cur.execute(
                """SELECT id, name, specialty
                   FROM users
                   WHERE role = 'doctor' AND specialty = %s
                   ORDER BY name""",
                (specialty_filter,)
            )
        else:
            cur.execute(
                """SELECT id, name, specialty
                   FROM users
                   WHERE role = 'doctor'
                   ORDER BY name"""
            )
        doctors = cur.fetchall()
        cur.close()
    finally:
        release_db(conn)

    return render_template(
        "browse_doctors.html",
        doctors=doctors,
        specialties=specialties,
        selected_specialty=specialty_filter
    )


@patient_bp.route("/book/<int:doctor_id>", methods=["GET", "POST"])
@login_required("patient")
def book_appointment(doctor_id):
    """
    Appointment booking page for a specific doctor.

    GET  (no date param)  → shows date picker only.
    GET  (?date=YYYY-MM-DD) → shows date picker + available slots for that date.
    POST → books the selected slot.

    Double-booking prevention (POST path)
    ──────────────────────────────────────
    psycopg2 operates in transaction mode (autocommit=False) by default, so
    every statement is inside an implicit transaction.

    1. SELECT … FOR UPDATE locks the time_slots row, blocking any concurrent
       transaction that tries to read or modify the same row.
    2. We verify is_available is TRUE inside the lock.
    3. UPDATE sets is_available = FALSE atomically.
    4. INSERT creates the booking record.
    5. conn.commit() releases the lock and persists both changes together.

    If the slot was grabbed between our read and our write, step 2 catches it
    and we ROLLBACK — the slot stays available and the user sees an error.

    Receives (POST form): slot_id, reason.
    Redirects (POST success): patient.my_bookings.
    """
    patient_id = session["user_id"]

    conn = get_db()
    try:
        cur = conn.cursor()

        # Verify the doctor exists
        cur.execute(
            "SELECT id, name, specialty FROM users WHERE id = %s AND role = 'doctor'",
            (doctor_id,)
        )
        doctor = cur.fetchone()

        if not doctor:
            flash("Doctor not found.", "error")
            cur.close()
            return redirect(url_for("patient.browse_doctors"))

        # ── POST: attempt to book the slot ───────────────────────────────────
        if request.method == "POST":
            slot_id = request.form.get("slot_id", "").strip()
            reason  = request.form.get("reason",  "").strip()

            if not slot_id:
                flash("Please select a time slot.", "error")
                cur.close()
                return redirect(url_for("patient.book_appointment", doctor_id=doctor_id))

            if not reason:
                flash("Please provide a reason for your visit.", "error")
                cur.close()
                return redirect(url_for("patient.book_appointment", doctor_id=doctor_id))

            try:
                # ── TRANSACTION START (implicit in psycopg2) ─────────────────
                # FOR UPDATE locks this row until commit/rollback,
                # preventing any other transaction from reading or writing it
                cur.execute(
                    """SELECT id, is_available FROM time_slots
                       WHERE id = %s AND doctor_id = %s
                       FOR UPDATE""",
                    (slot_id, doctor_id)
                )
                slot = cur.fetchone()

                if not slot:
                    conn.rollback()
                    flash("Invalid slot selected.", "error")
                    cur.close()
                    return redirect(url_for("patient.book_appointment", doctor_id=doctor_id))

                if not slot[1]:   # is_available is FALSE
                    conn.rollback()
                    flash("This slot was just booked by someone else. Please choose another.", "error")
                    cur.close()
                    return redirect(url_for("patient.book_appointment", doctor_id=doctor_id))

                # Mark the slot as taken
                cur.execute(
                    "UPDATE time_slots SET is_available = FALSE WHERE id = %s",
                    (slot_id,)
                )

                # Create the booking record
                cur.execute(
                    """INSERT INTO bookings
                           (patient_id, doctor_id, time_slot_id, status, reason)
                       VALUES (%s, %s, %s, 'pending', %s)""",
                    (patient_id, doctor_id, slot_id, reason)
                )

                # ── COMMIT — both changes are durable and the lock is released
                conn.commit()
                flash("Appointment booked! Awaiting doctor confirmation.", "success")
                cur.close()
                return redirect(url_for("patient.my_bookings"))

            except Exception:
                conn.rollback()
                flash("Booking failed due to a server error. Please try again.", "error")
                cur.close()
                return redirect(url_for("patient.book_appointment", doctor_id=doctor_id))

        # ── GET: show date picker and (if date supplied) available slots ─────
        chosen_date    = request.args.get("date", "").strip()
        available_slots = []

        if chosen_date:
            cur.execute(
                """SELECT id, start_time, end_time FROM time_slots
                   WHERE doctor_id = %s AND date = %s AND is_available = TRUE
                   ORDER BY start_time""",
                (doctor_id, chosen_date)
            )
            available_slots = cur.fetchall()

        cur.close()
        return render_template(
            "book_appointment.html",
            doctor=doctor,
            available_slots=available_slots,
            chosen_date=chosen_date
        )

    finally:
        release_db(conn)


@patient_bp.route("/bookings")
@login_required("patient")
def my_bookings():
    """
    Full booking history for the logged-in patient.

    Fetches all bookings with doctor name, specialty, slot time, status, and reason.
    Returns: rendered my_bookings.html.
    """
    patient_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT b.id,
                      d.name      AS doctor_name,
                      d.specialty,
                      ts.date,
                      ts.start_time,
                      ts.end_time,
                      b.status,
                      b.reason,
                      b.created_at,
                      b.time_slot_id
               FROM bookings b
               JOIN users      d  ON b.doctor_id    = d.id
               JOIN time_slots ts ON b.time_slot_id = ts.id
               WHERE b.patient_id = %s
               ORDER BY ts.date DESC, ts.start_time DESC""",
            (patient_id,)
        )
        bookings = cur.fetchall()
        cur.close()
    finally:
        release_db(conn)

    return render_template("my_bookings.html", bookings=bookings)


@patient_bp.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required("patient")
def cancel_booking(booking_id):
    """
    Cancels a pending booking and restores the time slot's availability.

    Only bookings with status='pending' can be cancelled by the patient.
    Confirmed/completed bookings require doctor or admin intervention.

    Steps:
    1. Verify the booking belongs to this patient and is pending.
    2. Set booking.status = 'cancelled'.
    3. Set time_slots.is_available = TRUE  (slot is free again).
    4. Commit both changes together.

    Receives: booking_id from URL path.
    Redirects: back to patient.my_bookings.
    """
    patient_id = session["user_id"]
    conn = get_db()
    try:
        cur = conn.cursor()

        # Fetch booking — verify ownership and status
        cur.execute(
            """SELECT id, time_slot_id, status
               FROM bookings
               WHERE id = %s AND patient_id = %s""",
            (booking_id, patient_id)
        )
        booking = cur.fetchone()

        if not booking:
            flash("Booking not found.", "error")
        elif booking[2] != "pending":
            flash("Only pending bookings can be cancelled.", "error")
        else:
            time_slot_id = booking[1]

            cur.execute(
                "UPDATE bookings   SET status = 'cancelled' WHERE id = %s",
                (booking_id,)
            )
            cur.execute(
                "UPDATE time_slots SET is_available = TRUE  WHERE id = %s",
                (time_slot_id,)
            )
            conn.commit()
            flash("Booking cancelled. The time slot is now available again.", "success")

        cur.close()
    except Exception:
        conn.rollback()
        flash("Failed to cancel booking.", "error")
    finally:
        release_db(conn)

    return redirect(url_for("patient.my_bookings"))
