"""Shared dataclasses for ce-figma-design-sync agent.

Contains all design token types and result structures used by both
main.py and scripts/figma_snapshot.py.
"""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ColorToken:
    """A color token extracted from Figma."""

    name: str
    hex_value: str
    opacity: float = 1.0
    fill_type: str = "solid"  # solid, gradient, etc.


@dataclass
class TypographyToken:
    """A typography token extracted from Figma."""

    name: str
    font_family: str
    font_size: float
    font_weight: int
    line_height: float
    letter_spacing: float = 0.0


@dataclass
class SpacingToken:
    """A spacing token extracted from Figma."""

    name: str
    value: float


@dataclass
class EffectToken:
    """An effect token (shadow, blur) from Figma."""

    name: str
    effect_type: str  # shadow, blur, etc.
    offset_x: float = 0.0
    offset_y: float = 0.0
    blur: float = 0.0
    spread: float = 0.0
    color: str = "#000000"
    opacity: float = 1.0


@dataclass
class BorderToken:
    """A border token from Figma."""

    name: str
    width: float
    style: str  # solid, dashed, etc.
    color: str


@dataclass
class DesignTokens:
    """Complete set of design tokens from Figma."""

    colors: list[ColorToken] = field(default_factory=list)
    typography: list[TypographyToken] = field(default_factory=list)
    spacing: list[SpacingToken] = field(default_factory=list)
    effects: list[EffectToken] = field(default_factory=list)
    borders: list[BorderToken] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "colors": [asdict(c) for c in self.colors],
            "typography": [asdict(t) for t in self.typography],
            "spacing": [asdict(s) for s in self.spacing],
            "effects": [asdict(e) for e in self.effects],
            "borders": [asdict(b) for b in self.borders],
        }


# Helper converters for scripts/figma_snapshot.py compatibility
def _color_to_dict(c: ColorToken) -> dict:
    """Convert ColorToken to dict."""
    return {"name": c.name, "hex": c.hex_value, "opacity": c.opacity, "fill_type": c.fill_type}


def _typography_to_dict(t: TypographyToken) -> dict:
    """Convert TypographyToken to dict."""
    return {
        "name": t.name,
        "fontFamily": t.font_family,
        "fontSize": t.font_size,
        "fontWeight": t.font_weight,
        "lineHeight": t.line_height,
        "letterSpacing": t.letter_spacing,
    }


def _spacing_to_dict(s: SpacingToken) -> dict:
    """Convert SpacingToken to dict."""
    return {"name": s.name, "value": s.value}


def _effect_to_dict(e: EffectToken) -> dict:
    """Convert EffectToken to dict."""
    return {
        "name": e.name,
        "effect_type": e.effect_type,
        "offsetX": e.offset_x,
        "offsetY": e.offset_y,
        "blur": e.blur,
        "spread": e.spread,
        "color": e.color,
        "opacity": e.opacity,
    }


def _border_to_dict(b: BorderToken) -> dict:
    """Convert BorderToken to dict."""
    return {"name": b.name, "width": b.width, "style": b.style, "color": b.color}


@dataclass
class DiffItem:
    """A single diff item between design and implementation."""

    category: str  # colors, typography, spacing, effects, borders
    token_name: str
    figma_value: str
    implementation_value: str
    severity: str  # high, medium, low
    selector: str = ""
    property_name: str = ""
    suggested_value: str = ""

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class SyncResult:
    """Result of a design sync operation."""

    status: str  # completed, partial, failed
    figma_url: str
    implementation_url: str
    tokens_matched: int = 0
    tokens_mismatched: int = 0
    tokens_missing: int = 0
    diff_items: list[DiffItem] = field(default_factory=list)
    css_snippet: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "status": self.status,
            "figma_url": self.figma_url,
            "implementation_url": self.implementation_url,
            "tokens_matched": self.tokens_matched,
            "tokens_mismatched": self.tokens_mismatched,
            "tokens_missing": self.tokens_missing,
            "diff": [asdict(d) for d in self.diff_items],
            "css_snippet": self.css_snippet,
            "errors": self.errors,
        }
