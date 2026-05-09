"""Tests for template_renderer.py module."""

import pytest
from jinja2 import TemplateNotFound

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kobetsu_contracts.scripts.template_renderer import ContractRenderer


class TestContractRenderer:
    """Test ContractRenderer class."""

    def test_init_with_valid_template_dir(self, template_dir):
        """Test initialization with valid template directory."""
        renderer = ContractRenderer(template_dir=template_dir)
        assert renderer.template_dir == template_dir
        assert renderer.env is not None

    def test_init_with_nonexistent_directory(self, temp_db_dir):
        """Test initialization with nonexistent directory raises error."""
        nonexistent = temp_db_dir / "nonexistent"

        with pytest.raises(FileNotFoundError):
            ContractRenderer(template_dir=nonexistent)

    def test_build_context(self, test_employee, test_contract):
        """Test context building."""
        renderer = ContractRenderer(template_dir=None)  # Will use default

        context = renderer.build_context(test_employee, test_contract)

        assert context["employee_id"] == "W001"
        assert context["employee_name_jp"] == "田中太郎"
        assert context["contract_number"] == "KOB-2026-001"
        assert context["job_title"] == "システムエンジニア"
        assert context["hourly_rate_jpy"] == 2500.0
        assert isinstance(context, dict)

    def test_render_html_valid(self, test_employee, test_contract, template_dir):
        """Test HTML rendering with valid template."""
        renderer = ContractRenderer(template_dir=template_dir)

        html = renderer.render_html(test_employee, test_contract)

        assert isinstance(html, str)
        assert len(html) > 0
        assert "KOB-2026-001" in html
        assert "田中太郎" in html
        assert "システムエンジニア" in html

    def test_render_html_template_not_found(self, test_employee, test_contract, template_dir):
        """Test HTML rendering with missing template raises error."""
        renderer = ContractRenderer(template_dir=template_dir)

        with pytest.raises(TemplateNotFound):
            renderer.render_html(
                test_employee, test_contract, template_name="missing_template.jinja2"
            )

    def test_render_text(self, test_employee, test_contract):
        """Test text rendering."""
        renderer = ContractRenderer(template_dir=None)

        text = renderer.render_text(test_employee, test_contract)

        assert isinstance(text, str)
        assert len(text) > 0
        assert "個別派遣契約書" in text
        assert "KOB-2026-001" in text
        assert "田中太郎" in text
        assert "システムエンジニア" in text
        assert "東京都渋谷区" in text
        assert "¥" in text  # Currency symbol

    def test_render_text_with_benefits(self, test_employee, test_contract):
        """Test text rendering includes benefits."""
        renderer = ContractRenderer(template_dir=None)

        text = renderer.render_text(test_employee, test_contract)

        assert "健康保険" in text
        assert "厚生年金" in text
        assert "雇用保険" in text

    def test_render_text_with_notes(self, test_employee, test_contract):
        """Test text rendering includes notes."""
        renderer = ContractRenderer(template_dir=None)

        text = renderer.render_text(test_employee, test_contract)

        assert test_contract.notes in text

    def test_render_text_date_formatting(self, test_employee, test_contract):
        """Test that dates are formatted correctly in text."""
        renderer = ContractRenderer(template_dir=None)

        text = renderer.render_text(test_employee, test_contract)

        assert "2026-04-03" in text  # contract_date
        assert "2026-04-01" in text  # effective_date
        assert "2027-03-31" in text  # expiration_date

    def test_render_html_currency_formatting(self, test_employee, test_contract, template_dir):
        """Test currency formatting in HTML."""
        renderer = ContractRenderer(template_dir=template_dir)

        html = renderer.render_html(test_employee, test_contract)

        # Template should have currency symbol
        assert "¥" in html or "2500" in html

    def test_render_text_currency_formatting(self, test_employee, test_contract):
        """Test currency formatting in text."""
        renderer = ContractRenderer(template_dir=None)

        text = renderer.render_text(test_employee, test_contract)

        assert f"¥{test_contract.hourly_rate_jpy:,.0f}" in text

    def test_render_html_with_custom_template_name(
        self, test_employee, test_contract, template_dir
    ):
        """Test HTML rendering with custom template name."""
        # Create an alternative template
        alt_template = """
        <html>
        <body>
        <h1>Alternative Template</h1>
        <p>Contract: {{ contract_number }}</p>
        </body>
        </html>
        """
        (template_dir / "contract_alternative.jinja2").write_text(alt_template)

        renderer = ContractRenderer(template_dir=template_dir)

        html = renderer.render_html(
            test_employee, test_contract, template_name="contract_alternative.jinja2"
        )

        assert "Alternative Template" in html
        assert "KOB-2026-001" in html

    def test_context_with_none_optional_fields(self, test_employee):
        """Test context building with None optional fields."""
        from _uns_employee_schema import KobetsuContract
        from datetime import date

        contract = KobetsuContract(
            id="TEST-1",
            employee_id="W001",
            contract_number="KOB-2026-TEST",
            contract_date=date(2026, 4, 3),
            effective_date=date(2026, 4, 1),
            expiration_date=None,  # None
            client_company=None,  # None
            job_title="Test",
            work_location="Tokyo",
            hourly_rate_jpy=1000.0,
            monthly_minimum_hours=None,  # None
            benefits=None,  # None
            terms_conditions=None,  # None
            notes=None,  # None
        )

        renderer = ContractRenderer(template_dir=None)
        context = renderer.build_context(test_employee, contract)

        # Check that None fields are handled gracefully
        assert context["expiration_date"] == "未定"
        assert context["client_company"] == "未定"
        assert context["monthly_minimum_hours"] is None
        assert context["benefits"] == []
        assert context["terms_conditions"] == ""
        assert context["notes"] == ""

    def test_render_html_escaping(self, test_employee, template_dir):
        """Test that HTML is properly escaped."""
        from _uns_employee_schema import KobetsuContract
        from datetime import date

        # Contract with HTML-like content
        contract = KobetsuContract(
            id="TEST-1",
            employee_id="W001",
            contract_number="KOB-<script>alert('xss')</script>",
            contract_date=date(2026, 4, 3),
            effective_date=date(2026, 4, 1),
            job_title="<img src=x onerror=alert('xss')>",
            work_location="Tokyo",
            hourly_rate_jpy=1000.0,
        )

        renderer = ContractRenderer(template_dir=template_dir)
        html = renderer.render_html(test_employee, contract)

        # Verify escaping
        assert "<script>" not in html or "&lt;script&gt;" in html
        assert "onerror=" not in html or "onerror=" not in html  # Should be escaped

    def test_render_text_with_multiline_terms(self, test_employee):
        """Test text rendering with multiline terms and conditions."""
        from _uns_employee_schema import KobetsuContract
        from datetime import date

        contract = KobetsuContract(
            id="TEST-1",
            employee_id="W001",
            contract_number="KOB-2026-001",
            contract_date=date(2026, 4, 3),
            effective_date=date(2026, 4, 1),
            job_title="Test",
            work_location="Tokyo",
            hourly_rate_jpy=1000.0,
            terms_conditions="Line 1\nLine 2\nLine 3",
        )

        renderer = ContractRenderer(template_dir=None)
        text = renderer.render_text(test_employee, contract)

        assert "Line 1" in text
        assert "Line 2" in text
        assert "Line 3" in text
