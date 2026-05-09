"""Tests for main entry point execution."""

import pytest
import tempfile
from pathlib import Path
from datetime import date

from scripts.main import ReportParams, HRReportProcessor


class TestReportParams:
    """Tests for ReportParams validation."""

    def test_valid_params(self) -> None:
        """Test valid parameters."""
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="roster",
        )
        assert params.report_type == "roster"

    def test_invalid_report_type(self) -> None:
        """Test invalid report type."""
        with pytest.raises(ValueError):
            ReportParams(
                start_date=date(2024, 3, 1),
                end_date=date(2024, 3, 31),
                report_type="invalid",
            )

    def test_invalid_file_format(self) -> None:
        """Test invalid file format."""
        with pytest.raises(ValueError):
            ReportParams(
                start_date=date(2024, 3, 1),
                end_date=date(2024, 3, 31),
                report_type="roster",
                file_format="pdf",
            )

    def test_invalid_date_range(self) -> None:
        """Test end_date < start_date."""
        with pytest.raises(ValueError):
            ReportParams(
                start_date=date(2024, 3, 31),
                end_date=date(2024, 3, 1),
                report_type="roster",
            )

    def test_params_from_dict(self) -> None:
        """Test creating params from dict."""
        params = ReportParams(
            **{
                "start_date": "2024-03-01",
                "end_date": "2024-03-31",
                "report_type": "hours",
            }
        )
        assert params.report_type == "hours"


class TestHRReportProcessor:
    """Tests for HR report processor."""

    def test_initialization(self, temp_db: str) -> None:
        """Test processor initialization."""
        processor = HRReportProcessor(temp_db)
        assert processor.db is not None

    def test_validate_params(self, temp_db: str) -> None:
        """Test parameter validation."""
        processor = HRReportProcessor(temp_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="roster",
        )
        assert processor.validate(params) is True

    def test_validate_invalid_output_path(self, temp_db: str) -> None:
        """Test validation with invalid output path."""
        processor = HRReportProcessor(temp_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="roster",
            output_path="/nonexistent/path/report.xlsx",
        )
        with pytest.raises(ValueError):
            processor.validate(params)

    def test_generate_roster(self, populated_db: str) -> None:
        """Test generating roster report."""
        processor = HRReportProcessor(populated_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="roster",
        )
        result = processor.generate_roster(params)

        assert result["success"] is True
        assert result["report_type"] == "roster"
        assert "data" in result
        assert "summary" in result
        assert result["records_count"] >= 0

    def test_generate_hours(self, populated_db: str) -> None:
        """Test generating hours report."""
        processor = HRReportProcessor(populated_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="hours",
        )
        result = processor.generate_hours(params)

        assert result["success"] is True
        assert result["report_type"] == "hours"
        assert "summary" in result
        assert "total_hours" in result["summary"]

    def test_generate_dispatch(self, populated_db: str) -> None:
        """Test generating dispatch report."""
        processor = HRReportProcessor(populated_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="dispatch",
        )
        result = processor.generate_dispatch(params)

        assert result["success"] is True
        assert result["report_type"] == "dispatch"
        assert "summary" in result

    def test_generate_absence(self, populated_db: str) -> None:
        """Test generating absence report."""
        processor = HRReportProcessor(populated_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="absence",
        )
        result = processor.generate_absence(params)

        assert result["success"] is True
        assert result["report_type"] == "absence"

    def test_execute_roster(self, populated_db: str) -> None:
        """Test execute with roster report."""
        processor = HRReportProcessor(populated_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="roster",
        )
        result = processor.execute(params)

        assert result["success"] is True
        assert result["report_type"] == "roster"

    def test_execute_with_dict(self, populated_db: str) -> None:
        """Test execute with dict params."""
        processor = HRReportProcessor(populated_db)
        params_dict = {
            "start_date": "2024-03-01",
            "end_date": "2024-03-31",
            "report_type": "hours",
        }
        result = processor.execute(params_dict)

        assert result["success"] is True

    def test_export_excel(self, populated_db: str) -> None:
        """Test exporting to Excel."""
        processor = HRReportProcessor(populated_db)
        params = ReportParams(
            start_date=date(2024, 3, 1),
            end_date=date(2024, 3, 31),
            report_type="roster",
        )
        report = processor.generate_roster(params)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "roster_report.xlsx"
            result_path = processor.export_excel(report, str(output_path))

            assert Path(result_path).exists()
            assert output_path.stat().st_size > 0
