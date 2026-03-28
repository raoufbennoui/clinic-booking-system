-- ============================================================
-- Clinic Booking System — Database Schema
-- Run this file first: psql -U postgres -d clinic_booking -f schema.sql
-- ============================================================

-- Users table stores all roles: admin, doctor, patient
-- specialty is NULL for admin and patient, filled for doctors
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100)  NOT NULL,
    email       VARCHAR(150)  UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role        VARCHAR(20)   NOT NULL CHECK (role IN ('admin', 'doctor', 'patient')),
    specialty   VARCHAR(100)  NULL,
    created_at  TIMESTAMP     DEFAULT NOW()
);

-- Time slots are created by doctors to show their availability
-- is_available flips to FALSE when a patient books the slot
CREATE TABLE IF NOT EXISTS time_slots (
    id           SERIAL PRIMARY KEY,
    doctor_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date         DATE    NOT NULL,
    start_time   TIME    NOT NULL,
    end_time     TIME    NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Bookings link a patient to a doctor's time slot
-- status lifecycle: pending -> confirmed -> completed
--                   pending -> cancelled  (by patient or doctor rejection)
CREATE TABLE IF NOT EXISTS bookings (
    id           SERIAL PRIMARY KEY,
    patient_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    time_slot_id INTEGER NOT NULL REFERENCES time_slots(id) ON DELETE CASCADE,
    status       VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed')),
    reason       TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Index for faster booking lookups by patient and doctor
CREATE INDEX IF NOT EXISTS idx_bookings_patient ON bookings(patient_id);
CREATE INDEX IF NOT EXISTS idx_bookings_doctor  ON bookings(doctor_id);
CREATE INDEX IF NOT EXISTS idx_slots_doctor     ON time_slots(doctor_id);
CREATE INDEX IF NOT EXISTS idx_slots_date       ON time_slots(date);
