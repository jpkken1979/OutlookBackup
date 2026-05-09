"""
Convierte un PDF a imagenes PNG (una por pagina).

Requiere: pip install pdf2image Pillow

Uso:
    python convert_pdf_to_images.py <input.pdf> <output_dir>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pdf2image import convert_from_path


def convert(pdf_path: str, output_dir: str, max_dim: int = 1000) -> None:
    """Convierte un PDF a imagenes PNG.

    Args:
        pdf_path: Ruta al PDF.
        output_dir: Directorio donde guardar las imagenes.
        max_dim: Maximo ancho o alto en pixels para reescalar.
                  Si 0, no reescala.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    imagenes = convert_from_path(pdf_path, dpi=200)

    for i, image in enumerate(imagenes, 1):
        width, height = image.size
        if max_dim > 0 and (width > max_dim or height > max_dim):
            scale = min(max_dim / width, max_dim / height)
            image = image.resize((int(width * scale), int(height * scale)))

        image_path = os.path.join(output_dir, f"page_{i}.png")
        image.save(image_path, "PNG")
        print(f"Page {i}: {image_path} ({image.size})")

    print(f"Convertido {len(imagenes)} paginas a PNG en {output_dir}")


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: convert_pdf_to_images.py <input.pdf> <output_dir>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
