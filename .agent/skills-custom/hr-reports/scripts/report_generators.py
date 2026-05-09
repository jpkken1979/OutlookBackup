"""Report generators for HR Reports - WEEK 2."""

import logging
from datetime import date
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    start_date: date
    end_date: date
    include_summary: bool = True
    include_details: bool = True
    format_currency: bool = True


class BaseReportGenerator:
    """Base class for all report generators."""

    def __init__(self, config: ReportConfig) -> None:
        """Initialize report generator.

        Args:
            config: Report configuration.
        """
        self.config = config
        self.data: list[dict[str, Any]] = []
        self.df: pd.DataFrame | None = None
        logger.info(f"Initialized {self.__class__.__name__}")

    def set_data(self, data: list[dict[str, Any]]) -> None:
        """Set raw data for report.

        Args:
            data: List of data records.
        """
        self.data = data
        logger.debug(f"Data set with {len(data)} records")

    def get_dataframe(self) -> pd.DataFrame:
        """Get report as pandas DataFrame.

        Returns:
            DataFrame with report data.
        """
        if self.df is None:
            self.df = self._build_dataframe()
        return self.df

    def _build_dataframe(self) -> pd.DataFrame:
        """Build DataFrame from raw data. Override in subclasses.

        Returns:
            Empty DataFrame (override in subclasses).
        """
        return pd.DataFrame(self.data)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics. Override in subclasses.

        Returns:
            Summary dict.
        """
        return {
            "period_start": self.config.start_date.isoformat(),
            "period_end": self.config.end_date.isoformat(),
            "record_count": len(self.data),
        }


class RosterReportGenerator(BaseReportGenerator):
    """Generate roster/attendance summary reports."""

    def _build_dataframe(self) -> pd.DataFrame:
        """Build roster report DataFrame.

        Returns:
            DataFrame with columns: employee_id, name, department, present_days, absent_days, etc.
        """
        if not self.data:
            return pd.DataFrame()

        # Group by employee
        employee_data = {}
        for record in self.data:
            emp_id = record.get("employee_id", "Unknown")
            if emp_id not in employee_data:
                employee_data[emp_id] = {
                    "employee_id": emp_id,
                    "name": record.get("name", ""),
                    "department": record.get("department", ""),
                    "present_days": 0,
                    "absent_days": 0,
                    "late_days": 0,
                    "early_leave_days": 0,
                    "total_hours": 0.0,
                }

            status = record.get("status", "present")
            if status == "present":
                employee_data[emp_id]["present_days"] += 1
            elif status == "absent":
                employee_data[emp_id]["absent_days"] += 1
            elif status == "late":
                employee_data[emp_id]["late_days"] += 1
            elif status == "early_leave":
                employee_data[emp_id]["early_leave_days"] += 1

            hours = record.get("hours_worked", 0.0)
            employee_data[emp_id]["total_hours"] += hours

        df = pd.DataFrame(list(employee_data.values()))
        logger.info(f"Roster report generated: {len(df)} employees")
        return df

    def get_summary(self) -> dict[str, Any]:
        """Get roster summary statistics.

        Returns:
            Summary with total employees, absences, etc.
        """
        df = self.get_dataframe()
        if df.empty:
            return super().get_summary()

        return {
            "period_start": self.config.start_date.isoformat(),
            "period_end": self.config.end_date.isoformat(),
            "total_employees": len(df),
            "total_present_days": df["present_days"].sum(),
            "total_absent_days": df["absent_days"].sum(),
            "total_late_arrivals": df["late_days"].sum(),
            "total_early_leaves": df["early_leave_days"].sum(),
            "average_hours": df["total_hours"].mean(),
        }


class HoursReportGenerator(BaseReportGenerator):
    """Generate hours/payroll detail reports."""

    def _build_dataframe(self) -> pd.DataFrame:
        """Build hours report DataFrame.

        Returns:
            DataFrame with columns: employee_id, date, hours_worked, hourly_rate, daily_earnings.
        """
        if not self.data:
            return pd.DataFrame()

        processed = []
        for record in self.data:
            processed.append(
                {
                    "employee_id": record.get("employee_id", ""),
                    "date": record.get("date", ""),
                    "hours_worked": float(record.get("hours_worked", 0.0)),
                    "hourly_rate": float(record.get("hourly_rate", 1500.0)),
                    "daily_earnings": float(record.get("hours_worked", 0.0))
                    * float(record.get("hourly_rate", 1500.0)),
                    "status": record.get("status", "present"),
                }
            )

        df = pd.DataFrame(processed)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values(["employee_id", "date"])

        logger.info(f"Hours report generated: {len(df)} entries")
        return df

    def get_summary(self) -> dict[str, Any]:
        """Get hours summary statistics.

        Returns:
            Summary with total hours, earnings, etc.
        """
        df = self.get_dataframe()
        if df.empty:
            return super().get_summary()

        return {
            "period_start": self.config.start_date.isoformat(),
            "period_end": self.config.end_date.isoformat(),
            "record_count": len(df),
            "total_hours": float(df["hours_worked"].sum()),
            "total_earnings": float(df["daily_earnings"].sum()),
            "average_hourly_rate": float(df["hourly_rate"].mean()),
            "unique_employees": df["employee_id"].nunique(),
        }


class DispatchReportGenerator(BaseReportGenerator):
    """Generate dispatch assignment reports."""

    def _build_dataframe(self) -> pd.DataFrame:
        """Build dispatch report DataFrame.

        Returns:
            DataFrame with dispatch assignments.
        """
        if not self.data:
            return pd.DataFrame()

        processed = []
        for record in self.data:
            processed.append(
                {
                    "employee_id": record.get("employee_id", ""),
                    "dispatch_date": record.get("dispatch_date", ""),
                    "client_name": record.get("client_name", ""),
                    "location": record.get("location", ""),
                    "hours_allocated": float(record.get("hours_allocated", 0.0)),
                    "start_time": record.get("start_time", ""),
                    "end_time": record.get("end_time", ""),
                    "hourly_rate": float(record.get("hourly_rate", 1500.0)),
                    "assigned_amount": float(record.get("hours_allocated", 0.0))
                    * float(record.get("hourly_rate", 1500.0)),
                }
            )

        df = pd.DataFrame(processed)
        if not df.empty:
            df["dispatch_date"] = pd.to_datetime(df["dispatch_date"])
            df = df.sort_values(["dispatch_date", "employee_id"])

        logger.info(f"Dispatch report generated: {len(df)} assignments")
        return df

    def get_summary(self) -> dict[str, Any]:
        """Get dispatch summary statistics.

        Returns:
            Summary with total assignments, budget, etc.
        """
        df = self.get_dataframe()
        if df.empty:
            return super().get_summary()

        return {
            "period_start": self.config.start_date.isoformat(),
            "period_end": self.config.end_date.isoformat(),
            "total_assignments": len(df),
            "total_hours_allocated": float(df["hours_allocated"].sum()),
            "total_assignment_cost": float(df["assigned_amount"].sum()),
            "unique_employees": df["employee_id"].nunique(),
            "unique_clients": df["client_name"].nunique(),
        }


class AbsenceReportGenerator(BaseReportGenerator):
    """Generate absence/leave reports."""

    def _build_dataframe(self) -> pd.DataFrame:
        """Build absence report DataFrame.

        Returns:
            DataFrame with absence records.
        """
        if not self.data:
            return pd.DataFrame()

        processed = []
        for record in self.data:
            processed.append(
                {
                    "employee_id": record.get("employee_id", ""),
                    "name": record.get("name", ""),
                    "department": record.get("department", ""),
                    "date": record.get("date", ""),
                    "status": record.get("status", "absent"),
                    "reason": record.get("reason", ""),
                    "notes": record.get("notes", ""),
                }
            )

        df = pd.DataFrame(processed)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values(["date", "employee_id"])

        logger.info(f"Absence report generated: {len(df)} records")
        return df

    def get_summary(self) -> dict[str, Any]:
        """Get absence summary statistics.

        Returns:
            Summary with absence counts by reason.
        """
        df = self.get_dataframe()
        if df.empty:
            return super().get_summary()

        reasons = df["reason"].fillna("Unspecified").value_counts().to_dict()

        return {
            "period_start": self.config.start_date.isoformat(),
            "period_end": self.config.end_date.isoformat(),
            "total_absences": len(df),
            "unique_employees": df["employee_id"].nunique(),
            "absence_breakdown": reasons,
        }


def create_generator(report_type: str, config: ReportConfig) -> BaseReportGenerator:
    """Factory function to create report generator.

    Args:
        report_type: Type of report (roster, hours, dispatch, absence).
        config: Report configuration.

    Returns:
        Appropriate report generator instance.

    Raises:
        ValueError: If report_type is unknown.
    """
    generators = {
        "roster": RosterReportGenerator,
        "hours": HoursReportGenerator,
        "dispatch": DispatchReportGenerator,
        "absence": AbsenceReportGenerator,
    }

    if report_type not in generators:
        raise ValueError(f"Unknown report type: {report_type}")

    return generators[report_type](config)
