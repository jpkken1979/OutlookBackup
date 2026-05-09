"""Template Renderer for Kobetsu contracts using Jinja2.

Renders contract HTML and text output from Jinja2 templates with employee and contract context.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _uns_employee_schema import KobetsuContract, Employee

logger = logging.getLogger(__name__)


class ContractRenderer:
    """Renders Kobetsu contracts from Jinja2 templates."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize renderer with template directory.

        Args:
            template_dir: Path to Jinja2 templates directory.
                         Defaults to ./templates/ relative to this module.

        Raises:
            FileNotFoundError: If template directory doesn't exist.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent.parent / "templates"

        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )

        logger.info(f"ContractRenderer initialized with templates from {template_dir}")

    def build_context(
        self,
        employee: Employee,
        contract: KobetsuContract,
    ) -> dict[str, Any]:
        """Build template context from employee and contract data.

        Args:
            employee: Employee record.
            contract: Contract record.

        Returns:
            Dictionary with template variables.
        """
        return {
            "employee_id": employee.id,
            "employee_name_jp": employee.name_jp,
            "employee_name_en": employee.name_en or "",
            "employee_email": employee.email,
            "employee_phone": employee.phone or "",
            "employee_status": employee.status,
            "contract_id": contract.id,
            "contract_number": contract.contract_number,
            "contract_date": contract.contract_date.isoformat(),
            "effective_date": contract.effective_date.isoformat(),
            "expiration_date": contract.expiration_date.isoformat()
            if contract.expiration_date
            else "未定",
            "dispatch_company": contract.dispatch_company,
            "client_company": contract.client_company or "未定",
            "job_title": contract.job_title,
            "work_location": contract.work_location,
            "work_hours_daily": contract.work_hours_daily,
            "work_days_weekly": contract.work_days_weekly,
            "hourly_rate_jpy": contract.hourly_rate_jpy,
            "monthly_minimum_hours": contract.monthly_minimum_hours,
            "benefits": contract.benefits or [],
            "terms_conditions": contract.terms_conditions or "",
            "notes": contract.notes or "",
            "generated_at": contract.generated_at or "",
            "template_version": contract.template_version,
        }

    def render_html(
        self,
        employee: Employee,
        contract: KobetsuContract,
        template_name: str = "contract_japanese.jinja2",
    ) -> str:
        """Render contract as HTML.

        Args:
            employee: Employee record.
            contract: Contract record.
            template_name: Name of Jinja2 template file (default: contract_japanese.jinja2).

        Returns:
            Rendered HTML string.

        Raises:
            TemplateNotFound: If template doesn't exist.
            Exception: If rendering fails.
        """
        try:
            template = self.env.get_template(template_name)
            context = self.build_context(employee, contract)
            html = template.render(**context)
            logger.info(f"Rendered HTML for contract {contract.contract_number}")
            return html
        except TemplateNotFound:
            logger.error(f"Template not found: {template_name}")
            raise
        except Exception as e:
            logger.error(f"HTML rendering failed: {e}")
            raise

    def render_text(
        self,
        employee: Employee,
        contract: KobetsuContract,
    ) -> str:
        """Render contract as plain text summary.

        Args:
            employee: Employee record.
            contract: Contract record.

        Returns:
            Rendered text string.
        """
        context = self.build_context(employee, contract)

        text_output = f"""
================================================================================
                    個別派遣契約書 (Individual Dispatch Contract)
================================================================================

契約番号: {context["contract_number"]}
契約日: {context["contract_date"]}
有効期間: {context["effective_date"]} 〜 {context["expiration_date"]}

【被派遣者情報】
氏名: {context["employee_name_jp"]}
従業員ID: {context["employee_id"]}
メール: {context["employee_email"]}
電話: {context["employee_phone"]}

【派遣先情報】
派遣会社: {context["dispatch_company"]}
勤務先企業: {context["client_company"]}
勤務地: {context["work_location"]}
職務内容: {context["job_title"]}

【勤務条件】
日当たり勤務時間: {context["work_hours_daily"]}時間
週間勤務日数: {context["work_days_weekly"]}日
時給: ¥{context["hourly_rate_jpy"]:,.0f}
月間最小勤務時間: {context["monthly_minimum_hours"] or "未定"}時間

【福利厚生】
{(chr(10).join(["・ " + benefit for benefit in context["benefits"]]) if context["benefits"] else "特記事項なし")}

【備考】
{context["notes"] or "特記事項なし"}

生成日時: {context["generated_at"]}
テンプレートバージョン: {context["template_version"]}

================================================================================
"""

        logger.info(f"Rendered text for contract {contract.contract_number}")
        return text_output.strip()
