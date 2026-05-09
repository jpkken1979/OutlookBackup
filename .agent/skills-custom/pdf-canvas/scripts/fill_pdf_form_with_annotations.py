"""
Rellena un PDF sin campos fillable agregando FreeText annotations.

Fields.json puede usar coordenadas PDF o imagen. El script auto-detecta
el sistema y convierte si es necesario.

Uso:
    python fill_pdf_form_with_annotations.py <input.pdf> <fields.json> <output.pdf>
"""

from __future__ import annotations

import json
import sys
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText


def transform_from_image_coords(
    bbox: list[float],
    image_width: float,
    image_height: float,
    pdf_width: float,
    pdf_height: float,
) -> tuple[float, float, float, float]:
    """Convierte [x0,y0,x1,y1] (imagen, origen top) a [l,b,r,t] (PDF).

    Args:
        bbox: Bounding box en coords de imagen.
        image_width: Ancho de la imagen.
        image_height: Alto de la imagen.
        pdf_width: Ancho del PDF en puntos.
        pdf_height: Alto del PDF en puntos.

    Returns:
        Tupla (left, bottom, right, top) en coordenadas PDF.
    """
    x_scale = pdf_width / image_width
    y_scale = pdf_height / image_height
    left = bbox[0] * x_scale
    right = bbox[2] * x_scale
    top = pdf_height - (bbox[3] * y_scale)
    bottom = pdf_height - (bbox[1] * y_scale)
    return left, bottom, right, top


def transform_from_pdf_coords(
    bbox: list[float],
    pdf_height: float,
) -> tuple[float, float, float, float]:
    """Convierte [x0,top,x1,bottom] (pdfplumber) a [l,b,r,t] (pypdf).

    Args:
        bbox: Bounding box en coords de pdfplumber.
        pdf_height: Alto del PDF en puntos.

    Returns:
        Tupla (left, bottom, right, top) en coordenadas PDF.
    """
    left = bbox[0]
    right = bbox[2]
    pypdf_top = pdf_height - bbox[1]
    pypdf_bottom = pdf_height - bbox[3]
    return left, pypdf_bottom, right, pypdf_top


def fill_pdf_form(
    input_pdf_path: str,
    fields_json_path: str,
    output_pdf_path: str,
) -> None:
    """Rellena un PDF con annotations FreeText.

    Args:
        input_pdf_path: PDF de entrada.
        fields_json_path: JSON con form_fields y pages (ver SKILL.md seccion 10.2).
        output_pdf_path: PDF de salida con annotations.
    """
    with open(fields_json_path, encoding="utf-8") as f:
        fields_data: dict[str, Any] = json.load(f)

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    writer.append(reader)

    # Dimensiones de cada pagina (1-based)
    pdf_dims: dict[int, tuple[float, float]] = {}
    for i, page in enumerate(reader.pages):
        mb = page.mediabox
        pdf_dims[i + 1] = (float(mb.width), float(mb.height))

    # Page infos del JSON
    page_infos: dict[int, dict] = {
        p["page_number"]: p for p in fields_data.get("pages", [])
    }

    total_annotations = 0
    for field in fields_data.get("form_fields", []):
        page_num = field["page_number"]
        page_info = page_infos.get(page_num, {})
        pdf_width, pdf_height = pdf_dims[page_num]

        entry_box = field["entry_bounding_box"]
        entry_text_cfg = field.get("entry_text", {})
        texto = entry_text_cfg.get("text", "")
        if not texto:
            continue

        # Auto-detectar sistema de coordenadas
        if "pdf_width" in page_info:
            transformed = transform_from_pdf_coords(entry_box, pdf_height)
        else:
            img_w = page_info.get("image_width", pdf_width)
            img_h = page_info.get("image_height", pdf_height)
            transformed = transform_from_image_coords(
                entry_box, img_w, img_h, pdf_width, pdf_height
            )

        font_name = entry_text_cfg.get("font", "Arial")
        font_size = str(entry_text_cfg.get("font_size", 10)) + "pt"

        annotation = FreeText(
            text=texto,
            rect=transformed,
            font=font_name,
            font_size=font_size,
            font_color="000000",
            border_color=None,
            background_color=None,
        )
        writer.add_annotation(page_number=page_num - 1, annotation=annotation)
        total_annotations += 1

    with open(output_pdf_path, "wb") as out:
        writer.write(out)
    print(f"Completado: {output_pdf_path} ({total_annotations} annotations)")


def main() -> None:
    if len(sys.argv) != 4:
        print("Uso: fill_pdf_form_with_annotations.py <input.pdf> <fields.json> <output.pdf>")
        sys.exit(1)
    fill_pdf_form(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
