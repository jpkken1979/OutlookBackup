"""Test configuration and fixtures for HR Reports."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import date
from typing import Generator

from fixtures.attendance_fixtures import (
    sample_employees,
    sample_attendance_records,
    sample_dispatch_assignments,
)


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create temporary SQLite database for testing.

    Yields:
        Path to temporary database file.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize schema
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_kana TEXT,
            department TEXT,
            employment_type TEXT,
            start_date DATE,
            status TEXT,
            email TEXT,
            phone TEXT,
            hourly_rate DECIMAL(8, 2) DEFAULT 1500.0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            date DATE NOT NULL,
            clock_in TIME,
            clock_out TIME,
            hours_worked DECIMAL(5, 2),
            status TEXT DEFAULT 'present',
            reason TEXT,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, date),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dispatch_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            dispatch_date DATE NOT NULL,
            client_name TEXT NOT NULL,
            location TEXT,
            hours_allocated DECIMAL(5, 2),
            start_time TIME,
            end_time TIME,
            hourly_rate DECIMAL(8, 2) DEFAULT 1500.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS hr_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            report_name TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            generated_by TEXT NOT NULL,
            file_path TEXT,
            file_format TEXT DEFAULT 'xlsx',
            total_records INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hash_value TEXT UNIQUE
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def populated_db(temp_db: str) -> str:
    """Create database with sample data.

    Args:
        temp_db: Path to temporary database.

    Returns:
        Path to populated database.
    """
    conn = sqlite3.connect(temp_db)

    # Insert employees
    for emp in sample_employees():
        conn.execute(
            """
            INSERT INTO employees
            (employee_id, name, name_kana, department, employment_type,
             start_date, status, email, phone, hourly_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                emp["employee_id"],
                emp["name"],
                emp["name_kana"],
                emp["department"],
                emp["employment_type"],
                emp["start_date"],
                emp["status"],
                emp["email"],
                emp["phone"],
                1500.0,
            ),
        )

    # Insert attendance records
    for rec in sample_attendance_records():
        conn.execute(
            """
            INSERT INTO attendance_records
            (employee_id, date, clock_in, clock_out, hours_worked, status, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rec["employee_id"],
                rec["date"],
                rec["clock_in"],
                rec["clock_out"],
                rec["hours_worked"],
                rec["status"],
                rec.get("reason"),
            ),
        )

    # Insert dispatch assignments
    for dispatch in sample_dispatch_assignments():
        conn.execute(
            """
            INSERT INTO dispatch_assignments
            (employee_id, dispatch_date, client_name, location,
             hours_allocated, start_time, end_time, hourly_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dispatch["employee_id"],
                dispatch["dispatch_date"],
                dispatch["client_name"],
                dispatch["location"],
                dispatch["hours_allocated"],
                dispatch["start_time"],
                dispatch["end_time"],
                dispatch["hourly_rate"],
            ),
        )

    conn.commit()
    conn.close()

    return temp_db


@pytest.fixture
def sample_start_date() -> date:
    """Sample report start date.

    Returns:
        Date object for 2024-03-01.
    """
    return date(2024, 3, 1)


@pytest.fixture
def sample_end_date() -> date:
    """Sample report end date.

    Returns:
        Date object for 2024-03-31.
    """
    return date(2024, 3, 31)
