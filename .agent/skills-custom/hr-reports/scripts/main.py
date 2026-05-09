"""HR Reports Generator Main Entry Point - WEEK 2."""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from pydantic import BaseModel, Field, validator

from .database import HRDatabase
from .report_generators import ReportConfig, create_generator
from .excel_builder import ExcelReportBuilder

logger = logging.getLogger(__name__)


class ReportParams(BaseModel):
    """Parameters for report generation."""

    start_date: date = Field(..., description="Report period start date")
    end_date: date = Field(..., description="Report period end date")
    report_type: str = Field(
        ...,
        description="Type: roster, hours, dispatch, or absence",
    )
    employee_id: str | None = Field(None, description="Optional employee filter")
    output_path: str | None = Field(None, description="Output file path")
    file_format: str = Field(default="xlsx", description="Format: xlsx, html, csv")
    include_summary: bool = Field(default=True, description="Include summary section")
    generated_by: str = Field(default="system", description="Report generator user")

    @validator("report_type")
    def validate_report_type(cls, v: str) -> str:
        """Validate report type."""
        valid = ["roster", "hours", "dispatch", "absence"]
        if v not in valid:
            raise ValueError(f"Report type must be one of {valid}")
        return v

    @validator("file_format")
    def validate_file_format(cls, v: str) -> str:
        """Validate file format."""
        valid = ["xlsx", "html", "csv"]
        if v not in valid:
            raise ValueError(f"File format must be one of {valid}")
        return v

    @validator("end_date")
    def validate_dates(cls, v: date, values: dict) -> date:
        """Validate date range."""
        if "start_date" in values:
            if v < values["start_date"]:
                raise ValueError("end_date must be >= start_date")
        return v


class HRReportProcessor:
    """Main processor for HR report generation."""

    def __init__(self, db_path: str) -> None:
        """Initialize processor.

        Args:
            db_path: Path to SQLite database.
        """
        self.db = HRDatabase(db_path)
        logger.info(f"HRReportProcessor initialized with {db_path}")

    def validate(self, params: ReportParams) -> bool:
        """Validate report parameters.

        Args:
            params: Report parameters.

        Returns:
            True if valid.

        Raises:
            ValueError: If validation fails.
        """
        if params.start_date > params.end_date:
            raise ValueError("start_date must be <= end_date")

        if params.output_path:
            output_dir = Path(params.output_path).parent
            if not output_dir.exists():
                raise ValueError(f"Output directory does not exist: {output_dir}")

        logger.info(f"Validation passed for {params.report_type} report")
        return True

    def generate_roster(self, params: ReportParams) -> dict[str, Any]:
        """Generate roster/attendance report.

        Args:
            params: Report parameters.

        Returns:
            Report result dict with data and metadata.
        """
        logger.info(f"Generating roster report: {params.start_date} to {params.end_date}")

        # Fetch data
        attendance_data = self.db.get_attendance_records(
            params.start_date,
            params.end_date,
            params.employee_id,
        )

        # Merge with employee info
        enriched_data = []
        for record in attendance_data:
            emp_data = self.db.load_employee(record["employee_id"])
            if emp_data:
                record.update(
                    {
                        "name": emp_data.get("name", ""),
                        "department": emp_data.get("department", ""),
                    }
                )
            enriched_data.append(record)

        # Generate report
        config = ReportConfig(
            start_date=params.start_date,
            end_date=params.end_date,
            include_summary=params.include_summary,
        )
        generator = create_generator("roster", config)
        generator.set_data(enriched_data)
        df = generator.get_dataframe()
        summary = generator.get_summary()

        result = {
            "success": True,
            "report_type": "roster",
            "data": df,
            "summary": summary,
            "records_count": len(enriched_data),
        }

        # Save metadata if output path provided
        if params.output_path:
            report_id = self.db.save_report_metadata(
                report_type="roster",
                report_name=f"Roster {params.start_date} to {params.end_date}",
                start_date=params.start_date,
                end_date=params.end_date,
                generated_by=params.generated_by,
                file_path=params.output_path,
                file_format=params.file_format,
                total_records=len(enriched_data),
            )
            result["report_id"] = report_id

        logger.info(f"Roster report generated: {len(df)} rows")
        return result

    def generate_hours(self, params: ReportParams) -> dict[str, Any]:
        """Generate hours/payroll detail report.

        Args:
            params: Report parameters.

        Returns:
            Report result dict with data and metadata.
        """
        logger.info(f"Generating hours report: {params.start_date} to {params.end_date}")

        # Fetch attendance data
        attendance_data = self.db.get_attendance_records(
            params.start_date,
            params.end_date,
            params.employee_id,
        )

        # Enrich with payroll rates
        enriched_data = []
        for record in attendance_data:
            emp_data = self.db.load_employee(record["employee_id"])
            if emp_data:
                record["hourly_rate"] = emp_data.get("hourly_rate", 1500.0)
            else:
                record["hourly_rate"] = 1500.0
            enriched_data.append(record)

        # Generate report
        config = ReportConfig(
            start_date=params.start_date,
            end_date=params.end_date,
            include_summary=params.include_summary,
        )
        generator = create_generator("hours", config)
        generator.set_data(enriched_data)
        df = generator.get_dataframe()
        summary = generator.get_summary()

        result = {
            "success": True,
            "report_type": "hours",
            "data": df,
            "summary": summary,
            "records_count": len(enriched_data),
        }

        # Save metadata if output path provided
        if params.output_path:
            report_id = self.db.save_report_metadata(
                report_type="hours",
                report_name=f"Hours {params.start_date} to {params.end_date}",
                start_date=params.start_date,
                end_date=params.end_date,
                generated_by=params.generated_by,
                file_path=params.output_path,
                file_format=params.file_format,
                total_records=len(enriched_data),
            )
            result["report_id"] = report_id

        logger.info(f"Hours report generated: {len(df)} rows")
        return result

    def generate_dispatch(self, params: ReportParams) -> dict[str, Any]:
        """Generate dispatch assignment report.

        Args:
            params: Report parameters.

        Returns:
            Report result dict with data and metadata.
        """
        logger.info(f"Generating dispatch report: {params.start_date} to {params.end_date}")

        # Fetch dispatch data
        dispatch_data = self.db.get_dispatch_assignments(
            params.start_date,
            params.end_date,
            params.employee_id,
        )

        # Generate report
        config = ReportConfig(
            start_date=params.start_date,
            end_date=params.end_date,
            include_summary=params.include_summary,
        )
        generator = create_generator("dispatch", config)
        generator.set_data(dispatch_data)
        df = generator.get_dataframe()
        summary = generator.get_summary()

        result = {
            "success": True,
            "report_type": "dispatch",
            "data": df,
            "summary": summary,
            "records_count": len(dispatch_data),
        }

        # Save metadata if output path provided
        if params.output_path:
            report_id = self.db.save_report_metadata(
                report_type="dispatch",
                report_name=f"Dispatch {params.start_date} to {params.end_date}",
                start_date=params.start_date,
                end_date=params.end_date,
                generated_by=params.generated_by,
                file_path=params.output_path,
                file_format=params.file_format,
                total_records=len(dispatch_data),
            )
            result["report_id"] = report_id

        logger.info(f"Dispatch report generated: {len(df)} rows")
        return result

    def generate_absence(self, params: ReportParams) -> dict[str, Any]:
        """Generate absence/leave report.

        Args:
            params: Report parameters.

        Returns:
            Report result dict with data and metadata.
        """
        logger.info(f"Generating absence report: {params.start_date} to {params.end_date}")

        # Fetch absence data
        absence_data = self.db.get_absence_records(
            params.start_date,
            params.end_date,
            params.employee_id,
        )

        # Enrich with employee info
        enriched_data = []
        for record in absence_data:
            emp_data = self.db.load_employee(record["employee_id"])
            if emp_data:
                record.update(
                    {
                        "name": emp_data.get("name", ""),
                        "department": emp_data.get("department", ""),
                    }
                )
            enriched_data.append(record)

        # Generate report
        config = ReportConfig(
            start_date=params.start_date,
            end_date=params.end_date,
            include_summary=params.include_summary,
        )
        generator = create_generator("absence", config)
        generator.set_data(enriched_data)
        df = generator.get_dataframe()
        summary = generator.get_summary()

        result = {
            "success": True,
            "report_type": "absence",
            "data": df,
            "summary": summary,
            "records_count": len(enriched_data),
        }

        # Save metadata if output path provided
        if params.output_path:
            report_id = self.db.save_report_metadata(
                report_type="absence",
                report_name=f"Absence {params.start_date} to {params.end_date}",
                start_date=params.start_date,
                end_date=params.end_date,
                generated_by=params.generated_by,
                file_path=params.output_path,
                file_format=params.file_format,
                total_records=len(enriched_data),
            )
            result["report_id"] = report_id

        logger.info(f"Absence report generated: {len(df)} rows")
        return result

    def execute(self, params: ReportParams) -> dict[str, Any]:
        """Execute report generation based on parameters.

        Args:
            params: Report parameters (dict or ReportParams).

        Returns:
            Report result dict.

        Raises:
            ValueError: If parameters are invalid.
        """
        # Convert dict to ReportParams if needed
        if isinstance(params, dict):
            params = ReportParams(**params)

        # Validate
        self.validate(params)

        # Route to appropriate generator
        if params.report_type == "roster":
            return self.generate_roster(params)
        elif params.report_type == "hours":
            return self.generate_hours(params)
        elif params.report_type == "dispatch":
            return self.generate_dispatch(params)
        elif params.report_type == "absence":
            return self.generate_absence(params)
        else:
            raise ValueError(f"Unknown report type: {params.report_type}")

    def export_excel(
        self,
        report_data: dict[str, Any],
        output_path: str,
    ) -> str:
        """Export report to Excel workbook.

        Args:
            report_data: Report data from execute().
            output_path: Path where to save workbook.

        Returns:
            Path to saved file.
        """
        builder = ExcelReportBuilder(f"HR {report_data['report_type'].title()} Report")

        # Add main sheet with data
        builder.add_sheet(
            "Data",
            report_data["data"],
            include_summary=True,
            summary_data=report_data["summary"],
        )

        # Save
        builder.save(output_path)
        logger.info(f"Report exported to Excel: {output_path}")
        return output_path
