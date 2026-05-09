"""Tests for Excel builder."""

import pytest
import tempfile
from pathlib import Path
import pandas as pd

from scripts.excel_builder import ExcelReportBuilder, create_multi_report_workbook


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "employee_id": ["EMP001", "EMP002", "EMP003"],
            "name": ["山田太郎", "佐藤花子", "鈴木次郎"],
            "department": ["派遣営業部", "事務部", "派遣営業部"],
            "hours": [8.5, 8.0, 7.5],
            "earnings": [12750.0, 12000.0, 10500.0],
        }
    )


@pytest.fixture
def summary_data() -> dict:
    """Create sample summary data."""
    return {
        "period_start": "2024-03-01",
        "period_end": "2024-03-31",
        "total_employees": 3,
        "total_hours": 24.0,
        "total_earnings": 35250.0,
    }


class TestExcelReportBuilder:
    """Tests for Excel report builder."""

    def test_initialization(self) -> None:
        """Test builder initialization."""
        builder = ExcelReportBuilder(title="Test Report")
        assert builder.title == "Test Report"
        assert builder.wb is not None
        builder.close()

    def test_add_sheet(self, sample_dataframe: pd.DataFrame) -> None:
        """Test adding sheet."""
        builder = ExcelReportBuilder()
        builder.add_sheet("Data", sample_dataframe)
        assert "Data" in builder.sheets
        builder.close()

    def test_add_sheet_with_summary(
        self,
        sample_dataframe: pd.DataFrame,
        summary_data: dict,
    ) -> None:
        """Test adding sheet with summary."""
        builder = ExcelReportBuilder()
        builder.add_sheet(
            "Data",
            sample_dataframe,
            include_summary=True,
            summary_data=summary_data,
        )
        assert "Data" in builder.sheets
        builder.close()

    def test_set_properties(self) -> None:
        """Test setting workbook properties."""
        builder = ExcelReportBuilder()
        builder.set_properties(
            title="Test",
            subject="HR Report",
            author="Test User",
        )
        assert builder.wb.properties.title == "Test"
        assert builder.wb.properties.subject == "HR Report"
        assert builder.wb.properties.author == "Test User"
        builder.close()

    def test_save(self, sample_dataframe: pd.DataFrame) -> None:
        """Test saving workbook."""
        builder = ExcelReportBuilder()
        builder.add_sheet("Data", sample_dataframe)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.xlsx"
            builder.save(str(output_path))
            assert output_path.exists()
            assert output_path.stat().st_size > 0

        builder.close()

    def test_get_bytes(self, sample_dataframe: pd.DataFrame) -> None:
        """Test getting workbook bytes."""
        builder = ExcelReportBuilder()
        builder.add_sheet("Data", sample_dataframe)

        data = builder.get_bytes()
        assert isinstance(data, bytes)
        assert len(data) > 0

        builder.close()

    def test_empty_dataframe(self) -> None:
        """Test adding empty DataFrame."""
        builder = ExcelReportBuilder()
        empty_df = pd.DataFrame()
        builder.add_sheet("Empty", empty_df)
        assert "Empty" in builder.sheets
        builder.close()

    def test_sheet_name_truncation(self, sample_dataframe: pd.DataFrame) -> None:
        """Test long sheet names are truncated."""
        builder = ExcelReportBuilder()
        long_name = "A" * 50
        builder.add_sheet(long_name, sample_dataframe)
        # Sheet name should be truncated to 31 chars
        assert len(list(builder.sheets.keys())[0]) <= 31
        builder.close()

    def test_multiple_sheets(self, sample_dataframe: pd.DataFrame) -> None:
        """Test adding multiple sheets."""
        builder = ExcelReportBuilder()
        builder.add_sheet("Sheet1", sample_dataframe)
        builder.add_sheet("Sheet2", sample_dataframe)
        builder.add_sheet("Sheet3", sample_dataframe)

        assert len(builder.sheets) == 3
        builder.close()


class TestCreateMultiReportWorkbook:
    """Tests for multi-report workbook factory."""

    def test_create_multi_report(self, sample_dataframe: pd.DataFrame) -> None:
        """Test creating multi-report workbook."""
        reports = {
            "Roster": sample_dataframe,
            "Hours": sample_dataframe,
            "Dispatch": sample_dataframe,
        }

        builder = create_multi_report_workbook(
            reports,
            title="HR Reports",
            author="Test",
        )

        assert len(builder.sheets) == 3
        assert "Roster" in builder.sheets
        assert "Hours" in builder.sheets
        assert "Dispatch" in builder.sheets

        builder.close()

    def test_save_multi_report(self, sample_dataframe: pd.DataFrame) -> None:
        """Test saving multi-report workbook."""
        reports = {
            "Data1": sample_dataframe,
            "Data2": sample_dataframe,
        }

        builder = create_multi_report_workbook(reports)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "multi_report.xlsx"
            builder.save(str(output_path))
            assert output_path.exists()

        builder.close()
