"""
Genera una imagen de validacion con bounding boxes dibujados sobre la pagina.

Para verificar visualmente que las coordenadas de fields.json son correctas
antes de rellenar el form.

Requiere: pip install Pillow

Uso:
    python create_validation_image.py <page_num> <fields.json> <input_image> <output_image>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def create_validation_image(
    page_number: int,
    fields_json_path: str,
    input_image_path: str,
    output_image_path: str,
) -> None:
    """Genera imagen de validacion con bounding boxes.

    Dibuja rectangulos sobre la imagen: azul=label, rojo=entry.

    Args:
        page_number: Numero de pagina 1-based a validar.
        fields_json_path: Ruta al archivo fields.json.
        input_image_path: Imagen PNG de la pagina (render del PDF).
        output_image_path: Ruta de la imagen de salida con boxes.
    """
    with open(fields_json_path, encoding="utf-8") as f:
        data = json.load(f)

    img = Image.open(input_image_path)
    draw = ImageDraw.Draw(img)
    num_boxes = 0

    for field in data.get("form_fields", []):
        if field["page_number"] == page_number:
            entry_box = field["entry_bounding_box"]
            label_box = field["label_bounding_box"]
            draw.rectangle(entry_box, outline="red", width=2)
            draw.rectangle(label_box, outline="blue", width=2)
            num_boxes += 2

    img.save(output_image_path)
    print(f"Imagen de validacion: {output_image_path} ({num_boxes} boxes)")


def main() -> None:
    if len(sys.argv) != 5:
        print("Uso: create_validation_image.py <page_num> <fields.json> "
              "<input_image> <output_image>")
        sys.exit(1)

    page_number = int(sys.argv[1])
    create_validation_image(
        page_number,
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
    )


if __name__ == "__main__":
    main()
