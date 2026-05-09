"""
Extrae la estructura de campos fillable de un PDF.

Devuelve un JSON con cada campo: field_id, page, rect, type,
y para checkbox/radio/choice los valores posibles.

Uso:
    python extract_form_field_info.py input.pdf field_info.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from pypdf import PdfReader


def get_full_annotation_field_id(annotation: Any) -> str | None:
    """Reconstruye el field_id completo desde la jerarquia de annotation."""
    components: list[str] = []
    while annotation:
        field_name = annotation.get("/T")
        if field_name:
            components.append(field_name)
        annotation = annotation.get("/Parent")
    return ".".join(reversed(components)) if components else None


def make_field_dict(field: Any, field_id: str) -> dict[str, Any]:
    """Convierte un field dict de pypdf a formato canonico."""
    result: dict[str, Any] = {"field_id": field_id}
    ft = field.get("/FT")
    if ft == "/Tx":
        result["type"] = "text"
    elif ft == "/Btn":
        result["type"] = "checkbox"
        states = field.get("/_States_", [])
        if len(states) == 2:
            if "/Off" in states:
                result["checked_value"] = states[0] if states[0] != "/Off" else states[1]
                result["unchecked_value"] = "/Off"
            else:
                print(f"Estado inesperado para checkbox '{field_id}'. "
                      "Verificar visualmente el resultado.", file=sys.stderr)
                result["checked_value"] = states[0]
                result["unchecked_value"] = states[1]
    elif ft == "/Ch":
        result["type"] = "choice"
        states = field.get("/_States_", [])
        result["choice_options"] = [{"value": s[0], "text": s[1]} for s in states]
    else:
        result["type"] = f"unknown ({ft})"
    return result


def get_field_info(reader: PdfReader) -> list[dict[str, Any]]:
    """Extrae informacion de todos los campos fillable del PDF.

    Args:
        reader: PdfReader abierto.

    Returns:
        Lista de dicts con field_id, page, rect, type, y opciones
        para checkbox/radio/choice.
    """
    fields = reader.get_fields()
    if not fields:
        return []

    field_info_by_id: dict[str, dict[str, Any]] = {}
    possible_radio_names: set[str] = set()

    for field_id, field in fields.items():
        if field.get("/Kids"):
            if field.get("/FT") == "/Btn":
                possible_radio_names.add(field_id)
            continue
        field_info_by_id[field_id] = make_field_dict(field, field_id)

    radio_fields_by_id: dict[str, dict[str, Any]] = {}

    for page_index, page in enumerate(reader.pages):
        annotations = page.get("/Annots", [])
        for ann in annotations:
            field_id = get_full_annotation_field_id(ann)
            if field_id in field_info_by_id:
                field_info_by_id[field_id]["page"] = page_index + 1
                field_info_by_id[field_id]["rect"] = ann.get("/Rect")
            elif field_id in possible_radio_names:
                try:
                    on_values = [v for v in ann["/AP"]["/N"] if v != "/Off"]
                except KeyError:
                    continue
                if len(on_values) == 1:
                    rect = ann.get("/Rect")
                    if field_id not in radio_fields_by_id:
                        radio_fields_by_id[field_id] = {
                            "field_id": field_id,
                            "type": "radio_group",
                            "page": page_index + 1,
                            "radio_options": [],
                        }
                    radio_fields_by_id[field_id]["radio_options"].append({
                        "value": on_values[0],
                        "rect": rect,
                    })

    # Filtrar campos sin location y ordenar
    sorted_fields: list[dict[str, Any]] = []
    for f in field_info_by_id.values():
        if "page" in f:
            sorted_fields.append(f)
        else:
            print(f"Ignorado (sin location): {f.get('field_id')}", file=sys.stderr)

    def sort_key(f: dict[str, Any]) -> list:
        if "radio_options" in f:
            rect = (f["radio_options"][0].get("rect") or [0, 0, 0, 0])
        else:
            rect = f.get("rect") or [0, 0, 0, 0]
        adjusted_position = [-rect[1], rect[0]]
        return [f.get("page"), adjusted_position]

    sorted_fields.sort(key=sort_key)
    sorted_fields.extend(list(radio_fields_by_id.values()))
    return sorted_fields


def write_field_info(pdf_path: str, json_output_path: str) -> None:
    """Escribe la info de campos a un archivo JSON.

    Args:
        pdf_path: Ruta al PDF de entrada.
        json_output_path: Ruta del JSON de salida.
    """
    reader = PdfReader(pdf_path)
    field_info = get_field_info(reader)
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(field_info, f, indent=2)
    print(f"{len(field_info)} campos escritos en {json_output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: extract_form_field_info.py <input.pdf> <output.json>")
        sys.exit(1)
    write_field_info(sys.argv[1], sys.argv[2])
