"""Tests for pdf_builder.py module."""

import pytest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from kobetsu_contracts.scripts.pdf_builder import PDFBuilder

    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False


class TestPDFBuilder:
    """Test PDFBuilder class."""

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_init(self):
        """Test PDF builder initialization."""
        builder = PDFBuilder()
        assert builder is not None

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_init_without_weasyprint(self):
        """Test initialization fails without weasyprint."""
        if HAS_WEASYPRINT:
            pytest.skip("weasyprint is installed")

        with pytest.raises(ImportError):
            PDFBuilder()

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_valid_html(self, temp_db_dir):
        """Test PDF building with valid HTML."""
        builder = PDFBuilder()

        html = "<html><body><h1>Test Contract</h1></body></html>"
        output_path = temp_db_dir / "test_contract.pdf"

        result = builder.build(html, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_empty_html_raises_error(self, temp_db_dir):
        """Test that empty HTML raises ValueError."""
        builder = PDFBuilder()
        output_path = temp_db_dir / "test.pdf"

        with pytest.raises(ValueError):
            builder.build("", output_path)

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_creates_output_directory(self, temp_db_dir):
        """Test that build creates output directory if needed."""
        builder = PDFBuilder()

        nested_path = temp_db_dir / "level1" / "level2" / "test.pdf"
        html = "<html><body><h1>Test</h1></body></html>"

        builder.build(html, nested_path)

        assert nested_path.exists()
        assert nested_path.parent == temp_db_dir / "level1" / "level2"

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_from_template(self, temp_db_dir):
        """Test build_from_template convenience method."""
        builder = PDFBuilder()

        html = "<html><body><h1>Contract KOB-2026-001</h1></body></html>"
        result = builder.build_from_template(
            html_content=html,
            contract_number="KOB-2026-001",
            output_dir=temp_db_dir,
        )

        assert result.exists()
        assert "KOB-2026-001" in result.name
        assert result.suffix == ".pdf"

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_from_template_sanitizes_filename(self, temp_db_dir):
        """Test that contract number is sanitized for filename."""
        builder = PDFBuilder()

        html = "<html><body><h1>Test</h1></body></html>"
        result = builder.build_from_template(
            html_content=html,
            contract_number="KOB/2026/001 (draft)",
            output_dir=temp_db_dir,
        )

        # Path separators should be replaced
        assert "/" not in result.name
        assert " " not in result.name or "_" in result.name

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_with_css(self, temp_db_dir):
        """Test PDF building with CSS stylesheet."""
        builder = PDFBuilder()

        # Create CSS file
        css_path = temp_db_dir / "styles.css"
        css_path.write_text("body { font-family: Arial; } h1 { color: blue; }")

        html = "<html><body><h1>Test Contract</h1></body></html>"
        output_path = temp_db_dir / "test_with_css.pdf"

        result = builder.build(html, output_path, css_path=css_path)

        assert result.exists()
        assert output_path.stat().st_size > 0

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_complex_html(self, temp_db_dir):
        """Test PDF building with complex HTML structure."""
        builder = PDFBuilder()

        html = """
        <html>
        <head><title>Complex Contract</title></head>
        <body>
            <h1>個別派遣契約書</h1>
            <table>
                <tr><th>Field</th><th>Value</th></tr>
                <tr><td>Contract Number</td><td>KOB-2026-001</td></tr>
                <tr><td>Employee</td><td>田中太郎</td></tr>
                <tr><td>Rate</td><td>¥2,500</td></tr>
            </table>
        </body>
        </html>
        """

        output_path = temp_db_dir / "complex.pdf"
        result = builder.build(html, output_path)

        assert result.exists()
        assert output_path.stat().st_size > 1000  # Should be reasonably sized

    @pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
    def test_build_japanese_text(self, temp_db_dir):
        """Test PDF generation with Japanese text."""
        builder = PDFBuilder()

        html = """
        <html>
        <head><meta charset="UTF-8"></head>
        <body>
            <h1>個別派遣契約書</h1>
            <p>被派遣者: 田中太郎</p>
            <p>職務内容: システムエンジニア</p>
            <p>勤務地: 東京都渋谷区</p>
        </body>
        </html>
        """

        output_path = temp_db_dir / "japanese.pdf"
        result = builder.build(html, output_path)

        assert result.exists()
