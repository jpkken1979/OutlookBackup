"""Attendance and HR data fixtures for testing."""

from datetime import date, datetime, time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AttendanceRecord:
    """Attendance record for testing."""

    employee_id: str
    date: date
    clock_in: time | None = None
    clock_out: time | None = None
    hours_worked: float | None = None
    status: str = "present"
    reason: str | None = None
    notes: str | None = None


@dataclass
class DispatchAssignment:
    """Dispatch assignment for testing."""

    employee_id: str
    dispatch_date: date
    client_name: str
    location: str
    hours_allocated: float
    start_time: time
    end_time: time
    hourly_rate: float = 1500.0  # 日本円


def sample_attendance_records() -> list[dict]:
    """Generate sample attendance records for testing."""
    return [
        {
            "employee_id": "EMP001",
            "date": "2024-03-01",
            "clock_in": "08:30:00",
            "clock_out": "17:30:00",
            "hours_worked": 8.5,
            "status": "present",
        },
        {
            "employee_id": "EMP001",
            "date": "2024-03-02",
            "clock_in": "08:45:00",
            "clock_out": "17:30:00",
            "hours_worked": 8.25,
            "status": "late",
            "reason": "Traffic",
        },
        {
            "employee_id": "EMP002",
            "date": "2024-03-01",
            "clock_in": None,
            "clock_out": None,
            "hours_worked": 0.0,
            "status": "absent",
            "reason": "Sick leave",
        },
        {
            "employee_id": "EMP002",
            "date": "2024-03-02",
            "clock_in": "09:00:00",
            "clock_out": "18:00:00",
            "hours_worked": 9.0,
            "status": "present",
        },
        {
            "employee_id": "EMP003",
            "date": "2024-03-01",
            "clock_in": "08:00:00",
            "clock_out": "16:30:00",
            "hours_worked": 8.0,
            "status": "early_leave",
            "reason": "Personal appointment",
        },
    ]


def sample_dispatch_assignments() -> list[dict]:
    """Generate sample dispatch assignments for testing."""
    return [
        {
            "employee_id": "EMP001",
            "dispatch_date": "2024-03-01",
            "client_name": "Tokyo Manufacturing Inc.",
            "location": "Shibuya Ward",
            "hours_allocated": 8.0,
            "start_time": "08:30:00",
            "end_time": "17:30:00",
            "hourly_rate": 1500.0,
        },
        {
            "employee_id": "EMP001",
            "dispatch_date": "2024-03-02",
            "client_name": "Tokyo Manufacturing Inc.",
            "location": "Shibuya Ward",
            "hours_allocated": 8.0,
            "start_time": "08:30:00",
            "end_time": "17:30:00",
            "hourly_rate": 1500.0,
        },
        {
            "employee_id": "EMP002",
            "dispatch_date": "2024-03-02",
            "client_name": "Osaka Tech Solutions",
            "location": "Osaka Ward",
            "hours_allocated": 9.0,
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "hourly_rate": 1600.0,
        },
        {
            "employee_id": "EMP003",
            "dispatch_date": "2024-03-01",
            "client_name": "Kyoto Service Center",
            "location": "Kyoto Ward",
            "hours_allocated": 7.5,
            "start_time": "08:00:00",
            "end_time": "16:30:00",
            "hourly_rate": 1400.0,
        },
    ]


def sample_employees() -> list[dict]:
    """Generate sample employee data for testing."""
    return [
        {
            "employee_id": "EMP001",
            "name": "山田太郎",
            "name_kana": "やまだたろう",
            "department": "派遣営業部",
            "employment_type": "haken",
            "start_date": "2023-01-15",
            "status": "active",
            "email": "yamada.taro@example.com",
            "phone": "090-1234-5678",
        },
        {
            "employee_id": "EMP002",
            "name": "佐藤花子",
            "name_kana": "さとうはなこ",
            "department": "事務部",
            "employment_type": "haken",
            "start_date": "2023-06-01",
            "status": "active",
            "email": "satoh.hanako@example.com",
            "phone": "090-2345-6789",
        },
        {
            "employee_id": "EMP003",
            "name": "鈴木次郎",
            "name_kana": "すずきじろう",
            "department": "派遣営業部",
            "employment_type": "haken",
            "start_date": "2022-04-01",
            "status": "active",
            "email": "suzuki.jiro@example.com",
            "phone": "090-3456-7890",
        },
    ]


def sample_payroll_data() -> list[dict]:
    """Generate sample payroll data for testing."""
    return [
        {
            "employee_id": "EMP001",
            "period_start": "2024-03-01",
            "period_end": "2024-03-31",
            "total_hours": 160.0,
            "hourly_rate": 1500.0,
            "gross_salary": 240000.0,
            "deductions": 30000.0,
            "net_salary": 210000.0,
        },
        {
            "employee_id": "EMP002",
            "period_start": "2024-03-01",
            "period_end": "2024-03-31",
            "total_hours": 155.0,
            "hourly_rate": 1600.0,
            "gross_salary": 248000.0,
            "deductions": 31000.0,
            "net_salary": 217000.0,
        },
        {
            "employee_id": "EMP003",
            "period_start": "2024-03-01",
            "period_end": "2024-03-31",
            "total_hours": 150.0,
            "hourly_rate": 1400.0,
            "gross_salary": 210000.0,
            "deductions": 26000.0,
            "net_salary": 184000.0,
        },
    ]


def create_mock_attendance_dict(
    employee_id: str = "EMP001",
    date_str: str = "2024-03-01",
    hours_worked: float = 8.5,
    status: str = "present",
) -> dict:
    """Create a minimal mock attendance record for testing."""
    return {
        "employee_id": employee_id,
        "date": date_str,
        "hours_worked": hours_worked,
        "status": status,
        "clock_in": "08:30:00",
        "clock_out": "17:00:00",
    }
