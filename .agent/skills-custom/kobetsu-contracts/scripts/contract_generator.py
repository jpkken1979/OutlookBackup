"""Contract Generator for Kobetsu (個別派遣契約) contracts.

Core business logic for validating, generating, and persisting individual dispatch contracts.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional, List
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import KobetsuContract, Employee

logger = logging.getLogger(__name__)

# Constants for contract validation
MIN_HOURLY_RATE = 800.0  # Japan minimum wage
MAX_CONTRACT_LENGTH_YEARS = 3
STANDARD_WORK_HOURS_DAILY = 8.0
STANDARD_WORK_DAYS_WEEKLY = 5


@dataclass
class ContractValidationResult:
    """Result of contract validation.

    Attributes:
        is_valid: Whether validation passed.
        errors: List of validation error messages.
        warnings: List of validation warnings (non-fatal).
    """

    is_valid: bool
    errors: list[str]
    warnings: list[str]


class KobetsuContractGenerator:
    """Generates and manages individual dispatch contracts (個別派遣契約)."""

    def __init__(self) -> None:
        """Initialize contract generator."""
        logger.info("KobetsuContractGenerator initialized")

    def validate_contract_data(
        self,
        employee: Employee,
        contract_number: str,
        job_title: str,
        work_location: str,
        hourly_rate_jpy: float,
        effective_date: date,
        expiration_date: date | None = None,
        work_hours_daily: float = STANDARD_WORK_HOURS_DAILY,
        work_days_weekly: int = STANDARD_WORK_DAYS_WEEKLY,
    ) -> ContractValidationResult:
        """Validate contract parameters before generation.

        Args:
            employee: Employee record.
            contract_number: Unique contract identifier (e.g., 'KOB-2026-001').
            job_title: Job title/position.
            work_location: Work location.
            hourly_rate_jpy: Hourly rate in JPY.
            effective_date: Contract start date.
            expiration_date: Contract end date (optional).
            work_hours_daily: Daily work hours (default 8.0).
            work_days_weekly: Weekly work days (default 5).

        Returns:
            ContractValidationResult with validation errors/warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Validate contract number format
        if not contract_number or len(contract_number.strip()) == 0:
            errors.append("contract_number cannot be empty")
        elif len(contract_number) > 50:
            errors.append("contract_number exceeds maximum length (50)")

        # Validate job title
        if not job_title or len(job_title.strip()) == 0:
            errors.append("job_title cannot be empty")

        # Validate work location
        if not work_location or len(work_location.strip()) == 0:
            errors.append("work_location cannot be empty")

        # Validate hourly rate
        if hourly_rate_jpy < MIN_HOURLY_RATE:
            errors.append(f"hourly_rate_jpy {hourly_rate_jpy} below minimum {MIN_HOURLY_RATE}")
        elif hourly_rate_jpy > 100000.0:
            warnings.append(f"hourly_rate_jpy {hourly_rate_jpy} unusually high")

        # Validate work hours
        if work_hours_daily <= 0 or work_hours_daily > 24:
            errors.append(f"work_hours_daily must be between 0 and 24, got {work_hours_daily}")

        if work_days_weekly <= 0 or work_days_weekly > 7:
            errors.append(f"work_days_weekly must be between 1 and 7, got {work_days_weekly}")

        # Validate dates
        if effective_date >= date.today() or effective_date.year < 2000:
            warnings.append(f"effective_date {effective_date} is in the past or before 2000")

        if expiration_date:
            if expiration_date <= effective_date:
                errors.append("expiration_date must be after effective_date")

            # Check contract length
            contract_length_days = (expiration_date - effective_date).days
            contract_length_years = contract_length_days / 365.25
            if contract_length_years > MAX_CONTRACT_LENGTH_YEARS:
                warnings.append(
                    f"Contract length {contract_length_years:.1f} years exceeds typical maximum {MAX_CONTRACT_LENGTH_YEARS}"
                )

        # Validate employee status (should be active for new contracts)
        if employee.status != "active":
            warnings.append(f"Employee status is {employee.status}, not active")

        is_valid = len(errors) == 0

        logger.info(
            f"Validation for {contract_number}: valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}"
        )

        return ContractValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )

    def generate_contract(
        self,
        employee: Employee,
        contract_number: str,
        job_title: str,
        work_location: str,
        hourly_rate_jpy: float,
        effective_date: date,
        expiration_date: date | None = None,
        client_company: str | None = None,
        work_hours_daily: float = STANDARD_WORK_HOURS_DAILY,
        work_days_weekly: int = STANDARD_WORK_DAYS_WEEKLY,
        monthly_minimum_hours: float | None = None,
        benefits: list[str] | None = None,
        terms_conditions: str | None = None,
        notes: str | None = None,
    ) -> KobetsuContract:
        """Generate a new Kobetsu contract.

        Args:
            employee: Employee record.
            contract_number: Unique contract identifier.
            job_title: Job title.
            work_location: Work location.
            hourly_rate_jpy: Hourly rate in JPY.
            effective_date: Contract start date.
            expiration_date: Contract end date (optional).
            client_company: Client/dispatch company name.
            work_hours_daily: Daily work hours (default 8.0).
            work_days_weekly: Weekly work days (default 5).
            monthly_minimum_hours: Minimum monthly hours (optional).
            benefits: List of benefits (optional).
            terms_conditions: Contract terms and conditions (optional).
            notes: Additional notes (optional).

        Returns:
            KobetsuContract: Generated contract.

        Raises:
            ValueError: If validation fails.
        """
        # Validate first
        validation = self.validate_contract_data(
            employee=employee,
            contract_number=contract_number,
            job_title=job_title,
            work_location=work_location,
            hourly_rate_jpy=hourly_rate_jpy,
            effective_date=effective_date,
            expiration_date=expiration_date,
            work_hours_daily=work_hours_daily,
            work_days_weekly=work_days_weekly,
        )

        if not validation.is_valid:
            error_msg = "; ".join(validation.errors)
            logger.error(f"Contract validation failed: {error_msg}")
            raise ValueError(f"Contract validation failed: {error_msg}")

        # Log warnings
        for warning in validation.warnings:
            logger.warning(f"Contract warning: {warning}")

        # Create contract
        contract = KobetsuContract(
            employee_id=employee.id,
            contract_number=contract_number,
            contract_date=date.today(),
            effective_date=effective_date,
            expiration_date=expiration_date,
            dispatch_company="UNS",
            client_company=client_company or employee.department,
            job_title=job_title,
            work_location=work_location,
            work_hours_daily=work_hours_daily,
            work_days_weekly=work_days_weekly,
            hourly_rate_jpy=hourly_rate_jpy,
            monthly_minimum_hours=monthly_minimum_hours,
            benefits=benefits or [],
            terms_conditions=terms_conditions,
            notes=notes,
        )

        logger.info(f"Generated contract {contract_number} for employee {employee.id}")
        return contract

    def validate_contract_number_uniqueness(
        self,
        contract_number: str,
        existing_contracts: list[str] | None = None,
    ) -> bool:
        """Check if contract number is unique.

        Args:
            contract_number: Contract number to check.
            existing_contracts: List of existing contract numbers (optional).

        Returns:
            bool: True if contract number is unique.
        """
        if existing_contracts is None:
            existing_contracts = []

        is_unique = contract_number not in existing_contracts
        if not is_unique:
            logger.warning(f"Contract number already exists: {contract_number}")

        return is_unique
