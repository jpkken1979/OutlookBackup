"""Contrast checker — validación WCAG 2.2 AA/AAA en espacios de color sRGB y OKLCH."""
import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_OKLCH_RE = re.compile(
    r"oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)\s*\)", re.IGNORECASE
)


@dataclass
class ContrastResult:
    """Resultado de validación de contraste entre dos colores."""

    foreground: str
    background: str
    ratio: float
    passes_aa_normal: bool
    passes_aa_large: bool
    passes_aaa_normal: bool
    suggestion: Optional[str] = None


def _hex_to_linear(hex_color: str) -> tuple[float, float, float]:
    """Convierte hex a RGB lineal (0-1) aplicando gamma inverso sRGB.

    Args:
        hex_color: Color en formato hex (#rgb o #rrggbb).

    Returns:
        Tupla (r, g, b) en espacio lineal.
    """
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return linearize(r), linearize(g), linearize(b)


def _oklch_to_linear_approx(lightness: float) -> float:
    """Aproxima luminancia relativa desde valor L de OKLCH (0-1).

    Args:
        lightness: Valor L de OKLCH en rango 0-1.

    Returns:
        Luminancia relativa aproximada.
    """
    return lightness ** 2


def _relative_luminance(color: str) -> Optional[float]:
    """Calcula luminancia relativa WCAG de un color.

    Args:
        color: Hex (#rrggbb) u oklch(L C H).

    Returns:
        Luminancia relativa (0-1) o None si el color no es reconocible.
    """
    if _HEX_RE.match(color):
        r, g, b = _hex_to_linear(color)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    m = _OKLCH_RE.match(color.strip())
    if m:
        raw_l = m.group(1)
        l_val = float(raw_l.rstrip("%")) / (100 if "%" in raw_l else 1)
        return _oklch_to_linear_approx(l_val)

    return None


def _contrast_ratio(l1: float, l2: float) -> float:
    """Calcula ratio de contraste WCAG entre dos valores de luminancia.

    Args:
        l1: Luminancia relativa del primer color.
        l2: Luminancia relativa del segundo color.

    Returns:
        Ratio de contraste (1:1 a 21:1).
    """
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _darken_hex(hex_color: str, factor: float = 0.8) -> str:
    """Oscurece un color hex por un factor (0-1).

    Args:
        hex_color: Color en formato hex.
        factor: Factor de oscurecimiento (0=negro, 1=sin cambio).

    Returns:
        Color hex oscurecido.
    """
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    r2, g2, b2 = (max(0, int(c * factor)) for c in (r, g, b))
    return f"#{r2:02x}{g2:02x}{b2:02x}"


def check_contrast(fg: str, bg: str) -> ContrastResult:
    """Valida contraste WCAG 2.2 entre dos colores.

    Args:
        fg: Color de primer plano (hex o oklch).
        bg: Color de fondo (hex o oklch).

    Returns:
        ContrastResult con ratio y niveles de compliance.
    """
    l_fg = _relative_luminance(fg)
    l_bg = _relative_luminance(bg)

    if l_fg is None or l_bg is None:
        logger.warning("No se pudo calcular luminancia para %s / %s", fg, bg)
        return ContrastResult(
            foreground=fg,
            background=bg,
            ratio=0.0,
            passes_aa_normal=False,
            passes_aa_large=False,
            passes_aaa_normal=False,
        )

    ratio = _contrast_ratio(l_fg, l_bg)
    passes_aa = ratio >= 4.5
    passes_aa_large = ratio >= 3.0
    passes_aaa = ratio >= 7.0

    suggestion = None
    if not passes_aa and _HEX_RE.match(fg):
        candidate = fg
        for _ in range(10):
            candidate = _darken_hex(candidate, 0.85)
            l_cand = _relative_luminance(candidate)
            if l_cand is not None and _contrast_ratio(l_cand, l_bg) >= 4.5:
                suggestion = f"Usar {candidate} en lugar de {fg} para cumplir WCAG AA"
                break

    return ContrastResult(
        foreground=fg,
        background=bg,
        ratio=round(ratio, 2),
        passes_aa_normal=passes_aa,
        passes_aa_large=passes_aa_large,
        passes_aaa_normal=passes_aaa,
        suggestion=suggestion,
    )


def check_tokens_contrast(tokens: dict) -> list[ContrastResult]:
    """Evalúa todos los pares de colores en los design tokens.

    Args:
        tokens: Design tokens en formato DTCG.

    Returns:
        Lista de ContrastResult que NO pasan WCAG AA.
    """
    colors: list[str] = []
    color_group = tokens.get("color", {})
    for v in color_group.values():
        if isinstance(v, dict) and "$value" in v:
            colors.append(v["$value"])

    violations: list[ContrastResult] = []
    for i, fg in enumerate(colors):
        for bg in colors[i + 1 :]:
            result = check_contrast(fg, bg)
            if not result.passes_aa_normal:
                violations.append(result)

    return violations
