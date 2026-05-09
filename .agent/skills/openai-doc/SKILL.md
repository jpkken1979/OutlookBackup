---
name: openai-doc
description: "Crea y edita documentos DOCX profesionales con python-docx. Pipeline de rendering con LibreOffice + pdftoppm. Incluye render_docx.py helper."
type: feature
---

# DOCX Document Creator

Crea y edita documentos Word (.docx) profesionales con pipeline de rendering integrado.

## Stack

- **python-docx** — Creación y edición programática de documentos
- **LibreOffice (soffice)** — Conversión DOCX → PDF
- **pdftoppm** — PDF → imágenes para preview/verificación

## Workflow

1. **Definir estructura** — Secciones, headings, contenido esperado.
2. **Crear documento** — Usar python-docx para generar el DOCX.
3. **Render preview** — Convertir a PDF/imagen para validación visual.
4. **Iterar** — Ajustar formato y contenido hasta calidad deseada.
5. **Entregar** — Documento client-ready.

## Script render_docx.py

```python
#!/usr/bin/env python3
"""Renderiza DOCX a PDF e imagen para preview."""

import subprocess
import shlex
from pathlib import Path

def render_docx(input_path: str, output_dir: str = "output") -> dict[str, str]:
    """Convierte DOCX a PDF y genera preview PNG.

    Args:
        input_path: Ruta al archivo .docx
        output_dir: Directorio de salida

    Returns:
        Dict con rutas a PDF y PNG generados.
    """
    input_file = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # DOCX → PDF via LibreOffice
    cmd_pdf = f"soffice --headless --convert-to pdf --outdir {out} {input_file}"
    subprocess.run(shlex.split(cmd_pdf), shell=False, check=True)

    pdf_path = out / f"{input_file.stem}.pdf"

    # PDF → PNG via pdftoppm
    png_prefix = out / input_file.stem
    cmd_png = f"pdftoppm -png -r 150 {pdf_path} {png_prefix}"
    subprocess.run(shlex.split(cmd_png), shell=False, check=True)

    return {
        "pdf": str(pdf_path),
        "png": str(png_prefix) + "-1.png"
    }
```

## Ejemplo de Creación

```python
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# Estilo del título
title = doc.add_heading("Quarterly Report", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Metadata
doc.add_paragraph("Prepared by: Engineering Team")
doc.add_paragraph("Date: March 2026")
doc.add_page_break()

# Tabla de contenidos (placeholder)
doc.add_heading("Table of Contents", level=1)
doc.add_paragraph("1. Executive Summary")
doc.add_paragraph("2. Key Metrics")
doc.add_paragraph("3. Recommendations")
doc.add_page_break()

# Contenido
doc.add_heading("1. Executive Summary", level=1)
doc.add_paragraph(
    "This report summarizes the key achievements and metrics "
    "for Q1 2026, highlighting areas of growth and improvement."
)

# Tabla
doc.add_heading("2. Key Metrics", level=1)
table = doc.add_table(rows=4, cols=3, style="Light Grid Accent 1")
headers = table.rows[0].cells
headers[0].text = "Metric"
headers[1].text = "Target"
headers[2].text = "Actual"

data = [
    ("Revenue", "$1M", "$1.2M"),
    ("Users", "10K", "12.5K"),
    ("Uptime", "99.9%", "99.95%"),
]
for i, (metric, target, actual) in enumerate(data, 1):
    row = table.rows[i].cells
    row[0].text = metric
    row[1].text = target
    row[2].text = actual

# Guardar
doc.save("quarterly_report.docx")
```

## Quality Expectations

Los documentos deben ser **client-ready**:
- Formato consistente (fuentes, espaciado, márgenes)
- Headers numerados para navegación
- Tablas con estilo profesional
- Imágenes con caption cuando aplique
- Page breaks entre secciones principales
- Footer con numeración de páginas

## Dependencias

```bash
pip install python-docx

# Para rendering (Linux/macOS)
apt-get install libreoffice poppler-utils

# Para rendering (Windows)
# Instalar LibreOffice + poppler manualmente
```

## Recursos

- [python-docx Documentation](https://python-docx.readthedocs.io/)
- [LibreOffice CLI](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)
