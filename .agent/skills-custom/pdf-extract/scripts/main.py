"""
PDF Extract Skill — Extraccion avanzada de contenido de PDFs.

Funciones disponibles:
    - extract_text(pdf_path) -> str
    - extract_tables(pdf_path, method='pdfplumber') -> list[dict]
    - extract_with_ocr(pdf_path, lang='jpn+eng') -> str
    - extract_images(pdf_path) -> list[bytes]
    - clone_format(pdf_path, page=0) -> dict

Uso CLI:
    python main.py --action extract_text --pdf document.pdf
    python main.py --action extract_tables --pdf document.pdf --method pdfplumber
    python main.py --action extract_with_ocr --pdf scanned.pdf --lang jpn+eng
    python main.py --action extract_images --pdf document.pdf
    python main.py --action clone_format --pdf document.pdf --page 0 --json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
#第三方库延迟导入（lazy import）—— 仅在调用对应 action 时才导入，
# 这样即使用户只用了 extract_text 而没装 camelot，也不会报错。
# 每个函数内部自行检测 ImportError 并给出提示。
# ----------------------------------------------------------------------


def _lazy_import(name: str, package: str | None = None) -> Any:
    """动态导入，失败时提示安装."""
    try:
        return __import__(name, fromlist=[package or ""])
    except ImportError as exc:
        raise ImportError(
            f"Library '{name}' not found. Install it first:\n"
            f"  pip install {exc.name}\n"
            f"Required for the selected action."
        ) from exc


# ----------------------------------------------------------------------
# extract_text
# ----------------------------------------------------------------------


def extract_text(pdf_path: str, method: str = "pypdf") -> str:
    """Extrae texto plano de un PDF.

    Args:
        pdf_path: Ruta al archivo PDF.
        method: Motor de extraccion. 'pypdf' (default) o 'pdfplumber'.

    Returns:
        Texto completo concatenado de todas las paginas.

    Raises:
        FileNotFoundError: Si el archivo PDF no existe.
        ImportError: Si falta la libreria necesaria.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    logger.info("[extract_text] Abriendo %s (method=%s)", pdf_path, method)

    if method == "pdfplumber":
        pdfplumber = _lazy_import("pdfplumber")
        lines: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    lines.append(f"--- Pagina {i + 1} ---\n{text}")
        result = "\n\n".join(lines)
        logger.info("[extract_text] %d paginas procesadas", len(pdf.pages))
        return result

    # Default: pypdf
    pypdf = _lazy_import("pypdf")
    reader = pypdf.PdfReader(pdf_path)
    lines: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            lines.append(f"--- Pagina {i + 1} ---\n{text}")
    result = "\n\n".join(lines)
    logger.info("[extract_text] %d paginas procesadas", len(reader.pages))
    return result


# ----------------------------------------------------------------------
# extract_tables
# ----------------------------------------------------------------------


def _tables_via_pdfplumber(pdf_path: str) -> list[dict[str, Any]]:
    """Extrae tablas usando pdfplumber."""
    pdfplumber = _lazy_import("pdfplumber")
    results: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                continue
            for table_idx, table in enumerate(tables):
                if table:
                    results.append({
                        "page": page_idx + 1,
                        "table_index": table_idx,
                        "rows": len(table),
                        "cols": len(table[0]) if table else 0,
                        "data": table,
                    })
    return results


def _tables_via_camelot(pdf_path: str, flavor: str = "stream") -> list[dict[str, Any]]:
    """Extrae tablas usando Camelot."""
    camelot = _lazy_import("camelot")
    table_list = camelot.read_pdf(pdf_path, pages="all", flavor=flavor)
    results: list[dict[str, Any]] = []
    for i, tbl in enumerate(table_list):
        df = tbl.df
        results.append({
            "page": int(df.iloc[0].name) if df is not None and not df.empty else i + 1,
            "table_index": i,
            "rows": len(df),
            "cols": len(df.columns),
            "data": df.values.tolist(),
            "accuracy": getattr(tbl, "accuracy", None),
        })
    return results


def _tables_via_tabula(pdf_path: str) -> list[dict[str, Any]]:
    """Extrae tablas usando Tabula."""
    tabula = _lazy_import("tabula")
    dfs = tabula.read_pdf(pdf_path, pages="all", multiple_candidates=True)
    results: list[dict[str, Any]] = []
    for i, df in enumerate(dfs):
        if df is None or df.empty:
            continue
        results.append({
            "page": i + 1,
            "table_index": i,
            "rows": len(df),
            "cols": len(df.columns),
            "data": df.values.tolist(),
        })
    return results


def extract_tables(pdf_path: str, method: str = "pdfplumber") -> list[dict[str, Any]]:
    """Extrae tablas de un PDF.

    Args:
        pdf_path: Ruta al archivo PDF.
        method: Motor de extraccion.
            'pdfplumber' (default) — rapido, buenos resultados en la mayoria.
            'camelot'       — mejor para bordes debiles.
            'camelot-lattice' — mejor para bordes fuertes.
            'tabula'        — estilo JVM, alternatica.

    Returns:
        Lista de diccionarios, cada uno con metadata de tabla + datos.
        Cada dict tiene keys: page, table_index, rows, cols, data.

    Raises:
        FileNotFoundError: Si el archivo PDF no existe.
        ImportError: Si falta la libreria necesaria.
        ValueError: Si method no es valido.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    logger.info("[extract_tables] Abriendo %s (method=%s)", pdf_path, method)

    if method == "camelot":
        results = _tables_via_camelot(pdf_path, flavor="stream")
    elif method == "camelot-lattice":
        results = _tables_via_camelot(pdf_path, flavor="lattice")
    elif method == "tabula":
        results = _tables_via_tabula(pdf_path)
    elif method == "pdfplumber":
        results = _tables_via_pdfplumber(pdf_path)
    else:
        raise ValueError(
            f"Metodo desconocido: '{method}'. "
            f"Validos: pdfplumber, camelot, camelot-lattice, tabula."
        )

    logger.info(
        "[extract_tables] %d tabla(s) extraida(s) de %s",
        len(results),
        pdf_path,
    )
    return results


# ----------------------------------------------------------------------
# extract_with_ocr
# ----------------------------------------------------------------------


@dataclass
class OcrResult:
    """Resultado de OCR para una pagina."""

    page: int
    text: str
    confidence_avg: float | None = None


def extract_with_ocr(
    pdf_path: str,
    lang: str = "jpn+eng",
    dpi: int = 300,
    psm: int = 6,
) -> str:
    """Extrae texto de un PDF escaneado usando Tesseract OCR.

    Args:
        pdf_path: Ruta al PDF escaneado (solo imagenes, sin texto embebido).
        lang: Idiomas de Tesseract. 'eng' (default), 'jpn+eng' para bilingue.
        dpi: Resolucion de conversion (default 300). Valores mayores mejoran
            precision pero usan mas memoria.
        psm: Page Segmentation Mode de Tesseract (default 6).
            6 = Assume a single uniform block of text.
            4 = Single column.
            3 = Fully automatic (default Tesseract).

    Returns:
        Texto OCR concatenado por pagina.

    Raises:
        FileNotFoundError: Si el PDF no existe.
        ImportError: Si faltan pytesseract o pdf2image.
        RuntimeError: Si Tesseract no esta instalado o no se encuentra.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    pytesseract = _lazy_import("pytesseract")
    pdf2image = _lazy_import("pdf2image")

    # Verificar que Tesseract este en PATH
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise RuntimeError(
            "Tesseract OCR no se encuentra en el PATH. "
            "Verifica que este instalado y agregado al PATH de tu sistema.\n"
            "Descarga: https://github.com/UB-Mannheim/tesseract/wiki"
        ) from exc

    logger.info(
        "[extract_with_ocr] Convirtiendo %s a imagenes (dpi=%d, lang=%s)",
        pdf_path,
        dpi,
        lang,
    )

    # Convertir PDF a imagenes
    images = pdf2image.convert_from_path(pdf_path, dpi=dpi)

    # Configuracion de PSM
    config = f"--psm {psm}"

    page_results: list[OcrResult] = []
    for i, image in enumerate(images, start=1):
        text = pytesseract.image_to_string(image, lang=lang, config=config)
        # Obtener confianza promedio si esta disponible
        try:
            data = pytesseract.image_to_data(
                image, lang=lang, config=config, output_type=pytesseract.Output.DICT
            )
            confs = [float(c) for c in data["conf"] if float(c) > 0]
            avg_conf = sum(confs) / len(confs) if confs else None
        except Exception:
            avg_conf = None

        page_results.append(OcrResult(page=i, text=text, confidence_avg=avg_conf))
        logger.info("[extract_with_ocr] Pagina %d procesada (conf=%.1f)", i, avg_conf or 0)

    # Ensamblar resultado
    output_lines: list[str] = []
    for pr in page_results:
        output_lines.append(f"--- Pagina {pr.page} (conf: {pr.confidence_avg:.1f}%) ---")
        output_lines.append(pr.text.strip())
        output_lines.append("")

    return "\n".join(output_lines)


# ----------------------------------------------------------------------
# extract_images
# ----------------------------------------------------------------------


def extract_images(pdf_path: str, output_dir: str | Path | None = None) -> list[bytes]:
    """Extrae todas las imagenes embebidas de un PDF.

    Args:
        pdf_path: Ruta al archivo PDF.
        output_dir: Directorio donde guardar las imagenes.
            Si es None, solo retorna las imagenes en memoria (no las graba).

    Returns:
        Lista de bytes de las imagenes extraidas (en orden de aparicion).

    Raises:
        FileNotFoundError: Si el PDF no existe.
        ImportError: Si falta pypdf.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    pypdf = _lazy_import("pypdf")
    out_dir = Path(output_dir) if output_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[extract_images] Abriendo %s", pdf_path)

    reader = pypdf.PdfReader(pdf_path)
    image_bytes_list: list[bytes] = []
    count = 0

    for page_num, page in enumerate(reader.pages):
        if "/XObject" not in page["/Resources"]:
            continue

        xobjects = page["/Resources"]["/XObject"].get_object()
        for obj_name, obj in xobjects.items():
            obj_ref = obj.get_object() if hasattr(obj, "get_object") else obj
            if obj_ref.get("/Subtype") != "/Image":
                continue

            try:
                data = obj_ref.get_data()
                color_space = obj_ref.get("/ColorSpace", "Unknown")
                width = obj_ref.get("/Width")
                height = obj_ref.get("/Height")

                image_bytes_list.append(data)
                count += 1

                if out_dir:
                    ext = "jpg" if "/DCTDecode" in obj_ref.get("/Filter", "") else "png"
                    fname = out_dir / f"img_p{page_num + 1}_{count}.{ext}"
                    fname.write_bytes(data)
                    logger.debug(
                        "[extract_images] Guardado: %s (%dx%d, %s)",
                        fname,
                        width,
                        height,
                        color_space,
                    )
            except Exception as exc:
                logger.warning(
                    "[extract_images] Error extrayendo imagen %s en pagina %d: %s",
                    obj_name,
                    page_num + 1,
                    exc,
                )
                continue

    logger.info(
        "[extract_images] %d imagen(es) extraida(s) de %s",
        count,
        pdf_path,
    )
    return image_bytes_list


# ----------------------------------------------------------------------
# clone_format
# ----------------------------------------------------------------------


@dataclass
class FontInfo:
    """Informacion de una fuente detectada en una pagina."""

    name: str = ""
    family: str = ""
    font_type: str = ""
    size: float = 0.0
    size_pt: float = 0.0
    color_rgb: list[int] = field(default_factory=list)
    color_hex: str = "#000000"
    is_embedded: bool = False
    is_bold: bool = False
    is_italic: bool = False


@dataclass
class PageInfo:
    """Informacion dimensional de una pagina."""

    width_pt: float = 0.0
    height_pt: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0
    width_inch: float = 0.0
    height_inch: float = 0.0
    rotation: int = 0


@dataclass
class MarginsInfo:
    """Margenes de una pagina en pt y mm."""

    left_pt: float = 0.0
    right_pt: float = 0.0
    top_pt: float = 0.0
    bottom_pt: float = 0.0
    left_mm: float = 0.0
    right_mm: float = 0.0
    top_mm: float = 0.0
    bottom_mm: float = 0.0


@dataclass
class LayoutInfo:
    """Estructura de layout de la pagina."""

    columns: int = 1
    line_spacing: float = 1.2
    paragraph_spacing_pt: float = 12.0
    text_direction: str = "ltr"
    text_alignment: str = "left"
    has_header: bool = False
    has_footer: bool = False


@dataclass
class GraphicsInfo:
    """Elementos graficos detectados."""

    has_rectangles: bool = False
    has_lines: bool = False
    has_images: bool = False
    has_annotations: bool = False


@dataclass
class MetadataInfo:
    """Metadata del documento."""

    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""
    modification_date: str = ""


@dataclass
class PageNumberingInfo:
    """Numeracion de pagina."""

    style: str = "arabic"
    position: str = "bottom-center"
    start: int = 1


@dataclass
class CharInfo:
    """Informacion de un caracter/texto en la pagina."""

    text: str = ""
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    font: str = ""
    size: float = 0.0
    color_rgb: list[int] = field(default_factory=list)


def clone_format(pdf_path: str, page: int = 0) -> dict[str, Any]:
    """Extrae TODAS las propiedades fisicas exactas de una pagina de PDF.

    El objetivo es permitir **replicar el formato** de un PDF existente:
    margenes exactos, fuentes con sus tamanos y colores, paleta de colores,
    espaciado, estructura de columnas, etc.

    Args:
        pdf_path: Ruta al archivo PDF.
        page: Numero de pagina (0-based). Default 0.

    Returns:
        Diccionario con todas las propiedades exactas del PDF:
        {
            "page": PageInfo,
            "margins": MarginsInfo,
            "fonts": list[FontInfo],
            "colors": {...},
            "layout": LayoutInfo,
            "graphics": GraphicsInfo,
            "metadata": MetadataInfo,
            "page_numbering": PageNumberingInfo,
            "raw_chars": list[CharInfo],
        }

    Raises:
        FileNotFoundError: Si el PDF no existe.
        IndexError: Si el numero de pagina no existe.
        ImportError: Si falta pdfplumber.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    pdfplumber = _lazy_import("pdfplumber")
    pypdf = _lazy_import("pypdf")

    logger.info("[clone_format] Analizando pagina %d de %s", page, pdf_path)

    # --- 1. Abrir con pypdf para metadata y tamanos
    reader = pypdf.PdfReader(pdf_path)
    if page >= len(reader.pages):
        raise IndexError(
            f"Pagina {page} fuera de rango. El PDF tiene {len(reader.pages)} paginas."
        )

    pdf_page = reader.pages[page]
    media_box = pdf_page.mediabox

    # Dimensiones en pt (1 pt = 1/72 inch)
    raw_w = float(media_box.width)
    raw_h = float(media_box.height)
    rotation = pdf_page.get("/Rotate", 0)

    # Ajustar por rotacion
    if rotation in (90, 270):
        width_pt, height_pt = raw_h, raw_w
    else:
        width_pt, height_pt = raw_w, raw_h

    # Conversiones
    PT_TO_MM = 25.4 / 72.0
    PT_TO_INCH = 1.0 / 72.0

    page_info: PageInfo = PageInfo(
        width_pt=width_pt,
        height_pt=height_pt,
        width_mm=round(width_pt * PT_TO_MM, 2),
        height_mm=round(height_pt * PT_TO_MM, 2),
        width_inch=round(width_pt * PT_TO_INCH, 2),
        height_inch=round(height_pt * PT_TO_INCH, 2),
        rotation=rotation,
    )

    # --- 2. Metadata
    meta = reader.metadata or {}
    metadata_info: MetadataInfo = MetadataInfo(
        title=str(meta.get("/Title", "")),
        author=str(meta.get("/Author", "")),
        subject=str(meta.get("/Subject", "")),
        keywords=str(meta.get("/Keywords", "")),
        creator=str(meta.get("/Creator", "")),
        producer=str(meta.get("/Producer", "")),
        creation_date=str(meta.get("/CreationDate", "")),
        modification_date=str(meta.get("/ModDate", "")),
    )

    # --- 3. Abrir con pdfplumber para analisis de pagina
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pdfplumber.open(pdf_path) as pdf:
            if page >= len(pdf.pages):
                raise IndexError(
                    f"Pagina {page} fuera de rango. El PDF tiene {len(pdf.pages)} paginas."
                )
            plumb_page = pdf.pages[page]

            # Margenes: estimar como la minima coordenada de texto en cada borde
            chars = plumb_page.chars or []
            if chars:
                left_margin = min(c["x0"] for c in chars)
                top_margin = min(c["top"] for c in chars)
                right_margin = width_pt - max(c["x1"] for c in chars)
                bottom_margin = height_pt - max(c["bottom"] for c in chars)
            else:
                left_margin = right_margin = top_margin = bottom_margin = 0.0

            margins_info: MarginsInfo = MarginsInfo(
                left_pt=round(left_margin, 2),
                right_pt=round(right_margin, 2),
                top_pt=round(top_margin, 2),
                bottom_pt=round(bottom_margin, 2),
                left_mm=round(left_margin * PT_TO_MM, 2),
                right_mm=round(right_margin * PT_TO_MM, 2),
                top_mm=round(top_margin * PT_TO_MM, 2),
                bottom_mm=round(bottom_margin * PT_TO_MM, 2),
            )

            # --- 4. Fuentes
            fonts_map: dict[str, FontInfo] = {}
            for char in chars:
                font_name = char.get("font", "Unknown")
                if font_name not in fonts_map:
                    size = char.get("size", 12.0)
                    fonts_map[font_name] = FontInfo(
                        name=font_name,
                        family=font_name,
                        size=size,
                        size_pt=round(size, 2),
                        font_type="Type1",  # pdfplumber no siempre lo expose
                    )

            fonts_list: list[FontInfo] = list(fonts_map.values())

            # --- 5. Colores unicos
            colors_set: set[tuple[int, int, int]] = set()
            for char in chars:
                raw = char.get("non_stroking_color") or char.get("stroking_color")
                if raw and isinstance(raw, (list, tuple)):
                    rgb = tuple(int(min(255, max(0, c * 255))) for c in raw[:3])
                    colors_set.add(rgb)

            # Incluir color de fondo de pagina si esta disponible
            bg_color = plumb_page.background_color or (255, 255, 255)
            if isinstance(bg_color, (list, tuple)):
                bg_rgb = tuple(int(min(255, max(0, c * 255))) for c in bg_color[:3])
            else:
                bg_rgb = (255, 255, 255)

            colors_dict = {
                "primary": [],
                "primary_hex": "#000000",
                "background": list(bg_rgb),
                "background_hex": f"#{bg_rgb[0]:02X}{bg_rgb[1]:02X}{bg_rgb[2]:02X}",
                "accent": [],
                "all_unique_rgb": [list(c) for c in sorted(colors_set)],
            }
            if colors_set:
                primary = list(max(colors_set, key=lambda c: colors_set.count(c)))
                colors_dict["primary"] = primary
                colors_dict["primary_hex"] = (
                    f"#{primary[0]:02X}{primary[1]:02X}{primary[2]:02X}"
                )

            # --- 6. Layout: deteccion de columnas
            # Agrupar chars por x0 (columna)
            if chars:
                x_positions = sorted({round(c["x0"]) for c in chars})
                # Cluster de posiciones cercanas
                col_clusters: list[list[int]] = []
                for x in x_positions:
                    placed = False
                    for cluster in col_clusters:
                        if abs(x - cluster[-1]) < 30:  # 30 pt de tolerancia
                            cluster.append(x)
                            placed = True
                            break
                    if not placed:
                        col_clusters.append([x])
                num_cols = len(col_clusters)
            else:
                num_cols = 1

            # Direccion de texto: detectar RTL
            text_dir = "ltr"
            if chars:
                first_chars = chars[:10]
                rtl_chars = sum(1 for c in first_chars if c.get("dir") == "rtl")
                if rtl_chars > len(first_chars) / 2:
                    text_dir = "rtl"
                elif chars and chars[0].get("dir") == "ttb":
                    text_dir = "ttb"

            layout_info: LayoutInfo = LayoutInfo(
                columns=num_cols,
                line_spacing=1.2,
                paragraph_spacing_pt=12.0,
                text_direction=text_dir,
                text_alignment="left",
                has_header=False,
                has_footer=False,
            )

            # --- 7. Graficos
            lines = plumb_page.lines or []
            rects = plumb_page.rects or []
            graphics_info: GraphicsInfo = GraphicsInfo(
                has_rectangles=bool(rects),
                has_lines=bool(lines),
                has_images=plumb_page.images is not None and len(plumb_page.images) > 0,
                has_annotations=plumb_page.annots is not None and len(plumb_page.annots or []) > 0,
            )

            # --- 8. Raw chars (muestreo: max 200 para no inflar)
            SAMPLE_SIZE = 200
            sampled = chars[::max(1, len(chars) // SAMPLE_SIZE)][:SAMPLE_SIZE]
            raw_chars: list[CharInfo] = []
            for char in sampled:
                color = char.get("non_stroking_color")
                rgb: list[int] = []
                if color and isinstance(color, (list, tuple)):
                    rgb = [int(min(255, max(0, c * 255))) for c in color[:3]]
                raw_chars.append(CharInfo(
                    text=char.get("text", ""),
                    x0=round(char.get("x0", 0.0), 2),
                    y0=round(char.get("top", 0.0), 2),
                    x1=round(char.get("x1", 0.0), 2),
                    y1=round(char.get("bottom", 0.0), 2),
                    font=char.get("font", ""),
                    size=round(char.get("size", 0.0), 2),
                    color_rgb=rgb,
                ))

    # --- Ensamblar resultado
    result: dict[str, Any] = {
        "page": page_info.__dict__,
        "margins": margins_info.__dict__,
        "fonts": [f.__dict__ for f in fonts_list],
        "colors": colors_dict,
        "layout": layout_info.__dict__,
        "graphics": graphics_info.__dict__,
        "metadata": metadata_info.__dict__,
        "page_numbering": PageNumberingInfo().__dict__,
        "raw_chars": [c.__dict__ for c in raw_chars],
    }

    logger.info(
        "[clone_format] Pagina %d: %dx%d pt, %d fuentes, %d colores, %d columnas",
        page,
        width_pt,
        height_pt,
        len(fonts_list),
        len(colors_set),
        num_cols,
    )
    return result


# ----------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------


def _configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] [pdf-extract] %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    """Entry point CLI del skill."""
    parser = argparse.ArgumentParser(
        description="PDF Extract - Extraccion avanzada de contenido PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=[
            "extract_text",
            "extract_tables",
            "extract_with_ocr",
            "extract_images",
            "clone_format",
        ],
        help="Accion a ejecutar",
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="Ruta al archivo PDF de entrada",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=0,
        help="Numero de pagina (0-based, solo para clone_format). Default: 0",
    )
    parser.add_argument(
        "--method",
        default="pdfplumber",
        help="Metodo de extraccion (para extract_tables). "
        "Valores: pdfplumber, camelot, camelot-lattice, tabula. Default: pdfplumber",
    )
    parser.add_argument(
        "--lang",
        default="jpn+eng",
        help="Idiomas para OCR (para extract_with_ocr). Default: jpn+eng",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directorio de salida para extract_images",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en formato JSON (para clone_format y extract_tables)",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Procesar todas las paginas (para clone_format)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Modo debug (log detallado)",
    )

    args = parser.parse_args()
    _configure_logging(args.verbose)

    logger.info("Skill pdf-extract | action=%s | pdf=%s", args.action, args.pdf)

    try:
        if args.action == "extract_text":
            result = extract_text(args.pdf, method=args.method)
            print(result)

        elif args.action == "extract_tables":
            tables = extract_tables(args.pdf, method=args.method)
            if args.json:
                print(json.dumps(tables, ensure_ascii=False, indent=2))
            else:
                for t in tables:
                    print(f"Tabla {t['table_index']+1} en pagina {t['page']}: "
                          f"{t['rows']} filas x {t['cols']} columnas")
                    for row in t["data"][:5]:  # muestro max 5 filas
                        print("  ", row)
                    if len(t["data"]) > 5:
                        print(f"  ... ({len(t['data']) - 5} filas mas)")

        elif args.action == "extract_with_ocr":
            result = extract_with_ocr(args.pdf, lang=args.lang)
            print(result)

        elif args.action == "extract_images":
            imgs = extract_images(args.pdf, output_dir=args.output_dir)
            print(f"{len(imgs)} imagen(es) extraida(s).")
            if args.output_dir:
                print(f"Guardadas en: {args.output_dir}")

        elif args.action == "clone_format":
            if args.all_pages:
                # Importar pypdf solo para contar paginas
                pypdf = _lazy_import("pypdf")
                reader = pypdf.PdfReader(args.pdf)
                total = len(reader.pages)
                results = []
                for p in range(total):
                    results.append({"page": p, "format": clone_format(args.pdf, page=p)})
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
                else:
                    for r in results:
                        fmt = r["format"]
                        print(f"Pagina {r['page']}: {fmt['page']['width_pt']:.1f}x"
                              f"{fmt['page']['height_pt']:.1f} pt, "
                              f"{len(fmt['fonts'])} fuentes, "
                              f"cols={fmt['layout']['columns']}")
            else:
                result = clone_format(args.pdf, page=args.page)
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    p = result["page"]
                    m = result["margins"]
                    print(f"Pagina {args.page}:")
                    print(f"  Tamano: {p['width_pt']:.1f}x{p['height_pt']:.1f} pt  "
                          f"({p['width_mm']}x{p['height_mm']} mm)")
                    print(f"  Margenes: izq={m['left_pt']} pt, der={m['right_pt']} pt, "
                          f"arr={m['top_pt']} pt, aba={m['bottom_pt']} pt")
                    print(f"  Fuentes ({len(result['fonts'])}): "
                          f"{[f['name'] for f in result['fonts']]}")
                    print(f"  Layout columnas: {result['layout']['columns']}, "
                          f"direccion: {result['layout']['text_direction']}")
                    print(f"  Color texto: {result['colors']['primary_hex']}, "
                          f"fondo: {result['colors']['background_hex']}")
                    print(f"  Graficos: rects={result['graphics']['has_rectangles']}, "
                          f"lineas={result['graphics']['has_lines']}, "
                          f"imagenes={result['graphics']['has_images']}")

        logger.info("Accion '%s' completada exitosamente.", args.action)
        return 0

    except (FileNotFoundError, IndexError, ValueError) as exc:
        logger.error("%s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ImportError as exc:
        logger.error("%s", exc)
        print(f"Error de dependencia: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("Error inesperado durante la extraccion")
        print(f"Error inesperado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
