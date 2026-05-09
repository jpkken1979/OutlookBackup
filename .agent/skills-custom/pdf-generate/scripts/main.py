#!/usr/bin/env python3
"""
Skill: pdf-generate — Entry point

Uso:
    python .agent/skills-custom/pdf-generate/scripts/main.py <action> [args]

Acciones disponibles:
    html-to-pdf         HTML a PDF
    excel-to-pdf         Excel a PDF
    clone-pdf-format     Clonar formato de PDF de referencia
    generate-from-template   Template Jinja2 a PDF
    url-to-pdf           URL a PDF

Ejemplos:
    python main.py html-to-pdf --html "<h1>Hola</h1>" --output test.pdf

    python main.py excel-to-pdf --excel datos.xlsx --output datos.pdf --sheet "Hoja1"

    python main.py clone-pdf-format \
        --source template.pdf \
        --data '{"title":"Factura","items":[{"description":"Item","total":1000}]}' \
        --output factura.pdf

    python main.py generate-from-template \
        --template templates/invoice.html \
        --data '{"company":{"name":"UNS"},"invoice":{"number":"001"}}' \
        --output invoice.pdf

    python main.py url-to-pdf --url "https://example.com" --output page.pdf
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Agregar el directorio del skill al path para importar pdf_generation
SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from pdf_generation import (  # noqa: I001
    clone_pdf_format,
    excel_to_pdf,
    generate_from_template,
    html_to_pdf,
    url_to_pdf,
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Delegado a pdf_generation.main()."""
    # Fix encoding Windows cp932 para output UTF-8
    import sys
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    return pdf_generation_main()


def pdf_generation_main() -> int:
    """CLI principal del skill — re-exporta desde pdf_generation."""
    import argparse
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        prog="pdf-generate",
        description="PDF Generate — Generacion unificada de PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="action", help="Accion a ejecutar")

    # ---- html-to-pdf ----
    p = sub.add_parser("html-to-pdf", help="Convierte HTML a PDF")
    p.add_argument("--html", required=True, help="Contenido HTML")
    p.add_argument("--output", required=True, help="Ruta de salida (.pdf)")
    p.add_argument(
        "--engine",
        default="weasyprint",
        choices=["weasyprint", "pdfkit", "playwright"],
        help="Motor de renderizado",
    )

    # ---- excel-to-pdf ----
    p = sub.add_parser("excel-to-pdf", help="Convierte Excel (.xlsx) a PDF")
    p.add_argument("--excel", required=True, help="Ruta al archivo Excel")
    p.add_argument("--output", required=True, help="Ruta de salida (.pdf)")
    p.add_argument("--sheet", help="Nombre de hoja (opcional, default=activa)")

    # ---- clone-pdf-format ----
    p = sub.add_parser("clone-pdf-format", help="Clona formato de un PDF de referencia")
    p.add_argument("--source", required=True, help="PDF de referencia")
    p.add_argument("--data", required=True, help="Datos JSON para el nuevo PDF")
    p.add_argument("--output", required=True, help="Ruta de salida (.pdf)")

    # ---- generate-from-template ----
    p = sub.add_parser("generate-from-template", help="Genera PDF desde template Jinja2")
    p.add_argument("--template", required=True, help="Ruta al template HTML")
    p.add_argument("--data", required=True, help="Datos JSON para el template")
    p.add_argument("--output", required=True, help="Ruta de salida (.pdf)")

    # ---- url-to-pdf ----
    p = sub.add_parser("url-to-pdf", help="Renderiza una URL como PDF")
    p.add_argument("--url", required=True, help="URL a renderizar")
    p.add_argument("--output", required=True, help="Ruta de salida (.pdf)")
    p.add_argument(
        "--engine",
        default="playwright",
        choices=["playwright", "weasyprint"],
        help="Motor de renderizado",
    )

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return 0

    try:
        match args.action:
            case "html-to-pdf":
                result = html_to_pdf(args.html, args.output, {"engine": args.engine})

            case "excel-to-pdf":
                result = excel_to_pdf(args.excel, args.output, sheet_name=args.sheet)

            case "clone-pdf-format":
                data = json.loads(args.data)
                result = clone_pdf_format(args.source, data, args.output)

            case "generate-from-template":
                data = json.loads(args.data)
                result = generate_from_template(args.template, data, args.output)

            case "url-to-pdf":
                result = url_to_pdf(args.url, args.output, {"engine": args.engine})

            case _:
                parser.print_help()
                return 0

        print(f"OK: {result}")
        logger.info("[main] PDF generado exitosamente: %s", result)
        return 0

    except Exception as exc:  # noqa: BLE001
        logger.error("[main] Error: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
