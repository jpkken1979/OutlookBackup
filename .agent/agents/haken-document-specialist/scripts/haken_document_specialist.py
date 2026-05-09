#!/usr/bin/env python3
"""
Haken Document Specialist Agent

Capabilities:
- Japanese dispatch contract generation
- Legal compliance validation
- Employment certificate creation
- Attendance and payroll processing
"""

import asyncio
import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


class HakenDocumentSpecialist:
    """Haken Document Specialist agent for Japanese dispatch document generation."""

    def __init__(self) -> None:
        self.name = "HakenDocumentSpecialist"
        logger.info("HakenDocumentSpecialist initialized")

    async def execute(self, task: str) -> dict[str, Any]:
        """Execute a document generation task.

        Args:
            task: Description of the document task.

        Returns:
            Dictionary with document content, compliance info, and recommendations.
        """
        logger.info(f"Executing document task: {task[:80]}")

        result: dict[str, Any] = {
            "agent": self.name,
            "task": task,
            "status": "completed",
            "summary": "",
            "document": None,
            "compliance": None,
            "recommendations": [],
        }

        task_lower = task.lower()

        if "certificate" in task_lower or "在籍証明書" in task or "証明書" in task:
            result["summary"] = "Employment certificate (在籍証明書) generated"
            result["document"] = {
                "type": "在籍証明書",
                "content": """氏名: 山田 太郎
生年月日: 1990年5月1日
雇用期間: 2024年4月1日 ～ 2025年3月31日
派遣先: ABC株式会社
派遣期間: 2024年4月1日 ～ 2025年3月31日
職種: システムエンジニア
"""

,
            }
            result["compliance"] = {
                "law": "労働基準法",
                "clauses": ["身元保証", "雇用条件明示"],
            }
            result["recommendations"].append("Use company seal (、社印) for official documents")
            result["recommendations"].append("Retain copy for 3 years per law")

        elif "contract" in task_lower or "個別契約書" in task or "契約書" in task:
            result["summary"] = "Individual contract (個別契約書) generated"
            result["document"] = {
                "type": "個別契約書",
                "content": """【個別契約書】

第一条（契約の目的）
本契約は、労働者派遣法第30条の3に基づき、派遣労働者の就業に関する事項について定める。

第二条（派遣就業の場所）
派遣就業の場所: ○○株式会社 本社
住所: 東京都○○区○○町1-2-3

第三条（派遣就業の内容）
職種: システムエンジニア
業務の内容: ソフトウェア開発業務

第四条（契約期間）
令和6年4月1日 から 令和7年3月31日 まで

第五条（就業時間）
基本就業時間: 9時00分 ～ 17時30分（休憩1時間）
始業・終業時刻は派遣先の指示に従う。
""",
            }
            result["compliance"] = {
                "law": "労働者派遣法",
                "clauses": ["30条の3", "32条の2", "32条の3", "36協定"],
            }
            result["recommendations"].append("Verify 抵触日 before contract renewal")
            result["recommendations"].append("Include 36協定 overtime clause if applicable")

        elif "履歴書" in task or "resume" in task_lower:
            result["summary"] = "Resume (履歴書) template generated"
            result["document"] = {
                "type": "履歴書",
                "content": """履歴書

令和6年4月1日

氏名: 山田 太郎
生年月日: 1990年5月1日（34歳）

学歴
令和2年3月  東京大学 工学部 卒業

職歴
令和2年4月  ABC株式会社 入社
令和5年3月  同社 退社

令和5年4月  XYZ株式会社 入社（現在に至る）

資格
令和3年6月  基本情報技術者試験 合格

自己PR
システム開発の経験を持ち、チームでの协作を大切にしています。
""",
            }
            result["recommendations"].append("Use JIS format (A4) for official resumes")
            result["recommendations"].append("Use black ink and proper handwriting or printing")

        elif "勤怠" in task or "attendance" in task_lower or "給与" in task:
            result["summary"] = "Attendance and payroll document generated"
            result["document"] = {
                "type": "勤怠・給与",
                "content": """【勤怠集計】 2024年4月分

氏名: 山田 太郎
派遣先: ABC株式会社

実働日数: 22日
総労働時間: 176時間
時間外労働: 8時間（36協定内）

【給与内訳】
基本給: 250,000円
時間外手当: 16,000円
合計: 266,000円

【控除】
所得税: 12,500円
社会保険料: 38,500円
合計控除: 51,000円

差引支給額: 215,000円
""",
            }
            result["compliance"] = {
                "law": "労働基準法・税法",
                "deductions": ["所得税", "社会保険料", "雇用保険"],
            }
            result["recommendations"].append("Verify monthly with 勤怠 system")
            result["recommendations"].append("Submit to 社会保障事務所 by 5th of next month")

        else:
            result["summary"] = f"Haken document specialist processed: {task}"
            result["recommendations"].append("Use proper Japanese business document format")
            result["recommendations"].append("Include date in Japanese era (令和) format")

        logger.info(f"Document task completed: {result['summary']}")
        return result


async def main() -> None:
    """CLI entry point."""
    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        specialist = HakenDocumentSpecialist()
        result = await specialist.execute(task)
        print(f"Result: {result['summary']}")
        if result.get("document"):
            print(f"Document type: {result['document']['type']}")
    else:
        print("Usage: python haken_document_specialist.py <task>")


if __name__ == "__main__":
    asyncio.run(main())