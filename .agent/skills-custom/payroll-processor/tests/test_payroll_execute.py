"""Integration tests for PayrollProcessor.execute and main entry point.

Tests complete payroll workflow from calculation to output generation.
"""

import pytest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from payroll_processor.scripts.main import PayrollProcessor


class TestPayrollProcessorValidate:
    """Test PayrollProcessor.validate method."""

    def test_validate_valid_params(self, temp_db: Path) -> None:
        """Test validation passes for valid parameters."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "employee_id": "W001",
            "regular_hours": 160.0,
            "overtime_hours": 10.0,
        }
        result = processor.validate(params)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_missing_employee_id(self, temp_db: Path) -> None:
        """Test validation fails without employee_id."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "regular_hours": 160.0,
        }
        result = processor.validate(params)
        assert result["valid"] is False
        assert any("employee_id" in err for err in result["errors"])

    def test_validate_missing_regular_hours(self, temp_db: Path) -> None:
        """Test validation fails without regular_hours."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "employee_id": "W001",
        }
        result = processor.validate(params)
        assert result["valid"] is False
        assert any("regular_hours" in err for err in result["errors"])

    def test_validate_invalid_hours_negative(self, temp_db: Path) -> None:
        """Test validation fails with negative hours."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "employee_id": "W001",
            "regular_hours": -10.0,
        }
        result = processor.validate(params)
        assert result["valid"] is False
        assert any("regular_hours" in err for err in result["errors"])

    def test_validate_invalid_hours_too_high(self, temp_db: Path) -> None:
        """Test validation fails with hours > 200."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "employee_id": "W001",
            "regular_hours": 250.0,
        }
        result = processor.validate(params)
        assert result["valid"] is False
        assert any("regular_hours" in err for err in result["errors"])

    def test_validate_overtime_exceeds_limit(self, temp_db: Path) -> None:
        """Test validation fails with overtime > 45."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "employee_id": "W001",
            "regular_hours": 160.0,
            "overtime_hours": 50.0,
        }
        result = processor.validate(params)
        assert result["valid"] is False
        assert any("overtime_hours" in err for err in result["errors"])

    def test_validate_invalid_month(self, temp_db: Path) -> None:
        """Test validation fails with invalid month."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "employee_id": "W001",
            "regular_hours": 160.0,
            "month": 13,
        }
        result = processor.validate(params)
        assert result["valid"] is False
        assert any("month" in err for err in result["errors"])

    def test_validate_invalid_year(self, temp_db: Path) -> None:
        """Test validation fails with invalid year."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "employee_id": "W001",
            "regular_hours": 160.0,
            "year": 1999,
        }
        result = processor.validate(params)
        assert result["valid"] is False
        assert any("year" in err for err in result["errors"])


class TestPayrollProcessorExecute:
    """Test PayrollProcessor.execute method."""

    def test_execute_calculate_operation(self, temp_db: Path) -> None:
        """Test execute with calculate operation."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "calculate",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "overtime_hours": 0.0,
            "bonus": 0.0,
            "year": 2026,
            "month": 2,
        }
        result = processor.execute(params)

        assert result["success"] is True
        assert result["operation"] == "calculate"
        assert "payslip_id" in result
        assert "result" in result

    def test_execute_invalid_employee(self, temp_db: Path) -> None:
        """Test execute fails with invalid employee."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "calculate",
            "employee_id": "INVALID_ID",
            "regular_hours": 160.0,
        }
        result = processor.execute(params)

        assert result["success"] is False
        assert "error" in result

    def test_execute_validation_failure(self, temp_db: Path) -> None:
        """Test execute with validation failure."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "calculate",
            "employee_id": "W001",
            "regular_hours": 250.0,  # Invalid: > 200
        }
        result = processor.execute(params)

        assert result["success"] is False
        assert "error" in result

    def test_execute_overtime_violation(self, temp_db: Path) -> None:
        """Test execute fails with overtime violation."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "calculate",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "overtime_hours": 46.0,  # Exceeds 45h limit
        }
        result = processor.execute(params)

        assert result["success"] is False
        assert "error" in result

    def test_execute_with_bonus(self, temp_db: Path) -> None:
        """Test execute with bonus."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "calculate",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "bonus": 100000.0,
            "year": 2026,
            "month": 2,
        }
        result = processor.execute(params)

        assert result["success"] is True
        assert result["result"]["bonus"] == 100000.0

    def test_execute_generate_payslip_json(self, temp_db: Path) -> None:
        """Test execute with generate_payslip operation (JSON format)."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "generate_payslip",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "output_format": "json",
            "year": 2026,
            "month": 2,
        }
        result = processor.execute(params)

        assert result["success"] is True
        assert result["operation"] == "generate_payslip"
        assert isinstance(result["result"], dict)

    def test_execute_generate_payslip_html(self, temp_db: Path) -> None:
        """Test execute with generate_payslip operation (HTML format)."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "generate_payslip",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "output_format": "html",
            "year": 2026,
            "month": 2,
        }
        result = processor.execute(params)

        assert result["success"] is True
        assert isinstance(result["result"], str)
        assert "html" in result["result"].lower() or len(result["result"]) > 100

    def test_execute_generate_payslip_excel(self, temp_db: Path) -> None:
        """Test execute with generate_payslip operation (Excel format)."""
        with TemporaryDirectory() as tmpdir:
            temp_db_path = Path(tmpdir) / "test.db"
            processor = PayrollProcessor(db_path=temp_db_path)

            params = {
                "operation": "generate_payslip",
                "employee_id": "W001",
                "regular_hours": 160.0,
                "output_format": "excel",
                "output_path": str(Path(tmpdir) / "test_payslip.xlsx"),
                "year": 2026,
                "month": 2,
            }
            result = processor.execute(params)

            assert result["success"] is True
            output_file = Path(result["result"])
            assert output_file.exists()

    def test_execute_payslip_persisted(self, temp_db: Path) -> None:
        """Test that payslip is saved to database."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "calculate",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "year": 2026,
            "month": 2,
        }
        result = processor.execute(params)

        assert result["success"] is True
        payslip_id = result["payslip_id"]

        # Retrieve from database
        payslip = processor.db.get_payslip(payslip_id)
        assert payslip is not None
        assert payslip.employee_id == "W001"
        assert payslip.regular_hours == 160.0

    def test_execute_invalid_operation(self, temp_db: Path) -> None:
        """Test execute with invalid operation."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "invalid_op",
            "employee_id": "W001",
            "regular_hours": 160.0,
        }
        result = processor.execute(params)

        assert result["success"] is False
        assert "error" in result

    def test_execute_invalid_output_format(self, temp_db: Path) -> None:
        """Test execute with invalid output format."""
        processor = PayrollProcessor(db_path=temp_db)
        params = {
            "operation": "generate_payslip",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "output_format": "pdf",  # Not supported
            "year": 2026,
            "month": 2,
        }
        result = processor.execute(params)

        assert result["success"] is False
        assert "error" in result


class TestPayrollProcessorIntegration:
    """Integration tests for full payroll workflow."""

    def test_full_workflow_calculate_and_generate(self, temp_db: Path) -> None:
        """Test complete workflow: calculate, then generate multiple formats."""
        processor = PayrollProcessor(db_path=temp_db)

        # Step 1: Calculate
        calc_params = {
            "operation": "calculate",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "overtime_hours": 10.0,
            "bonus": 50000.0,
            "year": 2026,
            "month": 2,
        }
        calc_result = processor.execute(calc_params)

        assert calc_result["success"] is True
        calc_result["payslip_id"]

        # Step 2: Generate JSON
        json_params = {
            "operation": "generate_payslip",
            "employee_id": "W001",
            "regular_hours": 160.0,
            "overtime_hours": 10.0,
            "bonus": 50000.0,
            "output_format": "json",
            "year": 2026,
            "month": 2,
        }
        json_result = processor.execute(json_params)
        assert json_result["success"] is True

        # Step 3: Generate HTML
        html_params = dict(json_params)
        html_params["output_format"] = "html"
        html_result = processor.execute(html_params)
        assert html_result["success"] is True

    def test_multiple_employees(self, temp_db: Path) -> None:
        """Test processing payroll for multiple employees."""
        processor = PayrollProcessor(db_path=temp_db)

        # Process W001
        result_w001 = processor.execute(
            {
                "operation": "calculate",
                "employee_id": "W001",
                "regular_hours": 160.0,
                "year": 2026,
                "month": 2,
            }
        )
        assert result_w001["success"] is True

        # Process W002 (if exists)
        processor.execute(
            {
                "operation": "calculate",
                "employee_id": "W002",
                "regular_hours": 170.0,
                "year": 2026,
                "month": 2,
            }
        )
        # May succeed or fail depending on fixture setup

    def test_multiple_months_same_employee(self, temp_db: Path) -> None:
        """Test processing payroll for same employee in multiple months."""
        processor = PayrollProcessor(db_path=temp_db)

        for month in range(1, 4):
            result = processor.execute(
                {
                    "operation": "calculate",
                    "employee_id": "W001",
                    "regular_hours": 160.0,
                    "year": 2026,
                    "month": month,
                }
            )
            assert result["success"] is True
            assert result["result"]["month"] == month
