Procesar archivos PDF: leer, extraer texto/tablas, combinar, dividir, rotar, crear, OCR, watermark, encriptar.

## Librerías Python

| Tarea | Librería | Uso |
|---|---|---|
| Merge/Split/Rotar | `pypdf` | `PdfReader`, `PdfWriter` |
| Extraer texto | `pdfplumber` | `page.extract_text()` |
| Extraer tablas | `pdfplumber` | `page.extract_tables()` |
| Crear PDFs | `reportlab` | Canvas o Platypus |
| OCR (scanned) | `pytesseract` + `pdf2image` | Convertir a imagen primero |
| Formularios | `pypdf` o `pdf-lib` | Ver FORMS.md del skill |

## Ejemplo rápido

```python
from pypdf import PdfReader
reader = PdfReader("documento.pdf")
for page in reader.pages:
    print(page.extract_text())
```

## Referencia completa

Ver `.agent/skills/pdf/SKILL.md` para ejemplos detallados de cada operación.

## Nota importante

Nunca usar caracteres Unicode de subíndice/superíndice (₀₁₂₃) en ReportLab — usar tags `<sub>` y `<super>` en Paragraph.
