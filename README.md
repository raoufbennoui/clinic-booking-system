# MediBook — Clinic Appointment Booking System

## Project Description

MediBook is a full-stack web application that solves a common problem in small and medium clinics: **scheduling chaos**. Without a booking system, clinics rely on phone calls, paper registers, and manual confirmation — leading to double bookings, missed appointments, and wasted doctor time.

MediBook provides:
- Patients a self-service portal to find doctors, view real-time availability, and book slots.
- Doctors a dashboard to manage their schedule, confirm or reject requests, and track completed visits.
- Admins a control panel to manage the clinic's doctor roster and monitor all activity.

---

## Tech Stack

| Layer      | Technology         | Why chosen |
|------------|-------------------|------------|
| Backend    | Python / Flask     | Lightweight, unopinionated, fast to build with; Blueprints give clean role separation |
| Database   | PostgreSQL         | ACID compliance is critical for preventing double bookings; `FOR UPDATE` row locking is a first-class feature |
| ORM/Driver | psycopg2           | Direct SQL control; connection pooling built-in; parameterised queries prevent SQL injection |
| Auth       | werkzeug.security  | Industry-standard password hashing (PBKDF2-SHA256); already ships with Flask |
| Frontend   | Jinja2 + custom CSS| Server-side rendering keeps the codebase simple; no JavaScript framework needed for this use case |
| Deployment | Flask dev server   | Deployment  Gunicorn + Railway  Production WSGI server cloud deployment with managed PostgreSQL|

---

## Database Schema

```
users
  id            SERIAL PK
  name          VARCHAR(100)
  email         VARCHAR(150) UNIQUE
  password_hash VARCHAR(255)
  role          VARCHAR(20)  CHECK ('admin'|'doctor'|'patient')
  specialty     VARCHAR(100) NULL     -- only set for doctors
  created_at    TIMESTAMP

time_slots
  id            SERIAL PK
  doctor_id     FK → users(id) CASCADE DELETE
  date          DATE
  start_time    TIME
  end_time      TIME
  is_available  BOOLEAN DEFAULT TRUE  -- flips to FALSE when booked
  created_at    TIMESTAMP

bookings
  id            SERIAL PK
  patient_id    FK → users(id) CASCADE DELETE
  doctor_id     FK → users(id) CASCADE DELETE
  time_slot_id  FK → time_slots(id) CASCADE DELETE
  status        VARCHAR(20) CHECK ('pending'|'confirmed'|'cancelled'|'completed')
  reason        TEXT
  created_at    TIMESTAMP
```

### Table Relationships

- `users` is the central table. A user's `role` determines which blueprints they access.
- `time_slots` belongs to a `doctor` (via `doctor_id`). Each slot has an `is_available` flag.
- `bookings` links a `patient` and a `doctor` through a specific `time_slot`.
- Cascade deletes ensure that removing a doctor removes their slots and all associated bookings automatically.

---

## Setup Instructions

### 1. Prerequisites

- Python 3.10+
- PostgreSQL 14+ running locally
- Git (optional)

### 2. Create the database

Open **SQL Shell (psql)** or any PostgreSQL client and run:

```sql
CREATE DATABASE clinic_booking;
```

### 3. Run the schema

```bash
psql -U postgres -d clinic_booking -f schema.sql
```

### 4. Install Python dependencies

```bash
cd clinic-booking
pip install -r requirements.txt
```

### 5. Configure the database password

Open `config.py` and update:

```python
DB_PASSWORD = "your_postgres_password_here"
```

### 6. Seed the database

```bash
python seed.py
```

### 7. Run the application

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## Default Login Credentials

| Role    | Email                | Password   | Notes                  |
|---------|---------------------|------------|------------------------|
| Admin   | admin@clinic.com    | admin123   | Full system access     |
| Doctor  | sarah@clinic.com    | doctor123  | General Medicine       |
| Doctor  | michael@clinic.com  | doctor123  | Dermatology            |
| Doctor  | emily@clinic.com    | doctor123  | Cardiology             |

Patients must register themselves at `/register`.

---

## Folder Structure

```
clinic-booking/
├── app.py              Entry point — creates the Flask app, registers blueprints
├── config.py           DB credentials, secret key, connection pool init/get/release
├── requirements.txt    pip dependencies
├── seed.py             Inserts default admin, 3 doctors, 45 sample time slots
├── schema.sql          CREATE TABLE statements for users, time_slots, bookings
│
├── routes/
│   ├── __init__.py     login_required() decorator used by all blueprints
│   ├── auth.py         /login  /register  /logout
│   ├── admin.py        /admin/dashboard  /admin/bookings  /admin/add-doctor  /admin/remove-doctor
│   ├── doctor.py       /doctor/dashboard  /doctor/slots/add  /doctor/bookings  + confirm/reject/complete
│   └── patient.py      /patient/dashboard  /patient/browse  /patient/book  /patient/bookings  /patient/cancel
│
├── static/
│   ├── css/style.css   All custom CSS (no frameworks) — blue/white, responsive
│   └── js/main.js      Confirmation dialogs, form validation, mobile nav
│
└── templates/
    ├── base.html               Shared layout: navbar + flash messages + footer
    ├── login.html              Login form (all roles)
    ├── register.html           Patient self-registration
    ├── admin_dashboard.html    Stats cards + doctor list + remove button
    ├── add_doctor.html         Form to create a doctor account
    ├── admin_bookings.html     Filterable system-wide booking table
    ├── doctor_dashboard.html   Today's schedule + stats + confirm/reject actions
    ├── add_slot.html           Form to add an available time slot
    ├── doctor_bookings.html    Full booking history for the logged-in doctor
    ├── patient_dashboard.html  Overview + upcoming confirmed appointments
    ├── browse_doctors.html     Doctor grid with specialty filter
    ├── book_appointment.html   Date picker → slot picker → reason → book
    └── my_bookings.html        Patient's booking history + cancel button
```

---

## How Double Booking Is Prevented

Double booking happens when two patients try to book the same slot at the exact same moment. Standard check-then-act logic has a race condition:

```
Patient A reads:  is_available = TRUE  ← both see TRUE simultaneously
Patient B reads:  is_available = TRUE
Patient A books:  UPDATE … FALSE, INSERT booking  ✓
Patient B books:  UPDATE … FALSE, INSERT booking  ✗ (double booking!)
```

MediBook prevents this using **PostgreSQL row-level locking** inside an explicit transaction:

```sql
-- psycopg2 is in autocommit=False mode (default), so this is inside a transaction

SELECT id, is_available FROM time_slots
WHERE id = %s AND doctor_id = %s
FOR UPDATE;                          -- acquires an exclusive row lock
                                     -- any other transaction trying to
                                     -- read or write this row BLOCKS here

-- (inside the application)
-- if is_available is FALSE → ROLLBACK, show error to user
-- if is_available is TRUE  → proceed

UPDATE time_slots SET is_available = FALSE WHERE id = %s;
INSERT INTO bookings (…) VALUES (…);
COMMIT;                              -- lock released, both changes durable
```

**Why this works:**
1. `FOR UPDATE` prevents two transactions from reading the same row simultaneously.
2. Only one transaction holds the lock at a time; the other waits.
3. When the first transaction commits (`is_available = FALSE`), the second transaction reads the updated value, sees `FALSE`, and rolls back gracefully.
4. The patient sees a friendly "slot already taken" message, not a duplicate booking.

This guarantee holds even under high concurrency because it's enforced at the **database engine level**, not in application code.

---

## Security Notes

- All SQL queries use **parameterised placeholders** (`%s`) — no string formatting in queries.
- Passwords are hashed with **PBKDF2-SHA256** via `werkzeug.security`.
- Sessions are signed with a **secret key** (change `SECRET_KEY` in `config.py` before deploying).
- Role enforcement via the `login_required` decorator prevents cross-role access.
- In production: use HTTPS, set `SESSION_COOKIE_SECURE = True`, and replace the dev server with Gunicorn.
