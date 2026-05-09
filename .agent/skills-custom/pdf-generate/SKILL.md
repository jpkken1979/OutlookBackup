---
name: pdf-generate
description: Generación unificada de PDFs — HTML-to-PDF, Excel-to-PDF, PDF Clone, Templates Jinja2, URL-to-PDF
type: skill
tags: [pdf, html-to-pdf, excel-to-pdf, weasyprint, pdfkit, reportlab, jinja2, clone]
inputs:
  - html_content | excel_path | template_path | url
outputs:
  - output_path: PDF file
requires:
  - python >= 3.11
  - weasyprint | pdfkit | reportlab | fpdf2
  - openpyxl  # for Excel-to-PDF
  - jinja2    # for templates
  - requests   # for URL-to-PDF
---

# PDF Generate — Skill Unificado

> Genera PDFs desde HTML, Excel, URLs y templates. Soporta encoding japonés (Shift-JIS/UTF-8).

---

## 1. Comparativa de Librerias

| Libreria | Enfoque | Pros | Contras | Encoding Japon |
|---|---|---|---|---|
| **WeasyPrint** | HTML→PDF | CSS Paged Media completo, fuentes web | Instalacion GTK pesada | Soporta via fontconfig |
| **pdfkit** (wkhtmltopdf) | HTML→PDF | Rapido, simple | wkhtmltopdf descontinuado, sin headless Chrome | Compatible |
| **reportlab** | Programatico | Potente, control total, PDF nativo | Mas codigo, curva empinada | Soporta UTF-8 nativamente |
| **fpdf2** | Programatico | Ligero, simple | Menos features que reportlab | UTF-8 via UniTrueTypeFont |
| **Playwright/Chromium** | HTML→PDF | Fidelidad maxima, CSS moderno | Pesado (Chromium ~150MB) | Soporta japones |
| **Puppeteer** | HTML→PDF | Similar a Playwright | Solo Node.js | Soporta japones |

**Recomendacion por caso:**
- Facturas/tickets con CSS: `weasyprint` o `pdfkit`
- Reportes con datos complejos: `reportlab` o `fpdf2`
- Reproduccion pixel-perfect de web: `playwright.chromium`
- Rapido y simple: `pdfkit`
- PDF nativo sin dependencias externas: `reportlab`

---

## 2. HTML-to-PDF

### 2.1 WeasyPrint (Recomendado para Japon)

```bash
pip install weasyprint jinja2
```

```python
from pdf_generation import html_to_pdf

html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body { font-family: 'Noto Sans CJK JP', 'Hiragino Kaku Gothic Pro', sans-serif; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #2563eb; color: white; padding: 12px; }
  td { padding: 10px; border-bottom: 1px solid #e5e7eb; }
</style>
</head>
<body>
  <h1>御請求書 — Invoice</h1>
  <table>
    <tr><th>項目</th><th>金額</th></tr>
    <tr><td>月額料金</td><td>¥12,000</td></tr>
  </table>
</body>
</html>
"""

output = html_to_pdf(html, "invoice.pdf", options={"page_size": "A4"})
print(f"PDF generado: {output}")
```

### 2.2 pdfkit (wkhtmltopdf)

```bash
pip install pdfkit
# Instalar wkhtmltopdf desde https://wkhtmltopdf.org/downloads.html
```

```python
import pdfkit

html = "<h1>Factura</h1><p>Total: $1,200</p>"
output_path = "factura.pdf"

pdfkit.from_string(html, output_path, options={
    "page-size": "A4",
    "margin-top": "20mm",
    "margin-bottom": "20mm",
    "encoding": "UTF-8",
    "enable-local-file-access": "",
})
```

### 2.3 Playwright (Chromium)

```bash
pip install playwright
playwright install chromium
```

```python
from playwright.sync_api import sync_playwright

def html_to_pdf_playwright(html: str, output_path: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=output_path, format="A4", print_background=True)
        browser.close()
    return output_path
```

### Opciones comunes

```python
options = {
    "page_size": "A4",          # A4, Letter, Legal
    "margin_top": "20mm",
    "margin_bottom": "20mm",
    "margin_left": "15mm",
    "margin_right": "15mm",
    "print_background": True,
    "display_header_footer": True,
    "header_template": "<div style='font-size:10px'>Header</div>",
    "footer_template": "<div style='font-size:10px;text-align:center'><span class='pageNumber'></span></div>",
    "scale": 1.0,
}
```

---

## 3. Excel-to-PDF

Dado un archivo Excel, genera un PDF que replica exactamente la disposicion y formato de celdas.

### 3.1 Dependencias

```bash
pip install openpyxl weasyprint jinja2
```

### 3.2 Proceso

1. Leer Excel con `openpyxl` (celdas, fusion, estilos, anchos)
2. Convertir cada hoja a HTML con estilos equivalents
3. Renderizar HTML→PDF con WeasyPrint

```python
from pdf_generation import excel_to_pdf

# Convertir hoja especifica
excel_to_pdf(
    "reporte_mensual.xlsx",
    "reporte_mensual.pdf",
    sheet_name="2026年4月"
)

# Convertir todas las hojas (un PDF por hoja)
from pathlib import Path
excel_path = Path("datos.xlsx")
for sheet in excel_to_pdf(excel_path, excel_path.with_suffix(".pdf"), sheet_name=None):
    print(f"Hoja convertida: {sheet}")
```

### 3.3 Mapeo de estilos

| Excel | CSS equivalent |
|---|---|
| Bold | `font-weight: bold` |
| Font size 14 | `font-size: 14pt` |
| Background color | `background-color` |
| Border | `border: 1px solid #000` |
| Text align center | `text-align: center` |
| Merged cells | CSS grid spanning |

### 3.4 Ejemplo completo

```python
from openpyxl import load_workbook
from weasyprint import HTML, CSS

def excel_to_pdf_detailed(excel_path: str, output_path: str, sheet_name: str | None = None) -> str:
    wb = load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    # Generar HTML desde las celdas
    html_rows = []
    for row in ws.iter_rows():
        cells = [f"<td style='border:1px solid #ccc;padding:6px'>{cell.value or ''}</td>"
                  for cell in row]
        html_rows.append(f"<tr>{''.join(cells)}</tr>")

    table_html = f"""
    <table style='border-collapse:collapse;width:100%;font-family:Noto Sans CJK JP,sans-serif'>
        {''.join(html_rows)}
    </table>
    """

    full_html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="UTF-8">
    <style>
        body {{ font-family: sans-serif; padding: 20px; }}
        table {{ border-collapse: collapse; }}
    </style>
    </head><body>{table_html}</body></html>
    """

    HTML(string=full_html).write_pdf(output_path)
    return output_path
```

---

## 4. Template-based (Jinja2)

Combina templates Jinja2 con datos para generar PDFs.

### 4.1 Template de factura

```html
{# templates/invoice.html #}
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body { font-family: 'Noto Sans CJK JP', sans-serif; font-size: 12px; }
  .header { display: flex; justify-content: space-between; margin-bottom: 30px; }
  .company { font-size: 20px; font-weight: bold; color: #2563eb; }
  .invoice-info { text-align: right; }
  .invoice-number { font-size: 18px; font-weight: bold; }
  .parties { display: flex; justify-content: space-between; margin-bottom: 30px; }
  .party { width: 45%; }
  .party-label { font-weight: bold; color: #666; margin-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
  th { background: #2563eb; color: white; padding: 10px; text-align: left; }
  td { padding: 10px; border-bottom: 1px solid #e5e7eb; }
  .amount { text-align: right; }
  .totals { margin-left: auto; width: 280px; }
  .total-final { font-size: 16px; font-weight: bold; background: #eff6ff; }
  .footer { margin-top: 40px; font-size: 10px; color: #666; }
</style>
</head>
<body>
  <div class="header">
    <div class="company">{{ company.name }}</div>
    <div class="invoice-info">
      <div class="invoice-number">請求書 #{{ invoice.number }}</div>
      <div>Date: {{ invoice.date }}</div>
      <div>支払期限: {{ invoice.due_date }}</div>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <div class="party-label">派遣元:</div>
      <div>{{ company.name }}</div>
      <div>{{ company.address }}</div>
      <div>{{ company.email }}</div>
    </div>
    <div class="party">
      <div class="party-label">派遣先:</div>
      <div>{{ customer.name }}</div>
      <div>{{ customer.address }}</div>
      <div>{{ customer.email }}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>項目 Description</th>
        <th>数量 Qty</th>
        <th class="amount">単価 Unit Price</th>
        <th class="amount">金額 Amount</th>
      </tr>
    </thead>
    <tbody>
    {% for item in invoice.items %}
      <tr>
        <td>{{ item.description }}</td>
        <td>{{ item.quantity }}</td>
        <td class="amount">{{ item.unit_price | currency }}</td>
        <td class="amount">{{ item.total | currency }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <table class="totals">
    <tr><td>小計 Subtotal:</td><td class="amount">{{ invoice.subtotal | currency }}</td></tr>
    <tr><td>消費税 Tax ({{ invoice.tax_rate * 100 | int }}%):</td>
        <td class="amount">{{ invoice.tax | currency }}</td></tr>
    <tr class="total-final">
      <td>合計 Total:</td><td class="amount">{{ invoice.total | currency }}</td>
    </tr>
  </table>

  <div class="footer">
    <p>銀行名: {{ company.bank_name }} 口座: {{ company.bank_account }}</p>
    <p>{{ company.notes }}</p>
  </div>
</body>
</html>
```

### 4.2 Generacion con Jinja2

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pdf_generation import generate_from_template

env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=select_autoescape(["html", "xml"]),
)

# Registrar filtros personalizados
def currency_filter(value):
    return f"¥{value:,.0f}"

env.filters["currency"] = currency_filter

# Datos
data = {
    "company": {
        "name": "UNS株式会社",
        "address": "東京都渋谷区...",
        "email": "billing@uns-kikaku.co.jp",
        "bank_name": "三菱UFJ銀行",
        "bank_account": "123-4567890",
        "notes": "お支払いは翌月末日までにお願いします。",
    },
    "customer": {
        "name": "クライアント企業",
        "address": "大阪府大阪市...",
        "email": "accounts@client.jp",
    },
    "invoice": {
        "number": "INV-2026-001",
        "date": "2026-04-01",
        "due_date": "2026-05-31",
        "items": [
            {"description": "派遣料金 4月分", "quantity": 1, "unit_price": 450000, "total": 450000},
            {"description": "交通費精算", "quantity": 1, "unit_price": 32000, "total": 32000},
        ],
        "tax_rate": 0.10,
    },
}

# Generar
output = generate_from_template(
    "templates/invoice.html",
    data,
    "factura_2026_001.pdf",
    jinja_env=env,
)
```

---

## 5. PDF Clone (Replicar formato exacto)

Dado un PDF de referencia, usa `clone_format` para extraer sus estilos/metadatos
y generar un nuevo PDF con datos diferentes pero formato identico.

### 5.1 Concepto

1. **Extraer** el formato del PDF de referencia (fuentes, colores, layout, margins)
2. **Mapear** ese formato a HTML/CSS o a comandos de `reportlab`
3. **Aplicar** el nuevo contenido sobre el formato extrado
4. **Renderizar** a PDF

### 5.2 Uso con clone_format

```python
from pdf_generation import clone_pdf_format

# PDF de referencia con el formato corporativo
source_pdf = "templates/invoice_template.pdf"

# Nuevos datos
data = {
    "invoice_number": "INV-2026-042",
    "date": "2026-04-28",
    "items": [
        {"description": "月額派遣料", "amount": 480000},
        {"description": "諸経費", "amount": 45000},
    ],
    "total": 525000,
}

output = clone_pdf_format(source_pdf, data, "factura_clonada.pdf")
print(f"PDF clonado: {output}")
```

### 5.3 Implementacion de extraccion de formato

```python
# Extrae metadata de un PDF para replicar su formato
def extract_pdf_format(source_pdf: str) -> dict:
    """Extrae formato de un PDF de referencia."""
    from reportlab.lib.pagesizes import A4
    from PyPDF2 import PdfReader

    reader = PdfReader(source_pdf)
    page = reader.pages[0]

    format_data = {
        "pagesize": page.mediabox,
        "fonts": [],
        "colors": [],
        "margin_top": float(page.mediabox.top - page.mediabox.top),
        "margin_bottom": 0,
    }

    # Extraer fuentes usadas
    if "/Resources" in page:
        resources = page["/Resources"]
        if "/Font" in resources:
            for font_name in resources["/Font"]:
                format_data["fonts"].append(font_name)

    return format_data
```

---

## 6. URL-to-PDF

Renderiza una pagina web como PDF usando Playwright o Puppeteer.

### 6.1 Playwright (Recomendado)

```python
from pdf_generation import url_to_pdf

output = url_to_pdf(
    "https://example.com/report",
    "reporte_web.pdf",
    options={"format": "A4", "print_background": True}
)
```

### 6.2 Implementacion

```python
import requests
from weasyprint import HTML

def url_to_pdf_weasyprint(url: str, output_path: str) -> str:
    """Descarga HTML de una URL y lo convierte a PDF."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    HTML(string=response.content).write_pdf(output_path)
    return output_path
```

---

## 7. Encoding Japones — Troubleshooting

### Problema: caracteres no se muestran

**Sintoma:** Los caracteres japoneses aparecen como cuadritos vacios o signos de interrogacion.

**Causa:** Falta fuente CJK instalada o encoding incorrecto.

**Solucion paso a paso:**

1. **Instalar fuentes CJK** (en el sistema o en WeasyPrint):

   ```bash
   # Ubuntu/Debian
   sudo apt install fonts-noto-cjk

   # macOS
   brew install font-noto-sans-cjk

   # Windows: descargar Noto CJK desde https://www.google.com/get/noto/
   ```

2. **Usar fuentes correctas en CSS:**

   ```css
   body {
     font-family:
       'Noto Sans CJK JP',
       'Hiragino Kaku Gothic Pro',
       'Yu Gothic',
       'MS Gothic',
       sans-serif;
   }
   ```

3. **Forzar UTF-8 en WeasyPrint:**

   ```python
   HTML(string=html_content.encode("utf-8"), base_url=os.getcwd()).write_pdf(output)
   ```

4. **Configurar font-config para WeasyPrint:**

   ```bash
   # Verificar que fontconfig reconoce las fuentes
   fc-list | grep -i noto | head -5
   ```

5. **Con fpdf2, usar fuente Unicode:**

   ```python
   from fpdf import FPDF

   class PDF(FPDF):
       def __init__(self):
           super().__init__()
           self.add_font("NotoSans", "", "NotoSans-Regular.ttf", uni=True)

   pdf = PDF()
   pdf.add_page()
   pdf.set_font("NotoSans", size=12)
   pdf.cell(0, 10, "日本語のテキスト", new_x="LMARGIN", new_y="NEXT", align="L")
   ```

### Encoding en PDFs de Excel-to-PDF

```python
# Al generar HTML desde Excel, asegurar UTF-8
html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<style>{css_styles}</style>
</head><body>{content}</body></html>"""

# En WeasyPrint, pasar el string directamente (ya es UTF-8 en Python 3)
HTML(string=html).write_pdf(output)
```

---

## 8. API del Script main.py

### Funciones disponibles

```python
from pdf_generation import (
    html_to_pdf,
    excel_to_pdf,
    clone_pdf_format,
    generate_from_template,
    url_to_pdf,
)
```

### html_to_pdf

```python
def html_to_pdf(
    html_content: str,
    output_path: str,
    options: dict | None = None,
) -> str:
    """
    Convierte HTML a PDF.

    Args:
        html_content: Contenido HTML (debe incluir charset UTF-8 meta tag).
        output_path: Ruta del PDF de salida.
        options: Opciones de renderizado.
            - page_size: str (default: "A4")
            - margin_top/bottom/left/right: str (default: "20mm")
            - print_background: bool (default: True)
            - engine: str ("weasyprint", "pdfkit", "playwright")

    Returns:
        Ruta absoluta del PDF generado.
    """
```

### excel_to_pdf

```python
def excel_to_pdf(
    excel_path: str,
    output_path: str,
    sheet_name: str | None = None,
    options: dict | None = None,
) -> str:
    """
    Convierte una hoja de Excel a PDF con formato de tabla.

    Args:
        excel_path: Ruta al archivo .xlsx.
        output_path: Ruta del PDF de salida.
        sheet_name: Nombre de la hoja a convertir (None = hoja activa).
        options: Opciones de renderizado (mismo formato que html_to_pdf).

    Returns:
        Ruta absoluta del PDF generado.
    """
```

### clone_pdf_format

```python
def clone_pdf_format(
    source_pdf: str,
    data: dict,
    output_path: str,
    options: dict | None = None,
) -> str:
    """
    Genera un PDF replicando el formato de uno de referencia.

    Usa clone_format para extraer metadata del PDF de referencia
    y aplicar ese formato a los nuevos datos.

    Args:
        source_pdf: Ruta al PDF de referencia.
        data: Diccionario con los nuevos datos.
            - Expected keys: title, date, items (list[dict]),
              totals (dict), metadata (dict)
        output_path: Ruta del PDF de salida.
        options: Opciones adicionales.

    Returns:
        Ruta absoluta del PDF generado.
    """
```

### generate_from_template

```python
def generate_from_template(
    template_path: str,
    data: dict,
    output_path: str,
    jinja_env: jinja2.Environment | None = None,
    pdf_options: dict | None = None,
) -> str:
    """
    Genera PDF desde un template Jinja2.

    Args:
        template_path: Ruta al archivo .html de template.
        data: Diccionario de datos para renderizar el template.
        output_path: Ruta del PDF de salida.
        jinja_env: Environment de Jinja2 personalizado (opcional).
        pdf_options: Opciones de renderizado PDF.

    Returns:
        Ruta absoluta del PDF generado.
    """
```

### url_to_pdf

```python
def url_to_pdf(
    url: str,
    output_path: str,
    options: dict | None = None,
) -> str:
    """
    Descarga una URL y la convierte a PDF.

    Args:
        url: URL a renderizar.
        output_path: Ruta del PDF de salida.
        options:
            - engine: str ("playwright", "weasyprint", "requests")
            - format: str (default: "A4")
            - print_background: bool (default: True)
            - timeout: int (default: 30 segundos)

    Returns:
        Ruta absoluta del PDF generado.
    """
```

---

## 9. Instalacion de dependencias

```bash
# Core (siempre necesarias)
pip install weasyprint jinja2 openpyxl requests

# Para PDF programatico
pip install reportlab fpdf2

# Para URL-to-PDF con Chromium
pip install playwright
playwright install chromium

# Para PDF Clone (extraccion de metadata)
pip install PyPDF2

# Fuentes CJK (Japones)
# Ubuntu: sudo apt install fonts-noto-cjk
# Windows: descargar Noto CJK y apuntar WEEASYPRINT_FONT_CONFIG
```

---

## 10. Integracion con el ecosistema

### Desde un skill o agente

```bash
python .agent/skills-custom/pdf-generate/scripts/main.py \
    --action html-to-pdf \
    --html "<h1>Test</h1>" \
    --output test.pdf
```

### Desde Python

```python
import sys
sys.path.insert(0, ".agent/skills-custom/pdf-generate/scripts")
from pdf_generation import html_to_pdf

html = open("factura.html").read()
pdf = html_to_pdf(html, "factura.pdf")
```

### Como skill del ecosystem

Este skill puede ser invocado via:

```bash
python .agent/scripts/invoke-agent.py pdf-generate \
    --action excel-to-pdf \
    --excel data/reporte.xlsx \
    --output data/reporte.pdf \
    --sheet "2026年4月"
```

---

## 11. Referencias

- [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/)
- [reportlab User Guide](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [fpdf2 documentation](https://pyfpdf.github.io/fpdf2/)
- [Playwright PDF](https://playwright.dev/python/docs/api/class-page#page-pdf)
- [Jinja2](https://jinja.palletsprojects.com/)
- [openpyxl documentation](https://openpyxl.readthedocs.io/)
- [wkhtmltopdf](https://wkhtmltopdf.org/) — en desuso, considerar Playwright
- [Noto Fonts CJK](https://www.google.com/get/noto/) — fuente japonesa recomendada

---

*Skill creado: 2026-04-28*
*Version: 1.0.0*
*Combina: pdf-generation-patterns + jwynia/agent-skills/pdf-generator*
