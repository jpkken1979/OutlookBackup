"""
Extrae estructura de un PDF sin campos fillable para generar coordinates
precisas de campos de entrada.

Analiza: texto labels, lineas horizontales, checkboxes, row boundaries.
Output: JSON con coordinates exactas en PDF points.

Uso:
    python extract_form_structure.py <input.pdf> <output.json>
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pdfplumber


def extract_form_structure(pdf_path: str) -> dict[str, Any]:
    """Extrae la estructura visual de un PDF.

    Args:
        pdf_path: Ruta al PDF.

    Returns:
        Diccionario con pages, labels, lines, checkboxes, row_boundaries.
    """
    structure: dict[str, Any] = {
        "pages": [],
        "labels": [],
        "lines": [],
        "checkboxes": [],
        "row_boundaries": [],
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            structure["pages"].append({
                "page_number": page_num,
                "width": float(page.width),
                "height": float(page.height),
            })

            # Texto con coordenadas
            words = page.extract_words()
            for word in words:
                structure["labels"].append({
                    "page": page_num,
                    "text": word["text"],
                    "x0": round(float(word["x0"]), 1),
                    "top": round(float(word["top"]), 1),
                    "x1": round(float(word["x1"]), 1),
                    "bottom": round(float(word["bottom"]), 1),
                })

            # Lineas horizontales (row boundaries)
            for line in page.lines:
                width_line = abs(float(line["x1"]) - float(line["x0"]))
                if width_line > page.width * 0.5:
                    structure["lines"].append({
                        "page": page_num,
                        "y": round(float(line["top"]), 1),
                        "x0": round(float(line["x0"]), 1),
                        "x1": round(float(line["x1"]), 1),
                    })

            # Checkboxes pequenos (rectangulos cuadrados ~5-15 pts)
            for rect in page.rects:
                rw = float(rect["x1"]) - float(rect["x0"])
                rh = float(rect["bottom"]) - float(rect["top"])
                if 5 <= rw <= 15 and 5 <= rh <= 15 and abs(rw - rh) < 2:
                    structure["checkboxes"].append({
                        "page": page_num,
                        "x0": round(float(rect["x0"]), 1),
                        "top": round(float(rect["top"]), 1),
                        "x1": round(float(rect["x1"]), 1),
                        "bottom": round(float(rect["bottom"]), 1),
                        "center_x": round((float(rect["x0"]) + float(rect["x1"])) / 2, 1),
                        "center_y": round((float(rect["top"]) + float(rect["bottom"])) / 2, 1),
                    })

    # Calcular row boundaries desde lineas
    lines_by_page: dict[int, list[float]] = {}
    for line in structure["lines"]:
        p = line["page"]
        lines_by_page.setdefault(p, []).append(line["y"])

    for page, ys in lines_by_page.items():
        ys = sorted(set(ys))
        for k in range(len(ys) - 1):
            structure["row_boundaries"].append({
                "page": page,
                "row_top": ys[k],
                "row_bottom": ys[k + 1],
                "row_height": round(ys[k + 1] - ys[k], 1),
            })

    return structure


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: extract_form_structure.py <input.pdf> <output.json>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2]

    print(f"Extrayendo estructura de {pdf_path}...")
    structure = extract_form_structure(pdf_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, indent=2)

    print("Encontrado:")
    print(f"  - {len(structure['pages'])} paginas")
    print(f"  - {len(structure['labels'])} labels de texto")
    print(f"  - {len(structure['lines'])} lineas horizontales")
    print(f"  - {len(structure['checkboxes'])} checkboxes")
    print(f"  - {len(structure['row_boundaries'])} row boundaries")
    print(f"Guardado en {output_path}")


if __name__ == "__main__":
    main()
