"""
seed.py — Populates the database with default accounts and sample data.

Run after schema.sql:
    python seed.py

Inserts:
  - 1 admin account
  - 3 doctor accounts (General Medicine, Dermatology, Cardiology)
  - 5 time slots per doctor for each of the next 3 days (45 slots total)
"""

import sys
import os
from datetime import date, time, timedelta

import psycopg2
from werkzeug.security import generate_password_hash

# Allow importing config from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT


def seed() -> None:
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        host=DB_HOST, port=DB_PORT
    )
    cur = conn.cursor()

    print("Clearing existing data …")
    # Delete in reverse dependency order to respect foreign-key constraints
    cur.execute("DELETE FROM bookings")
    cur.execute("DELETE FROM time_slots")
    cur.execute("DELETE FROM users")

    # ── Admin ─────────────────────────────────────────────────────────────────
    print("Inserting admin …")
    cur.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        ("Admin User", "admin@clinic.com", generate_password_hash("admin123"), "admin")
    )

    # ── Doctors ───────────────────────────────────────────────────────────────
    doctors_data = [
        ("Dr. Sarah Johnson",  "sarah@clinic.com",   "doctor123", "General Medicine"),
        ("Dr. Michael Chen",   "michael@clinic.com", "doctor123", "Dermatology"),
        ("Dr. Emily Rodriguez","emily@clinic.com",   "doctor123", "Cardiology"),
    ]

    doctor_ids = []
    print("Inserting doctors …")
    for name, email, password, specialty in doctors_data:
        cur.execute(
            """INSERT INTO users (name, email, password_hash, role, specialty)
               VALUES (%s, %s, %s, 'doctor', %s) RETURNING id""",
            (name, email, generate_password_hash(password), specialty)
        )
        doctor_ids.append(cur.fetchone()[0])

    # ── Time slots (5 per doctor per day, next 3 days) ────────────────────────
    # Each slot is 30 minutes; spread across morning and afternoon
    slot_times = [
        (time(9,  0), time(9,  30)),
        (time(10, 0), time(10, 30)),
        (time(11, 0), time(11, 30)),
        (time(14, 0), time(14, 30)),
        (time(15, 0), time(15, 30)),
    ]

    today = date.today()
    print("Inserting time slots …")
    for doctor_id in doctor_ids:
        for day_offset in range(1, 4):          # days: +1, +2, +3 from today
            slot_date = today + timedelta(days=day_offset)
            for start, end in slot_times:
                cur.execute(
                    """INSERT INTO time_slots (doctor_id, date, start_time, end_time, is_available)
                       VALUES (%s, %s, %s, %s, TRUE)""",
                    (doctor_id, slot_date, start, end)
                )

    conn.commit()
    cur.close()
    conn.close()

    print("\nSeeding complete!")
    print("─" * 40)
    print("Default credentials:")
    print("  Admin   : admin@clinic.com   / admin123")
    print("  Doctor 1: sarah@clinic.com   / doctor123  (General Medicine)")
    print("  Doctor 2: michael@clinic.com / doctor123  (Dermatology)")
    print("  Doctor 3: emily@clinic.com   / doctor123  (Cardiology)")
    print("─" * 40)


if __name__ == "__main__":
    seed()
