"""Tests for contract_generator.py module."""

import pytest
from datetime import date

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kobetsu_contracts.scripts.contract_generator import (
    KobetsuContractGenerator,
    ContractValidationResult,
)
from _uns_employee_schema import Employee, ContractType, EmployeeStatus


class TestKobetsuContractGenerator:
    """Test KobetsuContractGenerator class."""

    def test_init(self):
        """Test generator initialization."""
        gen = KobetsuContractGenerator()
        assert gen is not None

    def test_validate_contract_data_valid(self, test_employee):
        """Test validation with valid data."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
            expiration_date=date(2027, 3, 31),
        )

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert isinstance(result, ContractValidationResult)

    def test_validate_contract_number_empty(self, test_employee):
        """Test validation with empty contract number."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
        )

        assert result.is_valid is False
        assert "contract_number cannot be empty" in result.errors

    def test_validate_contract_number_too_long(self, test_employee):
        """Test validation with too long contract number."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="A" * 100,
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
        )

        assert result.is_valid is False
        assert "exceeds maximum length" in result.errors[0]

    def test_validate_job_title_empty(self, test_employee):
        """Test validation with empty job title."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
        )

        assert result.is_valid is False
        assert "job_title cannot be empty" in result.errors

    def test_validate_hourly_rate_below_minimum(self, test_employee):
        """Test validation with hourly rate below minimum."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=500.0,  # Below ¥800 minimum
            effective_date=date(2026, 4, 1),
        )

        assert result.is_valid is False
        assert "below minimum" in result.errors[0]

    def test_validate_hourly_rate_unusually_high(self, test_employee):
        """Test validation with unusually high hourly rate."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=150000.0,  # Very high
            effective_date=date(2026, 4, 1),
        )

        assert result.is_valid is True  # Valid but with warning
        assert len(result.warnings) > 0
        assert "unusually high" in result.warnings[0]

    def test_validate_work_hours_invalid(self, test_employee):
        """Test validation with invalid work hours."""
        gen = KobetsuContractGenerator()

        # Negative hours
        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
            work_hours_daily=-8.0,
        )

        assert result.is_valid is False
        assert "must be between 0 and 24" in result.errors[0]

        # Too many hours
        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
            work_hours_daily=25.0,
        )

        assert result.is_valid is False
        assert "must be between 0 and 24" in result.errors[0]

    def test_validate_work_days_invalid(self, test_employee):
        """Test validation with invalid work days."""
        gen = KobetsuContractGenerator()

        # Too many days
        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
            work_days_weekly=8,
        )

        assert result.is_valid is False
        assert "must be between 1 and 7" in result.errors[0]

    def test_validate_dates_invalid(self, test_employee):
        """Test validation with invalid date range."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2027, 3, 31),
            expiration_date=date(2026, 4, 1),  # End before start
        )

        assert result.is_valid is False
        assert "expiration_date must be after effective_date" in result.errors

    def test_validate_contract_length_warning(self, test_employee):
        """Test validation with very long contract."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
            expiration_date=date(2030, 4, 1),  # 4 years
        )

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "exceeds typical maximum" in result.warnings[0]

    def test_generate_contract_valid(self, test_employee):
        """Test contract generation with valid data."""
        gen = KobetsuContractGenerator()

        contract = gen.generate_contract(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
            expiration_date=date(2027, 3, 31),
            benefits=["健康保険", "厚生年金"],
        )

        assert contract.employee_id == "W001"
        assert contract.contract_number == "KOB-2026-001"
        assert contract.job_title == "システムエンジニア"
        assert contract.hourly_rate_jpy == 2500.0
        assert contract.benefits == ["健康保険", "厚生年金"]

    def test_generate_contract_invalid_raises_error(self, test_employee):
        """Test that invalid contract generation raises ValueError."""
        gen = KobetsuContractGenerator()

        with pytest.raises(ValueError):
            gen.generate_contract(
                employee=test_employee,
                contract_number="KOB-2026-001",
                job_title="システムエンジニア",
                work_location="東京都渋谷区",
                hourly_rate_jpy=500.0,  # Below minimum
                effective_date=date(2026, 4, 1),
            )

    def test_validate_contract_number_uniqueness_unique(self):
        """Test uniqueness check for new contract number."""
        gen = KobetsuContractGenerator()

        is_unique = gen.validate_contract_number_uniqueness(
            contract_number="KOB-2026-001",
            existing_contracts=["KOB-2026-002", "KOB-2026-003"],
        )

        assert is_unique is True

    def test_validate_contract_number_uniqueness_duplicate(self):
        """Test uniqueness check for duplicate contract number."""
        gen = KobetsuContractGenerator()

        is_unique = gen.validate_contract_number_uniqueness(
            contract_number="KOB-2026-001",
            existing_contracts=["KOB-2026-001", "KOB-2026-002"],
        )

        assert is_unique is False

    def test_validate_contract_number_uniqueness_empty_list(self):
        """Test uniqueness check with empty existing contracts."""
        gen = KobetsuContractGenerator()

        is_unique = gen.validate_contract_number_uniqueness(
            contract_number="KOB-2026-001",
            existing_contracts=[],
        )

        assert is_unique is True

    def test_multiple_validation_errors(self, test_employee):
        """Test validation with multiple errors."""
        gen = KobetsuContractGenerator()

        result = gen.validate_contract_data(
            employee=test_employee,
            contract_number="",  # Error 1
            job_title="",  # Error 2
            work_location="",  # Error 3
            hourly_rate_jpy=500.0,  # Error 4
            effective_date=date(2026, 4, 1),
            work_hours_daily=-5.0,  # Error 5
        )

        assert result.is_valid is False
        assert len(result.errors) >= 5

    def test_generate_contract_with_all_fields(self, test_employee):
        """Test contract generation with all optional fields."""
        gen = KobetsuContractGenerator()

        contract = gen.generate_contract(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
            expiration_date=date(2027, 3, 31),
            client_company="Tech Company A",
            work_hours_daily=8.0,
            work_days_weekly=5,
            monthly_minimum_hours=160.0,
            benefits=["健康保険", "厚生年金", "雇用保険"],
            terms_conditions="Standard dispatch contract terms",
            notes="Test contract with all fields",
        )

        assert contract.id is not None
        assert contract.employee_id == "W001"
        assert contract.contract_number == "KOB-2026-001"
        assert contract.client_company == "Tech Company A"
        assert contract.work_hours_daily == 8.0
        assert contract.work_days_weekly == 5
        assert contract.monthly_minimum_hours == 160.0
        assert len(contract.benefits) == 3
        assert contract.terms_conditions is not None
        assert contract.notes is not None

    def test_generate_contract_defaults(self, test_employee):
        """Test that generate_contract applies defaults correctly."""
        gen = KobetsuContractGenerator()

        contract = gen.generate_contract(
            employee=test_employee,
            contract_number="KOB-2026-001",
            job_title="システムエンジニア",
            work_location="東京都渋谷区",
            hourly_rate_jpy=2500.0,
            effective_date=date(2026, 4, 1),
        )

        assert contract.dispatch_company == "UNS"
        assert contract.work_hours_daily == 8.0
        assert contract.work_days_weekly == 5
        assert contract.benefits == []
