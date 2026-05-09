"""
Valida bounding boxes de fields.json antes de rellenar un form.

Checks:
    - Bounding boxes de label y entry no se intersectan
    - Alto del entry box es suficiente para el font_size

Uso:
    python check_bounding_boxes.py fields.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass


@dataclass
class RectAndField:
    """Rectangulo junto con su tipo y campo asociado."""
    rect: list[float]
    rect_type: str
    field: dict


def rects_intersect(r1: list[float], r2: list[float]) -> bool:
    """True si dos rectangulos [l,b,r,t] se intersectan."""
    disjoint_h = r1[0] >= r2[2] or r1[2] <= r2[0]
    disjoint_v = r1[1] >= r2[3] or r1[3] <= r2[1]
    return not (disjoint_h or disjoint_v)


def get_bounding_box_messages(fields_json_path: str) -> list[str]:
    """Valida un archivo fields.json y devuelve mensajes de error.

    Args:
        fields_json_path: Ruta al archivo fields.json.

    Returns:
        Lista de mensajes (SUCCESS o FAILURE).
    """
    messages: list[str] = []
    with open(fields_json_path, encoding="utf-8") as f:
        fields = json.load(f)

    messages.append(f"Read {len(fields['form_fields'])} fields")

    rects_and_fields: list[RectAndField] = []
    for field in fields["form_fields"]:
        rects_and_fields.append(RectAndField(field["label_bounding_box"], "label", field))
        rects_and_fields.append(RectAndField(field["entry_bounding_box"], "entry", field))

    has_error = False
    for i, ri in enumerate(rects_and_fields):
        for j in range(i + 1, len(rects_and_fields)):
            rj = rects_and_fields[j]
            if ri.field["page_number"] == rj.field["page_number"] and \
               rects_intersect(ri.rect, rj.rect):
                has_error = True
                if ri.field is rj.field:
                    messages.append(
                        f"FAILURE: label y entry se intersectan para "
                        f"`{ri.field['description']}` ({ri.rect}, {rj.rect})"
                    )
                else:
                    messages.append(
                        f"FAILURE: {ri.rect_type} box para "
                        f"`{ri.field['description']}` ({ri.rect}) intersecta con "
                        f"{rj.rect_type} box para `{rj.field['description']}` ({rj.rect})"
                    )
                if len(messages) >= 20:
                    messages.append("Abortando. Corregir bounding boxes e intentar de nuevo.")
                    return messages

        if ri.rect_type == "entry":
            entry_text = ri.field.get("entry_text") or {}
            if entry_text:
                font_size = entry_text.get("font_size", 14)
                entry_height = ri.rect[3] - ri.rect[1]
                if entry_height < font_size:
                    has_error = True
                    messages.append(
                        f"FAILURE: entry box height ({entry_height}) para "
                        f"`{ri.field['description']}` es menor al font_size ({font_size}). "
                        f"Aumentar alto o reducir font_size."
                    )
                    if len(messages) >= 20:
                        messages.append("Abortando. Corregir bounding boxes e intentar de nuevo.")
                        return messages

    if not has_error:
        messages.append("SUCCESS: All bounding boxes are valid")
    return messages


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: check_bounding_boxes.py <fields.json>")
        sys.exit(1)

    messages = get_bounding_box_messages(sys.argv[1])
    for msg in messages:
        print(msg)


if __name__ == "__main__":
    main()
