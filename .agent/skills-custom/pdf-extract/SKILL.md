---
name: pdf-extract
description: Extraccion avanzada de contenido de PDFs: texto, tablas, OCR, imagenes, metadata y CLONE FORMAT (replicar formato exacto de una pagina).
category: pdf
version: "1.0.0"
author: Antigravity Ecosystem
tags: [pdf, extraction, tables, ocr, clone-format, text, images, metadata]
status: active
interface:
  inputs:
    - name: pdf_path
      type: string
      description: Ruta al archivo PDF de entrada
      required: true
    - name: page
      type: integer
      description: Numero de pagina (0-based para clone_format)
      required: false
    - name: method
      type: string
      description: Metodo de extraccion de tablas (pdfplumber, camelot, tabula)
      required: false
    - name: lang
      type: string
      description: Idiomas para OCR (ej: jpn+eng, eng, jpn)
      required: false
  outputs:
    - name: result
      type: string | list[dict] | list[bytes] | dict
      description: Contenido extraido segun el metodo elegido
---

# PDF Extract — Extraccion Avanzada de Contenido PDF

## Descripcion

Skill especializado en la **extraccion exhaustiva** de contenido de archivos PDF. A diferencia
del skill `pdf` (que cubre creacion, mergeo, forms), este se enfoca unicamente en
**leer** PDFs con capacidades avanzadas para replica de formato.

## Metodos de Extraccion Disponibles

| Metodo | Funcion | Mejor para |
|--------|---------|------------|
| `pypdf` | `extract_text()` | Texto simple, rapido |
| `pdfplumber` | `extract_tables()` | Tablas con layout complejo |
| `camelot` | `extract_tables(method='camelot')` | Tablas con bordes debilies |
| `tabula` | `extract_tables(method='tabula')` | Tablas estilo JVM |
| `pytesseract` | `extract_with_ocr()` | PDFs escaneados (imagenes) |
| `pypdf` | `extract_images()` | Imagenes embebidas |
| `pdfplumber + pypdf` | `clone_format()` |Replica de formato exacto |

---

## 1. Extraccion de Texto

### pypdf (basico, rapido)

```python
from pypdf import PdfReader

reader = PdfReader("document.pdf")
for i, page in enumerate(reader.pages):
    text = page.extract_text()
    print(f"--- Pagina {i+1} ---")
    print(text)
```

### pdfplumber (con layout preservado)

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        print(f"--- Pagina {i+1} ---")
        print(text)
```

### Extraccion de metadata

```python
from pypdf import PdfReader

reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"Titulo: {meta.title}")
print(f"Autor: {meta.author}")
print(f"Creado: {meta.creator}")
print(f"Productor: {meta.producer}")
print(f"Paginas: {len(reader.pages)}")
```

---

## 2. Extraccion de Tablas

### 2a. pdfplumber (recomendado por defecto)

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Tabla {j+1} en pagina {i+1}:")
            for row in table:
                print(row)
```

#### Parametros finos de pdfplumber

```python
with pdfplumber.open("document.pdf") as pdf:
    page = pdf.pages[0]
    # Extraccion con configuracion custom
    tables = page.extract_tables(
        table_settings={
            "vertical_strategy": "text",     # 'text' | 'lines' | 'lines_strict'
            "horizontal_strategy": "text", # 'text' | 'lines' | 'lines_strict'
            "intersection_tolerance": 5,     # pixeles de tolerancia
            "min_words_vertical": 3,         # palabras minimas para considerar columna
        }
    )
```

### 2b. Camelot (para tablas con bordes debiles)

```python
# pip install camelot-py[plot]
import camelot

tables = camelot.read_pdf("document.pdf", pages="1-end", flavor="stream")
# flavor: 'lattice' (bordes fuertes) | 'stream' (bordes debiles)
print(tables.n)
for i, table in enumerate(tables):
    df = table.df
    print(f"Tabla {i+1}:")
    print(df.head())
    # Guardar a CSV
    table.to_csv(f"table_{i}.csv")
```

### 2c. Tabula (estilo Java, JVM)

```python
# pip install tabula-py
import tabula

dfs = tabula.read_pdf("document.pdf", pages="all")
for i, df in enumerate(dfs):
    print(f"Tabla {i+1}:")
    print(df.head())
    df.to_csv(f"table_{i}.csv", index=False)
```

### 2d. pdftables (alternativa comercial, precisa)

```python
# pip install pdftables
from pdftables import get_tables
from pdftables import pdftables

with open("document.pdf", "rb") as f:
    tables = get_tables(f)
    for table in tables:
        for row in table:
            print(row)
```

### Comparativa de metodos de tablas

| Criterio | pdfplumber | Camelot stream | Camelot lattice | Tabula |
|----------|------------|----------------|-----------------|--------|
| Bordes debiles | Bueno | Excelente | Malo | Bueno |
| Bordes fuertes | Regular | Malo | Excelente | Regular |
| PDF escaneado | No | No | No | No |
| Japonés/UTF-8 | Excelente | Regular | Regular | Regular |
| Rapidez | Rapido | Medio | Medio | Medio |
| Dependencias | Ligero | Pesado | Pesado | Medio |

**Recomendacion**: empezar con `pdfplumber`, si las tablas salen mal, intentar `camelot(stream)`.

---

## 3. OCR (Tesseract)

### 3a. Setup en Windows

```powershell
# 1. Instalar Tesseract (OCR engine)
# Descargar desde: https://github.com/UB-Mannheim/tesseract/wiki
# Instalar en C:\Program Files\Tesseract-OCR\

# 2. Agregar al PATH
$env:PATH += ";C:\Program Files\Tesseract-OCR"

# 3. Instalar datos de idioma japones
# Descargar: https://github.com/tesseract-ocr/tessdata
# Copiar archivos .traineddata a C:\Program Files\Tesseract-OCR\tessdata\
# Archivos necesarios: jpn.traineddata, jpn_vert.traineddata

# 4. Instalar Python bindings
pip install pytesseract pdf2image Pillow
```

### 3b. Setup en Linux/Mac

```bash
# Instalar Tesseract
sudo apt install tesseract-ocr tesseract-ocr-jpn  # Ubuntu/Debian
brew install tesseract tesseract-lang              # macOS

# Verificar instalacion
tesseract --version
tesseract --list-langs
```

### 3c. Uso basico de OCR

```python
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

# Convertir PDF a imagenes
images = convert_from_path("scanned.pdf", dpi=300)

for i, image in enumerate(images):
    # OCR con idioma japones e ingles
    text = pytesseract.image_to_string(
        image,
        lang="jpn+eng",
        config="--psm 6"  # PSM: Page Segmentation Mode
    )
    print(f"--- Pagina {i+1} ---")
    print(text)
```

### 3d. Configuracion avanzada de PSM

```python
# PSM modes disponibles:
#  0 = Orientation and script detection (OSD) only
#  1 = Automatic page segmentation with OSD
#  3 = Fully automatic page segmentation, but no OSD (DEFAULT)
#  4 = Assume a single column of text of variable sizes
#  5 = Assume a single uniform block of vertically aligned text
#  6 = Assume a single uniform block of text
#  7 = Treat the image as a single text line
#  8 = Treat the image as a single word
#  9 = Treat the image as a single word in a circle
# 10 = Treat the image as a single character
# 11 = Sparse text. Find as much text as possible in no particular order
# 12 = Sparse text with OSD
# 13 = Raw line. Treat the image as a single text line, bypassing hacks

config = "--psm 6 --oem 3"
# OEM: OCR Engine Mode
#  0 = Legacy engine only
#  1 = Neural nets LSTM only
#  2 = Legacy + LSTM
#  3 = Default (basado en lo disponible)
```

### 3e. OCR con preprocesamiento de imagen

```python
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Mejora la imagen para OCR: escala de grises, umbralizacion, deskew."""
    img = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # Threshold binario
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Deskew (corregir rotacion)
    coords = np.column_stack(np.where(binary > 0))
    if coords.size > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 0.5:
            (h, w) = binary.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            binary = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC)
    return Image.fromarray(binary)

images = convert_from_path("scanned.pdf", dpi=400)
for image in images:
    processed = preprocess_for_ocr(image)
    text = pytesseract.image_to_string(processed, lang="jpn+eng", config="--psm 6")
    print(text)
```

### 3f. OCR con datos de layout de Tesseract

```python
import pytesseract
from pdf2image import convert_from_path

images = convert_from_path("scanned.pdf")
for image in images:
    # Obtener datos de layout completo (bounding boxes)
    data = pytesseract.image_to_data(image, lang="jpn+eng", output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data["text"]):
        if text.strip():
            print(f"'{text}' at ({data['left'][i]}, {data['top'][i]}) "
                  f"conf={data['conf'][i]} block={data['block_num'][i]}")
```

---

## 4. Extraccion de Imagenes

### 4a. pdfimages (poppler-utils, command-line)

```bash
# Extraer todas las imagenes como JPEGs
pdfimages -j document.pdf output_prefix

# Extraer como PNGs (sin compresion)
pdfimages -png document.pdf output_prefix

# Extraer solo imagenes mayores a 100x100 px
pdfimages -all -l 50 document.pdf output_prefix  # solo pagina 50
```

### 4b. pypdf (programatico)

```python
from pypdf import PdfReader
from pathlib import Path

reader = PdfReader("document.pdf")
for page_num, page in enumerate(reader.pages):
    if "/XObject" in page["/Resources"]:
        xobjects = page["/Resources"]["/XObject"].get_object()
        for obj_name, obj in xobjects.items():
            if obj.get("/Subtype") == "/Image":
                image = obj
                data = image.get_data()
                color_space = image.get("/ColorSpace", "Unknown")
                width = image.get("/Width")
                height = image.get("/Height")
                ext = "jpg" if "/DCTDecode" in image.get("/Filter", "") else "png"
                out_path = Path(f"image_p{page_num}_{obj_name}.{ext}")
                out_path.write_bytes(data)
                print(f"Extraida: {out_path} ({width}x{height}, {color_space})")
```

### 4c. PyMuPDF / fitz (mas completo)

```python
# pip install pymupdf
import fitz

doc = fitz.open("document.pdf")
for page_num in range(len(doc)):
    page = doc[page_num]
    images = page.get_images()
    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        out_path = f"image_p{page_num}_{img_index}.{image_ext}"
        with open(out_path, "wb") as f:
            f.write(image_bytes)
        print(f"Extraida: {out_path}")
doc.close()
```

---

## 5. CLONE FORMAT — Replica Exacta de Formato

Esta es la caracteristica mas avanzada. Dada una pagina de un PDF existente, extrae
**TODAS** las propiedades fisicas exactas para poder replicar su diseño.

### Que extrae clone_format()

```python
{
  "page": {
    "width_pt": 595.28,          # Ancho en puntos (1 pt = 1/72 inch)
    "height_pt": 841.89,         # Alto en puntos (A4)
    "width_mm": 210.0,            # Ancho en milimetros
    "height_mm": 297.0,           # Alto en milimetros
    "width_inch": 8.27,           # Ancho en pulgadas
    "height_inch": 11.69,         # Alto en pulgadas
    "rotation": 0,                # Rotacion en grados
  },
  "margins": {
    "left_pt": 72.0,              # Margen izquierdo
    "right_pt": 72.0,             # Margen derecho
    "top_pt": 72.0,               # Margen superior
    "bottom_pt": 72.0,            # Margen inferior
    "left_mm": 25.4,
    "right_mm": 25.4,
    "top_mm": 25.4,
    "bottom_mm": 25.4,
  },
  "fonts": [
    {
      "name": "Helvetica",
      "family": "helvetica",
      "type": "Type1",
      "size": 12,
      "size_pt": 12.0,
      "color_rgb": [0, 0, 0],
      "color_hex": "#000000",
      "is_embedded": false,
      "is_bold": false,
      "is_italic": false,
    }
  ],
  "colors": {
    "primary": [0, 0, 0],          # Color principal de texto
    "primary_hex": "#000000",
    "background": [255, 255, 255],
    "background_hex": "#FFFFFF",
    "accent": [],                  # Colores detectados en graficos
  },
  "layout": {
    "columns": 1,                  # Numero de columnas de texto
    "line_spacing": 1.2,          # Interlineado relativo
    "paragraph_spacing": 12.0,    # Espacio entre parrafos en pt
    "text_direction": "ltr",      # 'ltr' | 'rtl' | 'ttb' (vertical japones)
    "text_alignment": "left",      # 'left' | 'center' | 'right' | 'justify'
    "has_header": True,           # Hay encabezado repetido
    "has_footer": True,           # Hay pie repetido
  },
  "graphics": {
    "has_rectangles": True,
    "has_lines": True,
    "has_images": False,
    "has_annotations": False,
  },
  "metadata": {
    "title": "",
    "author": "",
    "subject": "",
    "keywords": "",
    "creator": "",
    "producer": "",
    "creation_date": "",
    "modification_date": "",
  },
  "page_numbering": {
    "style": "arabic",            # 'arabic' | 'roman' | 'letters'
    "position": "bottom-center",  # Posicion del numero de pagina
    "start": 1,                   # Numero de pagina inicial
  },
  "raw_chars": [
    {
      "text": "H",
      "x0": 72.0, "y0": 720.0,
      "x1": 79.5, "y1": 732.0,
      "font": "Helvetica",
      "size": 12,
      "color_rgb": [0, 0, 0],
    }
  ]
}
```

### Uso de clone_format()

```python
from pdf_extractor import clone_format

result = clone_format("document.pdf", page=0)
print(result["fonts"])       # Lista de fuentes usadas
print(result["colors"])      # Paleta de colores
print(result["margins"])     # Margenes exactos
print(result["layout"])       # Estructura de columnas, espaciado
```

### Como replicar el formato con reportlab

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, pt
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Usar propiedades extraidas de clone_format()
fmt = clone_format("source.pdf", page=0)

# 1. Tamaño de pagina
page_width = fmt["page"]["width_pt"]
page_height = fmt["page"]["height_pt"]

# 2. Margenes
margin_left = fmt["margins"]["left_pt"]
margin_right = fmt["margins"]["right_pt"]
margin_top = fmt["margins"]["top_pt"]
margin_bottom = fmt["margins"]["bottom_pt"]

# 3. Fuente
font_info = fmt["fonts"][0] if fmt["fonts"] else {}
font_name = font_info.get("name", "Helvetica")
font_size = font_info.get("size_pt", 12)

# 4. Color
color_hex = fmt["colors"]["primary_hex"]
text_color = HexColor(color_hex)

# Crear estilo
style = ParagraphStyle(
    name="ClonedStyle",
    fontName=font_name,
    fontSize=font_size,
    textColor=text_color,
    leading=font_size * fmt["layout"]["line_spacing"],
    alignment=TA_LEFT,
    spaceBefore=fmt["layout"]["paragraph_spacing"],
)

# Crear documento
doc = SimpleDocTemplate(
    "replica.pdf",
    pagesize=(page_width, page_height),
    leftMargin=margin_left,
    rightMargin=margin_right,
    topMargin=margin_top,
    bottomMargin=margin_bottom,
)
doc.build([Paragraph("Texto replicado con formato exacto.", style)])
```

---

## 6. CLI — Uso desde Command Line

```bash
# Extraccion de texto
python .agent/skills-custom/pdf-extract/scripts/main.py \
  --action extract_text --pdf document.pdf

# Extraccion de tablas
python .agent/skills-custom/pdf-extract/scripts/main.py \
  --action extract_tables --pdf document.pdf --method pdfplumber

# OCR
python .agent/skills-custom/pdf-extract/scripts/main.py \
  --action extract_with_ocr --pdf scanned.pdf --lang jpn+eng

# Extraccion de imagenes
python .agent/skills-custom/pdf-extract/scripts/main.py \
  --action extract_images --pdf document.pdf --output-dir ./images

# Clone format (replica de formato)
python .agent/skills-custom/pdf-extract/scripts/main.py \
  --action clone_format --pdf document.pdf --page 0 --json

#Todas las paginas como JSON
python .agent/skills-custom/pdf-extract/scripts/main.py \
  --action clone_format --pdf document.pdf --all-pages --json
```

---

## Dependencias

```bash
# Core (siempre necesario)
pip install pypdf pdfplumber

# Tablas avanzadas
pip install camelot-py[plot] tabula-py

# OCR
pip install pytesseract pdf2image Pillow opencv-python

# Extraccion de imagenes avanzada
pip install pymupdf

# Creacion de PDFs (para clone_format + replica)
pip install reportlab
```

---

## Gotchas y Limitaciones

1. **PDFs escaneados** sin texto embebido: requieren OCR obligatoriamente.
2. **Tablas sin bordes**: usar `camelot(flavor='stream')` o `pdfplumber` con `table_settings`.
3. **Caracteres japoneses**: usar `pdfplumber` (maneja UTF-8 nativamente), para OCR
   instalar `tesseract-ocr-jpn` y usar `lang="jpn"`.
4. **Imagenes como fondo**: `pdf2image` las rasteriza automaticamente.
5. **clone_format()** depende de `pdfplumber` + `pypdf` + `reportlab`. Si el PDF tiene
   fuentes embebidas cifradas,部分 de la info puede no estar disponible.
6. **Tesseract en Windows**: el path de instalacion default cambia segun version;
   verificar con `where tesseract` en PowerShell.

## Integracion con el Ecosistema

- Para **crear** PDFs con el formato extraido, usar `reportlab` (ver seccion 5).
- Para **modificar** PDFs existentes, usar `pypdf` + la guia en `.agent/skills/pdf/SKILL.md`.
- Para **rellenar forms** (PDF interactivo), ver `.agent/skills/pdf/FORMS.md`.
- Para **comparar** PDFs (diff visual), usar `pdfdiff` o PyMuPDF.
