#!/usr/bin/env python3
"""
PDF Generation Patterns Demo

Este script demuestra patrones de generación de PDFs incluyendo:
- Generación programática
- Templates de facturas
- Reportes con tablas
- Headers/Footers

Uso:
    python pdf_demo.py --demo invoice
    python pdf_demo.py --demo report
    python pdf_demo.py --output invoice.pdf
"""

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Company:
    """Información de empresa."""

    name: str
    address: str
    email: str
    phone: str
    tax_id: str = ""


@dataclass
class Customer:
    """Información de cliente."""

    name: str
    address: str
    email: str


@dataclass
class InvoiceItem:
    """Línea de factura."""

    description: str
    quantity: int
    unit_price: float

    @property
    def total(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Invoice:
    """Factura completa."""

    number: str
    date: datetime
    due_date: datetime
    company: Company
    customer: Customer
    items: list[InvoiceItem]
    tax_rate: float = 0.21  # 21% IVA

    @property
    def subtotal(self) -> float:
        return sum(item.total for item in self.items)

    @property
    def tax(self) -> float:
        return self.subtotal * self.tax_rate

    @property
    def total(self) -> float:
        return self.subtotal + self.tax


@dataclass
class ReportData:
    """Datos para reporte."""

    title: str
    subtitle: str
    generated_at: datetime
    sections: list[dict]
    summary: dict


class SimplePDFGenerator:
    """
    Generador de PDFs simplificado usando texto plano.

    Esta es una demostración de la estructura de datos.
    En producción, usar:
    - Python: reportlab, weasyprint, fpdf2
    - Node.js: puppeteer, pdfkit, react-pdf
    """

    def __init__(self) -> None:
        self.content: list[str] = []
        self.page_width = 80
        logger.info("PDFGenerator inicializado")

    def add_header(self, text: str, level: int = 1) -> None:
        """Añadir encabezado."""
        if level == 1:
            self.content.append("=" * self.page_width)
            self.content.append(text.center(self.page_width))
            self.content.append("=" * self.page_width)
        elif level == 2:
            self.content.append("")
            self.content.append("-" * len(text))
            self.content.append(text)
            self.content.append("-" * len(text))
        else:
            self.content.append("")
            self.content.append(f"### {text}")

    def add_text(self, text: str) -> None:
        """Añadir texto."""
        self.content.append(text)

    def add_line(self) -> None:
        """Añadir línea separadora."""
        self.content.append("-" * self.page_width)

    def add_space(self, lines: int = 1) -> None:
        """Añadir espacio."""
        for _ in range(lines):
            self.content.append("")

    def add_two_columns(self, left: str, right: str) -> None:
        """Añadir contenido en dos columnas."""
        padding = self.page_width - len(left) - len(right)
        self.content.append(f"{left}{' ' * padding}{right}")

    def add_table(
        self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None
    ) -> None:
        """Añadir tabla."""
        if not col_widths:
            col_widths = [self.page_width // len(headers)] * len(headers)

        # Headers
        header_row = ""
        for i, header in enumerate(headers):
            header_row += header.ljust(col_widths[i])
        self.content.append(header_row)
        self.content.append("-" * self.page_width)

        # Rows
        for row in rows:
            row_text = ""
            for i, cell in enumerate(row):
                row_text += str(cell).ljust(col_widths[i])
            self.content.append(row_text)

    def render(self) -> str:
        """Renderizar PDF como texto."""
        return "\n".join(self.content)

    def save(self, filepath: str) -> None:
        """Guardar a archivo."""
        content = self.render()
        Path(filepath).write_text(content)
        logger.info(f"PDF guardado en: {filepath}")


def generate_invoice_html(invoice: Invoice) -> str:
    """
    Generar HTML de factura.

    Este HTML puede ser convertido a PDF usando:
    - Puppeteer (Node.js)
    - WeasyPrint (Python)
    - wkhtmltopdf
    """
    items_html = ""
    for item in invoice.items:
        items_html += f"""
        <tr>
            <td>{item.description}</td>
            <td class="center">{item.quantity}</td>
            <td class="right">${item.unit_price:.2f}</td>
            <td class="right">${item.total:.2f}</td>
        </tr>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; font-size: 12px; color: #333; padding: 40px; }}
        .header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
        .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; }}
        .invoice-info {{ text-align: right; }}
        .invoice-number {{ font-size: 18px; font-weight: bold; }}
        .parties {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
        .party {{ width: 45%; }}
        .party-title {{ font-weight: bold; color: #666; margin-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
        th {{ background: #f3f4f6; padding: 12px; text-align: left; }}
        td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; }}
        .center {{ text-align: center; }}
        .right {{ text-align: right; }}
        .totals {{ margin-left: auto; width: 300px; }}
        .total-row {{ font-weight: bold; background: #f3f4f6; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">{invoice.company.name}</div>
        <div class="invoice-info">
            <div class="invoice-number">Factura #{invoice.number}</div>
            <div>Fecha: {invoice.date.strftime("%Y-%m-%d")}</div>
            <div>Vencimiento: {invoice.due_date.strftime("%Y-%m-%d")}</div>
        </div>
    </div>

    <div class="parties">
        <div class="party">
            <div class="party-title">De:</div>
            <div>{invoice.company.name}</div>
            <div>{invoice.company.address}</div>
            <div>{invoice.company.email}</div>
            <div>NIF: {invoice.company.tax_id}</div>
        </div>
        <div class="party">
            <div class="party-title">Para:</div>
            <div>{invoice.customer.name}</div>
            <div>{invoice.customer.address}</div>
            <div>{invoice.customer.email}</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Descripción</th>
                <th class="center">Cantidad</th>
                <th class="right">Precio</th>
                <th class="right">Total</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <table class="totals">
        <tr>
            <td>Subtotal:</td>
            <td class="right">${invoice.subtotal:.2f}</td>
        </tr>
        <tr>
            <td>IVA ({invoice.tax_rate * 100:.0f}%):</td>
            <td class="right">${invoice.tax:.2f}</td>
        </tr>
        <tr class="total-row">
            <td>Total:</td>
            <td class="right">${invoice.total:.2f}</td>
        </tr>
    </table>
</body>
</html>
    """


def demo_invoice() -> None:
    """Demostrar generación de factura."""
    logger.info("=== Demo: Generación de Factura ===")

    # Datos de ejemplo
    company = Company(
        name="TechCorp S.L.",
        address="Calle Principal 123, Madrid 28001",
        email="facturacion@techcorp.es",
        phone="+34 91 123 4567",
        tax_id="B12345678",
    )

    customer = Customer(
        name="Cliente Ejemplo S.A.",
        address="Avenida Secundaria 456, Barcelona 08001",
        email="compras@cliente.com",
    )

    items = [
        InvoiceItem("Desarrollo web - Frontend React", 40, 75.00),
        InvoiceItem("Desarrollo web - Backend Node.js", 35, 80.00),
        InvoiceItem("Diseño UI/UX", 15, 65.00),
        InvoiceItem("Configuración servidor AWS", 8, 90.00),
        InvoiceItem("Mantenimiento mensual", 1, 500.00),
    ]

    invoice = Invoice(
        number="2026-001",
        date=datetime.now(),
        due_date=datetime.now() + timedelta(days=30),
        company=company,
        customer=customer,
        items=items,
    )

    # Generar PDF simplificado
    pdf = SimplePDFGenerator()

    pdf.add_header(f"FACTURA #{invoice.number}")
    pdf.add_space()

    pdf.add_two_columns("Fecha:", invoice.date.strftime("%Y-%m-%d"))
    pdf.add_two_columns("Vencimiento:", invoice.due_date.strftime("%Y-%m-%d"))
    pdf.add_space()

    pdf.add_header("EMISOR", 2)
    pdf.add_text(company.name)
    pdf.add_text(company.address)
    pdf.add_text(f"Email: {company.email}")
    pdf.add_text(f"NIF: {company.tax_id}")
    pdf.add_space()

    pdf.add_header("CLIENTE", 2)
    pdf.add_text(customer.name)
    pdf.add_text(customer.address)
    pdf.add_text(f"Email: {customer.email}")
    pdf.add_space()

    pdf.add_header("DETALLE", 2)
    pdf.add_table(
        headers=["Descripción", "Cant", "Precio", "Total"],
        rows=[
            [
                item.description[:35],
                str(item.quantity),
                f"${item.unit_price:.2f}",
                f"${item.total:.2f}",
            ]
            for item in invoice.items
        ],
        col_widths=[40, 8, 15, 15],
    )
    pdf.add_line()

    pdf.add_space()
    pdf.add_two_columns("Subtotal:", f"${invoice.subtotal:.2f}")
    pdf.add_two_columns(f"IVA ({invoice.tax_rate * 100:.0f}%):", f"${invoice.tax:.2f}")
    pdf.add_line()
    pdf.add_two_columns("TOTAL:", f"${invoice.total:.2f}")

    print("\n" + pdf.render())

    # Mostrar HTML para conversión real
    print("\n\n--- HTML para Puppeteer/WeasyPrint ---")
    html = generate_invoice_html(invoice)
    print(html[:500] + "...")

    logger.info(f"Factura generada: #{invoice.number}, Total: ${invoice.total:.2f}")


def demo_report() -> None:
    """Demostrar generación de reporte."""
    logger.info("=== Demo: Generación de Reporte ===")

    report = ReportData(
        title="Reporte de Ventas Q4 2025",
        subtitle="Análisis trimestral de rendimiento",
        generated_at=datetime.now(),
        sections=[
            {
                "title": "Resumen Ejecutivo",
                "content": "Este trimestre hemos superado los objetivos de ventas en un 15%...",
            },
            {
                "title": "Ventas por Región",
                "data": [
                    ["Norte", "$125,000", "+12%"],
                    ["Sur", "$98,000", "+8%"],
                    ["Este", "$156,000", "+22%"],
                    ["Oeste", "$87,000", "-3%"],
                ],
            },
            {
                "title": "Top Productos",
                "data": [
                    ["Producto A", "1,234 uds", "$89,000"],
                    ["Producto B", "987 uds", "$76,000"],
                    ["Producto C", "654 uds", "$54,000"],
                ],
            },
        ],
        summary={"total_sales": "$466,000", "growth": "+12.5%", "avg_ticket": "$2,340"},
    )

    pdf = SimplePDFGenerator()

    pdf.add_header(report.title)
    pdf.add_text(report.subtitle.center(80))
    pdf.add_text(f"Generado: {report.generated_at.strftime('%Y-%m-%d %H:%M')}".center(80))
    pdf.add_space(2)

    for section in report.sections:
        pdf.add_header(section["title"], 2)

        if "content" in section:
            pdf.add_text(section["content"])

        if "data" in section:
            for row in section["data"]:
                pdf.add_text("  • " + " | ".join(row))

        pdf.add_space()

    pdf.add_header("RESUMEN", 2)
    for key, value in report.summary.items():
        label = key.replace("_", " ").title()
        pdf.add_two_columns(f"  {label}:", value)

    print("\n" + pdf.render())

    logger.info("Reporte generado exitosamente")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="PDF Generation Patterns Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python pdf_demo.py --demo invoice
    python pdf_demo.py --demo report
    python pdf_demo.py --demo all
    python pdf_demo.py --output factura.txt
        """,
    )

    parser.add_argument(
        "--demo",
        choices=["invoice", "report", "all"],
        default="all",
        help="Tipo de demo a ejecutar",
    )

    parser.add_argument("--output", type=str, help="Archivo de salida (opcional)")

    args = parser.parse_args()

    print("=" * 60)
    print("        PDF GENERATION PATTERNS DEMO")
    print("=" * 60)

    if args.demo in ("invoice", "all"):
        demo_invoice()
        print()

    if args.demo in ("report", "all"):
        demo_report()

    print("\n" + "=" * 60)
    print("Demo completada. Ver SKILL.md para patrones de producción")
    print("con Puppeteer, React-PDF y PDFKit.")
    print("=" * 60)


if __name__ == "__main__":
    main()
