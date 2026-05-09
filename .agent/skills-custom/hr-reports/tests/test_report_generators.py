"""Tests for report generators."""

import pytest
from datetime import date
import pandas as pd

from scripts.report_generators import (
    ReportConfig,
    RosterReportGenerator,
    HoursReportGenerator,
    DispatchReportGenerator,
    AbsenceReportGenerator,
    create_generator,
)
from fixtures.attendance_fixtures import (
    sample_attendance_records,
    sample_dispatch_assignments,
)


@pytest.fixture
def report_config(sample_start_date: date, sample_end_date: date) -> ReportConfig:
    """Create report configuration."""
    return ReportConfig(
        start_date=sample_start_date,
        end_date=sample_end_date,
        include_summary=True,
    )


class TestRosterReportGenerator:
    """Tests for roster report generation."""

    def test_initialization(self, report_config: ReportConfig) -> None:
        """Test generator initialization."""
        gen = RosterReportGenerator(report_config)
        assert gen.config == report_config
        assert gen.data == []
        assert gen.df is None

    def test_set_data(self, report_config: ReportConfig) -> None:
        """Test setting data."""
        gen = RosterReportGenerator(report_config)
        data = sample_attendance_records()
        gen.set_data(data)
        assert len(gen.data) == len(data)

    def test_get_dataframe(self, report_config: ReportConfig) -> None:
        """Test DataFrame generation."""
        gen = RosterReportGenerator(report_config)
        data = sample_attendance_records()
        # Add employee info
        for rec in data:
            rec["name"] = "Test Employee"
            rec["department"] = "Test Dept"
        gen.set_data(data)

        df = gen.get_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "present_days" in df.columns
        assert "absent_days" in df.columns

    def test_get_summary(self, report_config: ReportConfig) -> None:
        """Test summary generation."""
        gen = RosterReportGenerator(report_config)
        data = sample_attendance_records()
        for rec in data:
            rec["name"] = "Test"
            rec["department"] = "Test"
        gen.set_data(data)

        summary = gen.get_summary()
        assert isinstance(summary, dict)
        assert "period_start" in summary
        assert "period_end" in summary
        assert "total_employees" in summary

    def test_empty_dataframe(self, report_config: ReportConfig) -> None:
        """Test with empty data."""
        gen = RosterReportGenerator(report_config)
        df = gen.get_dataframe()
        assert df.empty


class TestHoursReportGenerator:
    """Tests for hours report generation."""

    def test_hours_report_creation(self, report_config: ReportConfig) -> None:
        """Test hours report creation."""
        gen = HoursReportGenerator(report_config)
        data = sample_attendance_records()
        for rec in data:
            rec["hourly_rate"] = 1500.0
        gen.set_data(data)

        df = gen.get_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert "hours_worked" in df.columns
        assert "daily_earnings" in df.columns

    def test_hours_summary(self, report_config: ReportConfig) -> None:
        """Test hours summary."""
        gen = HoursReportGenerator(report_config)
        data = sample_attendance_records()
        for rec in data:
            rec["hourly_rate"] = 1500.0
        gen.set_data(data)

        summary = gen.get_summary()
        assert "total_hours" in summary
        assert "total_earnings" in summary
        assert summary["total_hours"] > 0


class TestDispatchReportGenerator:
    """Tests for dispatch report generation."""

    def test_dispatch_report_creation(self, report_config: ReportConfig) -> None:
        """Test dispatch report creation."""
        gen = DispatchReportGenerator(report_config)
        data = sample_dispatch_assignments()
        gen.set_data(data)

        df = gen.get_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert "client_name" in df.columns
        assert "hours_allocated" in df.columns

    def test_dispatch_summary(self, report_config: ReportConfig) -> None:
        """Test dispatch summary."""
        gen = DispatchReportGenerator(report_config)
        data = sample_dispatch_assignments()
        gen.set_data(data)

        summary = gen.get_summary()
        assert "total_assignments" in summary
        assert "unique_employees" in summary
        assert "unique_clients" in summary


class TestAbsenceReportGenerator:
    """Tests for absence report generation."""

    def test_absence_report_creation(self, report_config: ReportConfig) -> None:
        """Test absence report creation."""
        gen = AbsenceReportGenerator(report_config)
        # Filter absence records only
        data = [
            r
            for r in sample_attendance_records()
            if r.get("status") in ["absent", "excused_absence"]
        ]
        for rec in data:
            rec["name"] = "Test"
            rec["department"] = "Test"
        gen.set_data(data)

        df = gen.get_dataframe()
        assert isinstance(df, pd.DataFrame)

    def test_absence_summary(self, report_config: ReportConfig) -> None:
        """Test absence summary."""
        gen = AbsenceReportGenerator(report_config)
        data = [
            {
                "employee_id": "EMP001",
                "name": "Test",
                "department": "Test",
                "date": "2024-03-01",
                "status": "absent",
                "reason": "Sick leave",
                "notes": "",
            }
        ]
        gen.set_data(data)

        summary = gen.get_summary()
        assert "total_absences" in summary
        assert "absence_breakdown" in summary


class TestCreateGenerator:
    """Tests for generator factory function."""

    def test_create_roster_generator(self, report_config: ReportConfig) -> None:
        """Test creating roster generator."""
        gen = create_generator("roster", report_config)
        assert isinstance(gen, RosterReportGenerator)

    def test_create_hours_generator(self, report_config: ReportConfig) -> None:
        """Test creating hours generator."""
        gen = create_generator("hours", report_config)
        assert isinstance(gen, HoursReportGenerator)

    def test_create_dispatch_generator(self, report_config: ReportConfig) -> None:
        """Test creating dispatch generator."""
        gen = create_generator("dispatch", report_config)
        assert isinstance(gen, DispatchReportGenerator)

    def test_create_absence_generator(self, report_config: ReportConfig) -> None:
        """Test creating absence generator."""
        gen = create_generator("absence", report_config)
        assert isinstance(gen, AbsenceReportGenerator)

    def test_create_invalid_generator(self, report_config: ReportConfig) -> None:
        """Test creating invalid generator."""
        with pytest.raises(ValueError):
            create_generator("invalid", report_config)
