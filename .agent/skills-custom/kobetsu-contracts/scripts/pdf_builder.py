"""PDF Builder for Kobetsu contracts using WeasyPrint.

Converts HTML contract output to PDF format for printing and archiving.
"""

import logging
from pathlib import Path
from typing import Optional

try:
    from weasyprint import HTML, CSS

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class PDFBuilder:
    """Builds PDF documents from HTML contract templates."""

    def __init__(self) -> None:
        """Initialize PDF builder.

        Raises:
            ImportError: If weasyprint is not installed.
        """
        if not WEASYPRINT_AVAILABLE:
            raise ImportError(
                "weasyprint is required for PDF generation. Install with: pip install weasyprint"
            )
        logger.info("PDFBuilder initialized with weasyprint")

    def build(
        self,
        html_content: str,
        output_path: Path,
        css_path: Path | None = None,
    ) -> Path:
        """Build PDF from HTML content.

        Args:
            html_content: HTML string to convert to PDF.
            output_path: Path where PDF will be saved.
            css_path: Optional CSS file path for additional styling.

        Returns:
            Path to generated PDF file.

        Raises:
            ValueError: If HTML is empty or invalid.
            Exception: If PDF generation fails.
        """
        if not html_content or len(html_content.strip()) == 0:
            raise ValueError("html_content cannot be empty")

        try:
            # Create output directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert HTML to PDF
            doc = HTML(string=html_content)

            # Apply optional CSS
            css_list = []
            if css_path and css_path.exists():
                css_list.append(CSS(filename=str(css_path)))

            # Write PDF
            doc.write_pdf(
                str(output_path),
                stylesheets=css_list,
            )

            logger.info(f"Generated PDF: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise

    def build_from_template(
        self,
        html_content: str,
        contract_number: str,
        output_dir: Path | None = None,
        css_path: Path | None = None,
    ) -> Path:
        """Build PDF from HTML, using contract number in filename.

        Args:
            html_content: HTML string to convert.
            contract_number: Contract number for filename.
            output_dir: Output directory (default: ./output/pdfs/).
            css_path: Optional CSS file path.

        Returns:
            Path to generated PDF file.
        """
        if output_dir is None:
            output_dir = Path.cwd() / "output" / "pdfs"

        # Sanitize contract number for filename
        safe_filename = contract_number.replace("/", "_").replace(" ", "_")
        output_path = output_dir / f"{safe_filename}.pdf"

        return self.build(
            html_content=html_content,
            output_path=output_path,
            css_path=css_path,
        )
