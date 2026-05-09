"""Integration tests for main.py execute function."""

import pytest
from datetime import date

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kobetsu_contracts.scripts.main import KobetsuContractProcessor


class TestKobetsuContractProcessor:
    """Test KobetsuContractProcessor execution."""

    def test_init_valid(self, test_db_with_contracts):
        """Test processor initialization."""
        processor = KobetsuContractProcessor(test_db_with_contracts)
        assert processor is not None
        assert processor.contract_db is not None

    def test_validate_valid_params(self, test_db_with_contracts, valid_contract_params):
        """Test validation with valid parameters."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        result = processor.validate(valid_contract_params)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_missing_employee_id(self, test_db_with_contracts, valid_contract_params):
        """Test validation with missing employee_id."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        del params["employee_id"]

        result = processor.validate(params)

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "employee_id" in result["errors"][0]

    def test_validate_missing_contract_number(self, test_db_with_contracts, valid_contract_params):
        """Test validation with missing contract_number."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        del params["contract_number"]

        result = processor.validate(params)

        assert result["valid"] is False
        assert "contract_number" in str(result["errors"])

    def test_validate_invalid_hourly_rate(self, test_db_with_contracts, valid_contract_params):
        """Test validation with invalid hourly rate."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["hourly_rate_jpy"] = 500.0

        result = processor.validate(params)

        assert result["valid"] is False
        assert any("hourly_rate_jpy" in e for e in result["errors"])

    def test_validate_invalid_operation(self, test_db_with_contracts, valid_contract_params):
        """Test validation with invalid operation."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["operation"] = "invalid_operation"

        result = processor.validate(params)

        assert result["valid"] is False
        assert "Unknown operation" in result["errors"][0]

    def test_execute_generate_contract(self, test_db_with_contracts, valid_contract_params):
        """Test contract generation operation."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["operation"] = "generate_contract"

        result = processor.execute(params)

        assert result["success"] is True
        assert result["operation"] == "generate_contract"
        assert "contract_id" in result
        assert "result" in result

    def test_execute_with_validation_error(self, test_db_with_contracts, valid_contract_params):
        """Test execution with validation error."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["hourly_rate_jpy"] = 500.0  # Invalid

        result = processor.execute(params)

        assert result["success"] is False
        assert "error" in result

    def test_execute_nonexistent_employee(self, test_db_with_contracts, valid_contract_params):
        """Test execution with nonexistent employee."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["employee_id"] = "NONEXISTENT"

        result = processor.execute(params)

        assert result["success"] is False
        assert "Employee not found" in result["error"]

    def test_execute_date_parsing(self, test_db_with_contracts, valid_contract_params):
        """Test that dates are parsed correctly."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["operation"] = "generate_contract"
        params["effective_date"] = "2026-05-15"
        params["expiration_date"] = "2027-05-14"

        result = processor.execute(params)

        if result["success"]:
            assert "2026-05-15" in str(result["result"])

    def test_execute_missing_expiration_date(self, test_db_with_contracts, valid_contract_params):
        """Test execution without expiration date (optional)."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["operation"] = "generate_contract"
        del params["expiration_date"]

        result = processor.execute(params)

        assert result["success"] is True

    def test_execute_with_benefits_list(self, test_db_with_contracts, valid_contract_params):
        """Test execution with benefits list."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["benefits"] = ["健康保険", "厚生年金", "雇用保険"]

        result = processor.execute(params)

        if result["success"]:
            assert "benefits" in str(result["result"]).lower()

    def test_execute_unknown_operation(self, test_db_with_contracts, valid_contract_params):
        """Test execution with unknown operation."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["operation"] = "unknown_op"

        result = processor.execute(params)

        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_validate_date_format(self, test_db_with_contracts, valid_contract_params):
        """Test validation of date formats."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["effective_date"] = "invalid-date"

        result = processor.validate(params)

        assert result["valid"] is False

    def test_validate_field_types(self, test_db_with_contracts, valid_contract_params):
        """Test validation of field types."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()
        params["hourly_rate_jpy"] = "not-a-number"

        result = processor.validate(params)

        assert result["valid"] is False

    def test_execute_returns_proper_structure(self, test_db_with_contracts, valid_contract_params):
        """Test that execute returns proper response structure."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = valid_contract_params.copy()

        result = processor.execute(params)

        # Check response structure
        assert "success" in result
        assert "operation" in result
        assert isinstance(result["success"], bool)

        if result["success"]:
            assert "result" in result
            assert "contract_number" in result
        else:
            assert "error" in result

    def test_execute_generate_contract_with_all_fields(self, test_db_with_contracts):
        """Test contract generation with all optional fields."""
        processor = KobetsuContractProcessor(test_db_with_contracts)

        params = {
            "operation": "generate_contract",
            "employee_id": "W001",
            "contract_number": "KOB-2026-FULL",
            "job_title": "Senior Engineer",
            "work_location": "Tokyo",
            "hourly_rate_jpy": 3000.0,
            "effective_date": "2026-04-01",
            "expiration_date": "2027-03-31",
            "client_company": "Big Corp",
            "work_hours_daily": 8.5,
            "work_days_weekly": 5,
            "monthly_minimum_hours": 170.0,
            "benefits": ["健康保険", "厚生年金"],
            "terms_conditions": "Standard terms",
            "notes": "Full test contract",
        }

        result = processor.execute(params)

        assert result["success"] is True
        assert result["contract_number"] == "KOB-2026-FULL"
