"""
Rellena campos fillable de un PDF con valores dados.

Verifica que los field_ids y valores sean validos antes de escribir.

Requiere: pip install pypdf

Uso:
    python fill_fillable_fields.py <input.pdf> <field_values.json> <output.pdf>

field_values.json formato:
    [
        {"field_id": "nombre", "page": 1, "value": "Kaneshiro"},
        {"field_id": "Checkbox1", "page": 1, "value": "/On"}
    ]
"""

from __future__ import annotations

import json
import sys
from typing import Any

from pypdf import PdfReader, PdfWriter

from extract_form_field_info import get_field_info


def monkeypatch_pydpf_choice_fields() -> None:
    """Patch pypdf para que /Opt en fields choice devuelva valores simples."""
    from pypdf.generic import DictionaryObject
    from pypdf.constants import FieldDictionaryAttributes

    original = DictionaryObject.get_inherited

    def patched(self: Any, key: str, default: Any = None) -> Any:
        result = original(self, key, default)
        if key == FieldDictionaryAttributes.Opt:
            if isinstance(result, list) and \
               all(isinstance(v, list) and len(v) == 2 for v in result):
                result = [r[0] for r in result]
        return result

    DictionaryObject.get_inherited = patched  # type: ignore[method-assign]


def validation_error_for_field_value(field_info: dict, field_value: str) -> str | None:
    """Valida que un valor sea correcto para el tipo de campo.

    Args:
        field_info: Info del campo de get_field_info().
        field_value: Valor a validar.

    Returns:
        Mensaje de error o None si es valido.
    """
    ftype = field_info["type"]
    fid = field_info["field_id"]

    if ftype == "checkbox":
        checked = field_info["checked_value"]
        unchecked = field_info["unchecked_value"]
        if field_value != checked and field_value != unchecked:
            return (f'ERROR: Valor invalido "{field_value}" para checkbox "{fid}". '
                    f'Valores validos: "{checked}" (checked) o "{unchecked}" (unchecked)')
    elif ftype == "radio_group":
        options = [opt["value"] for opt in field_info["radio_options"]]
        if field_value not in options:
            return (f'ERROR: Valor invalido "{field_value}" para radio group "{fid}". '
                    f'Opciones: {options}')
    elif ftype == "choice":
        choices = [opt["value"] for opt in field_info["choice_options"]]
        if field_value not in choices:
            return (f'ERROR: Valor invalido "{field_value}" para choice "{fid}". '
                    f'Opciones: {choices}')
    return None


def fill_pdf_fields(
    input_pdf_path: str,
    fields_json_path: str,
    output_pdf_path: str,
) -> None:
    """Rellena campos fillable de un PDF con validacion.

    Args:
        input_pdf_path: PDF de entrada con campos fillable.
        fields_json_path: JSON con valores de campos.
        output_pdf_path: PDF de salida.

    Raises:
        SystemExit: Si hay errores de validacion.
    """
    with open(fields_json_path, encoding="utf-8") as f:
        fields = json.load(f)

    # Agrupar por pagina
    por_pagina: dict[int, dict[str, str]] = {}
    for field in fields:
        if "value" in field:
            fid = field["field_id"]
            page = field["page"]
            por_pagina.setdefault(page, {})[fid] = field["value"]

    reader = PdfReader(input_pdf_path)

    # Validar field_ids y page numbers
    has_error = False
    field_info = get_field_info(reader)
    por_id: dict[str, dict] = {f["field_id"]: f for f in field_info}

    for field in fields:
        fid = field["field_id"]
        existing = por_id.get(fid)
        if not existing:
            print(f"ERROR: `{fid}` no es un field_id valido.", file=sys.stderr)
            has_error = True
        elif field.get("page") != existing.get("page"):
            print(f"ERROR: Pagina incorrecta para `{fid}` "
                  f"(dio {field.get('page')}, expected {existing.get('page')}).",
                  file=sys.stderr)
            has_error = True
        elif "value" in field:
            err = validation_error_for_field_value(existing, field["value"])
            if err:
                print(err, file=sys.stderr)
                has_error = True

    if has_error:
        sys.exit(1)

    # Escribir
    writer = PdfWriter(clone_from=reader)
    for page_num, values in por_pagina.items():
        writer.update_page_form_field_values(
            writer.pages[page_num - 1], values, auto_regenerate=False
        )
    writer.set_need_appearances_writer(True)

    with open(output_pdf_path, "wb") as out:
        writer.write(out)
    print(f"Completado: {output_pdf_path} ({sum(len(v) for v in por_pagina.values())} campos)")


def main() -> None:
    if len(sys.argv) != 4:
        print("Uso: fill_fillable_fields.py <input.pdf> <field_values.json> <output.pdf>")
        sys.exit(1)

    monkeypatch_pydpf_choice_fields()
    fill_pdf_fields(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
