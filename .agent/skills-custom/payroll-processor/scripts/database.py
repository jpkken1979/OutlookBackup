"""Database operations for Payroll Processor.

Handles SQLite operations: initialization, employee loading, and payslip persistence.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from pydantic import ValidationError

# Import schemas from parent directory
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import Employee, Payslip, ContractType, EmployeeStatus

logger = logging.getLogger(__name__)


class PayrollDatabase:
    """SQLite database manager for payroll operations."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.

        Raises:
            ValueError: If db_path parent directory doesn't exist.
        """
        self.db_path = Path(db_path)
        if not self.db_path.parent.exists():
            raise ValueError(f"Database parent directory does not exist: {self.db_path.parent}")

        logger.info(f"Initializing database at {self.db_path}")

    def init_database(self) -> None:
        """Create tables if they don't exist.

        Reads sql_schema.sql and executes it. Creates indices and triggers.

        Raises:
            FileNotFoundError: If sql_schema.sql not found.
            sqlite3.DatabaseError: If schema creation fails.
        """
        schema_path = Path(__file__).parent.parent / "sql_schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"SQL schema not found at {schema_path}")

        with open(schema_path, encoding="utf-8") as f:
            schema_sql = f.read()

        try:
            conn = sqlite3.connect(self.db_path)
            conn.executescript(schema_sql)
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except sqlite3.DatabaseError as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    def load_employee(self, employee_id: str) -> Employee:
        """Load employee record from database.

        Args:
            employee_id: Employee ID (e.g., 'W001').

        Returns:
            Employee: Pydantic Employee instance.

        Raises:
            ValueError: If employee not found.
            ValidationError: If employee data is invalid.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM employee_master WHERE id = ?",
                (employee_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                raise ValueError(f"Employee not found: {employee_id}")

            # Convert to Employee model
            employee_data = {
                "id": row["id"],
                "name_jp": row["name_jp"],
                "name_en": row["name_en"],
                "email": row["email"],
                "phone": row["phone"],
                "contract_type": row["contract_type"],
                "status": row["status"],
                "hire_date": row["hire_date"],
                "termination_date": row["termination_date"],
                "hourly_rate_jpy": row["hourly_rate_jpy"],
                "monthly_salary_jpy": row["monthly_salary_jpy"],
                "income_tax_rate": row["income_tax_rate"],
                "social_insurance_rate": row["social_insurance_rate"],
                "employment_insurance_rate": row["employment_insurance_rate"],
                "department": row["department"],
                "manager_id": row["manager_id"],
                "bank_name": row["bank_name"],
                "account_number": row["account_number"],
                "account_holder": row["account_holder"],
                "notes": row["notes"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

            employee = Employee(**employee_data)
            logger.info(f"Loaded employee: {employee_id}")
            return employee

        except sqlite3.Error as e:
            logger.error(f"Database error loading employee {employee_id}: {e}")
            raise

    def save_payslip(self, payslip: Payslip) -> str:
        """Save payslip to database.

        Args:
            payslip: Payslip Pydantic model instance.

        Returns:
            str: Payslip ID (UUID).

        Raises:
            sqlite3.IntegrityError: If employee doesn't exist or duplicate payslip.
            ValueError: If payslip data is invalid.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Generate ID if not present
            payslip_id = payslip.id
            if payslip_id.startswith("PAYSLIP-"):
                # Format: PAYSLIP-20260201-W001
                payslip_id = (
                    f"PAYSLIP-{payslip.year:04d}{payslip.month:02d}01-{payslip.employee_id}"
                )

            # Insert payslip
            cursor.execute(
                """
                INSERT OR REPLACE INTO payroll_records (
                    id, employee_id, year, month,
                    regular_hours, overtime_hours, night_shift_hours,
                    regular_pay, overtime_pay, night_shift_pay, bonus, other_earnings,
                    gross_pay, income_tax, social_insurance, employment_insurance,
                    health_insurance, pension_contribution, other_deductions, total_deductions,
                    net_pay, notes, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payslip_id,
                    payslip.employee_id,
                    payslip.year,
                    payslip.month,
                    payslip.regular_hours,
                    payslip.overtime_hours,
                    0.0,  # night_shift_hours
                    payslip.regular_pay,
                    payslip.overtime_pay,
                    0.0,  # night_shift_pay
                    payslip.bonus,
                    0.0,  # other_earnings
                    payslip.gross_pay,
                    payslip.income_tax,
                    payslip.social_insurance,
                    payslip.employment_insurance,
                    0.0,  # health_insurance
                    0.0,  # pension_contribution
                    payslip.other_deductions,
                    payslip.total_deductions,
                    payslip.net_pay,
                    payslip.notes,
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            conn.close()

            logger.info(f"Saved payslip: {payslip_id}")
            return payslip_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error saving payslip: {e}")
            raise
        except sqlite3.Error as e:
            logger.error(f"Database error saving payslip: {e}")
            raise

    def get_payslip(self, payslip_id: str) -> Payslip:
        """Retrieve payslip from database.

        Args:
            payslip_id: Payslip ID.

        Returns:
            Payslip: Pydantic Payslip instance.

        Raises:
            ValueError: If payslip not found.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM payroll_records WHERE id = ?",
                (payslip_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                raise ValueError(f"Payslip not found: {payslip_id}")

            payslip = Payslip(
                id=row["id"],
                employee_id=row["employee_id"],
                year=row["year"],
                month=row["month"],
                regular_hours=row["regular_hours"],
                overtime_hours=row["overtime_hours"],
                regular_pay=row["regular_pay"],
                overtime_pay=row["overtime_pay"],
                bonus=row["bonus"],
                gross_pay=row["gross_pay"],
                income_tax=row["income_tax"],
                social_insurance=row["social_insurance"],
                employment_insurance=row["employment_insurance"],
                other_deductions=row["other_deductions"],
                total_deductions=row["total_deductions"],
                net_pay=row["net_pay"],
                notes=row["notes"],
                generated_at=row["generated_at"],
            )

            logger.info(f"Retrieved payslip: {payslip_id}")
            return payslip

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving payslip {payslip_id}: {e}")
            raise

    def list_payslips(self, employee_id: str, year: int, month: int | None = None) -> list[Payslip]:
        """List payslips for employee by year/month.

        Args:
            employee_id: Employee ID.
            year: Year (e.g., 2026).
            month: Month (1-12), or None for all months in year.

        Returns:
            List[Payslip]: List of payslips.

        Raises:
            ValueError: If employee_id is invalid.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if month is None:
                cursor.execute(
                    """
                    SELECT * FROM payroll_records
                    WHERE employee_id = ? AND year = ?
                    ORDER BY month ASC
                    """,
                    (employee_id, year),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM payroll_records
                    WHERE employee_id = ? AND year = ? AND month = ?
                    """,
                    (employee_id, year, month),
                )

            rows = cursor.fetchall()
            conn.close()

            payslips = [
                Payslip(
                    id=row["id"],
                    employee_id=row["employee_id"],
                    year=row["year"],
                    month=row["month"],
                    regular_hours=row["regular_hours"],
                    overtime_hours=row["overtime_hours"],
                    regular_pay=row["regular_pay"],
                    overtime_pay=row["overtime_pay"],
                    bonus=row["bonus"],
                    gross_pay=row["gross_pay"],
                    income_tax=row["income_tax"],
                    social_insurance=row["social_insurance"],
                    employment_insurance=row["employment_insurance"],
                    other_deductions=row["other_deductions"],
                    total_deductions=row["total_deductions"],
                    net_pay=row["net_pay"],
                    notes=row["notes"],
                    generated_at=row["generated_at"],
                )
                for row in rows
            ]

            logger.info(f"Retrieved {len(payslips)} payslips for {employee_id}")
            return payslips

        except sqlite3.Error as e:
            logger.error(f"Database error listing payslips: {e}")
            raise

    def get_query_plan(self, query: str) -> list[dict]:
        """Get EXPLAIN QUERY PLAN for profiling (PHASE 3 optimization).

        Args:
            query: SQL query to profile.

        Returns:
            List[dict]: Query plan steps.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(f"EXPLAIN QUERY PLAN {query}")
            rows = cursor.fetchall()
            conn.close()

            plans = [dict(row) for row in rows]
            logger.info(f"Query plan for '{query[:50]}...': {plans}")
            return plans

        except sqlite3.Error as e:
            logger.error(f"Error profiling query: {e}")
            raise

    def enable_pragmas(self) -> None:
        """Enable performance pragmas (PHASE 3 optimization).

        Sets WAL mode, memory mapping, cache size for optimal performance.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # WAL mode for concurrency
            cursor.execute("PRAGMA journal_mode = WAL;")

            # Memory-mapped I/O (30MB)
            cursor.execute("PRAGMA mmap_size = 30000000;")

            # Increase page cache (10000 pages)
            cursor.execute("PRAGMA cache_size = -10000;")

            # NORMAL synchronous for balance
            cursor.execute("PRAGMA synchronous = NORMAL;")

            # Memory temp storage
            cursor.execute("PRAGMA temp_store = MEMORY;")

            conn.commit()
            conn.close()

            logger.info("Performance pragmas enabled: WAL mode, mmap, cache optimization")

        except sqlite3.Error as e:
            logger.error(f"Error enabling pragmas: {e}")
            raise

    def analyze_database(self) -> dict:
        """Analyze database statistics for query optimization (PHASE 3).

        Returns:
            dict: Database stats (table sizes, row counts, index info).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Analyze tables
            cursor.execute("ANALYZE;")

            # Get table stats
            cursor.execute(
                "SELECT name, COUNT(*) as row_count FROM sqlite_master "
                "WHERE type='table' GROUP BY name"
            )
            tables = cursor.fetchall()

            # Get index stats
            cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
            indices = cursor.fetchall()

            conn.close()

            stats = {
                "tables": [{"name": t[0], "row_count": t[1]} for t in tables],
                "indices": [{"name": i[0], "table": i[1]} for i in indices],
            }

            logger.info(f"Database analysis: {len(tables)} tables, {len(indices)} indices")
            return stats

        except sqlite3.Error as e:
            logger.error(f"Error analyzing database: {e}")
            raise


def init_database(db_path: Path) -> PayrollDatabase:
    """Factory function to initialize database.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        PayrollDatabase: Initialized database manager.
    """
    db = PayrollDatabase(db_path)
    db.init_database()
    db.enable_pragmas()  # PHASE 3: Enable performance pragmas
    return db
