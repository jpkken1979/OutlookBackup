"""Kobetsu Contracts Generator WEEK 2 — Main entry point.

Orchestrates contract generation, validation, and output generation (PDF + DOCX).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, date

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import Employee, KobetsuContract
from payroll_processor.scripts.database import PayrollDatabase
from kobetsu_contracts.scripts.contract_generator import KobetsuContractGenerator
from kobetsu_contracts.scripts.template_renderer import ContractRenderer
from kobetsu_contracts.scripts.pdf_builder import PDFBuilder
from kobetsu_contracts.scripts.docx_builder import DOCXBuilder
from kobetsu_contracts.scripts.database import ContractDatabase

# Configure logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / f"contracts_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class KobetsuContractProcessor:
    """Main orchestrator for Kobetsu contract processing."""

    def __init__(
        self,
        db_path: Path,
        template_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize processor with database and output paths.

        Args:
            db_path: Path to SQLite database.
            template_dir: Path to Jinja2 templates directory.
            output_dir: Path for contract output (PDF/DOCX).

        Raises:
            ValueError: If initialization fails.
        """
        try:
            # Initialize database layers
            self.employee_db = PayrollDatabase(db_path)
            self.employee_db.init_database()

            self.contract_db = ContractDatabase(db_path)
            self.contract_db.init_database()

            # Initialize generators
            self.generator = KobetsuContractGenerator()
            self.renderer = ContractRenderer(template_dir=template_dir)

            # Output paths
            self.output_dir = output_dir or Path.cwd() / "output"
            self.pdf_dir = self.output_dir / "pdfs"
            self.docx_dir = self.output_dir / "docx"

            logger.info("KobetsuContractProcessor initialized successfully")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate input parameters.

        Args:
            params: Dictionary with keys:
                - operation (str): 'generate_contract', 'generate_output'
                - employee_id (str)
                - contract_number (str)
                - job_title (str)
                - work_location (str)
                - hourly_rate_jpy (float)
                - effective_date (str, YYYY-MM-DD)
                - expiration_date (str, YYYY-MM-DD, optional)
                - output_formats (list, optional): ['pdf', 'docx']

        Returns:
            Dict with keys:
                - valid (bool): True if all validations pass
                - errors (List[str]): List of validation errors (empty if valid)
        """
        errors: list[str] = []

        # Check required fields
        required_fields = [
            "operation",
            "employee_id",
            "contract_number",
            "job_title",
            "work_location",
            "hourly_rate_jpy",
            "effective_date",
        ]

        for field in required_fields:
            if field not in params or not params[field]:
                errors.append(f"{field} is required")

        if errors:
            return {"valid": False, "errors": errors}

        # Validate employee exists
        employee_id = params.get("employee_id", "")
        try:
            self.employee_db.load_employee(employee_id)
        except ValueError:
            errors.append(f"Employee not found: {employee_id}")

        # Validate hourly rate
        try:
            hourly_rate = float(params.get("hourly_rate_jpy", 0))
            if hourly_rate < 800.0:
                errors.append(f"hourly_rate_jpy must be >= 800, got {hourly_rate}")
        except (ValueError, TypeError):
            errors.append("hourly_rate_jpy must be numeric")

        # Validate dates
        try:
            effective_date = datetime.fromisoformat(params.get("effective_date", "")).date()
        except (ValueError, TypeError):
            errors.append("effective_date must be YYYY-MM-DD format")

        if not errors and "expiration_date" in params and params["expiration_date"]:
            try:
                expiration_date = datetime.fromisoformat(params.get("expiration_date", "")).date()
                effective_date = datetime.fromisoformat(params.get("effective_date", "")).date()
                if expiration_date <= effective_date:
                    errors.append("expiration_date must be after effective_date")
            except (ValueError, TypeError):
                errors.append("expiration_date must be YYYY-MM-DD format if provided")

        # Validate operation
        operation = params.get("operation", "")
        if operation not in ["generate_contract", "generate_output", "save_contract"]:
            errors.append(f"Unknown operation: {operation}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute contract operation.

        Args:
            params: Operation parameters (see validate method).

        Returns:
            Dict with success status, contract data, and output paths.
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

            operation = params.get("operation", "")
            employee_id = params.get("employee_id", "")
            contract_number = params.get("contract_number", "")
            job_title = params.get("job_title", "")
            work_location = params.get("work_location", "")
            hourly_rate_jpy = float(params.get("hourly_rate_jpy", 0))
            effective_date = datetime.fromisoformat(params.get("effective_date")).date()

            expiration_date = None
            if "expiration_date" in params and params["expiration_date"]:
                expiration_date = datetime.fromisoformat(params.get("expiration_date")).date()

            # Load employee
            employee = self.employee_db.load_employee(employee_id)

            # Generate contract
            contract = self.generator.generate_contract(
                employee=employee,
                contract_number=contract_number,
                job_title=job_title,
                work_location=work_location,
                hourly_rate_jpy=hourly_rate_jpy,
                effective_date=effective_date,
                expiration_date=expiration_date,
                client_company=params.get("client_company"),
                work_hours_daily=float(params.get("work_hours_daily", 8.0)),
                work_days_weekly=int(params.get("work_days_weekly", 5)),
                monthly_minimum_hours=params.get("monthly_minimum_hours"),
                benefits=params.get("benefits"),
                terms_conditions=params.get("terms_conditions"),
                notes=params.get("notes"),
            )

            logger.info(f"Generated contract {contract_number} for {employee_id}")

            # Handle different operations
            if operation == "generate_contract":
                # Return contract data in JSON format
                return {
                    "success": True,
                    "operation": operation,
                    "contract_id": contract.id,
                    "contract_number": contract.contract_number,
                    "result": json.loads(contract.json()),
                }

            elif operation == "generate_output":
                # Generate PDF and/or DOCX
                output_formats = params.get("output_formats", ["pdf", "docx"])
                result_paths = {}

                try:
                    # Render HTML for PDF
                    html = self.renderer.render_html(employee, contract)

                    if "pdf" in output_formats:
                        try:
                            pdf_builder = PDFBuilder()
                            pdf_path = pdf_builder.build_from_template(
                                html_content=html,
                                contract_number=contract.contract_number,
                                output_dir=self.pdf_dir,
                            )
                            result_paths["pdf"] = str(pdf_path)
                            logger.info(f"Generated PDF: {pdf_path}")
                        except ImportError:
                            logger.warning("weasyprint not installed, skipping PDF")

                    if "docx" in output_formats:
                        try:
                            docx_builder = DOCXBuilder()
                            docx_path = docx_builder.build_from_contract(
                                employee=employee,
                                contract=contract,
                                output_dir=self.docx_dir,
                            )
                            result_paths["docx"] = str(docx_path)
                            logger.info(f"Generated DOCX: {docx_path}")
                        except ImportError:
                            logger.warning("python-docx not installed, skipping DOCX")

                    return {
                        "success": True,
                        "operation": operation,
                        "contract_id": contract.id,
                        "contract_number": contract.contract_number,
                        "result": result_paths,
                    }

                except Exception as e:
                    logger.error(f"Output generation failed: {e}")
                    return {
                        "success": False,
                        "operation": operation,
                        "error": str(e),
                    }

            elif operation == "save_contract":
                # Save to database
                try:
                    contract_id = self.contract_db.save_contract(contract)
                    self.contract_db.add_audit_entry(
                        contract_id=contract.id,
                        version=1,
                        change_type="create",
                        changed_by="system",
                    )
                    logger.info(f"Saved contract to database: {contract_id}")

                    return {
                        "success": True,
                        "operation": operation,
                        "contract_id": contract.id,
                        "contract_number": contract.contract_number,
                        "result": {"status": "saved", "db_id": contract_id},
                    }

                except Exception as e:
                    logger.error(f"Database save failed: {e}")
                    return {
                        "success": False,
                        "operation": operation,
                        "error": str(e),
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
    """Skill entry point — execute contract operation.

    Args:
        params: Operation parameters (see KobetsuContractProcessor.execute).

    Returns:
        Dict with result or error.
    """
    db_path = Path(__file__).parent.parent / "contracts.db"
    processor = KobetsuContractProcessor(db_path=db_path)
    return processor.execute(params)


def validate(params: dict[str, Any]) -> dict[str, Any]:
    """Skill entry point — validate parameters.

    Args:
        params: Parameters to validate.

    Returns:
        Dict with validation result.
    """
    db_path = Path(__file__).parent.parent / "contracts.db"
    processor = KobetsuContractProcessor(db_path=db_path)
    return processor.validate(params)


if __name__ == "__main__":
    # Example usage
    db_path = Path(__file__).parent.parent / "contracts.db"
    processor = KobetsuContractProcessor(db_path=db_path)

    # Test parameters
    test_params = {
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
        "benefits": ["健康保険", "厚生年金", "雇用保険"],
        "notes": "試験的派遣契約",
    }

    result = processor.execute(test_params)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
