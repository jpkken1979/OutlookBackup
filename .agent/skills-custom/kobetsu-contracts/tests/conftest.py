"""Test configuration and shared fixtures for Kobetsu Contracts tests."""

import pytest
import sqlite3
from pathlib import Path
from datetime import date, datetime
from tempfile import TemporaryDirectory

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import Employee, ContractType, EmployeeStatus, KobetsuContract


@pytest.fixture
def temp_db_dir():
    """Create temporary directory for test databases."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_employee():
    """Create a test employee."""
    return Employee(
        id="W001",
        name_jp="田中太郎",
        name_en="Taro Tanaka",
        email="taro.tanaka@uns.com",
        phone="09012345678",
        contract_type=ContractType.HAKKEN,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2024, 1, 1),
        termination_date=None,
        hourly_rate_jpy=1500.0,
        monthly_salary_jpy=None,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department="Engineering",
        manager_id="M001",
        bank_name="Bank of Japan",
        account_number="123456789",
        account_holder="Taro Tanaka",
        notes="Test employee",
    )


@pytest.fixture
def test_contract():
    """Create a test contract."""
    return KobetsuContract(
        id="CONTRACT-2026-04-03-1",
        employee_id="W001",
        contract_number="KOB-2026-001",
        contract_date=date(2026, 4, 3),
        effective_date=date(2026, 4, 1),
        expiration_date=date(2027, 3, 31),
        dispatch_company="UNS",
        client_company="Tech Company A",
        job_title="システムエンジニア",
        work_location="東京都渋谷区",
        work_hours_daily=8.0,
        work_days_weekly=5,
        hourly_rate_jpy=2500.0,
        monthly_minimum_hours=160.0,
        benefits=["健康保険", "厚生年金", "雇用保険"],
        terms_conditions="This is a dispatch contract for system engineering work.",
        notes="Test contract",
        generated_at=datetime.now().isoformat(),
        template_version="1.0",
    )


@pytest.fixture
def valid_contract_params():
    """Create valid contract parameters."""
    return {
        "operation": "generate_contract",
        "employee_id": "W001",
        "contract_number": "KOB-2026-001",
        "job_title": "システムエンジニア",
        "work_location": "東京都渋谷区",
        "hourly_rate_jpy": 2500.0,
        "effective_date": "2026-04-01",
        "expiration_date": "2027-03-31",
        "client_company": "Tech Company A",
        "work_hours_daily": 8.0,
        "work_days_weekly": 5,
        "monthly_minimum_hours": 160.0,
        "benefits": ["健康保険", "厚生年金"],
        "notes": "Test contract",
    }


@pytest.fixture
def template_dir(temp_db_dir):
    """Create templates directory with sample template."""
    templates = temp_db_dir / "templates"
    templates.mkdir()

    # Create minimal Jinja2 template for testing
    template_content = """
<html>
<head><title>Test Contract</title></head>
<body>
<h1>{{ contract_number }}</h1>
<p>Employee: {{ employee_name_jp }}</p>
<p>Position: {{ job_title }}</p>
<p>Rate: ¥{{ hourly_rate_jpy|int }}</p>
</body>
</html>
"""
    (templates / "contract_japanese.jinja2").write_text(template_content)

    # Create CSS file
    css_content = """
body { font-family: Arial; }
h1 { color: #003366; }
"""
    (templates / "styles.css").write_text(css_content)

    return templates


@pytest.fixture
def test_db_with_employee(temp_db_dir, test_employee):
    """Create test database with sample employee."""
    db_path = temp_db_dir / "test.db"

    # Create minimal schema for testing
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE employees (
                id TEXT PRIMARY KEY,
                name_jp TEXT,
                name_en TEXT,
                email TEXT,
                contract_type TEXT,
                status TEXT,
                hire_date DATE,
                hourly_rate_jpy REAL,
                department TEXT,
                manager_id TEXT,
                bank_name TEXT,
                account_number TEXT,
                account_holder TEXT,
                income_tax_rate REAL,
                social_insurance_rate REAL,
                employment_insurance_rate REAL,
                phone TEXT,
                notes TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Insert test employee
        conn.execute(
            """
            INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                test_employee.id,
                test_employee.name_jp,
                test_employee.name_en,
                test_employee.email,
                test_employee.contract_type,
                test_employee.status,
                test_employee.hire_date.isoformat(),
                test_employee.hourly_rate_jpy,
                test_employee.department,
                test_employee.manager_id,
                test_employee.bank_name,
                test_employee.account_number,
                test_employee.account_holder,
                test_employee.income_tax_rate,
                test_employee.social_insurance_rate,
                test_employee.employment_insurance_rate,
                test_employee.phone,
                test_employee.notes,
                None,
                None,
            ),
        )

        conn.commit()

    return db_path


@pytest.fixture
def test_db_with_contracts(test_db_with_employee):
    """Create test database with contracts tables."""
    db_path = test_db_with_employee

    with sqlite3.connect(db_path) as conn:
        # Create contracts table
        conn.execute("""
            CREATE TABLE kobetsu_contracts (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                contract_number TEXT NOT NULL UNIQUE,
                contract_date DATE,
                effective_date DATE,
                expiration_date DATE,
                dispatch_company TEXT,
                client_company TEXT,
                job_title TEXT,
                work_location TEXT,
                work_hours_daily REAL,
                work_days_weekly INTEGER,
                hourly_rate_jpy REAL,
                monthly_minimum_hours REAL,
                benefits TEXT,
                terms_conditions TEXT,
                notes TEXT,
                generated_at TIMESTAMP,
                template_version TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)

        # Create audit table
        conn.execute("""
            CREATE TABLE kobetsu_contracts_audit (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                version INTEGER,
                change_type TEXT,
                changed_at TIMESTAMP,
                previous_value TEXT,
                new_value TEXT,
                changed_by TEXT,
                FOREIGN KEY (contract_id) REFERENCES kobetsu_contracts(id)
            )
        """)

        conn.commit()

    return db_path
