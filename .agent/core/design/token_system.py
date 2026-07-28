# mypy: ignore-errors
#!/usr/bin/env python3
"""
Design Token System.

Comprehensive token architecture following industry best practices:
- Primitive tokens (raw values)
- Semantic tokens (meaning)
- Component tokens (specific usage)

Exports to:
- CSS Custom Properties
- Tailwind config
- SCSS variables
- JSON
- Swift (iOS)
- Kotlin (Android)

Version: 1.0.0
"""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("token-system")


class TokenCategory(Enum):
    """Token categories."""

    COLOR = "color"
    TYPOGRAPHY = "typography"
    SPACING = "spacing"
    BORDER_RADIUS = "borderRadius"
    SHADOW = "shadow"
    MOTION = "motion"
    BREAKPOINT = "breakpoint"
    Z_INDEX = "zIndex"


class TokenLevel(Enum):
    """Token hierarchy levels."""

    PRIMITIVE = "primitive"
    SEMANTIC = "semantic"
    COMPONENT = "component"


@dataclass
class Token:
    """A design token."""

    name: str
    value: Any
    category: TokenCategory
    level: TokenLevel
    description: str | None = None
    reference: str | None = None  # Reference to another token
    deprecated: bool = False


@dataclass
class TokenTheme:
    """A collection of tokens for a theme."""

    name: str
    tokens: dict[str, Token]
    extends: str | None = None


class DesignTokenSystem:
    """
    Comprehensive design token system.

    Features:
    - Three-level hierarchy (primitive → semantic → component)
    - Theme support (light/dark/brand)
    - Multi-format export
    - Validation and consistency checks
    - Reference resolution
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.primitives: dict[str, Token] = {}
        self.semantics: dict[str, Token] = {}
        self.components: dict[str, Token] = {}
        self.themes: dict[str, TokenTheme] = {}

        # Initialize with defaults
        self._init_default_primitives()

    def _init_default_primitives(self):
        """Initialize default primitive tokens."""
        # Colors - Gray scale
        grays = {
            "50": "#fafafa",
            "100": "#f4f4f5",
            "200": "#e4e4e7",
            "300": "#d4d4d8",
            "400": "#a1a1aa",
            "500": "#71717a",
            "600": "#52525b",
            "700": "#3f3f46",
            "800": "#27272a",
            "900": "#18181b",
            "950": "#09090b",
        }
        for shade, value in grays.items():
            self.add_primitive(f"color.gray.{shade}", value, TokenCategory.COLOR)

        # Colors - Primary (blue)
        blues = {
            "50": "#eff6ff",
            "100": "#dbeafe",
            "200": "#bfdbfe",
            "300": "#93c5fd",
            "400": "#60a5fa",
            "500": "#3b82f6",
            "600": "#2563eb",
            "700": "#1d4ed8",
            "800": "#1e40af",
            "900": "#1e3a8a",
            "950": "#172554",
        }
        for shade, value in blues.items():
            self.add_primitive(f"color.primary.{shade}", value, TokenCategory.COLOR)

        # Colors - Feedback
        self.add_primitive("color.red.500", "#ef4444", TokenCategory.COLOR)
        self.add_primitive("color.red.600", "#dc2626", TokenCategory.COLOR)
        self.add_primitive("color.green.500", "#22c55e", TokenCategory.COLOR)
        self.add_primitive("color.green.600", "#16a34a", TokenCategory.COLOR)
        self.add_primitive("color.amber.500", "#f59e0b", TokenCategory.COLOR)
        self.add_primitive("color.amber.600", "#d97706", TokenCategory.COLOR)

        # White/Black
        self.add_primitive("color.white", "#ffffff", TokenCategory.COLOR)
        self.add_primitive("color.black", "#000000", TokenCategory.COLOR)

        # Typography
        self.add_primitive(
            "font.family.sans", "Inter, system-ui, sans-serif", TokenCategory.TYPOGRAPHY
        )
        self.add_primitive(
            "font.family.mono", "JetBrains Mono, monospace", TokenCategory.TYPOGRAPHY
        )

        font_sizes = {
            "xs": "0.75rem",
            "sm": "0.875rem",
            "base": "1rem",
            "lg": "1.125rem",
            "xl": "1.25rem",
            "2xl": "1.5rem",
            "3xl": "1.875rem",
            "4xl": "2.25rem",
        }
        for size, value in font_sizes.items():
            self.add_primitive(f"font.size.{size}", value, TokenCategory.TYPOGRAPHY)

        font_weights = {"normal": "400", "medium": "500", "semibold": "600", "bold": "700"}
        for weight, value in font_weights.items():
            self.add_primitive(f"font.weight.{weight}", value, TokenCategory.TYPOGRAPHY)

        line_heights = {"tight": "1.25", "normal": "1.5", "relaxed": "1.75"}
        for height, value in line_heights.items():
            self.add_primitive(f"font.lineHeight.{height}", value, TokenCategory.TYPOGRAPHY)

        # Spacing
        spacing = {
            "0": "0",
            "1": "0.25rem",
            "2": "0.5rem",
            "3": "0.75rem",
            "4": "1rem",
            "5": "1.25rem",
            "6": "1.5rem",
            "8": "2rem",
            "10": "2.5rem",
            "12": "3rem",
            "16": "4rem",
            "20": "5rem",
        }
        for size, value in spacing.items():
            self.add_primitive(f"spacing.{size}", value, TokenCategory.SPACING)

        # Border radius
        radii = {
            "none": "0",
            "sm": "0.125rem",
            "md": "0.375rem",
            "lg": "0.5rem",
            "xl": "0.75rem",
            "2xl": "1rem",
            "full": "9999px",
        }
        for size, value in radii.items():
            self.add_primitive(f"radius.{size}", value, TokenCategory.BORDER_RADIUS)

        # Shadows
        self.add_primitive("shadow.sm", "0 1px 2px 0 rgb(0 0 0 / 0.05)", TokenCategory.SHADOW)
        self.add_primitive("shadow.md", "0 4px 6px -1px rgb(0 0 0 / 0.1)", TokenCategory.SHADOW)
        self.add_primitive("shadow.lg", "0 10px 15px -3px rgb(0 0 0 / 0.1)", TokenCategory.SHADOW)
        self.add_primitive("shadow.xl", "0 20px 25px -5px rgb(0 0 0 / 0.1)", TokenCategory.SHADOW)

        # Motion
        self.add_primitive("motion.duration.fast", "150ms", TokenCategory.MOTION)
        self.add_primitive("motion.duration.normal", "300ms", TokenCategory.MOTION)
        self.add_primitive("motion.duration.slow", "500ms", TokenCategory.MOTION)
        self.add_primitive(
            "motion.easing.default", "cubic-bezier(0.4, 0, 0.2, 1)", TokenCategory.MOTION
        )
        self.add_primitive("motion.easing.in", "cubic-bezier(0.4, 0, 1, 1)", TokenCategory.MOTION)
        self.add_primitive("motion.easing.out", "cubic-bezier(0, 0, 0.2, 1)", TokenCategory.MOTION)

        # Breakpoints
        self.add_primitive("breakpoint.sm", "640px", TokenCategory.BREAKPOINT)
        self.add_primitive("breakpoint.md", "768px", TokenCategory.BREAKPOINT)
        self.add_primitive("breakpoint.lg", "1024px", TokenCategory.BREAKPOINT)
        self.add_primitive("breakpoint.xl", "1280px", TokenCategory.BREAKPOINT)

        # Z-index
        self.add_primitive("zIndex.dropdown", "1000", TokenCategory.Z_INDEX)
        self.add_primitive("zIndex.sticky", "1100", TokenCategory.Z_INDEX)
        self.add_primitive("zIndex.modal", "1200", TokenCategory.Z_INDEX)
        self.add_primitive("zIndex.popover", "1300", TokenCategory.Z_INDEX)
        self.add_primitive("zIndex.toast", "1400", TokenCategory.Z_INDEX)

    def add_primitive(
        self, name: str, value: Any, category: TokenCategory, description: str | None = None
    ):
        """Add a primitive token."""
        token = Token(
            name=name,
            value=value,
            category=category,
            level=TokenLevel.PRIMITIVE,
            description=description,
        )
        self.primitives[name] = token

    def add_semantic(
        self, name: str, reference: str, category: TokenCategory, description: str | None = None
    ):
        """Add a semantic token (references a primitive)."""
        if reference not in self.primitives:
            logger.warning(f"Semantic token {name} references unknown primitive: {reference}")

        token = Token(
            name=name,
            value=None,  # Resolved at export time
            category=category,
            level=TokenLevel.SEMANTIC,
            description=description,
            reference=reference,
        )
        self.semantics[name] = token

    def add_component(
        self, name: str, reference: str, category: TokenCategory, description: str | None = None
    ):
        """Add a component token (references semantic or primitive)."""
        token = Token(
            name=name,
            value=None,
            category=category,
            level=TokenLevel.COMPONENT,
            description=description,
            reference=reference,
        )
        self.components[name] = token

    def setup_semantic_tokens(self):
        """Setup default semantic tokens."""
        # Background colors
        self.add_semantic("color.background.primary", "color.white", TokenCategory.COLOR)
        self.add_semantic("color.background.secondary", "color.gray.50", TokenCategory.COLOR)
        self.add_semantic("color.background.tertiary", "color.gray.100", TokenCategory.COLOR)
        self.add_semantic("color.background.inverse", "color.gray.900", TokenCategory.COLOR)
        self.add_semantic("color.background.accent", "color.primary.500", TokenCategory.COLOR)

        # Text colors
        self.add_semantic("color.text.primary", "color.gray.900", TokenCategory.COLOR)
        self.add_semantic("color.text.secondary", "color.gray.600", TokenCategory.COLOR)
        self.add_semantic("color.text.tertiary", "color.gray.500", TokenCategory.COLOR)
        self.add_semantic("color.text.disabled", "color.gray.400", TokenCategory.COLOR)
        self.add_semantic("color.text.inverse", "color.white", TokenCategory.COLOR)
        self.add_semantic("color.text.link", "color.primary.600", TokenCategory.COLOR)

        # Border colors
        self.add_semantic("color.border.default", "color.gray.200", TokenCategory.COLOR)
        self.add_semantic("color.border.strong", "color.gray.300", TokenCategory.COLOR)
        self.add_semantic("color.border.focus", "color.primary.500", TokenCategory.COLOR)

        # Feedback colors
        self.add_semantic("color.feedback.error", "color.red.500", TokenCategory.COLOR)
        self.add_semantic("color.feedback.errorHover", "color.red.600", TokenCategory.COLOR)
        self.add_semantic("color.feedback.success", "color.green.500", TokenCategory.COLOR)
        self.add_semantic("color.feedback.successHover", "color.green.600", TokenCategory.COLOR)
        self.add_semantic("color.feedback.warning", "color.amber.500", TokenCategory.COLOR)
        self.add_semantic("color.feedback.warningHover", "color.amber.600", TokenCategory.COLOR)
        self.add_semantic("color.feedback.info", "color.primary.500", TokenCategory.COLOR)

        # Interactive colors
        self.add_semantic("color.interactive.primary", "color.primary.500", TokenCategory.COLOR)
        self.add_semantic(
            "color.interactive.primaryHover", "color.primary.600", TokenCategory.COLOR
        )
        self.add_semantic(
            "color.interactive.primaryActive", "color.primary.700", TokenCategory.COLOR
        )

    def setup_component_tokens(self):
        """Setup default component tokens."""
        # Button
        self.add_component(
            "button.primary.background", "color.interactive.primary", TokenCategory.COLOR
        )
        self.add_component(
            "button.primary.backgroundHover", "color.interactive.primaryHover", TokenCategory.COLOR
        )
        self.add_component("button.primary.text", "color.text.inverse", TokenCategory.COLOR)
        self.add_component(
            "button.primary.border", "color.interactive.primary", TokenCategory.COLOR
        )

        self.add_component(
            "button.secondary.background", "color.background.secondary", TokenCategory.COLOR
        )
        self.add_component(
            "button.secondary.backgroundHover", "color.background.tertiary", TokenCategory.COLOR
        )
        self.add_component("button.secondary.text", "color.text.primary", TokenCategory.COLOR)

        # Input
        self.add_component("input.background", "color.background.primary", TokenCategory.COLOR)
        self.add_component("input.border", "color.border.default", TokenCategory.COLOR)
        self.add_component("input.borderFocus", "color.border.focus", TokenCategory.COLOR)
        self.add_component("input.borderError", "color.feedback.error", TokenCategory.COLOR)
        self.add_component("input.text", "color.text.primary", TokenCategory.COLOR)
        self.add_component("input.placeholder", "color.text.tertiary", TokenCategory.COLOR)

        # Card
        self.add_component("card.background", "color.background.primary", TokenCategory.COLOR)
        self.add_component("card.border", "color.border.default", TokenCategory.COLOR)

    def resolve_reference(self, reference: str) -> Any:
        """Resolve a token reference to its final value."""
        # Check components first
        if reference in self.components:
            return self.resolve_reference(self.components[reference].reference)
        # Then semantics
        if reference in self.semantics:
            return self.resolve_reference(self.semantics[reference].reference)
        # Finally primitives
        if reference in self.primitives:
            return self.primitives[reference].value
        return reference  # Return as-is if not found

    def get_all_tokens(self) -> dict[str, Any]:
        """Get all tokens with resolved values."""
        result = {}

        # Primitives
        for name, token in self.primitives.items():
            result[name] = token.value

        # Semantics
        for name, token in self.semantics.items():
            result[name] = self.resolve_reference(token.reference)

        # Components
        for name, token in self.components.items():
            result[name] = self.resolve_reference(token.reference)

        return result

    # Export methods
    def export_css(self) -> str:
        """Export as CSS custom properties."""
        lines = [":root {"]

        tokens = self.get_all_tokens()
        for name, value in sorted(tokens.items()):
            css_name = "--" + name.replace(".", "-")
            lines.append(f"  {css_name}: {value};")

        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _set_nested_color(colors: dict, parts: list[str], value: str) -> None:
        """Inserta un color en la estructura anidada según los segmentos del nombre.

        Args:
            colors: Dict raíz de colores (se muta).
            parts: Segmentos del nombre del token (ej. ["color", "primary", "500"]).
            value: Valor del color.
        """
        current = colors
        for part in parts[1:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value

    def _bucketize_tokens(self, tokens: dict[str, str]) -> dict[str, dict]:
        """Agrupa tokens por categoría Tailwind (colors, spacing, font, etc.).

        Args:
            tokens: Mapa nombre.punteado -> valor.

        Returns:
            Dict con las 6 categorías de tokens organizadas.
        """
        buckets: dict[str, dict] = {
            "colors": {},
            "spacing": {},
            "font_size": {},
            "font_family": {},
            "border_radius": {},
            "box_shadow": {},
        }
        for name, value in tokens.items():
            parts = name.split(".")
            head = parts[0]
            if head == "color":
                self._set_nested_color(buckets["colors"], parts, value)
            elif head == "spacing":
                buckets["spacing"][parts[1]] = value
            elif head == "font":
                if parts[1] == "size":
                    buckets["font_size"][parts[2]] = value
                elif parts[1] == "family":
                    buckets["font_family"][parts[2]] = value.split(",")
            elif head == "radius":
                buckets["border_radius"][parts[1]] = value
            elif head == "shadow":
                buckets["box_shadow"][parts[1]] = value
        return buckets

    def export_tailwind_config(self) -> str:
        """Export as Tailwind config."""
        b = self._bucketize_tokens(self.get_all_tokens())

        config = {
            "theme": {
                "extend": {
                    "colors": b["colors"],
                    "spacing": b["spacing"],
                    "fontSize": b["font_size"],
                    "fontFamily": b["font_family"],
                    "borderRadius": b["border_radius"],
                    "boxShadow": b["box_shadow"],
                }
            }
        }

        return f"module.exports = {json.dumps(config, indent=2)}"

    def export_scss(self) -> str:
        """Export as SCSS variables."""
        lines = ["// Design Tokens - Auto-generated", "// Do not edit manually", ""]

        tokens = self.get_all_tokens()
        for name, value in sorted(tokens.items()):
            scss_name = "$" + name.replace(".", "-")
            lines.append(f"{scss_name}: {value};")

        return "\n".join(lines)

    def export_json(self) -> str:
        """Export as JSON."""
        return json.dumps(self.get_all_tokens(), indent=2)

    def export_swift(self) -> str:
        """Export as Swift (iOS)."""
        lines = ["// Design Tokens - Auto-generated", "import SwiftUI", "", "struct DesignTokens {"]

        tokens = self.get_all_tokens()

        # Colors
        lines.append("    struct Colors {")
        for name, value in sorted(tokens.items()):
            if name.startswith("color."):
                swift_name = self._to_camel_case(name.replace("color.", ""))
                if value.startswith("#"):
                    hex_value = value.lstrip("#")
                    lines.append(f'        static let {swift_name} = Color(hex: "{hex_value}")')
        lines.append("    }")

        # Spacing
        lines.append("    struct Spacing {")
        for name, value in sorted(tokens.items()):
            if name.startswith("spacing."):
                swift_name = "size" + name.split(".")[-1]
                # Convert rem to points (assuming 1rem = 16pt)
                pt_value = float(value.replace("rem", "")) * 16 if "rem" in value else value
                lines.append(f"        static let {swift_name}: CGFloat = {pt_value}")
        lines.append("    }")

        lines.append("}")

        # Color extension
        lines.extend(
            [
                "",
                "extension Color {",
                "    init(hex: String) {",
                "        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)",
                "        var int: UInt64 = 0",
                "        Scanner(string: hex).scanHexInt64(&int)",
                "        let a, r, g, b: UInt64",
                "        switch hex.count {",
                "        case 6: (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)",
                "        case 8: (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)",
                "        default: (a, r, g, b) = (255, 0, 0, 0)",
                "        }",
                "        self.init(.sRGB, red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255, opacity: Double(a) / 255)",
                "    }",
                "}",
            ]
        )

        return "\n".join(lines)

    def export_kotlin(self) -> str:
        """Export as Kotlin (Android)."""
        lines = [
            "// Design Tokens - Auto-generated",
            "package com.example.design",
            "",
            "import androidx.compose.ui.graphics.Color",
            "import androidx.compose.ui.unit.dp",
            "import androidx.compose.ui.unit.sp",
            "",
            "object DesignTokens {",
        ]

        tokens = self.get_all_tokens()

        # Colors
        lines.append("    object Colors {")
        for name, value in sorted(tokens.items()):
            if name.startswith("color.") and value.startswith("#"):
                kotlin_name = self._to_camel_case(name.replace("color.", ""))
                hex_value = value.lstrip("#")
                if len(hex_value) == 6:
                    hex_value = "FF" + hex_value
                lines.append(f"        val {kotlin_name} = Color(0x{hex_value.upper()})")
        lines.append("    }")

        # Spacing
        lines.append("    object Spacing {")
        for name, value in sorted(tokens.items()):
            if name.startswith("spacing."):
                kotlin_name = "size" + name.split(".")[-1]
                dp_value = (
                    float(value.replace("rem", "")) * 16
                    if "rem" in value
                    else value.replace("px", "")
                )
                lines.append(f"        val {kotlin_name} = {dp_value}.dp")
        lines.append("    }")

        lines.append("}")

        return "\n".join(lines)

    def _to_camel_case(self, s: str) -> str:
        """Convert to camelCase."""
        parts = re.split(r"[.\-_]", s)
        return parts[0].lower() + "".join(p.title() for p in parts[1:])

    def validate(self) -> list[str]:
        """Validate token system."""
        issues = []

        # Check for broken references
        for name, token in {**self.semantics, **self.components}.items():
            if token.reference:
                all_tokens = {**self.primitives, **self.semantics, **self.components}
                if token.reference not in all_tokens:
                    issues.append(f"Broken reference: {name} -> {token.reference}")

        # Check for color contrast (simplified)
        # In a real implementation, would check WCAG contrast ratios

        return issues

    def save(self, output_dir: str, formats: list[str] = None):
        """Save tokens in multiple formats."""
        formats = formats or ["css", "json", "tailwind"]
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        export_methods = {
            "css": (self.export_css, "tokens.css"),
            "scss": (self.export_scss, "_tokens.scss"),
            "json": (self.export_json, "tokens.json"),
            "tailwind": (self.export_tailwind_config, "tailwind.tokens.js"),
            "swift": (self.export_swift, "DesignTokens.swift"),
            "kotlin": (self.export_kotlin, "DesignTokens.kt"),
        }

        for fmt in formats:
            if fmt in export_methods:
                method, filename = export_methods[fmt]
                content = method()
                (output_path / filename).write_text(content)
                logger.info(f"Exported {fmt} to {filename}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def create_default_token_system() -> DesignTokenSystem:
    """Create a token system with sensible defaults."""
    system = DesignTokenSystem()
    system.setup_semantic_tokens()
    system.setup_component_tokens()
    return system


def create_brand_token_system(
    primary_color: str, secondary_color: str = None, font_family: str = None
) -> DesignTokenSystem:
    """Create a token system with custom brand colors."""
    system = DesignTokenSystem()

    # Override primary colors
    # In a real implementation, would generate full palette from primary color
    system.primitives["color.primary.500"].value = primary_color

    if secondary_color:
        system.add_primitive("color.secondary.500", secondary_color, TokenCategory.COLOR)

    if font_family:
        system.primitives["font.family.sans"].value = font_family

    system.setup_semantic_tokens()
    system.setup_component_tokens()

    return system


# =============================================================================
# CLI
# =============================================================================


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Design Token System")
    parser.add_argument(
        "--export", nargs="+", help="Export formats (css, scss, json, tailwind, swift, kotlin)"
    )
    parser.add_argument("--output", default="./tokens", help="Output directory")
    parser.add_argument("--primary", help="Primary brand color (hex)")
    parser.add_argument("--validate", action="store_true", help="Validate tokens")
    parser.add_argument("--list", action="store_true", help="List all tokens")
    args = parser.parse_args()

    if args.primary:
        system = create_brand_token_system(args.primary)
    else:
        system = create_default_token_system()

    if args.validate:
        issues = system.validate()
        if issues:
            print("Validation issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("Token system is valid!")

    elif args.list:
        tokens = system.get_all_tokens()
        for name, value in sorted(tokens.items()):
            print(f"{name}: {value}")

    elif args.export:
        system.save(args.output, args.export)
        print(f"Exported to {args.output}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
