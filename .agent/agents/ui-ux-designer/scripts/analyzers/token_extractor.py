"""Token extractor — CSS/Tailwind v4 → W3C DTCG 2025.10 format."""
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field

import tinycss2

logger = logging.getLogger(__name__)

_COLOR_PATTERNS = re.compile(
    r"(color|bg|background|text|border|ring|fill|stroke|shadow)", re.IGNORECASE
)
_SPACING_PATTERNS = re.compile(
    r"(spacing|gap|padding|margin|inset|space|size|width|height)", re.IGNORECASE
)
_FONT_PATTERNS = re.compile(
    r"(font|text-size|line-height|letter-spacing|tracking|leading)", re.IGNORECASE
)
_DRIFT_PATTERNS = re.compile(
    r'(?:text|bg|border|fill|stroke)-\[#[0-9a-fA-F]{3,6}\]'
    r'|color:\s*["\']?#[0-9a-fA-F]{3,6}'
    r'|style=\{.*?#[0-9a-fA-F]{3,6}.*?\}',
    re.DOTALL,
)


@dataclass
class TokenExtractionResult:
    """Resultado completo de extracción de tokens."""

    tokens: dict = field(default_factory=dict)
    drift_violations: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)


def _classify_token(name: str, value: str) -> tuple[str, list[str]]:  # noqa: ARG001
    """Clasifica un CSS custom property en tipo DTCG y jerarquía de nombre.

    Args:
        name: Nombre de la variable CSS (ej. --color-primary-500).
        value: Valor de la variable.

    Returns:
        Tupla (dtcg_type, path_parts) donde path_parts es la jerarquía de claves.
    """
    clean = name.lstrip("-")
    parts = clean.split("-")

    if _COLOR_PATTERNS.match(parts[0]):
        return "color", parts
    if _SPACING_PATTERNS.match(parts[0]):
        return "dimension", parts
    if _FONT_PATTERNS.match(parts[0]):
        dtcg_type = "fontFamily" if "family" in clean else "dimension"
        return dtcg_type, parts
    return "string", parts


def _set_nested(d: dict, keys: list[str], value: object) -> None:
    """Inserta value en d siguiendo la jerarquía de keys."""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def extract_tokens_from_css(css_text: str) -> dict:
    """Extrae design tokens de CSS/Tailwind v4 en formato W3C DTCG.

    Args:
        css_text: Contenido CSS con custom properties.

    Returns:
        Dict en formato DTCG anidado por categoría.
    """
    if not css_text.strip():
        return {}

    result: dict = {}
    try:
        rules = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
    except Exception as exc:
        logger.warning("Error parseando CSS: %s", exc)
        return {}

    for rule in rules:
        if rule.type == "qualified-rule":
            decls = tinycss2.parse_declaration_list(
                rule.content, skip_comments=True, skip_whitespace=True
            )
            for decl in decls:
                if decl.type == "declaration" and decl.name.startswith("--"):
                    raw_value = tinycss2.serialize(decl.value).strip()
                    dtcg_type, path_parts = _classify_token(decl.name, raw_value)
                    token_node = {"$value": raw_value, "$type": dtcg_type}
                    _set_nested(result, path_parts, token_node)
        elif rule.type == "at-rule" and rule.at_keyword in ("layer", "theme"):
            if rule.content:
                inner_css = tinycss2.serialize(rule.content)
                nested = extract_tokens_from_css(inner_css)
                for k, v in nested.items():
                    if k in result and isinstance(result[k], dict):
                        result[k].update(v)
                    else:
                        result[k] = v

    return result


def detect_token_drift(code: str, tokens: dict) -> list[str]:  # noqa: ARG001
    """Detecta valores hardcodeados que deberían usar design tokens.

    Args:
        code: Código fuente (TSX, JSX, CSS).
        tokens: Design tokens extraídos del proyecto.

    Returns:
        Lista de strings describiendo cada violación.
    """
    violations: list[str] = []
    for match in _DRIFT_PATTERNS.finditer(code):
        violations.append(f"Valor hardcodeado detectado: {match.group().strip()[:80]}")
    return violations


def extract_tokens_from_project(project_path: Path) -> TokenExtractionResult:
    """Escanea el proyecto y extrae todos los design tokens.

    Args:
        project_path: Raíz del proyecto a analizar.

    Returns:
        TokenExtractionResult con tokens, violaciones y archivos procesados.
    """
    all_tokens: dict = {}
    all_drift: list[str] = []
    processed: list[str] = []

    css_files = list(project_path.rglob("*.css")) + list(project_path.rglob("*.scss"))
    css_files = [f for f in css_files if "node_modules" not in str(f) and "dist" not in str(f)]

    for css_file in css_files:
        try:
            text = css_file.read_text(encoding="utf-8")
            tokens = extract_tokens_from_css(text)
            for k, v in tokens.items():
                if k in all_tokens and isinstance(all_tokens[k], dict):
                    all_tokens[k].update(v)
                else:
                    all_tokens[k] = v
            processed.append(str(css_file))
        except Exception as exc:
            logger.warning("No se pudo procesar %s: %s", css_file, exc)

    for ext in ("*.tsx", "*.jsx", "*.ts"):
        for src_file in project_path.rglob(ext):
            if "node_modules" not in str(src_file):
                try:
                    code = src_file.read_text(encoding="utf-8")
                    drift = detect_token_drift(code, all_tokens)
                    all_drift.extend(drift)
                except Exception:
                    pass

    return TokenExtractionResult(
        tokens=all_tokens,
        drift_violations=all_drift,
        source_files=processed,
    )
