#!/usr/bin/env python3
"""
Haken Contracts - Contract Generator
====================================
Generador de documentos legales para 人材派遣.

Genera:
- 個別契約書 (Contrato Individual 派遣元↔派遣先)
- 労働者派遣契約書 (Contrato de Empleo 派遣元↔派遣労働者)

Uso:
    python generate_contracts.py --type kobetsu --input data.json --output contract.pdf
    python generate_contracts.py --type roudousha --input data.json --output contract.pdf
    python generate_contracts.py --type all --input data.json --output-dir contracts/
"""

import argparse
import json
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Intentar importar dependencias opcionales
try:
    from jinja2 import Environment, FileSystemLoader

    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False

try:
    from weasyprint import HTML, CSS

    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

# Agregar path para importar models
sys.path.insert(0, str(Path(__file__).parent))
from models import (
    AgencyInfo,
    ClientInfo,
    WorkerInfo,
    PlacementDetails,
    WorkHours,
    KobetsuKeiyaku,
    RoudoushaKeiyaku,
    InsuranceStatus,
    DEFAULT_AGENCY,
    generate_contract_number,
)


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
ARTIFACTS_DIR = Path("artifacts/haken-contracts")


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def parse_date(date_str: str) -> date:
    """Parse date from string (YYYY-MM-DD)."""
    return date.fromisoformat(date_str)


def load_contract_data(filepath: str) -> dict:
    """Load contract data from JSON file."""
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def create_agency_from_dict(data: dict) -> AgencyInfo:
    """Create AgencyInfo from dictionary."""
    return AgencyInfo(**data)


def create_client_from_dict(data: dict) -> ClientInfo:
    """Create ClientInfo from dictionary."""
    return ClientInfo(**data)


def create_worker_from_dict(data: dict) -> WorkerInfo:
    """Create WorkerInfo from dictionary."""
    # Convert insurance status strings to enum
    for field in ["health_insurance", "pension", "employment_insurance"]:
        if field in data and isinstance(data[field], str):
            data[field] = InsuranceStatus(data[field])

    # Parse birth_date if present
    if "birth_date" in data and isinstance(data["birth_date"], str):
        data["birth_date"] = parse_date(data["birth_date"])

    return WorkerInfo(**data)


def create_placement_from_dict(data: dict) -> PlacementDetails:
    """Create PlacementDetails from dictionary."""
    # Make a copy to avoid modifying original
    data = data.copy()

    # Parse dates (only if they're strings)
    if isinstance(data["start_date"], str):
        data["start_date"] = parse_date(data["start_date"])
    if isinstance(data["end_date"], str):
        data["end_date"] = parse_date(data["end_date"])

    # Convert rates to Decimal
    for field in [
        "billing_rate",
        "billing_rate_overtime",
        "billing_rate_night",
        "billing_rate_holiday",
        "worker_wage",
        "worker_wage_overtime",
        "transport_allowance",
    ]:
        if field in data and data[field] is not None:
            data[field] = Decimal(str(data[field]))

    # Handle work_hours
    if "work_hours" in data and isinstance(data["work_hours"], dict):
        data["work_hours"] = WorkHours(**data["work_hours"])

    return PlacementDetails(**data)


# ═══════════════════════════════════════════════════════════════
# CONTRACT BUILDERS
# ═══════════════════════════════════════════════════════════════


def build_kobetsu_keiyaku(data: dict) -> KobetsuKeiyaku:
    """Build 個別契約書 from data dictionary."""
    # Use default agency if not provided
    agency_data = data.get("agency", {})
    if not agency_data:
        agency = DEFAULT_AGENCY
    else:
        agency = create_agency_from_dict(agency_data)

    client = create_client_from_dict(data["client"])
    worker = create_worker_from_dict(data["worker"])
    placement = create_placement_from_dict(data["placement"])

    # Calculate teishoku_bi (3 years from start)
    teishoku_bi = data.get("teishoku_bi")
    if teishoku_bi:
        teishoku_bi = parse_date(teishoku_bi)
    else:
        teishoku_bi = placement.start_date + timedelta(days=365 * 3)

    return KobetsuKeiyaku(
        contract_number=data.get(
            "contract_number", generate_contract_number("KC", placement.start_date.year, 1)
        ),
        contract_date=parse_date(data.get("contract_date", date.today().isoformat())),
        agency=agency,
        client=client,
        worker=worker,
        placement=placement,
        teishoku_bi=teishoku_bi,
        safety_health_items=data.get("safety_health_items", "別紙安全衛生事項による"),
        welfare_facilities=data.get("welfare_facilities", "派遣先の福利厚生施設の利用可"),
        special_conditions=data.get("special_conditions", ""),
    )


def build_roudousha_keiyaku(data: dict) -> RoudoushaKeiyaku:
    """Build 労働者派遣契約書 from data dictionary."""
    # Use default agency if not provided
    agency_data = data.get("agency", {})
    if not agency_data:
        agency = DEFAULT_AGENCY
    else:
        agency = create_agency_from_dict(agency_data)

    client = create_client_from_dict(data["client"])
    worker = create_worker_from_dict(data["worker"])
    placement = create_placement_from_dict(data["placement"])

    return RoudoushaKeiyaku(
        contract_number=data.get(
            "contract_number", generate_contract_number("RC", placement.start_date.year, 1)
        ),
        contract_date=parse_date(data.get("contract_date", date.today().isoformat())),
        agency=agency,
        client=client,
        worker=worker,
        placement=placement,
        employment_type=data.get("employment_type", "派遣社員"),
        employment_period_type=data.get("employment_period_type", "有期雇用"),
        paid_leave_days=data.get("paid_leave_days", 0),
        holidays=data.get("holidays", "土日祝日、年末年始"),
        social_insurance_note=data.get(
            "social_insurance_note", "健康保険、厚生年金、雇用保険に加入"
        ),
        resignation_notice_days=data.get("resignation_notice_days", 14),
        special_conditions=data.get("special_conditions", ""),
    )


# ═══════════════════════════════════════════════════════════════
# HTML GENERATION
# ═══════════════════════════════════════════════════════════════


def render_html(template_name: str, contract) -> str:
    """Render contract to HTML using Jinja2."""
    if not HAS_JINJA:
        raise ImportError("Jinja2 is required. Install with: pip install jinja2")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)

    template = env.get_template(template_name)
    return template.render(contract=contract)


def generate_html_file(contract, template_name: str, output_path: Path) -> Path:
    """Generate HTML file from contract."""
    html_content = render_html(template_name, contract)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path


# ═══════════════════════════════════════════════════════════════
# PDF GENERATION
# ═══════════════════════════════════════════════════════════════


def generate_pdf(html_content: str, output_path: Path, css_path: Path | None = None) -> Path:
    """
    Generate PDF from HTML content.

    Para A4 Vertical (縦向き):
    - El CSS incluye @page { size: A4 portrait; }
    - WeasyPrint respeta esta configuración automáticamente
    """
    if not HAS_WEASYPRINT:
        raise ImportError(
            "WeasyPrint is required for PDF generation.\n"
            "Install with: pip install weasyprint\n"
            "For Japanese fonts on Linux: sudo apt-get install fonts-noto-cjk"
        )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load base CSS
    stylesheets = []
    if css_path and css_path.exists():
        stylesheets.append(CSS(filename=str(css_path)))
    elif (TEMPLATES_DIR / "base.css").exists():
        stylesheets.append(CSS(filename=str(TEMPLATES_DIR / "base.css")))

    # Generate PDF
    html = HTML(string=html_content, base_url=str(TEMPLATES_DIR))
    html.write_pdf(str(output_path), stylesheets=stylesheets)

    return output_path


def generate_contract_pdf(contract, template_name: str, output_path: Path) -> Path:
    """Generate PDF contract file."""
    html_content = render_html(template_name, contract)
    return generate_pdf(html_content, output_path)


# ═══════════════════════════════════════════════════════════════
# MAIN GENERATOR FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def generate_kobetsu(data: dict, output_path: Path, format: str = "pdf") -> Path:
    """
    Generate 個別契約書 (Individual Contract).

    Args:
        data: Contract data dictionary
        output_path: Output file path
        format: 'pdf' or 'html'

    Returns:
        Path to generated file
    """
    contract = build_kobetsu_keiyaku(data)
    template_name = "kobetsu_keiyaku.html"

    if format == "html":
        return generate_html_file(contract, template_name, output_path)
    else:
        return generate_contract_pdf(contract, template_name, output_path)


def generate_roudousha(data: dict, output_path: Path, format: str = "pdf") -> Path:
    """
    Generate 労働者派遣契約書 (Worker Contract).

    Args:
        data: Contract data dictionary
        output_path: Output file path
        format: 'pdf' or 'html'

    Returns:
        Path to generated file
    """
    contract = build_roudousha_keiyaku(data)
    template_name = "roudousha_keiyaku.html"

    if format == "html":
        return generate_html_file(contract, template_name, output_path)
    else:
        return generate_contract_pdf(contract, template_name, output_path)


def generate_all(data: dict, output_dir: Path, format: str = "pdf") -> list[Path]:
    """
    Generate all contract types.

    Returns:
        List of paths to generated files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    # Generate 個別契約書
    worker_name = data.get("worker", {}).get("name", "unknown")
    start_date = data.get("placement", {}).get("start_date", date.today().isoformat())

    kobetsu_path = output_dir / f"kobetsu_{worker_name}_{start_date}.{format}"
    generated.append(generate_kobetsu(data, kobetsu_path, format))

    # Generate 労働者派遣契約書
    roudousha_path = output_dir / f"roudousha_{worker_name}_{start_date}.{format}"
    generated.append(generate_roudousha(data, roudousha_path, format))

    return generated


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Haken Contracts Generator - 派遣契約書ジェネレーター",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 個別契約書
  python generate_contracts.py --type kobetsu --input data.json --output kobetsu.pdf

  # Generate 労働者派遣契約書
  python generate_contracts.py --type roudousha --input data.json --output roudousha.pdf

  # Generate all contracts
  python generate_contracts.py --type all --input data.json --output-dir contracts/

  # Generate HTML instead of PDF
  python generate_contracts.py --type kobetsu --input data.json --output kobetsu.html --format html

A4 Vertical Format (縦向き):
  Documents are automatically generated in A4 portrait orientation (210mm x 297mm).
  This is configured in the CSS template using @page { size: A4 portrait; }
        """,
    )

    parser.add_argument(
        "--type",
        "-t",
        choices=["kobetsu", "roudousha", "all"],
        required=True,
        help="Contract type to generate",
    )

    parser.add_argument("--input", "-i", required=True, help="Input JSON file with contract data")

    parser.add_argument("--output", "-o", help="Output file path (for single contract)")

    parser.add_argument("--output-dir", "-d", help="Output directory (for --type all)")

    parser.add_argument(
        "--format",
        "-f",
        choices=["pdf", "html"],
        default="pdf",
        help="Output format (default: pdf)",
    )

    args = parser.parse_args()

    # Load input data
    try:
        data = load_contract_data(args.input)
    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}")
        sys.exit(1)

    # Validate output arguments
    if args.type == "all":
        output_dir = Path(args.output_dir or ARTIFACTS_DIR)
    else:
        if not args.output:
            print("Error: --output is required for single contract generation")
            sys.exit(1)

    # Generate contracts
    try:
        if args.type == "kobetsu":
            output_path = generate_kobetsu(data, Path(args.output), args.format)
            print(f"✅ 個別契約書 generated: {output_path}")

        elif args.type == "roudousha":
            output_path = generate_roudousha(data, Path(args.output), args.format)
            print(f"✅ 労働者派遣契約書 generated: {output_path}")

        elif args.type == "all":
            generated = generate_all(data, output_dir, args.format)
            print(f"✅ Generated {len(generated)} contracts:")
            for path in generated:
                print(f"   - {path}")

    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating contract: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
