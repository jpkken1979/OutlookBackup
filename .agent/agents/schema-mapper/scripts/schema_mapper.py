#!/usr/bin/env python3
"""
Schema Mapper Agent - Mapea datos extraídos a esquemas del usuario.

Transforma campos extraídos (con etiquetas japonesas/inglesas) a
campos normalizados según un schema definido por el usuario.

Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class FieldSchema:
    """Schema de un campo."""

    name: str
    type: str = "string"
    required: bool = False
    aliases: list[str] = field(default_factory=list)


@dataclass
class MappingResult:
    """Resultado del mapeo."""

    success: bool
    mapped_fields: dict[str, Any]
    unmapped_fields: list[str]
    missing_required: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "mapped_fields": self.mapped_fields,
            "unmapped_fields": self.unmapped_fields,
            "missing_required": self.missing_required,
            "warnings": self.warnings,
        }


class SchemaMapper:
    """Mapea datos extraídos a un schema."""

    # Mapeo predefinido de etiquetas japonesas a normalizadas
    JAPANESE_TO_NORMALIZED = {
        "氏名": "nombre",
        "NAME": "nombre",
        "名前": "nombre",
        "生年月日": "fecha_nacimiento",
        "DATE OF BIRTH": "fecha_nacimiento",
        "DOB": "fecha_nacimiento",
        "性別": "genero",
        "SEX": "genero",
        "国籍・地域": "nacionalidad",
        "NATIONALITY/REGION": "nacionalidad",
        "国籍": "nacionalidad",
        "住居地": "direccion",
        "ADDRESS": "direccion",
        "住所": "direccion",
        "在留資格": "estado_residencia",
        "STATUS OF RESIDENCE": "estado_residencia",
        "在留期間": "periodo_estancia",
        "PERIOD OF STAY": "periodo_estancia",
        "在留カード番号": "numero_tarjeta",
        "RESIDENCE CARD NUMBER": "numero_tarjeta",
        "有効期限": "fecha_expiracion",
        "DATE OF EXPIRY": "fecha_expiracion",
        "交付年月日": "fecha_emision",
        "DATE OF ISSUE": "fecha_emision",
    }

    def __init__(self, form_schema: dict[str, Any]):
        """
        Inicializa con el schema.

        Args:
            form_schema: Schema de campos
        """
        self.fields: dict[str, FieldSchema] = {}
        for name, config in form_schema.items():
            if isinstance(config, dict):
                aliases = config.get("aliases", [name])
                # Add Japanese mappings if applicable
                norm_aliases = []
                for alias in aliases:
                    norm_aliases.append(alias)
                    # Add reverse mappings
                    if alias in self.JAPANESE_TO_NORMALIZED:
                        norm_aliases.append(self.JAPANESE_TO_NORMALIZED[alias])

                self.fields[name] = FieldSchema(
                    name=name,
                    type=config.get("type", "string"),
                    required=config.get("required", False),
                    aliases=list(set(norm_aliases)),
                )
            else:
                self.fields[name] = FieldSchema(name=name, aliases=[name])

    def map_fields(self, extracted_data: dict[str, Any]) -> MappingResult:
        """
        Mapea datos extraídos al schema.

        Args:
            extracted_data: Datos extraídos (label -> value)

        Returns:
            MappingResult con datos mapeados
        """
        result = {}
        warnings = []
        unmapped = []
        missing_required = []

        # Track which input fields were used
        used_keys = set()

        for field_name, field_schema in self.fields.items():
            value = None
            matched_key = None

            # Search by aliases
            for alias in field_schema.aliases:
                alias_lower = alias.lower()

                for key, val in extracted_data.items():
                    key_lower = key.lower() if isinstance(key, str) else str(key)

                    if (
                        alias_lower == key_lower
                        or alias_lower in key_lower
                        or key_lower in alias_lower
                    ):
                        value = val
                        matched_key = key
                        break

                if value is not None:
                    break

            # Validate type if value found
            if value is not None:
                used_keys.add(matched_key)

                if field_schema.type == "date" and not self._is_valid_date(value):
                    warnings.append(
                        f"Campo '{field_name}' tiene formato de fecha inválido: {value}"
                    )

                if field_schema.type == "number":
                    try:
                        value = float(value) if isinstance(value, str) else value
                    except (ValueError, TypeError):
                        warnings.append(f"Campo '{field_name}' no es un número válido: {value}")

            # Check required fields
            if value is None and field_schema.required:
                missing_required.append(field_name)

            result[field_name] = value

        # Find unmapped fields
        for key in extracted_data:
            if key not in used_keys:
                unmapped.append(key)

        success = len(missing_required) == 0

        return MappingResult(
            success=success,
            mapped_fields=result,
            unmapped_fields=unmapped,
            missing_required=missing_required,
            warnings=warnings,
        )

    @staticmethod
    def _is_valid_date(value: Any) -> bool:
        """Verifica si es una fecha válida (YYYY-MM-DD)."""
        if not isinstance(value, str):
            return False
        return bool(re.match(r"\d{4}-\d{2}-\d{2}", value))


# Default schema for Japanese ID documents
DEFAULT_ZAIRYUCARD_SCHEMA = {
    "nombre": {"type": "string", "required": True, "aliases": ["氏名", "NAME", "名前"]},
    "fecha_nacimiento": {
        "type": "date",
        "required": True,
        "aliases": ["生年月日", "DATE OF BIRTH", "DOB"],
    },
    "genero": {"type": "string", "aliases": ["性別", "SEX"]},
    "nacionalidad": {"type": "string", "aliases": ["国籍・地域", "国籍", "NATIONALITY"]},
    "direccion": {"type": "string", "aliases": ["住居地", "住所", "ADDRESS"]},
    "estado_residencia": {"type": "string", "aliases": ["在留資格", "STATUS OF RESIDENCE"]},
    "periodo_estancia": {"type": "string", "aliases": ["在留期間", "PERIOD OF STAY"]},
    "numero_tarjeta": {"type": "string", "aliases": ["在留カード番号", "RESIDENCE CARD NUMBER"]},
    "fecha_expiracion": {"type": "date", "aliases": ["有効期限", "DATE OF EXPIRY"]},
}


def map_data(data: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Función de conveniencia para mapear datos.

    Args:
        data: Datos extraídos
        schema: Schema a usar (default: Zairyū Card)

    Returns:
        Resultado del mapeo
    """
    if schema is None:
        schema = DEFAULT_ZAIRYUCARD_SCHEMA

    mapper = SchemaMapper(schema)
    result = mapper.map_fields(data)
    return result.to_dict()


def main():
    parser = argparse.ArgumentParser(
        description="Schema Mapper Agent - Mapea datos extraídos a esquemas"
    )
    parser.add_argument("input", help="Archivo JSON con datos extraídos")
    parser.add_argument(
        "--schema", help="Archivo JSON con schema de campos (default: Zairyū Card schema)"
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")

    args = parser.parse_args()

    # Load input data
    try:
        with open(args.input) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error cargando datos: {e}", file=sys.stderr)
        sys.exit(1)

    # Load schema
    schema = DEFAULT_ZAIRYUCARD_SCHEMA
    if args.schema:
        try:
            with open(args.schema) as f:
                schema = json.load(f)
        except Exception as e:
            print(f"Error cargando schema: {e}", file=sys.stderr)
            sys.exit(1)

    # Map
    mapper = SchemaMapper(schema)
    result = mapper.map_fields(data)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Mapeo {'exitoso' if result.success else 'con errores'}")

        print("\n=== Campos mapeados ===")
        for field, value in result.mapped_fields.items():
            status = "OK" if value is not None else "MISSING"
            print(f"  [{status}] {field}: {value}")

        if result.unmapped_fields:
            print("\n=== Campos no mapeados ===")
            for field in result.unmapped_fields:
                print(f"  - {field}")

        if result.missing_required:
            print("\n=== Campos requeridos faltantes ===")
            for field in result.missing_required:
                print(f"  - {field}")

        if result.warnings:
            print("\n=== Advertencias ===")
            for w in result.warnings:
                print(f"  - {w}")


if __name__ == "__main__":
    main()
