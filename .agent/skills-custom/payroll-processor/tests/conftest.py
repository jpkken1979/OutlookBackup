"""Pytest fixtures for Payroll Processor tests.

Shared fixtures for employee data, database setup, and payslip samples.
"""

import pytest
import sqlite3
import logging
from pathlib import Path
from datetime import date
from tempfile import TemporaryDirectory

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import Employee, Payslip, ContractType, EmployeeStatus

logger = logging.getLogger(__name__)


@pytest.fixture
def sample_employee() -> Employee:
    """Create sample employee (hakken worker, ¥1250/h).

    Returns:
        Employee: W001 employee record.
    """
    return Employee(
        id="W001",
        name_jp="田中 太郎",
        name_en="Taro Tanaka",
        email="tanaka@uns-kikaku.com",
        phone="090-1234-5678",
        contract_type=ContractType.HAKKEN,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2024, 1, 1),
        termination_date=None,
        hourly_rate_jpy=1250.0,
        monthly_salary_jpy=None,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department="Operations",
        manager_id=None,
        bank_name="Sumitomo Bank",
        account_number="1234567890",
        account_holder="Taro Tanaka",
        notes="Test employee",
        created_at=None,
        updated_at=None,
    )


@pytest.fixture
def sample_employee_seishain() -> Employee:
    """Create salaried employee sample.

    Returns:
        Employee: W002 salaried employee.
    """
    return Employee(
        id="W002",
        name_jp="山田 花子",
        name_en="Hanako Yamada",
        email="yamada@uns-kikaku.com",
        phone="090-9876-5432",
        contract_type=ContractType.SEISHAIN,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2020, 4, 1),
        termination_date=None,
        hourly_rate_jpy=2000.0,
        monthly_salary_jpy=200000.0,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department="HR",
        manager_id="W001",
        bank_name="Mitsubishi Bank",
        account_number="9876543210",
        account_holder="Hanako Yamada",
        notes="Salaried employee",
        created_at=None,
        updated_at=None,
    )


@pytest.fixture
def sample_payslip(sample_employee: Employee) -> Payslip:
    """Create sample payslip for February 2026.

    Args:
        sample_employee: Employee fixture.

    Returns:
        Payslip: Basic payslip with 168 regular hours.
    """
    return Payslip(
        id="PAYSLIP-20260201-W001",
        employee_id=sample_employee.id,
        year=2026,
        month=2,
        regular_hours=168.0,
        overtime_hours=0.0,
        regular_pay=0.0,
        overtime_pay=0.0,
        bonus=0.0,
        gross_pay=210000.0,  # 168 * 1250
        income_tax=21000.0,
        social_insurance=20685.0,
        employment_insurance=840.0,
        other_deductions=0.0,
        total_deductions=42525.0,
        net_pay=167475.0,
        notes="Sample payslip",
        generated_at="2026-02-01T10:00:00",
    )


@pytest.fixture
def temp_db_dir() -> Path:
    """Create temporary directory for test database.

    Yields:
        Path: Temporary directory path.
    """
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db(temp_db_dir: Path) -> Path:
    """Create temporary SQLite database for testing.

    Args:
        temp_db_dir: Temporary directory.

    Yields:
        Path: Path to test database file.
    """
    db_path = temp_db_dir / "test_payroll.db"

    # Create empty database
    conn = sqlite3.connect(db_path)
    conn.close()

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def logging_setup(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Enable logging capture for tests.

    Args:
        caplog: Pytest caplog fixture.

    Returns:
        pytest.LogCaptureFixture: Configured caplog.
    """
    caplog.set_level(logging.INFO)
    return caplog
