"""
Detecta si un PDF tiene campos fillable.

Uso:
    python check_fillable_fields.py <file.pdf>

Salida:
    "This PDF has fillable form fields" -> usar fill_fillable_fields.py
    "This PDF does not have fillable form fields" -> usar fill_pdf_form_with_annotations.py
"""

from __future__ import annotations

import sys

from pypdf import PdfReader


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: check_fillable_fields.py <file.pdf>")
        sys.exit(1)

    reader = PdfReader(sys.argv[1])
    if reader.get_fields():
        print("This PDF has fillable form fields")
    else:
        print("This PDF does not have fillable form fields; "
              "you will need to visually determine where to enter data")


if __name__ == "__main__":
    main()
