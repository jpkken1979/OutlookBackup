"""Database queries for HR Reports Generator - WEEK 2."""

import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any
import sqlite3

logger = logging.getLogger(__name__)


class HRDatabase:
    """Database access layer for HR reports."""

    def __init__(self, db_path: str) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._ensure_connection()
        logger.info(f"HRDatabase initialized with {db_path}")

    def _ensure_connection(self) -> None:
        """Ensure database connection is available."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory.

        Returns:
            SQLite connection object.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_employee(self, employee_id: str) -> dict[str, Any] | None:
        """Load employee information by ID.

        Args:
            employee_id: Employee ID to load.

        Returns:
            Employee record dict or None if not found.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM employees
                WHERE employee_id = ?
                """,
                (employee_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            logger.warning(f"Employee not found: {employee_id}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Error loading employee {employee_id}: {e}")
            raise
        finally:
            conn.close()

    def load_employees(self, status: str = "active") -> list[dict[str, Any]]:
        """Load all employees with optional status filter.

        Args:
            status: Filter by employment status (default: 'active').

        Returns:
            List of employee records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM employees
                WHERE status = ?
                ORDER BY employee_id
                """,
                (status,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error loading employees: {e}")
            raise
        finally:
            conn.close()

    def get_attendance_records(
        self,
        start_date: date,
        end_date: date,
        employee_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get attendance records for date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            employee_id: Optional filter by employee.

        Returns:
            List of attendance records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if employee_id:
                cursor.execute(
                    """
                    SELECT * FROM attendance_records
                    WHERE date BETWEEN ? AND ?
                    AND employee_id = ?
                    ORDER BY date, employee_id
                    """,
                    (start_date, end_date, employee_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM attendance_records
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date, employee_id
                    """,
                    (start_date, end_date),
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error loading attendance records: {e}")
            raise
        finally:
            conn.close()

    def get_payroll_hours(
        self,
        employee_id: str,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        """Get payroll hours for employee in period.

        Args:
            employee_id: Employee ID.
            period_start: Period start date.
            period_end: Period end date.

        Returns:
            Dict with hours, rate, and salary info.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Get hours from attendance
            cursor.execute(
                """
                SELECT
                    COUNT(*) as days_worked,
                    SUM(hours_worked) as total_hours,
                    AVG(hours_worked) as avg_hours
                FROM attendance_records
                WHERE employee_id = ?
                AND date BETWEEN ? AND ?
                AND status IN ('present', 'late', 'early_leave')
                """,
                (employee_id, period_start, period_end),
            )
            attendance_row = cursor.fetchone()

            # Get hourly rate from employee
            cursor.execute(
                "SELECT hourly_rate FROM employees WHERE employee_id = ?",
                (employee_id,),
            )
            rate_row = cursor.fetchone()

            total_hours = attendance_row["total_hours"] if attendance_row["total_hours"] else 0.0
            hourly_rate = (
                rate_row["hourly_rate"] if rate_row and rate_row["hourly_rate"] else 1500.0
            )

            return {
                "employee_id": employee_id,
                "days_worked": attendance_row["days_worked"] or 0,
                "total_hours": total_hours,
                "avg_hours": attendance_row["avg_hours"] or 0.0,
                "hourly_rate": hourly_rate,
                "gross_salary": total_hours * hourly_rate,
            }
        except sqlite3.Error as e:
            logger.error(f"Error getting payroll hours: {e}")
            raise
        finally:
            conn.close()

    def get_dispatch_assignments(
        self,
        start_date: date,
        end_date: date,
        employee_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get dispatch assignments for date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            employee_id: Optional filter by employee.

        Returns:
            List of dispatch assignment records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if employee_id:
                cursor.execute(
                    """
                    SELECT * FROM dispatch_assignments
                    WHERE dispatch_date BETWEEN ? AND ?
                    AND employee_id = ?
                    ORDER BY dispatch_date, employee_id
                    """,
                    (start_date, end_date, employee_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM dispatch_assignments
                    WHERE dispatch_date BETWEEN ? AND ?
                    ORDER BY dispatch_date, employee_id
                    """,
                    (start_date, end_date),
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting dispatch assignments: {e}")
            raise
        finally:
            conn.close()

    def get_absence_records(
        self,
        start_date: date,
        end_date: date,
        employee_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get absence records for date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            employee_id: Optional filter by employee.

        Returns:
            List of absence records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if employee_id:
                cursor.execute(
                    """
                    SELECT * FROM attendance_records
                    WHERE date BETWEEN ? AND ?
                    AND employee_id = ?
                    AND status IN ('absent', 'excused_absence')
                    ORDER BY date, employee_id
                    """,
                    (start_date, end_date, employee_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM attendance_records
                    WHERE date BETWEEN ? AND ?
                    AND status IN ('absent', 'excused_absence')
                    ORDER BY date, employee_id
                    """,
                    (start_date, end_date),
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting absence records: {e}")
            raise
        finally:
            conn.close()

    def save_report_metadata(
        self,
        report_type: str,
        report_name: str,
        start_date: date,
        end_date: date,
        generated_by: str,
        file_path: str | None = None,
        file_format: str = "xlsx",
        total_records: int = 0,
        hash_value: str | None = None,
    ) -> int:
        """Save report metadata to database.

        Args:
            report_type: Type of report (roster, hours, dispatch, absence).
            report_name: Name/title of report.
            start_date: Report period start.
            end_date: Report period end.
            generated_by: User/system that generated report.
            file_path: Optional path where report was saved.
            file_format: File format (xlsx, html, csv).
            total_records: Number of records in report.
            hash_value: Optional hash for deduplication.

        Returns:
            Report ID.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO hr_reports
                (report_type, report_name, start_date, end_date,
                 generated_by, file_path, file_format, total_records, hash_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_type,
                    report_name,
                    start_date,
                    end_date,
                    generated_by,
                    file_path,
                    file_format,
                    total_records,
                    hash_value,
                ),
            )
            conn.commit()
            report_id = cursor.lastrowid
            logger.info(f"Report metadata saved: {report_id}")
            return report_id
        except sqlite3.Error as e:
            logger.error(f"Error saving report metadata: {e}")
            raise
        finally:
            conn.close()
