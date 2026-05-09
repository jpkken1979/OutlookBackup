---
name: pdf-canvas
description: >
  Guia canonica del ecosistema para todo lo relacionado con PDF:
  leer, extraer texto/tablas, combinar, split, rotar, watermarks,
  crear, forms, encrypt, extraer images, OCR.
  Usar cuando el usuario mencione archivos .pdf o pida generar uno.
license: MIT
trigger: pdf, documento, pdf form, ocr, watermark, merge pdf, split pdf
---

# PDF Canvas — Guia Canonica del Ecosistema Antigravity

> Guia unificada para todas las operaciones PDF en el ecosistema.
> Fuente base: anthropics/skills@pdf (86.5K installs) + extensiones propias.

## Indice

1. [Overview de Capacidades](#1-overview-de-capacidades)
2. [Quick Start — pypdf](#2-quick-start--pypdf)
3. [Extraer Texto](#3-extraer-texto)
4. [Extraer Tablas](#4-extraer-tablas)
5. [Combinar / Merge PDFs](#5-combinar--merge-pdfs)
6. [Split PDFs](#6-split-pdfs)
7. [Rotar Paginas](#7-rotar-paginas)
8. [Watermarks](#8-watermarks)
9. [Crear PDFs desde cero](#9-crear-pdfs-desde-cero)
10. [Rellenar PDF Forms](#10-rellenar-pdf-forms)
11. [Encrypt / Decrypt](#11-encrypt--decrypt)
12. [Extraer Imagenes](#12-extraer-imagenes)
13. [OCR en PDFs escaneados](#13-ocr-en-pdfs-escaneados)
14. [Referencia de Herramientas Externas](#14-referencia-de-herramientas-externas)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Overview de Capacidades

| Operacion | Libreria Preferida | Alternativa CLI |
|---|---|---|
| Leer metadata | `pypdf` | `qpdf --show-all-pages` |
| Extraer texto | `pdfplumber` | `pdftotext` (poppler) |
| Extraer tablas | `pdfplumber` | `camelot`, `tabula` |
| Combinar PDFs | `pypdf` | `qpdf`, `pdftk` |
| Split PDFs | `pypdf` | `qpdf --split-pages` |
| Rotar paginas | `pypdf` | `qpdf --rotate` |
| Watermarks | `pypdf` | `qpdf` |
| Crear PDFs | `reportlab` | — |
| Rellenar forms | `pypdf` (fillable) / annotaciones (no-fillable) | — |
| Encrypt / Decrypt | `pypdf` | `qpdf --encrypt`, `qpdf --decrypt` |
| Extraer imagenes | `pdfimages` (CLI) | `pypdf` o `pypdfium2` |
| OCR escaneados | `pytesseract` + `pdf2image` | `pdftotext` con OCR |
| Render a imagenes | `pypdfium2` | `pdftoppm`, `convert` (ImageMagick) |

### Dependencias Python

```bash
pip install pypdf pdfplumber reportlab pypdfium2 pdf2image Pillow pandas
pip install pytesseract  # requiere tesseract-ocr en el sistema
pip install camelot-py tabula-py  # opcional para tablas complejas
```

---

## 2. Quick Start — pypdf

```python
from pypdf import PdfReader, PdfWriter

# Leer
reader = PdfReader("document.pdf")
print(f"Paginas: {len(reader.pages)}")

# Extraer texto
text = ""
for page in reader.pages:
    text += page.extract_text() or ""

# Metadata
meta = reader.metadata
print(f"Titulo: {meta.title}")
print(f"Autor: {meta.author}")

# Escribir
writer = PdfWriter()
writer.add_page(reader.pages[0])
with open("output.pdf", "wb") as f:
    writer.write(f)
```

---

## 3. Extraer Texto

### 3.1 pdfplumber (recomendado — respeta layout)

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages, 1):
        texto = page.extract_text()
        print(f"Pagina {i}: {texto[:200]}...")
```

### 3.2 pypdf (baseline)

```python
from pypdf import PdfReader

reader = PdfReader("document.pdf")
for i, page in enumerate(reader.pages, 1):
    texto = page.extract_text()
    if texto:
        print(f"Pagina {i}: {texto[:200]}")
```

### 3.3 pypdfium2 (rapido, render + texto)

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("document.pdf")
for i, page in enumerate(pdf):
    texto = page.get_text()
    print(f"Pagina {i}: {texto[:200]}")
```

### 3.4 CLI — pdftotext

```bash
# Texto plano
pdftotext input.pdf output.txt

# Preserva layout
pdftotext -layout input.pdf output.txt

# Paginas 1 a 5
pdftotext -f 1 -l 5 input.pdf output.txt
```

---

## 4. Extraer Tablas

### 4.1 pdfplumber (recomendado)

```python
import pdfplumber
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    todas_tablas = []
    for i, page in enumerate(pdf.pages, 1):
        tablas = page.extract_tables()
        for j, tabla in enumerate(tablas):
            if tabla:
                df = pd.DataFrame(tabla[1:], columns=tabla[0])
                df["_pagina"] = i
                df["_tabla"] = j + 1
                todas_tablas.append(df)

if todas_tablas:
    combinada = pd.concat(todas_tablas, ignore_index=True)
    combinada.to_excel("tablas_extraidas.xlsx", index=False)
    print(f"Extraidas {len(todas_tablas)} tablas")
```

### 4.2 pdfplumber — Configuracion avanzada

```python
table_settings = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "intersection_tolerance": 15,
}
tablas = page.extract_tables(table_settings)

# Debug visual
img = page.to_image(resolution=150)
img.save("debug_layout.png")
```

### 4.3 camelot (tablas muy complejas)

```bash
pip install camelot-py
```

```python
import camelot

tablas = camelot.read_pdf("document.pdf", pages="1-end", flavor="stream")
# o para tablas con bordes definidos:
tablas = camelot.read_pdf("document.pdf", pages="1", flavor="lattice")

tablas.export("tablas.json", f="json")
tablas[0].df.to_csv("tabla_1.csv")
```

---

## 5. Combinar / Merge PDFs

### 5.1 pypdf

```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

### 5.2 qpdf (CLI)

```bash
qpdf --empty --pages doc1.pdf doc2.pdf doc3.pdf -- merged.pdf

# Paginas especificas de cada archivo
qpdf --empty --pages doc1.pdf 1-3 doc2.pdf 5 doc3.pdf 2,4 -- combined.pdf
```

### 5.3 pdftk (si disponible)

```bash
pdftk doc1.pdf doc2.pdf cat output merged.pdf
```

---

## 6. Split PDFs

### 6.1 pypdf — Una pagina por archivo

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"pagina_{i+1}.pdf", "wb") as out:
        writer.write(out)
```

### 6.2 pypdf — Rangos personalizados

```python
def split_pdf(input_path: str, ranges: list[tuple[int, int]], output_prefix: str):
    """Separa un PDF en grupos de paginas.

    Args:
        input_path: Ruta al PDF de entrada.
        ranges: Lista de tuplas (inicio, fin) pagina (1-based).
        output_prefix: Prefijo para archivos de salida.
    """
    reader = PdfReader(input_path)
    total = len(reader.pages)
    for idx, (start, end) in enumerate(ranges, 1):
        writer = PdfWriter()
        for page_num in range(start - 1, min(end, total)):
            writer.add_page(reader.pages[page_num])
        with open(f"{output_prefix}_{idx}.pdf", "wb") as out:
            writer.write(out)
```

### 6.3 qpdf (CLI)

```bash
# Split en grupos de N paginas
qpdf --split-pages=3 input.pdf output_%02d.pdf

# Paginas 1-5 en un archivo
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
```

---

## 7. Rotar Paginas

### 7.1 pypdf

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for i, page in enumerate(reader.pages):
    if i == 0:
        page.rotate(90)  # 90 grados clockwise
    writer.add_page(page)

with open("rotated.pdf", "wb") as out:
    writer.write(out)
```

### 7.2 qpdf (CLI)

```bash
# Rotar pagina 1 +90 grados
qpdf input.pdf output.pdf --rotate=+90:1

# Todas las paginas -90 grados (counter-clockwise)
qpdf input.pdf output.pdf --rotate=-90
```

---

## 8. Watermarks

### 8.1 Watermark de otra pagina PDF (pypdf)

```python
from pypdf import PdfReader, PdfWriter

watermark_page = PdfReader("watermark.pdf").pages[0]
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark_page)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as out:
    writer.write(out)
```

### 8.2 Watermark de texto con reportlab

```python
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

def crear_watermark_texto(texto: str) -> PdfReader:
    """Crea una pagina PDF con texto de watermark."""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    c.saveState()
    c.setFont("Helvetica-Bold", 60)
    c.setFillColorRGB(0.8, 0.8, 0.8, alpha=0.3)
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, texto)
    c.restoreState()
    c.save()
    packet.seek(0)
    return PdfReader(packet)

reader = PdfReader("document.pdf")
wm_page = crear_watermark_texto("CONFIDENCIAL").pages[0]
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(wm_page)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as out:
    writer.write(out)
```

---

## 9. Crear PDFs desde cero

### 9.1 reportlab — Canvas (bajo nivel)

```python
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter

c.drawString(100, height - 100, "Titulo del Documento")
c.drawString(100, height - 120, "Subtitulo")
c.line(100, height - 140, 400, height - 140)
c.save()
```

### 9.2 reportlab — Platypus (alto nivel, paragraphs)

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

# Titulo
story.append(Paragraph("Titulo del Informe", styles["Title"]))
story.append(Spacer(1, 12))

# Cuerpo
story.append(Paragraph("Contenido del documento. " * 20, styles["Normal"]))
story.append(PageBreak())

# Pagina 2
story.append(Paragraph("Pagina 2", styles["Heading1"]))
story.append(Paragraph("Mas contenido.", styles["Normal"]))

# Tabla
data = [["Producto", "Cantidad", "Precio"], ["Widget", "10", "$100"], ["Gadget", "5", "$75"]]
tabla = Table(data)
tabla.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 1, colors.black),
]))
story.append(tabla)

doc.build(story)
```

### 9.3 Subindices y superindices (ATENCION)

> **NUNCA usar caracteres Unicode subscript/superscript** (₀₁₂₃, ⁰¹²³) en ReportLab
> con fuentes built-in — renderizan como cuadros negros.

Usar tags XML de ReportLab:

```python
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()
# Subscript
chemical = Paragraph("H<sub>2</sub>O", styles["Normal"])
# Superscript
squared = Paragraph("x<super>2</super> + y<super>2</super>", styles["Normal"])
```

---

## 10. Rellenar PDF Forms

### Paso 0: Detectar tipo de form

```python
import subprocess, shlex, sys

# Ejecutar detector de fillable fields
result = subprocess.run(
    shlex.split("python scripts/check_fillable_fields.py input.pdf"),
    shell=False, capture_output=True, text=True
)
print(result.stdout)
# "This PDF has fillable form fields"  -> usar seccion 10.1
# "This PDF does not have fillable form fields" -> usar seccion 10.2
```

### 10.1 PDF con campos fillable

**Script disponible**: `scripts/fill_fillable_fields.py` (del skill base)

Flujo completo:

```bash
# 1. Extraer info de campos fillable
python scripts/extract_form_field_info.py input.pdf fields_info.json

# 2. Convertir a imagenes para inspeccion visual
python scripts/convert_pdf_to_images.py input.pdf images_dir/

# 3. Crear field_values.json
cat > field_values.json << 'EOF'
[
  {"field_id": "last_name", "page": 1, "value": "Simpson"},
  {"field_id": "Checkbox12", "page": 1, "value": "/On"}
]
EOF

# 4. Rellenar
python scripts/fill_fillable_fields.py input.pdf field_values.json output.pdf
```

**Estructura de field_values.json**:

```json
[
  {
    "field_id": "nombre_campo",
    "description": "Descripcion del campo",
    "page": 1,
    "value": "Valor a ingresar"
  },
  {
    "field_id": "Checkbox1",
    "page": 1,
    "value": "/On"
  }
]
```

### 10.2 PDF sin campos fillable (annotaciones)

**Scripts disponibles**: `scripts/extract_form_structure.py`, `scripts/fill_pdf_form_with_annotations.py`

Flujo completo:

```bash
# 1. Extraer estructura (labels, lineas, checkboxes)
python scripts/extract_form_structure.py input.pdf structure.json

# 2. Convertir a imagenes
python scripts/convert_pdf_to_images.py input.pdf images/

# 3. Analizar visualmente images/ y crear fields.json
# Ver seccion 10.2.1 abajo

# 4. Validar bounding boxes
python scripts/check_bounding_boxes.py fields.json

# 5. Rellenar con annotations
python scripts/fill_pdf_form_with_annotations.py input.pdf fields.json output.pdf

# 6. Verificar
python scripts/convert_pdf_to_images.py output.pdf verify_images/
```

#### 10.2.1 Crear fields.json

**Coordenadas PDF** (si extraccion estructural funciono):

```json
{
  "pages": [
    {"page_number": 1, "pdf_width": 612, "pdf_height": 792}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "Campo nombre",
      "field_label": "Nombre",
      "label_bounding_box": [43, 63, 87, 73],
      "entry_bounding_box": [92, 63, 260, 79],
      "entry_text": {"text": "Kaneshiro", "font_size": 10}
    },
    {
      "page_number": 1,
      "description": "Checkbox si/no",
      "field_label": "Si",
      "label_bounding_box": [260, 200, 280, 210],
      "entry_bounding_box": [285, 197, 292, 205],
      "entry_text": {"text": "X", "font_size": 8}
    }
  ]
}
```

**Coordenadas imagen** (si es PDF escaneado):

```json
{
  "pages": [
    {"page_number": 1, "image_width": 1700, "image_height": 2200}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "Nombre",
      "field_label": "Nombre",
      "label_bounding_box": [120, 175, 242, 198],
      "entry_bounding_box": [255, 175, 720, 218],
      "entry_text": {"text": "Kaneshiro", "font_size": 10}
    }
  ]
}
```

> **Conversion imagen -> PDF**: `pdf_x = img_x * (pdf_w / img_w)`
> **Sistema coordenadas imagen**: y=0 en TOP; en PDF y=0 en BOTTOM.

#### 10.2.2 Hybrid Approach

Cuando la extraccion estructural encuentra labels pero no todos los campos:

1. Usar Approach A para campos detectados
2. Usar zoom ImageMagick para campos no detectados
3. Combinar coordenadas (convertir a PDF si es necesario)
4. Crear un solo `fields.json` con `pdf_width`/`pdf_height`

Refinamiento visual con ImageMagick:

```bash
# Zoom a una region para precision
magick images/page_1.png -crop 300x80+50+120 +repage crops/nombre_campo.png
# coords en crop: crop_x + offset = coords globales
```

---

## 11. Encrypt / Decrypt

### 11.1 pypdf — Encriptar

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# user_password: para abrir el PDF
# owner_password: para permisos administrativos
writer.encrypt("userpassword", "ownerpassword")

with open("encrypted.pdf", "wb") as out:
    writer.write(out)
```

### 11.2 pypdf — Desencriptar

```python
from pypdf import PdfReader

reader = PdfReader("encrypted.pdf")
if reader.is_encrypted:
    reader.decrypt("userpassword")

writer = PdfWriter()
for page in reader.pages:
    writer.add_page(page)

with open("decrypted.pdf", "wb") as out:
    writer.write(out)
```

### 11.3 qpdf (CLI)

```bash
# Desencriptar
qpdf --password=mypass --decrypt encrypted.pdf decrypted.pdf

# Encriptar con permisos
qpdf --encrypt userpass ownerpass 256 \
  --print=none --modify=none -- annotations.pdf encrypted.pdf

# Ver estado de encriptacion
qpdf --show-encryption encrypted.pdf
```

---

## 12. Extraer Imagenes

### 12.1 pdfimages (CLI — rapido)

```bash
# Extraer todas como JPEG
pdfimages -j input.pdf output_prefix

# Lista info sin extraer
pdfimages -list input.pdf

# Extraer en formato original
pdfimages -all input.pdf images/img

# JPEG calidad maxima
pdfimages -j -l 95 input.pdf output_prefix
```

### 12.2 pypdfium2 (Python)

```python
import pypdfium2 as pdfium
from PIL import Image

def pdf_a_imagenes(pdf_path: str, output_dir: str, scale: float = 2.0):
    """Renderiza cada pagina de un PDF a imagen PNG.

    Args:
        pdf_path: Ruta al PDF.
        output_dir: Directorio donde guardar las imagenes.
        scale: Escala de renderizado (2.0 = alta resolucion).
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    pdf = pdfium.PdfDocument(pdf_path)
    for i, page in enumerate(pdf):
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        img.save(f"{output_dir}/page_{i+1}.png", "PNG")
        print(f"Pagina {i+1}: {img.size}")

pdf_a_imagenes("document.pdf", "imagenes/", scale=2.0)
```

### 12.3 Extraccion de figuras (render + process)

```python
import pypdfium2 as pdfium
import numpy as np

def detectar_figuras(pdf_path: str, output_dir: str, threshold: int = 240):
    """Detecta regiones no-blancas en paginas PDF (figuras/tablas).

    Args:
        pdf_path: Ruta al PDF.
        output_dir: Directorio de salida.
        threshold: Valor de corte para blanco (0-255).
    """
    import os, cv2
    os.makedirs(output_dir, exist_ok=True)

    pdf = pdfium.PdfDocument(pdf_path)
    for i, page in enumerate(pdf):
        bitmap = page.render(scale=1.0)
        img = np.array(bitmap.to_pil())

        # Mask de regiones no-blancas
        gris = np.mean(img[:, :, :3], axis=2) if img.ndim == 3 else img
        mask = gris < threshold
        coords = np.argwhere(mask)

        if coords.size > 0:
            y0, x0 = coords.min(axis=0)
            y1, x1 = coords.max(axis=0) + 1
            figura = img[y0:y1, x0:x1]
            cv2.imwrite(f"{output_dir}/figura_pagina_{i+1}.png", figura[:, :, ::-1])
            print(f"Pagina {i+1}: figura detectada ({x1-x0}x{y1-y0})")
```

---

## 13. OCR en PDFs escaneados

### 13.1 pytesseract + pdf2image

```python
import pytesseract
from pdf2image import convert_from_path

def ocr_pdf(pdf_path: str, lang: str = "jpn+eng", dpi: int = 300) -> str:
    """Extrae texto de PDF escaneado usando OCR.

    Args:
        pdf_path: Ruta al PDF escaneado.
        lang: Idiomas de tesseract (jpn+eng para japones + ingles).
        dpi: Resolucion de conversion (mayor = mejor OCR, mas lento).

    Returns:
        Texto extraido de todo el PDF.
    """
    imagenes = convert_from_path(pdf_path, dpi=dpi)
    texto_total = ""

    for i, img in enumerate(imagenes, 1):
        texto_pagina = pytesseract.image_to_string(img, lang=lang)
        texto_total += f"\n--- Pagina {i} ---\n{texto_pagina}"

    return texto_total

# Uso
texto = ocr_pdf("scanned.pdf", lang="jpn+eng")
print(texto)
```

### 13.2 PDF a texto con OCR desde CLI

```bash
# Requiere tesseract-ocr instalado en el sistema
pdftoppm -png -r 300 scanned.pdf pagina
for img in pagina-*.png; do
    tesseract "$img" stdout -l jpn+eng >> resultado.txt
done
```

### 13.3 Render + OCR con pypdfium2

```python
import pytesseract
import pypdfium2 as pdfium

def ocr_render(pdf_path: str) -> str:
    """OCR via render con pypdfium2 (mas control que pdf2image)."""
    pdf = pdfium.PdfDocument(pdf_path)
    resultado = []
    for i, page in enumerate(pdf):
        bitmap = page.render(scale=2.0)
        img = bitmap.to_pil()
        texto = pytesseract.image_to_string(img, lang="eng")
        resultado.append(f"Pagina {i+1}: {texto[:100]}...")
    return "\n".join(resultado)
```

---

## 14. Referencia de Herramientas Externas

### Python

| Libreria | Proposito | License | Install |
|---|---|---|---|
| `pypdf` | Lectura, escritura, merge, split, rotate, encrypt | BSD | `pip install pypdf` |
| `pdfplumber` | Texto y tablas con layout | MIT | `pip install pdfplumber` |
| `reportlab` | Crear PDFs desde cero | BSD | `pip install reportlab` |
| `pypdfium2` | Render a imagenes, rapido | Apache/BSD | `pip install pypdfium2` |
| `pdf2image` | Convertir PDF a PIL Images | BSD | `pip install pdf2image` |
| `Pillow` | Manipulacion de imagenes | HPND | `pip install Pillow` |
| `pytesseract` | OCR wrapper | Apache | `pip install pytesseract` |
| `camelot` | Extraccion de tablas compleja | MIT | `pip install camelot-py` |
| `tabula` | Extraccion de tablas Java-based | MIT | `pip install tabula-py` |
| `pandas` | Dataframes para tablas | BSD | `pip install pandas` |

### CLI (requieren instalacion en sistema)

| Herramienta | Proposito | Paquete |
|---|---|---|
| `pdftotext` | Extraer texto | `poppler-utils` |
| `pdfimages` | Extraer imagenes | `poppler-utils` |
| `pdftoppm` | PDF a imagenes | `poppler-utils` |
| `qpdf` | Manipulacion avanzada, encriptar | `qpdf` |
| `pdftk` | Merge, split, rotate | `pdftk-java` o `pdftk` |
| `tesseract` | OCR engine | `tesseract-ocr` |
| `magick` | ImageMagick para crops/zoom | `ImageMagick` |

### JavaScript

| Libreria | Proposito | License |
|---|---|---|
| `pdf-lib` | Crear/modificar PDFs en Node/browser | MIT |
| `pdfjs-dist` | Render PDFs en browser | Apache |

---

## 15. Troubleshooting

### 15.1 PDF encriptado

```python
from pypdf import PdfReader

try:
    reader = PdfReader("encrypted.pdf")
    if reader.is_encrypted:
        resultado = reader.decrypt("password")
        print(f"Decrypt result: {resultado}")
except Exception as e:
    print(f"Fallo: {e}")
```

### 15.2 PDF corrupto

```bash
# Verificar con qpdf
qpdf --check damaged.pdf

# Reparar
qpdf --check damaged.pdf > repair.log 2>&1
qpdf damaged.pdf --fix-qdf repaired.pdf
```

### 15.3 OCR en japones

```python
# Instalar tesseract japones
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Idioma: jpn, jpn_vert

import pytesseract
from PIL import Image

img = Image.open("pagina.png")
texto = pytesseract.image_to_string(img, lang="jpn+eng")
print(texto)
```

### 15.4 Coordenadas en PDF vs Imagen

```
Sistema              | Origen Y | Uso tipico
---------------------|----------|-------------------------------
PDF (pypdf)          | Bottom   | Rotaciones, crop, forms
PDF (reportlab)      | Bottom   | Crear PDFs
pdfplumber           | Top      | Extraccion de texto/tablas
Imagen (PIL/numpy)   | Top      | OCR, manipulacion
```

Conversion imagen -> PDF (origen Y invertido):

```python
def imagen_a_pdf_coords(bbox, img_h, pdf_h):
    """Convierte [x0, y0, x1, y1] (origen top) a [l, b, r, t] (origen bottom)."""
    return [
        bbox[0],
        pdf_h - bbox[3],   # bottom = pdf_h - top_de_imagen
        bbox[2],
        pdf_h - bbox[1],   # top = pdf_h - bottom_de_imagen
    ]
```

### 15.5 PDF grande — procesamiento por chunks

```python
from pypdf import PdfReader, PdfWriter

def procesar_chunk(input_path: str, chunk_size: int = 10):
    reader = PdfReader(input_path)
    total = len(reader.pages)
    for inicio in range(0, total, chunk_size):
        fin = min(inicio + chunk_size, total)
        writer = PdfWriter()
        for i in range(inicio, fin):
            writer.add_page(reader.pages[i])
        with open(f"chunk_{inicio // chunk_size}.pdf", "wb") as out:
            writer.write(out)
        print(f"Chunk {inicio // chunk_size}: paginas {inicio+1}-{fin}")
```

### 15.6 Performance

| Operacion | Recomendacion |
|---|---|
| Texto de PDFs grandes | `pdftotext -bbox-layout` o pdfplumber |
| Tablas complejas | `camelot` con `flavor="lattice"` |
| Imagenes | `pdfimages` (CLI) es mas rapido que render Python |
| Forms fillable | Validar campos con `check_fillable_fields.py` antes de procesar |
| Render a imagen | `pypdfium2` con `scale=2.0` para balance velocidad/calidad |

### 15.7 Error comun: fuente no embebida

Si al crear PDF con reportlab aparecen simbolos faltantes:

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Registrar fuente con glifos japoneses si es necesario
pdfmetrics.registerFont(TTFont("NotoSansJP", "NotoSansJP-Regular.ttf"))
```

---

## Quick Reference Card

```
| Tarea                  | Tool            | Command / Code                        |
|------------------------|-----------------|---------------------------------------|
| Leer metadata          | pypdf           | reader.metadata                        |
| Extraer texto          | pdfplumber      | page.extract_text()                    |
| Extraer tablas         | pdfplumber      | page.extract_tables()                  |
| Merge PDFs             | pypdf / qpdf    | writer.add_page() / qpdf --empty       |
| Split por pagina       | pypdf           | for page in reader.pages               |
| Rotar                  | pypdf / qpdf    | page.rotate(90) / qpdf --rotate        |
| Watermark              | pypdf           | page.merge_page(watermark_page)        |
| Crear PDF              | reportlab       | canvas.Canvas() / SimpleDocTemplate() |
| Fill forms fillable    | pypdf           | writer.update_page_form_field_values() |
| Fill forms annotacion  | pypdf annot     | FreeText() + add_annotation()           |
| Encrypt                | pypdf / qpdf    | writer.encrypt() / qpdf --encrypt      |
| Decrypt                | pypdf / qpdf    | reader.decrypt() / qpdf --decrypt      |
| Extraer imagenes       | pdfimages       | pdfimages -j input.pdf out_            |
| OCR escaneado          | pytesseract     | image_to_string() sobre convert_from_path |
| Render a imagen        | pypdfium2       | page.render(scale=2.0).to_pil()         |
```
