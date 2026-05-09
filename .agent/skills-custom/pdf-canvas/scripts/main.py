"""
pdf-canvas — Entry point para operaciones PDF.

Funciones clave del ecosystem Antigravity para:
    - extraer texto y tablas
    - combinar / split / rotar
    - watermarks
    - creacion
    - forms fillable y annotation-based
    - encrypt / decrypt
    - extraccion de imagenes
    - OCR

Requiere:
    pip install pypdf pdfplumber reportlab pypdfium2 pdf2image Pillow pandas pytesseract
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Optional

import pdfplumber
import pandas as pd
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def get_metadata(pdf_path: str) -> dict[str, str | None]:
    """Extrae metadata de un PDF.

    Args:
        pdf_path: Ruta al archivo PDF.

    Returns:
        Diccionario con titulo, autor, subject, creator, producer,
        y numero de paginas.
    """
    reader = PdfReader(pdf_path)
    meta = reader.metadata or {}
    return {
        "titulo": meta.get("/Title"),
        "autor": meta.get("/Author"),
        "subject": meta.get("/Subject"),
        "creator": meta.get("/Creator"),
        "producer": meta.get("/Producer"),
        "paginas": len(reader.pages),
        "encriptado": reader.is_encrypted,
    }


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------

def extract_text_plumber(
    pdf_path: str,
    pages: list[int] | None = None,
) -> str:
    """Extrae texto de un PDF usando pdfplumber (respeta layout).

    Args:
        pdf_path: Ruta al PDF.
        pages: Lista de paginas 1-based a procesar. Si None, todas.

    Returns:
        Texto concatenado del PDF.
    """
    fragmentos: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        paginas_a_procesar = pages or range(1, len(pdf.pages) + 1)
        for i in paginas_a_procesar:
            if 1 <= i <= len(pdf.pages):
                texto = pdf.pages[i - 1].extract_text() or ""
                fragmentos.append(f"--- Pagina {i} ---\n{texto}")
    logger.info("Extraido texto de %d paginas: %s", len(paginas_a_procesar), pdf_path)
    return "\n\n".join(fragmentos)


def extract_text_pypdf(pdf_path: str) -> str:
    """Extrae texto de un PDF usando pypdf (baseline).

    Args:
        pdf_path: Ruta al PDF.

    Returns:
        Texto completo del PDF.
    """
    reader = PdfReader(pdf_path)
    fragmentos: list[str] = []
    for i, page in enumerate(reader.pages, 1):
        texto = page.extract_text() or ""
        fragmentos.append(f"--- Pagina {i} ---\n{texto}")
    return "\n\n".join(fragmentos)


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------

def extract_tables(
    pdf_path: str,
    output_excel: str | None = None,
    table_settings: dict | None = None,
) -> list[pd.DataFrame]:
    """Extrae tablas de un PDF usando pdfplumber.

    Args:
        pdf_path: Ruta al PDF.
        output_excel: Ruta opcional para escribir Excel consolidado.
        table_settings: Config de extraccion de pdfplumber
            (vertical_strategy, horizontal_strategy, etc.).

    Returns:
        Lista de DataFrames, uno por tabla encontrada.
    """
    tablas: list[pd.DataFrame] = []
    defaults = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "intersection_tolerance": 15,
    }
    cfg = {**defaults, **(table_settings or {})}

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            detectadas = page.extract_tables(cfg) if table_settings else page.extract_tables()
            for j, tabla in enumerate(detectadas or [], 1):
                if tabla and len(tabla) > 1:
                    df = pd.DataFrame(tabla[1:], columns=tabla[0])
                    df["_pagina"] = i
                    df["_tabla"] = j
                    tablas.append(df)

    if output_excel and tablas:
        pd.concat(tablas, ignore_index=True).to_excel(output_excel, index=False)
        logger.info("Tablas guardadas en %s", output_excel)

    logger.info("Extraidas %d tablas de %s", len(tablas), pdf_path)
    return tablas


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_pdfs(pdf_paths: list[str], output_path: str) -> None:
    """Combina multiples PDFs en uno solo.

    Args:
        pdf_paths: Lista de rutas de PDFs a combinar (en orden).
        output_path: Ruta del PDF de salida.
    """
    writer = PdfWriter()
    total_paginas = 0
    for pdf_path in pdf_paths:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)
        total_paginas += len(reader.pages)
        logger.debug("Agregado %s: %d paginas", pdf_path, len(reader.pages))

    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("Merge completo: %d PDFs -> %s (%d paginas)", len(pdf_paths), output_path, total_paginas)


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split_pdf_by_page(input_path: str, output_dir: str) -> list[str]:
    """Separa un PDF en archivos de una pagina.

    Args:
        input_path: Ruta al PDF de entrada.
        output_dir: Directorio donde se guardan los archivos de salida.

    Returns:
        Lista de rutas de los PDFs generados.
    """
    os.makedirs(output_dir, exist_ok=True)
    reader = PdfReader(input_path)
    base = Path(input_path).stem
    salidas: list[str] = []

    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        out_path = os.path.join(output_dir, f"{base}_pagina_{i+1}.pdf")
        with open(out_path, "wb") as out:
            writer.write(out)
        salidas.append(out_path)

    logger.info("Split completo: %s -> %d archivos en %s", input_path, len(salidas), output_dir)
    return salidas


def split_pdf_by_ranges(
    input_path: str,
    ranges: list[tuple[int, int]],
    output_prefix: str,
) -> list[str]:
    """Separa un PDF en grupos de rangos de paginas.

    Args:
        input_path: Ruta al PDF de entrada.
        ranges: Lista de tuplas (inicio, fin) pagina (1-based, inclusivo).
        output_prefix: Prefijo para los archivos de salida.

    Returns:
        Lista de rutas de los PDFs generados.
    """
    reader = PdfReader(input_path)
    total = len(reader.pages)
    salidas: list[str] = []

    for idx, (start, end) in enumerate(ranges, 1):
        writer = PdfWriter()
        for pn in range(max(0, start - 1), min(end, total)):
            writer.add_page(reader.pages[pn])
        out_path = f"{output_prefix}_{idx}.pdf"
        with open(out_path, "wb") as out:
            writer.write(out)
        salidas.append(out_path)

    logger.info("Split ranges: %s -> %d archivos", input_path, len(salidas))
    return salidas


# ---------------------------------------------------------------------------
# Rotar
# ---------------------------------------------------------------------------

def rotate_pdf(
    input_path: str,
    output_path: str,
    rotations: dict[int, int] | None = None,
) -> None:
    """Rota paginas de un PDF.

    Args:
        input_path: Ruta al PDF de entrada.
        output_path: Ruta del PDF de salida.
        rotations: Diccionario {pagina_1based: grados}. Ej: {1: 90, 3: 180}.
                   Rotacion positiva = clockwise.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    rotaciones = rotations or {}

    for i, page in enumerate(reader.pages, 1):
        if i in rotaciones:
            page.rotate(rotaciones[i])
        writer.add_page(page)

    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("Rotacion aplicada: %s -> %s (%s)", input_path, output_path, rotaciones)


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------

def apply_watermark_from_page(input_path: str, output_path: str, watermark_pdf: str) -> None:
    """Aplica watermark desde la pagina 1 de otro PDF.

    Args:
        input_path: PDF de entrada.
        output_path: PDF de salida con watermark.
        watermark_pdf: PDF cuya pagina 1 se usa como marca de agua.
    """
    wm_page = PdfReader(watermark_pdf).pages[0]
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(wm_page)
        writer.add_page(page)

    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("Watermark de %s aplicado a %s -> %s", watermark_pdf, input_path, output_path)


def apply_text_watermark(input_path: str, output_path: str, texto: str) -> None:
    """Crea watermark de texto y lo aplica a todas las paginas.

    Args:
        input_path: PDF de entrada.
        output_path: PDF de salida.
        texto: Texto del watermark.
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    w, h = letter
    c.saveState()
    c.setFont("Helvetica-Bold", 60)
    c.setFillColorRGB(0.8, 0.8, 0.8, alpha=0.3)
    c.translate(w / 2, h / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, texto)
    c.restoreState()
    c.save()
    packet.seek(0)

    wm_reader = PdfReader(packet)
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(wm_reader.pages[0])
        writer.add_page(page)

    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("Watermark de texto '%s' aplicado a %s -> %s", texto, input_path, output_path)


# ---------------------------------------------------------------------------
# Crear PDF
# ---------------------------------------------------------------------------

def create_pdf_simple(output_path: str, lineas: list[tuple]) -> None:
    """Crea un PDF basico con lineas de texto.

    Args:
        output_path: Ruta del PDF a crear.
        lineas: Lista de tuplas (x, y, texto) con coordenadas en puntos.
    """
    c = canvas.Canvas(output_path, pagesize=letter)
    w, h = letter
    for x, y, texto in lineas:
        c.drawString(x, h - y, texto)
    c.save()
    logger.info("PDF creado: %s (%d lineas)", output_path, len(lineas))


# ---------------------------------------------------------------------------
# Forms — Fillable
# ---------------------------------------------------------------------------

def fill_form_fillable(
    input_path: str,
    field_values: dict[str, str],
    output_path: str,
) -> None:
    """Rellena campos fillable de un PDF.

    Args:
        input_path: PDF con campos fillable.
        field_values: Diccionario {field_id: valor}.
        output_path: PDF de salida.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter(clone_from=reader)

    for page_num, values in _group_by_page(reader, field_values):
        writer.update_page_form_field_values(
            writer.pages[page_num], values, auto_regenerate=False
        )
    writer.set_need_appearances_writer(True)

    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("Form fillable completado: %s -> %s (%d campos)", input_path, output_path, len(field_values))


def fill_form_annotations(
    input_path: str,
    fields_data: dict,
    output_path: str,
) -> None:
    """Rellena un PDF sin campos fillable usando FreeText annotations.

    Args:
        input_path: PDF de entrada.
        fields_data: Diccionario con "pages" y "form_fields" (ver SKILL.md seccion 10.2).
        output_path: PDF de salida.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append(reader)

    # Dimensiones de cada pagina
    dims: dict[int, tuple[float, float]] = {}
    for i, page in enumerate(reader.pages):
        mb = page.mediabox
        dims[i + 1] = (float(mb.width), float(mb.height))

    total_anotaciones = 0
    for field in fields_data.get("form_fields", []):
        page_num = field["page_number"]
        pdf_w, pdf_h = dims[page_num]
        page_info = next(
            (p for p in fields_data["pages"] if p["page_number"] == page_num), {}
        )

        entry_box = field["entry_bounding_box"]
        entry_text_cfg = field.get("entry_text", {})
        texto = entry_text_cfg.get("text", "")
        if not texto:
            continue

        if "pdf_width" in page_info:
            # Coordenadas PDF (y=bottom en pypdf)
            left, right = entry_box[0], entry_box[2]
            top = pdf_h - entry_box[1]
            bottom = pdf_h - entry_box[3]
        else:
            img_w = page_info.get("image_width", pdf_w)
            img_h = page_info.get("image_height", pdf_h)
            x_scale = pdf_w / img_w
            y_scale = pdf_h / img_h
            left = entry_box[0] * x_scale
            right = entry_box[2] * x_scale
            top = pdf_h - (entry_box[3] * y_scale)
            bottom = pdf_h - (entry_box[1] * y_scale)

        font_name = entry_text_cfg.get("font", "Arial")
        font_size = str(entry_text_cfg.get("font_size", 10)) + "pt"

        annot = FreeText(
            text=texto,
            rect=(left, bottom, right, top),
            font=font_name,
            font_size=font_size,
            font_color="000000",
            border_color=None,
            background_color=None,
        )
        writer.add_annotation(page_number=page_num - 1, annotation=annot)
        total_anotaciones += 1

    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("Form annotations completado: %s -> %s (%d anotaciones)", input_path, output_path, total_anotaciones)


# ---------------------------------------------------------------------------
# Encrypt / Decrypt
# ---------------------------------------------------------------------------

def encrypt_pdf(input_path: str, output_path: str, password: str) -> None:
    """Encripta un PDF con password.

    Args:
        input_path: PDF de entrada.
        output_path: PDF encriptado de salida.
        password: Password para abrir el PDF.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password, password)
    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("PDF encriptado: %s -> %s", input_path, output_path)


def decrypt_pdf(input_path: str, output_path: str, password: str) -> bool:
    """Desencripta un PDF con password.

    Args:
        input_path: PDF encriptado.
        output_path: PDF desencriptado de salida.
        password: Password del PDF.

    Returns:
        True si el decrypt fue exitoso, False si fallo.
    """
    reader = PdfReader(input_path)
    if not reader.is_encrypted:
        logger.warning("El PDF %s no esta encriptado", input_path)
        return False

    resultado = reader.decrypt(password)
    if resultado == 0:
        logger.error("Password incorrecto para %s", input_path)
        return False

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(output_path, "wb") as out:
        writer.write(out)
    logger.info("PDF desencriptado: %s -> %s", input_path, output_path)
    return True


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def ocr_pdf(pdf_path: str, lang: str = "eng", dpi: int = 300) -> str:
    """Extrae texto de PDF escaneado usando OCR (pytesseract + pdf2image).

    Args:
        pdf_path: Ruta al PDF escaneado.
        lang: Idiomas de tesseract. Default: "eng".
              Para japones: "jpn+eng".
        dpi: Resolucion de conversion. Mayor = mejor OCR, mas lento.

    Returns:
        Texto extraido de todas las paginas.
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as exc:
        logger.error("Requiere pdf2image y pytesseract: pip install pdf2image pytesseract")
        raise exc

    imagenes = convert_from_path(pdf_path, dpi=dpi)
    fragmentos: list[str] = []

    for i, img in enumerate(imagenes, 1):
        texto = pytesseract.image_to_string(img, lang=lang)
        fragmentos.append(f"--- Pagina {i} ---\n{texto}")

    resultado = "\n\n".join(fragmentos)
    logger.info("OCR completado: %s (%d paginas, %d chars)", pdf_path, len(imagenes), len(resultado))
    return resultado


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _group_by_page(
    reader: PdfReader,
    field_values: dict[str, str],
) -> list[tuple[int, dict[str, str]]]:
    """Agrupa valores de campos por numero de pagina."""
    from extract_form_field_info import get_field_info  # type: ignore[attr-defined]

    field_info = get_field_info(reader)
    field_to_page: dict[str, int] = {f["field_id"]: f["page"] for f in field_info if "page" in f}

    por_pagina: dict[int, dict[str, str]] = {}
    for fid, valor in field_values.items():
        if fid in field_to_page:
            pagina = field_to_page[fid]
            por_pagina.setdefault(pagina, {})[fid] = valor

    return sorted(por_pagina.items())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI para operaciones rapidas del skill pdf-canvas."""
    import argparse
    import shlex

    parser = argparse.ArgumentParser(description="pdf-canvas CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_meta = sub.add_parser("metadata")
    p_meta.add_argument("pdf", help="Archivo PDF")

    p_text = sub.add_parser("text")
    p_text.add_argument("pdf", help="Archivo PDF")

    p_tables = sub.add_parser("tables")
    p_tables.add_argument("pdf", help="Archivo PDF")
    p_tables.add_argument("--output", "-o", help="Archivo Excel de salida")

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("output", help="PDF de salida")
    p_merge.add_argument("inputs", nargs="+", help="PDFs de entrada")

    p_split = sub.add_parser("split")
    p_split.add_argument("pdf", help="PDF de entrada")
    p_split.add_argument("--output-dir", "-o", default="split_output", help="Directorio de salida")

    p_rotate = sub.add_parser("rotate")
    p_rotate.add_argument("pdf", help="PDF de entrada")
    p_rotate.add_argument("output", help="PDF de salida")
    p_rotate.add_argument("--pages", '-p', default="", help='Paginas a rotar (ej: "1:90,3:180")')

    p_wm = sub.add_parser("watermark")
    p_wm.add_argument("pdf", help="PDF de entrada")
    p_wm.add_argument("output", help="PDF de salida")
    p_wm.add_argument("--text", "-t", help="Texto de watermark")
    p_wm.add_argument("--file", "-f", help="Archivo PDF de watermark (pagina 1)")

    p_enc = sub.add_parser("encrypt")
    p_enc.add_argument("pdf", help="PDF de entrada")
    p_enc.add_argument("output", help="PDF encriptado")
    p_enc.add_argument("--password", "-p", required=True)

    p_dec = sub.add_parser("decrypt")
    p_dec.add_argument("pdf", help="PDF encriptado")
    p_dec.add_argument("output", help="PDF desencriptado")
    p_dec.add_argument("--password", "-p", required=True)

    p_ocr = sub.add_parser("ocr")
    p_ocr.add_argument("pdf", help="PDF escaneado")
    p_ocr.add_argument("--lang", "-l", default="eng", help="Idioma tesseract")
    p_ocr.add_argument("--output", "-o", help="Archivo de texto de salida")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )

    if args.cmd == "metadata":
        meta = get_metadata(args.pdf)
        for k, v in meta.items():
            print(f"{k}: {v}")

    elif args.cmd == "text":
        print(extract_text_plumber(args.pdf))

    elif args.cmd == "tables":
        tablas = extract_tables(args.pdf, args.output)
        print(f"Extraidas {len(tablas)} tablas")
        if args.output:
            print(f"Guardadas en: {args.output}")

    elif args.cmd == "merge":
        merge_pdfs(args.inputs, args.output)
        print(f"Merge completado: {args.output}")

    elif args.cmd == "split":
        outs = split_pdf_by_page(args.pdf, args.output_dir)
        for o in outs:
            print(f"  {o}")

    elif args.cmd == "rotate":
        rot: dict[int, int] = {}
        if args.pages:
            for part in args.pages.split(","):
                pg, deg = part.strip().split(":")
                rot[int(pg.strip())] = int(deg.strip())
        rotate_pdf(args.pdf, args.output, rot)
        print(f"Rotacion aplicada: {args.output}")

    elif args.cmd == "watermark":
        if args.file:
            apply_watermark_from_page(args.pdf, args.output, args.file)
        elif args.text:
            apply_text_watermark(args.pdf, args.output, args.text)
        else:
            print("Especificar --text o --file para watermark")
        print(f"Watermark aplicado: {args.output}")

    elif args.cmd == "encrypt":
        encrypt_pdf(args.pdf, args.output, args.password)
        print(f"Encriptado: {args.output}")

    elif args.cmd == "decrypt":
        ok = decrypt_pdf(args.pdf, args.output, args.password)
        print(f"Desencriptado: {args.output}" if ok else "Password incorrecto")

    elif args.cmd == "ocr":
        texto = ocr_pdf(args.pdf, lang=args.lang)
        if args.output:
            Path(args.output).write_text(texto, encoding="utf-8")
            print(f"OCR guardado en: {args.output}")
        else:
            print(texto)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
