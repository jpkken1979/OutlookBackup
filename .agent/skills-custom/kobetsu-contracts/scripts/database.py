"""Database layer for Kobetsu Contracts.

SQLite persistence for contracts and audit trails with schema extensions.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import KobetsuContract

logger = logging.getLogger(__name__)


class ContractDatabase:
    """Manages Kobetsu contract persistence in SQLite."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        logger.info(f"ContractDatabase initialized with {db_path}")

    def init_database(self) -> None:
        """Initialize database schema from SQL script.

        Creates tables if they don't exist.
        """
        schema_file = Path(__file__).parent.parent / "sql_schema_extensions.sql"

        if not schema_file.exists():
            logger.warning(f"Schema file not found: {schema_file}")
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                with open(schema_file, encoding="utf-8") as f:
                    sql_script = f.read()
                conn.executescript(sql_script)
                conn.commit()

            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            raise

    def save_contract(self, contract: KobetsuContract) -> str:
        """Save contract to database.

        Args:
            contract: Contract to save.

        Returns:
            Contract ID.

        Raises:
            sqlite3.IntegrityError: If contract_number is not unique.
            Exception: If database operation fails.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO kobetsu_contracts (
                        id, employee_id, contract_number, contract_date,
                        effective_date, expiration_date, dispatch_company,
                        client_company, job_title, work_location,
                        work_hours_daily, work_days_weekly, hourly_rate_jpy,
                        monthly_minimum_hours, benefits, terms_conditions,
                        notes, generated_at, template_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        contract.id,
                        contract.employee_id,
                        contract.contract_number,
                        contract.contract_date.isoformat(),
                        contract.effective_date.isoformat(),
                        contract.expiration_date.isoformat() if contract.expiration_date else None,
                        contract.dispatch_company,
                        contract.client_company,
                        contract.job_title,
                        contract.work_location,
                        contract.work_hours_daily,
                        contract.work_days_weekly,
                        contract.hourly_rate_jpy,
                        contract.monthly_minimum_hours,
                        ",".join(contract.benefits) if contract.benefits else "",
                        contract.terms_conditions,
                        contract.notes,
                        contract.generated_at,
                        contract.template_version,
                    ),
                )
                conn.commit()

            logger.info(f"Saved contract: {contract.contract_number}")
            return contract.id

        except sqlite3.IntegrityError:
            logger.error(f"Contract number not unique: {contract.contract_number}")
            raise
        except Exception as e:
            logger.error(f"Failed to save contract: {e}")
            raise

    def load_contract(self, contract_id: str) -> KobetsuContract | None:
        """Load contract from database.

        Args:
            contract_id: Contract ID to load.

        Returns:
            Contract or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM kobetsu_contracts WHERE id = ?",
                    (contract_id,),
                )
                row = cursor.fetchone()

            if not row:
                logger.warning(f"Contract not found: {contract_id}")
                return None

            # Reconstruct contract from row
            contract = KobetsuContract(
                id=row["id"],
                employee_id=row["employee_id"],
                contract_number=row["contract_number"],
                contract_date=row["contract_date"],
                effective_date=row["effective_date"],
                expiration_date=row["expiration_date"],
                dispatch_company=row["dispatch_company"],
                client_company=row["client_company"],
                job_title=row["job_title"],
                work_location=row["work_location"],
                work_hours_daily=row["work_hours_daily"],
                work_days_weekly=row["work_days_weekly"],
                hourly_rate_jpy=row["hourly_rate_jpy"],
                monthly_minimum_hours=row["monthly_minimum_hours"],
                benefits=row["benefits"].split(",") if row["benefits"] else [],
                terms_conditions=row["terms_conditions"],
                notes=row["notes"],
                generated_at=row["generated_at"],
                template_version=row["template_version"],
            )

            logger.info(f"Loaded contract: {contract_id}")
            return contract

        except Exception as e:
            logger.error(f"Failed to load contract: {e}")
            return None

    def list_employee_contracts(self, employee_id: str) -> list[str]:
        """List all contract IDs for an employee.

        Args:
            employee_id: Employee ID.

        Returns:
            List of contract IDs.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id FROM kobetsu_contracts WHERE employee_id = ? ORDER BY contract_date DESC",
                    (employee_id,),
                )
                contract_ids = [row[0] for row in cursor.fetchall()]

            logger.info(f"Found {len(contract_ids)} contracts for employee {employee_id}")
            return contract_ids

        except Exception as e:
            logger.error(f"Failed to list contracts: {e}")
            return []

    def check_contract_number_exists(self, contract_number: str) -> bool:
        """Check if contract number already exists.

        Args:
            contract_number: Contract number to check.

        Returns:
            True if contract number exists.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM kobetsu_contracts WHERE contract_number = ?",
                    (contract_number,),
                )
                count = cursor.fetchone()[0]

            exists = count > 0
            if exists:
                logger.debug(f"Contract number exists: {contract_number}")

            return exists

        except Exception as e:
            logger.error(f"Failed to check contract number: {e}")
            return False

    def add_audit_entry(
        self,
        contract_id: str,
        version: int,
        change_type: str,
        previous_value: str | None = None,
        new_value: str | None = None,
        changed_by: str | None = None,
    ) -> None:
        """Add audit trail entry for contract change.

        Args:
            contract_id: Contract ID.
            version: Version number.
            change_type: Type of change (e.g., 'create', 'update', 'delete').
            previous_value: Previous value (optional).
            new_value: New value (optional).
            changed_by: User/system that made change.
        """
        try:
            audit_id = f"AUDIT-{contract_id}-{version}-{datetime.now().timestamp()}"

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO kobetsu_contracts_audit (
                        id, contract_id, version, change_type,
                        previous_value, new_value, changed_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        audit_id,
                        contract_id,
                        version,
                        change_type,
                        previous_value,
                        new_value,
                        changed_by,
                    ),
                )
                conn.commit()

            logger.info(f"Audit entry added: {audit_id}")

        except Exception as e:
            logger.error(f"Failed to add audit entry: {e}")
