"""Factory functions for creating test employee data.

Provides fixture factories for various employee types and scenarios.
"""

from datetime import date
from typing import Optional

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from _uns_employee_schema import Employee, ContractType, EmployeeStatus


def create_hakken_employee(
    employee_id: str = "W001",
    name_jp: str = "田中 太郎",
    name_en: str = "Taro Tanaka",
    hourly_rate_jpy: float = 1250.0,
    department: str = "Operations",
) -> Employee:
    """Create a hakken (dispatch) worker.

    Args:
        employee_id: Employee ID.
        name_jp: Japanese name.
        name_en: English name.
        hourly_rate_jpy: Hourly rate in JPY.
        department: Department name.

    Returns:
        Employee: Configured hakken employee.
    """
    return Employee(
        id=employee_id,
        name_jp=name_jp,
        name_en=name_en,
        email=f"{employee_id}@uns-kikaku.com",
        phone="090-1234-5678",
        contract_type=ContractType.HAKKEN,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2024, 1, 1),
        termination_date=None,
        hourly_rate_jpy=hourly_rate_jpy,
        monthly_salary_jpy=None,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department=department,
        manager_id=None,
        bank_name="Sumitomo Bank",
        account_number="1234567890",
        account_holder=name_jp,
        notes="Test hakken employee",
    )


def create_seishain_employee(
    employee_id: str = "W002",
    name_jp: str = "山田 花子",
    name_en: str = "Hanako Yamada",
    monthly_salary_jpy: float = 200000.0,
    department: str = "HR",
) -> Employee:
    """Create a seishain (permanent salaried) employee.

    Args:
        employee_id: Employee ID.
        name_jp: Japanese name.
        name_en: English name.
        monthly_salary_jpy: Monthly salary in JPY.
        department: Department name.

    Returns:
        Employee: Configured seishain employee.
    """
    return Employee(
        id=employee_id,
        name_jp=name_jp,
        name_en=name_en,
        email=f"{employee_id}@uns-kikaku.com",
        phone="090-9876-5432",
        contract_type=ContractType.SEISHAIN,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2020, 4, 1),
        termination_date=None,
        hourly_rate_jpy=2000.0,
        monthly_salary_jpy=monthly_salary_jpy,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department=department,
        manager_id="W001",
        bank_name="Mitsubishi Bank",
        account_number="9876543210",
        account_holder=name_jp,
        notes="Test seishain employee",
    )


def create_part_time_employee(
    employee_id: str = "W003",
    name_jp: str = "佐藤 次郎",
    name_en: str = "Jiro Sato",
    hourly_rate_jpy: float = 1100.0,
    department: str = "Retail",
) -> Employee:
    """Create a part-time employee.

    Args:
        employee_id: Employee ID.
        name_jp: Japanese name.
        name_en: English name.
        hourly_rate_jpy: Hourly rate in JPY.
        department: Department name.

    Returns:
        Employee: Configured part-time employee.
    """
    return Employee(
        id=employee_id,
        name_jp=name_jp,
        name_en=name_en,
        email=f"{employee_id}@uns-kikaku.com",
        phone="090-5555-6666",
        contract_type=ContractType.PART_TIME,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2025, 1, 15),
        termination_date=None,
        hourly_rate_jpy=hourly_rate_jpy,
        monthly_salary_jpy=None,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department=department,
        manager_id=None,
        bank_name="Japan Bank",
        account_number="5555666677",
        account_holder=name_jp,
        notes="Test part-time employee",
    )


def create_kobetsu_employee(
    employee_id: str = "W004",
    name_jp: str = "鈴木 三郎",
    name_en: str = "Saburo Suzuki",
    hourly_rate_jpy: float = 1500.0,
    department: str = "Engineering",
) -> Employee:
    """Create a kobetsu (individual dispatch contract) employee.

    Args:
        employee_id: Employee ID.
        name_jp: Japanese name.
        name_en: English name.
        hourly_rate_jpy: Hourly rate in JPY.
        department: Department name.

    Returns:
        Employee: Configured kobetsu employee.
    """
    return Employee(
        id=employee_id,
        name_jp=name_jp,
        name_en=name_en,
        email=f"{employee_id}@uns-kikaku.com",
        phone="090-7777-8888",
        contract_type=ContractType.KOBETSU,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2023, 6, 1),
        termination_date=date(2027, 5, 31),
        hourly_rate_jpy=hourly_rate_jpy,
        monthly_salary_jpy=None,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department=department,
        manager_id="W001",
        bank_name="Mizuho Bank",
        account_number="7777888899",
        account_holder=name_jp,
        notes="Test kobetsu employee with fixed term",
    )


def create_high_earner() -> Employee:
    """Create a high-earning salaried employee for testing.

    Returns:
        Employee: High-earner employee with ¥400,000/month salary.
    """
    return Employee(
        id="W005",
        name_jp="大橋 部長",
        name_en="Bucho Ohashi",
        email="ohashi@uns-kikaku.com",
        phone="090-9999-0000",
        contract_type=ContractType.SEISHAIN,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2015, 4, 1),
        termination_date=None,
        hourly_rate_jpy=2500.0,
        monthly_salary_jpy=400000.0,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department="Management",
        manager_id=None,
        bank_name="MUFG Bank",
        account_number="0000111122",
        account_holder="大橋 部長",
        notes="High-earner test employee",
    )


def create_low_rate_employee() -> Employee:
    """Create a minimum-wage employee for testing.

    Returns:
        Employee: Employee with minimum hourly rate (¥800).
    """
    return Employee(
        id="W006",
        name_jp="新人 太郎",
        name_en="Taro Shinjin",
        email="shinjin@uns-kikaku.com",
        phone="090-1111-2222",
        contract_type=ContractType.PART_TIME,
        status=EmployeeStatus.ACTIVE,
        hire_date=date(2026, 4, 1),
        termination_date=None,
        hourly_rate_jpy=800.0,  # Minimum legal wage
        monthly_salary_jpy=None,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department="Training",
        manager_id="W001",
        bank_name="Local Bank",
        account_number="1111222233",
        account_holder="新人 太郎",
        notes="Minimum wage employee",
    )


def create_on_leave_employee() -> Employee:
    """Create an employee on leave for testing.

    Returns:
        Employee: Employee with ON_LEAVE status.
    """
    return Employee(
        id="W007",
        name_jp="休暇 太郎",
        name_en="Taro Kyuka",
        email="kyuka@uns-kikaku.com",
        phone="090-3333-4444",
        contract_type=ContractType.SEISHAIN,
        status=EmployeeStatus.ON_LEAVE,
        hire_date=date(2018, 1, 1),
        termination_date=None,
        hourly_rate_jpy=2000.0,
        monthly_salary_jpy=250000.0,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department="Operations",
        manager_id="W001",
        bank_name="Citibank",
        account_number="3333444455",
        account_holder="休暇 太郎",
        notes="Employee on leave",
    )


def create_terminated_employee() -> Employee:
    """Create a terminated employee for testing.

    Returns:
        Employee: Employee with TERMINATED status.
    """
    return Employee(
        id="W008",
        name_jp="退職 太郎",
        name_en="Taro Taishoku",
        email="taishoku@uns-kikaku.com",
        phone="090-5555-6666",
        contract_type=ContractType.SEISHAIN,
        status=EmployeeStatus.TERMINATED,
        hire_date=date(2010, 4, 1),
        termination_date=date(2026, 3, 31),
        hourly_rate_jpy=2000.0,
        monthly_salary_jpy=300000.0,
        income_tax_rate=0.10,
        social_insurance_rate=0.0985,
        employment_insurance_rate=0.004,
        department="Former",
        manager_id=None,
        bank_name="Sumitomo Bank",
        account_number="5555666677",
        account_holder="退職 太郎",
        notes="Terminated employee",
    )
