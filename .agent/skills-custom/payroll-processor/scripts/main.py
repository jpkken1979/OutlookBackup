"""Payroll Processor WEEK 1 — Main entry point.

Orchestrates payroll calculation, validation, and output generation.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import Employee, Payslip
from payroll_processor.scripts.database import PayrollDatabase
from payroll_processor.scripts.payroll_calculator import PayrollCalculator
from payroll_processor.scripts.payroll_generators import PayslipGenerator

# Configure logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / f"payroll_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class PayrollProcessor:
    """Main orchestrator for payroll processing."""

    def __init__(self, db_path: Path, template_dir: Path | None = None) -> None:
        """Initialize processor with database and template paths.

        Args:
            db_path: Path to SQLite database.
            template_dir: Path to Jinja2 templates directory.

        Raises:
            ValueError: If database initialization fails.
        """
        try:
            self.db = PayrollDatabase(db_path)
            self.db.init_database()
            self.generator = PayslipGenerator(template_dir=template_dir)
            logger.info("PayrollProcessor initialized successfully")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate input parameters.

        Args:
            params: Dictionary with keys:
                - employee_id (str)
                - regular_hours (float)
                - overtime_hours (float, optional)
                - bonus (float, optional)
                - year (int, optional)
                - month (int, optional)

        Returns:
            Dict with keys:
                - valid (bool): True if all validations pass
                - errors (List[str]): List of validation errors (empty if valid)
        """
        errors: list[str] = []

        # Check required fields
        if "employee_id" not in params or not params["employee_id"]:
            errors.append("employee_id is required")

        if "regular_hours" not in params:
            errors.append("regular_hours is required")

        # Validate employee exists
        if errors:
            return {"valid": False, "errors": errors}

        employee_id = params.get("employee_id", "")
        try:
            self.db.load_employee(employee_id)
        except ValueError:
            errors.append(f"Employee not found: {employee_id}")

        # Validate hours
        regular_hours = params.get("regular_hours", 0.0)
        overtime_hours = params.get("overtime_hours", 0.0)

        if not isinstance(regular_hours, (int, float)):
            errors.append("regular_hours must be numeric")
        elif regular_hours < 0 or regular_hours > 200:
            errors.append("regular_hours must be between 0 and 200")

        if not isinstance(overtime_hours, (int, float)):
            errors.append("overtime_hours must be numeric")
        elif overtime_hours < 0 or overtime_hours > 45:
            errors.append("overtime_hours must be between 0 and 45 (36協定 limit)")

        # Validate bonus
        bonus = params.get("bonus", 0.0)
        if not isinstance(bonus, (int, float)):
            errors.append("bonus must be numeric")
        elif bonus < 0:
            errors.append("bonus cannot be negative")

        # Validate year/month
        year = params.get("year", datetime.now().year)
        month = params.get("month", datetime.now().month)

        if not isinstance(year, int) or year < 2000 or year > 2099:
            errors.append(f"year must be between 2000 and 2099: {year}")

        if not isinstance(month, int) or month < 1 or month > 12:
            errors.append(f"month must be between 1 and 12: {month}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def calculate(
        self,
        employee_id: str,
        regular_hours: float,
        overtime_hours: float = 0.0,
        bonus: float = 0.0,
        year: int = 2026,
        month: int = 1,
    ) -> Payslip:
        """Calculate payroll for an employee.

        Args:
            employee_id: Employee ID.
            regular_hours: Regular work hours.
            overtime_hours: Overtime hours.
            bonus: Bonus amount (¥).
            year: Fiscal year.
            month: Fiscal month.

        Returns:
            Payslip: Calculated payslip.

        Raises:
            ValueError: If calculation fails.
        """
        try:
            employee = self.db.load_employee(employee_id)
            calculator = PayrollCalculator(employee)
            payslip = calculator.process_payroll(
                regular_hours=regular_hours,
                overtime_hours=overtime_hours,
                bonus=bonus,
                year=year,
                month=month,
            )
            logger.info(f"Calculated payslip: {payslip.id}")
            return payslip
        except Exception as e:
            logger.error(f"Calculation failed for {employee_id}: {e}")
            raise

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute payroll operation.

        Args:
            params: Dictionary with keys:
                - operation (str): 'calculate', 'generate_payslip', or 'export_report'
                - employee_id (str)
                - regular_hours (float)
                - overtime_hours (float, optional)
                - bonus (float, optional)
                - year (int, optional)
                - month (int, optional)
                - output_format (str, optional): 'json', 'html', 'excel' (default: 'json')
                - output_path (str, optional): Path for file output

        Returns:
            Dict with keys:
                - success (bool): Operation status
                - operation (str): Operation performed
                - payslip_id (str): Generated payslip ID
                - result (dict or str): Output data or file path
                - error (str, optional): Error message if failed
        """
        try:
            # Validate input
            validation = self.validate(params)
            if not validation["valid"]:
                return {
                    "success": False,
                    "operation": params.get("operation", "unknown"),
                    "error": "; ".join(validation["errors"]),
                }

            operation = params.get("operation", "calculate")
            employee_id = params.get("employee_id", "")
            regular_hours = float(params.get("regular_hours", 0.0))
            overtime_hours = float(params.get("overtime_hours", 0.0))
            bonus = float(params.get("bonus", 0.0))
            year = int(params.get("year", 2026))
            month = int(params.get("month", 1))

            # Calculate payroll
            payslip = self.calculate(
                employee_id=employee_id,
                regular_hours=regular_hours,
                overtime_hours=overtime_hours,
                bonus=bonus,
                year=year,
                month=month,
            )

            # Save to database
            payslip_id = self.db.save_payslip(payslip)
            logger.info(f"Saved payslip to database: {payslip_id}")

            # Generate output based on operation
            if operation == "calculate":
                # Return JSON by default
                result = self.generator.to_json(payslip)
                return {
                    "success": True,
                    "operation": operation,
                    "payslip_id": payslip_id,
                    "result": result,
                }

            elif operation == "generate_payslip":
                # Generate requested output format
                output_format = params.get("output_format", "json").lower()

                if output_format == "json":
                    result = self.generator.to_json(payslip)
                    return {
                        "success": True,
                        "operation": operation,
                        "payslip_id": payslip_id,
                        "result": result,
                    }

                elif output_format == "html":
                    employee = self.db.load_employee(employee_id)
                    html = self.generator.to_html(payslip, employee=employee)
                    output_path = params.get("output_path")
                    if output_path:
                        Path(output_path).write_text(html, encoding="utf-8")
                        logger.info(f"Saved HTML to {output_path}")
                        return {
                            "success": True,
                            "operation": operation,
                            "payslip_id": payslip_id,
                            "result": str(output_path),
                        }
                    else:
                        return {
                            "success": True,
                            "operation": operation,
                            "payslip_id": payslip_id,
                            "result": html,
                        }

                elif output_format == "excel":
                    output_path = params.get("output_path")
                    if output_path is None:
                        output_path = f"payslip_{payslip_id}.xlsx"
                    excel_path = self.generator.to_excel(payslip, output_path=Path(output_path))
                    logger.info(f"Saved Excel to {excel_path}")
                    return {
                        "success": True,
                        "operation": operation,
                        "payslip_id": payslip_id,
                        "result": str(excel_path),
                    }

                else:
                    return {
                        "success": False,
                        "operation": operation,
                        "error": f"Unknown output format: {output_format}",
                    }

            elif operation == "export_report":
                # Export to requested format
                output_format = params.get("output_format", "json").lower()
                if output_format == "json":
                    result = self.generator.to_json(payslip)
                else:
                    result = f"Report export for {payslip_id} in {output_format} format"

                return {
                    "success": True,
                    "operation": operation,
                    "payslip_id": payslip_id,
                    "result": result,
                }

            else:
                return {
                    "success": False,
                    "operation": operation,
                    "error": f"Unknown operation: {operation}",
                }

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "operation": params.get("operation", "unknown"),
                "error": str(e),
            }


def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Skill entry point — execute payroll operation.

    Args:
        params: Operation parameters (see PayrollProcessor.execute)

    Returns:
        Dict with result or error.
    """
    # Initialize processor with default paths
    db_path = Path(__file__).parent.parent / "payroll.db"
    processor = PayrollProcessor(db_path=db_path)
    return processor.execute(params)


def validate(params: dict[str, Any]) -> dict[str, Any]:
    """Skill entry point — validate parameters.

    Args:
        params: Parameters to validate.

    Returns:
        Dict with validation result.
    """
    db_path = Path(__file__).parent.parent / "payroll.db"
    processor = PayrollProcessor(db_path=db_path)
    return processor.validate(params)


if __name__ == "__main__":
    # Example usage
    db_path = Path(__file__).parent.parent / "payroll.db"
    processor = PayrollProcessor(db_path=db_path)

    # Test calculation
    test_params = {
        "operation": "calculate",
        "employee_id": "W001",
        "regular_hours": 160.0,
        "overtime_hours": 10.0,
        "bonus": 50000.0,
        "year": 2026,
        "month": 2,
    }

    result = processor.execute(test_params)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
