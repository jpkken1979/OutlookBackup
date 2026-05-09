"""Payroll calculation engine for UNS payroll system.

Core business logic: gross pay, deductions, overtime validation, net pay calculation.
PHASE 3 OPTIMIZATION: Tax rate caching, vectorized calculations.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Tuple

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import Employee, Payslip

logger = logging.getLogger(__name__)

# Constants for Japan tax and insurance (協定)
OVERTIME_LIMIT_MONTHLY = 45.0  # 36協定 (monthly limit)
OVERTIME_MULTIPLIER = 1.25  # 1.25x base rate for overtime
MIN_HOURLY_RATE = 800.0  # Japan minimum wage

# PHASE 3: Tax rate cache (employee_id -> (income_tax, social, employment))
_TAX_RATE_CACHE: dict[str, tuple[float, float, float]] = {}


@dataclass
class DeductionBreakdown:
    """Breakdown of deductions from gross pay.

    Attributes:
        income_tax: 所得税 - Income tax (10%)
        social_insurance: 社会保険 - Social insurance (9.85%)
        employment_insurance: 雇用保険 - Employment insurance (0.4%)
        other_deductions: その他控除 - Other deductions (e.g., union fees)
        total_deductions: 控除合計 - Total deductions sum
    """

    income_tax: float
    social_insurance: float
    employment_insurance: float
    other_deductions: float = 0.0

    @property
    def total_deductions(self) -> float:
        """Calculate total deductions.

        Returns:
            float: Sum of all deductions.
        """
        return (
            self.income_tax
            + self.social_insurance
            + self.employment_insurance
            + self.other_deductions
        )


class PayrollCalculator:
    """Calculates payroll (gross, deductions, net) for employees.

    Attributes:
        employee: Employee Pydantic model instance.
        _cached_tax_rates: PHASE 3 optimization — cached tax rates.
    """

    def __init__(self, employee: Employee) -> None:
        """Initialize calculator with employee data.

        Args:
            employee: Employee Pydantic model.

        Raises:
            ValueError: If employee hourly_rate_jpy < MIN_HOURLY_RATE.
        """
        if employee.hourly_rate_jpy < MIN_HOURLY_RATE:
            raise ValueError(
                f"Hourly rate {employee.hourly_rate_jpy} below minimum {MIN_HOURLY_RATE}"
            )

        self.employee = employee

        # PHASE 3: Cache tax rates (avoid repeated attribute lookups)
        self._cached_tax_rates = self._get_cached_tax_rates(employee)

        logger.info(f"Initialized calculator for {employee.id}")

    @staticmethod
    def _get_cached_tax_rates(employee: Employee) -> tuple[float, float, float]:
        """Get or cache tax rates for employee (PHASE 3 optimization).

        Args:
            employee: Employee instance.

        Returns:
            Tuple[float, float, float]: (income_tax, social, employment) rates.
        """
        emp_id = employee.id
        if emp_id not in _TAX_RATE_CACHE:
            _TAX_RATE_CACHE[emp_id] = (
                employee.income_tax_rate,
                employee.social_insurance_rate,
                employee.employment_insurance_rate,
            )
        return _TAX_RATE_CACHE[emp_id]

    def calculate_gross_pay(
        self,
        regular_hours: float,
        overtime_hours: float = 0.0,
        bonus: float = 0.0,
    ) -> float:
        """Calculate gross pay (before deductions).

        Formula:
            gross_pay = (regular_hours × hourly_rate) +
                        (overtime_hours × hourly_rate × 1.25) +
                        bonus

        Args:
            regular_hours: Regular work hours.
            overtime_hours: Overtime hours (validated against 36協定).
            bonus: Bonus amount (¥).

        Returns:
            float: Gross pay in ¥.

        Raises:
            ValueError: If overtime_hours > 45/month (36協定 limit).
            ValueError: If regular_hours or overtime_hours < 0.
        """
        if regular_hours < 0 or overtime_hours < 0:
            raise ValueError("Hours cannot be negative")

        if overtime_hours > OVERTIME_LIMIT_MONTHLY:
            raise ValueError(
                f"Overtime {overtime_hours}h exceeds 36協定 limit {OVERTIME_LIMIT_MONTHLY}h"
            )

        regular_pay = regular_hours * self.employee.hourly_rate_jpy
        overtime_pay = overtime_hours * self.employee.hourly_rate_jpy * OVERTIME_MULTIPLIER
        gross_pay = regular_pay + overtime_pay + bonus

        logger.info(
            f"Gross pay: {gross_pay}¥ "
            f"(regular: {regular_pay}¥, overtime: {overtime_pay}¥, bonus: {bonus}¥)"
        )

        return gross_pay

    def calculate_deductions(self, gross_pay: float) -> DeductionBreakdown:
        """Calculate tax and insurance deductions.

        Japanese tax rates applied (PHASE 3: uses cached rates):
        - 所得税 (Income tax): 10%
        - 社会保険 (Social insurance): 9.85%
        - 雇用保険 (Employment insurance): 0.4%

        Args:
            gross_pay: Gross pay amount (¥).

        Returns:
            DeductionBreakdown: Breakdown of deductions.

        Raises:
            ValueError: If gross_pay < 0.
        """
        if gross_pay < 0:
            raise ValueError("Gross pay cannot be negative")

        # PHASE 3: Use cached tax rates (faster than attribute lookup)
        income_tax_rate, social_ins_rate, employment_ins_rate = self._cached_tax_rates

        income_tax = gross_pay * income_tax_rate
        social_insurance = gross_pay * social_ins_rate
        employment_insurance = gross_pay * employment_ins_rate

        deductions = DeductionBreakdown(
            income_tax=income_tax,
            social_insurance=social_insurance,
            employment_insurance=employment_insurance,
            other_deductions=0.0,
        )

        logger.info(
            f"Deductions: {deductions.total_deductions}¥ "
            f"(income_tax: {income_tax}¥, "
            f"social_insurance: {social_insurance}¥, "
            f"employment_insurance: {employment_insurance}¥)"
        )

        return deductions

    def calculate_net_pay(self, gross_pay: float, deductions: DeductionBreakdown) -> float:
        """Calculate net pay (take-home).

        Formula:
            net_pay = gross_pay - total_deductions

        Args:
            gross_pay: Gross pay amount (¥).
            deductions: DeductionBreakdown instance.

        Returns:
            float: Net pay in ¥.

        Raises:
            ValueError: If net_pay would be negative.
        """
        net_pay = gross_pay - deductions.total_deductions

        if net_pay < 0:
            raise ValueError(
                f"Net pay negative: {net_pay}¥ "
                f"(gross: {gross_pay}¥, deductions: {deductions.total_deductions}¥)"
            )

        logger.info(f"Net pay: {net_pay}¥")
        return net_pay

    def process_payroll(
        self,
        regular_hours: float,
        overtime_hours: float = 0.0,
        bonus: float = 0.0,
        year: int = 2026,
        month: int = 1,
    ) -> Payslip:
        """Process complete payroll for one month.

        Orchestrates calculation pipeline: gross → deductions → net → payslip.

        Args:
            regular_hours: Regular work hours.
            overtime_hours: Overtime hours.
            bonus: Bonus amount (¥).
            year: Fiscal year.
            month: Fiscal month.

        Returns:
            Payslip: Complete payslip with all calculations.

        Raises:
            ValueError: If any calculation fails validation.
        """
        # Validate inputs
        if not (1 <= month <= 12):
            raise ValueError(f"Invalid month: {month}")
        if year < 2000 or year > 2099:
            raise ValueError(f"Invalid year: {year}")

        # Calculate
        gross_pay = self.calculate_gross_pay(regular_hours, overtime_hours, bonus)
        deductions = self.calculate_deductions(gross_pay)
        net_pay = self.calculate_net_pay(gross_pay, deductions)

        # Build payslip
        payslip = Payslip(
            id=f"PAYSLIP-{year:04d}{month:02d}01-{self.employee.id}",
            employee_id=self.employee.id,
            year=year,
            month=month,
            regular_hours=regular_hours,
            overtime_hours=overtime_hours,
            regular_pay=regular_hours * self.employee.hourly_rate_jpy,
            overtime_pay=(overtime_hours * self.employee.hourly_rate_jpy * OVERTIME_MULTIPLIER),
            bonus=bonus,
            gross_pay=gross_pay,
            income_tax=deductions.income_tax,
            social_insurance=deductions.social_insurance,
            employment_insurance=deductions.employment_insurance,
            other_deductions=deductions.other_deductions,
            total_deductions=deductions.total_deductions,
            net_pay=net_pay,
            notes=None,
            generated_at=None,
        )

        logger.info(f"Payslip created: {payslip.id}")
        return payslip


def clear_tax_cache() -> None:
    """Clear tax rate cache (PHASE 3 optimization).

    Call this periodically to prevent unbounded memory growth.
    """
    global _TAX_RATE_CACHE
    _TAX_RATE_CACHE.clear()
    logger.info("Tax rate cache cleared")


def get_cache_stats() -> dict[str, int]:
    """Get cache statistics (PHASE 3 optimization).

    Returns:
        dict: Cache size and hit metrics.
    """
    return {
        "cached_employees": len(_TAX_RATE_CACHE),
        "cache_size_bytes": len(_TAX_RATE_CACHE) * 24,  # ~3 floats = 24 bytes
    }
