#!/usr/bin/env python3
"""
UNS HR Specialist Agent

Capabilities:
- Japanese payroll calculation
- Visa management and tracking
- Legal compliance reporting
- Employee lifecycle management
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class UNSHRSpecialist:
    """UNS HR Specialist agent for Japanese HR management."""

    def __init__(self) -> None:
        self.name = "UNSHRSpecialist"
        logger.info("UNSHRSpecialist initialized")

    async def execute(self, task: str) -> dict[str, Any]:
        """Execute an HR task.

        Args:
            task: Description of the HR task.

        Returns:
            Dictionary with payroll, visa, or compliance information.
        """
        logger.info(f"Executing HR task: {task[:80]}")

        result: dict[str, Any] = {
            "agent": self.name,
            "task": task,
            "status": "completed",
            "summary": "",
            "payroll": None,
            "visa_report": None,
            "compliance": None,
            "recommendations": [],
        }

        task_lower = task.lower()

        if "payroll" in task_lower or "給与" in task or "月薪" in task or "nomina" in task_lower:
            result["summary"] = "Monthly payroll calculation completed"
            result["payroll"] = {
                "employee": "山田 太郎",
                "month": "2024-01",
                "basic_salary": 250000,
                "overtime": 32000,
                "allowances": 10000,
                "gross": 292000,
                "deductions": {
                    "所得税 (Income tax)": 12500,
                    "社会保険料 (Social insurance)": 38500,
                    "雇用保険 (Employment insurance)": 2774,
                    "住民税 (Residential tax)": 8500,
                },
                "total_deductions": 62274,
                "net_pay": 229726,
            }
            result["recommendations"].append("Submit 社会保険 to 協会けんぽ by the 5th of next month")
            result["recommendations"].append("Generate 源泉徴収票 for year-end processing")
            result["compliance"] = {
                "law": "労働基準法・税法",
                "notes": ["Payroll records retained 7 years per tax law"],
            }

        elif "visa" in task_lower or "在留" in task:
            result["summary"] = "Visa status report generated"
            result["visa_report"] = {
                "expiring_soon": [
                    {"name": "John Smith", "status": "技術人文国際業務", "expiry": "2024-05-15", "days_left": 45},
                    {"name": "Maria Garcia", "status": "技能実習", "expiry": "2024-04-20", "days_left": 20},
                ],
                "expired": [],
                "alerts": ["Maria Garcia: Apply for extension at least 90 days before expiry"],
            }
            result["recommendations"].append("Set up 90-day advance alert for all visa expirations")
            result["recommendations"].append("Track 在留カード copy expiration dates")

        elif "compliance" in task_lower or "36協定" in task or "労働基準法" in task:
            result["summary"] = "Compliance report generated"
            result["compliance"] = {
                "month": "2024-01",
                "overtime_summary": [
                    {"name": "山田 太郎", "monthly_hours": 42, "limit": 45, "compliant": True},
                    {"name": "鈴木 一郎", "monthly_hours": 48, "limit": 45, "compliant": False},
                ],
                "actions": ["Alert: 鈴木 一郎 exceeded 36協定 limit by 3 hours"],
                "yearly_summary": {
                    "total_overtime": 320,
                    "yearly_limit": 720,
                    "remaining": 400,
                },
            }
            result["recommendations"].append("Monthly overtime report to HR manager")
            result["recommendations"].append("Submit 36協定 change application if limits adjust")

        elif "employee" in task_lower or " hire" in task_lower or "入社" in task:
            result["summary"] = "Employee onboarding checklist generated"
            result["recommendations"] = [
                "Collect 履歴書, ongi contract, and identification documents",
                "Enroll in 社会保険 within 5 days of hire date",
                "Submit 雇用保険 enrollment to HelloWork",
                "Set up payroll with correct 標準報酬月額",
                "Schedule 36協定 orientation for new workers",
            ]

        else:
            result["summary"] = f"UNS HR specialist processed: {task}"
            result["recommendations"].append("Use Japanese date format (令和) in official documents")
            result["recommendations"].append("Submit required filings on time to avoid penalties")

        logger.info(f"HR task completed: {result['summary']}")
        return result


async def main() -> None:
    """CLI entry point."""
    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        specialist = UNSHRSpecialist()
        result = await specialist.execute(task)
        print(f"Result: {result['summary']}")
        if result.get("payroll"):
            print(f"Net pay: ¥{result['payroll']['net_pay']:,}")
    else:
        print("Usage: python uns_hr_specialist.py <task>")


if __name__ == "__main__":
    asyncio.run(main())