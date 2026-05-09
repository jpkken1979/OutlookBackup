"""Unit tests for PayrollCalculator.

Tests gross pay, deductions, net pay, overtime validation, and payslip generation.
"""

import pytest
from datetime import date

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import Employee, Payslip, ContractType, EmployeeStatus
from payroll_processor.scripts.payroll_calculator import (
    PayrollCalculator,
    DeductionBreakdown,
)


class TestPayrollCalculatorInit:
    """Test PayrollCalculator initialization."""

    def test_init_valid_employee(self, sample_employee: Employee) -> None:
        """Test initialization with valid employee."""
        calc = PayrollCalculator(sample_employee)
        assert calc.employee.id == "W001"
        assert calc.employee.hourly_rate_jpy == 1250.0

    def test_init_minimum_wage_violation(self) -> None:
        """Test initialization fails with hourly_rate below minimum."""
        invalid_employee = Employee(
            id="W999",
            name_jp="Low Pay",
            name_en="Low Pay",
            email="low@test.com",
            contract_type=ContractType.HAKKEN,
            status=EmployeeStatus.ACTIVE,
            hire_date=date(2026, 1, 1),
            termination_date=None,
            hourly_rate_jpy=700.0,  # Below 800 minimum
            monthly_salary_jpy=None,
            income_tax_rate=0.10,
            social_insurance_rate=0.0985,
            employment_insurance_rate=0.004,
            department="Test",
        )

        with pytest.raises(ValueError, match="below minimum"):
            PayrollCalculator(invalid_employee)


class TestCalculateGrossPay:
    """Test gross pay calculation."""

    def test_calculate_gross_pay_regular_only(self, sample_employee: Employee) -> None:
        """Test gross pay with regular hours only (no overtime, no bonus)."""
        calc = PayrollCalculator(sample_employee)
        # 160 hours * ¥1250/h = ¥200,000
        gross = calc.calculate_gross_pay(regular_hours=160.0)
        assert gross == 200000.0

    def test_calculate_gross_pay_with_overtime(self, sample_employee: Employee) -> None:
        """Test gross pay with regular hours + overtime."""
        calc = PayrollCalculator(sample_employee)
        # 160 * 1250 = 200,000
        # 20 * 1250 * 1.25 = 31,250
        # Total = 231,250
        gross = calc.calculate_gross_pay(regular_hours=160.0, overtime_hours=20.0)
        assert gross == 231250.0

    def test_calculate_gross_pay_with_bonus(self, sample_employee: Employee) -> None:
        """Test gross pay with bonus."""
        calc = PayrollCalculator(sample_employee)
        gross = calc.calculate_gross_pay(regular_hours=160.0, overtime_hours=0.0, bonus=50000.0)
        assert gross == 250000.0

    def test_calculate_gross_pay_all_components(self, sample_employee: Employee) -> None:
        """Test gross pay with all components."""
        calc = PayrollCalculator(sample_employee)
        # 160 * 1250 = 200,000
        # 10 * 1250 * 1.25 = 15,625
        # bonus = 30,000
        # Total = 245,625
        gross = calc.calculate_gross_pay(regular_hours=160.0, overtime_hours=10.0, bonus=30000.0)
        assert gross == 245625.0

    def test_calculate_gross_pay_overtime_limit_violation(self, sample_employee: Employee) -> None:
        """Test overtime validation against 36協定 (45h/month limit)."""
        calc = PayrollCalculator(sample_employee)
        with pytest.raises(ValueError, match="exceeds 36協定"):
            calc.calculate_gross_pay(regular_hours=160.0, overtime_hours=46.0)

    def test_calculate_gross_pay_negative_hours(self, sample_employee: Employee) -> None:
        """Test calculation rejects negative hours."""
        calc = PayrollCalculator(sample_employee)
        with pytest.raises(ValueError, match="cannot be negative"):
            calc.calculate_gross_pay(regular_hours=-10.0)

    def test_calculate_gross_pay_negative_overtime(self, sample_employee: Employee) -> None:
        """Test calculation rejects negative overtime."""
        calc = PayrollCalculator(sample_employee)
        with pytest.raises(ValueError, match="cannot be negative"):
            calc.calculate_gross_pay(regular_hours=160.0, overtime_hours=-5.0)


class TestCalculateDeductions:
    """Test deduction calculation."""

    def test_calculate_deductions_standard_rates(self, sample_employee: Employee) -> None:
        """Test deductions with standard Japanese tax rates."""
        calc = PayrollCalculator(sample_employee)
        gross_pay = 200000.0
        deductions = calc.calculate_deductions(gross_pay)

        # Expected:
        # Income tax: 200,000 * 0.10 = 20,000
        # Social insurance: 200,000 * 0.0985 = 19,700
        # Employment insurance: 200,000 * 0.004 = 800
        # Total: 40,500

        assert deductions.income_tax == 20000.0
        assert deductions.social_insurance == 19700.0
        assert deductions.employment_insurance == 800.0
        assert deductions.other_deductions == 0.0
        assert deductions.total_deductions == 40500.0

    def test_calculate_deductions_negative_gross(self, sample_employee: Employee) -> None:
        """Test deductions reject negative gross pay."""
        calc = PayrollCalculator(sample_employee)
        with pytest.raises(ValueError, match="cannot be negative"):
            calc.calculate_deductions(-1000.0)

    def test_calculate_deductions_zero_gross(self, sample_employee: Employee) -> None:
        """Test deductions with zero gross pay."""
        calc = PayrollCalculator(sample_employee)
        deductions = calc.calculate_deductions(0.0)
        assert deductions.total_deductions == 0.0


class TestCalculateNetPay:
    """Test net pay calculation."""

    def test_calculate_net_pay_standard(self, sample_employee: Employee) -> None:
        """Test net pay = gross - deductions."""
        calc = PayrollCalculator(sample_employee)
        gross_pay = 200000.0
        deductions = calc.calculate_deductions(gross_pay)
        net_pay = calc.calculate_net_pay(gross_pay, deductions)

        # 200,000 - 40,500 = 159,500
        assert net_pay == 159500.0

    def test_calculate_net_pay_high_bonus(self, sample_employee: Employee) -> None:
        """Test net pay with high bonus."""
        calc = PayrollCalculator(sample_employee)
        gross_pay = 300000.0
        deductions = calc.calculate_deductions(gross_pay)
        net_pay = calc.calculate_net_pay(gross_pay, deductions)

        # 300,000 - (30,000 + 29,550 + 1,200) = 239,250
        assert deductions.total_deductions == 60750.0
        assert net_pay == 239250.0


class TestProcessPayroll:
    """Test complete payroll processing."""

    def test_process_payroll_happy_path(self, sample_employee: Employee) -> None:
        """Test full payroll calculation with standard hours."""
        calc = PayrollCalculator(sample_employee)
        payslip = calc.process_payroll(
            regular_hours=160.0, overtime_hours=0.0, bonus=0.0, year=2026, month=2
        )

        assert payslip.employee_id == "W001"
        assert payslip.year == 2026
        assert payslip.month == 2
        assert payslip.regular_hours == 160.0
        assert payslip.overtime_hours == 0.0
        assert payslip.gross_pay == 200000.0
        assert payslip.total_deductions == 40500.0
        assert payslip.net_pay == 159500.0
        assert payslip.id.startswith("PAYSLIP-202602")

    def test_process_payroll_with_overtime(self, sample_employee: Employee) -> None:
        """Test payroll with overtime."""
        calc = PayrollCalculator(sample_employee)
        payslip = calc.process_payroll(
            regular_hours=160.0, overtime_hours=20.0, bonus=0.0, year=2026, month=3
        )

        assert payslip.regular_hours == 160.0
        assert payslip.overtime_hours == 20.0
        assert payslip.gross_pay == 231250.0
        assert payslip.net_pay > 159500.0

    def test_process_payroll_with_bonus(self, sample_employee: Employee) -> None:
        """Test payroll with bonus."""
        calc = PayrollCalculator(sample_employee)
        payslip = calc.process_payroll(
            regular_hours=160.0, overtime_hours=0.0, bonus=100000.0, year=2026, month=6
        )

        assert payslip.bonus == 100000.0
        assert payslip.gross_pay == 300000.0

    def test_process_payroll_invalid_month(self, sample_employee: Employee) -> None:
        """Test payroll rejects invalid month."""
        calc = PayrollCalculator(sample_employee)
        with pytest.raises(ValueError, match="Invalid month"):
            calc.process_payroll(
                regular_hours=160.0, overtime_hours=0.0, bonus=0.0, year=2026, month=13
            )

    def test_process_payroll_invalid_year(self, sample_employee: Employee) -> None:
        """Test payroll rejects invalid year."""
        calc = PayrollCalculator(sample_employee)
        with pytest.raises(ValueError, match="Invalid year"):
            calc.process_payroll(
                regular_hours=160.0, overtime_hours=0.0, bonus=0.0, year=1999, month=1
            )

    def test_process_payroll_overtime_max_valid(self, sample_employee: Employee) -> None:
        """Test payroll accepts maximum valid overtime (45h)."""
        calc = PayrollCalculator(sample_employee)
        payslip = calc.process_payroll(
            regular_hours=160.0, overtime_hours=45.0, bonus=0.0, year=2026, month=4
        )

        assert payslip.overtime_hours == 45.0
        assert payslip.gross_pay > 0

    def test_process_payroll_overtime_exceeds_limit(self, sample_employee: Employee) -> None:
        """Test payroll rejects overtime > 45h."""
        calc = PayrollCalculator(sample_employee)
        with pytest.raises(ValueError, match="exceeds 36協定"):
            calc.process_payroll(
                regular_hours=160.0, overtime_hours=46.0, bonus=0.0, year=2026, month=5
            )


class TestPayslipStructure:
    """Test payslip output structure."""

    def test_payslip_contains_all_fields(self, sample_employee: Employee) -> None:
        """Test payslip has all required fields."""
        calc = PayrollCalculator(sample_employee)
        payslip = calc.process_payroll(
            regular_hours=168.0, overtime_hours=5.0, bonus=20000.0, year=2026, month=1
        )

        assert hasattr(payslip, "id")
        assert hasattr(payslip, "employee_id")
        assert hasattr(payslip, "year")
        assert hasattr(payslip, "month")
        assert hasattr(payslip, "regular_hours")
        assert hasattr(payslip, "overtime_hours")
        assert hasattr(payslip, "regular_pay")
        assert hasattr(payslip, "overtime_pay")
        assert hasattr(payslip, "bonus")
        assert hasattr(payslip, "gross_pay")
        assert hasattr(payslip, "income_tax")
        assert hasattr(payslip, "social_insurance")
        assert hasattr(payslip, "employment_insurance")
        assert hasattr(payslip, "other_deductions")
        assert hasattr(payslip, "total_deductions")
        assert hasattr(payslip, "net_pay")

    def test_payslip_financial_integrity(self, sample_employee: Employee) -> None:
        """Test payslip financial formula: gross - deductions = net."""
        calc = PayrollCalculator(sample_employee)
        payslip = calc.process_payroll(
            regular_hours=160.0, overtime_hours=10.0, bonus=30000.0, year=2026, month=2
        )

        # Verify: gross - deductions = net
        calculated_net = payslip.gross_pay - payslip.total_deductions
        assert abs(calculated_net - payslip.net_pay) < 0.01
