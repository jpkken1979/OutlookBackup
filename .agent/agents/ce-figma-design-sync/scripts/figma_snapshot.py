"""Figma snapshot extraction utilities.

Extracts design tokens (colors, typography, spacing, effects, borders)
from Figma via Figma MCP server and structures them for comparison.
"""
import logging
from typing import Optional

from models import (
    BorderToken,
    ColorToken,
    DesignTokens,
    EffectToken,
    SpacingToken,
    TypographyToken,
    _border_to_dict,
    _color_to_dict,
    _effect_to_dict,
    _spacing_to_dict,
    _typography_to_dict,
)

logger = logging.getLogger(__name__)


class FigmaSnapshotExtractor:
    """Extracts design tokens from Figma via Figma MCP."""

    def extract_tokens(
        self,
        figma_url: str,
        node_id: str,
    ) -> DesignTokens:
        """Extract design tokens from a Figma node.

        Args:
            figma_url: URL del archivo Figma.
            node_id: ID del node a extraer.

        Returns:
            DesignTokens con todos los tokens extraidos.
        """
        logger.info("Extracting tokens from Figma node: %s", node_id)

        tokens = DesignTokens()

        # Try to use Figma MCP tools if available
        try:
            tokens = self._extract_from_figma_mcp(figma_url, node_id)
        except Exception as e:
            logger.warning("Figma MCP not available: %s. Using fallback extraction.", str(e))
            tokens = self._fallback_extraction(figma_url, node_id)

        return tokens

    def _extract_from_figma_mcp(self, figma_url: str, node_id: str) -> DesignTokens:
        """Extract tokens using Figma MCP server.

        This method calls the Figma MCP tools to get node data.
        In production, this would use the actual MCP client to call:
        - figma_query_file_nodes
        - figma_get_node
        - figma_get_styles

        Args:
            figma_url: URL del archivo Figma.
            node_id: ID del node a extraer.

        Returns:
            DesignTokens extraidos.
        """
        # Placeholder for Figma MCP integration
        # In production:
        # from mcp.client import MCPClient
        # client = MCPClient()
        # node_data = await client.figma_get_node(node_id)
        # styles_data = await client.figma_get_styles()

        logger.info("Using Figma MCP for token extraction (placeholder)")

        tokens = DesignTokens()

        # Parse file key from Figma URL
        # URL format: https://www.figma.com/file/<file_key>/<title>?node-id=<node_id>
        file_key = self._parse_file_key(figma_url)
        logger.info("Parsed file key: %s", file_key)

        # Placeholder: In production, this would call the Figma API
        # to get the actual design tokens from the specified node

        # For now, return empty tokens to indicate no data extracted
        # The agent will report this as tokens_missing

        return tokens

    def _fallback_extraction(self, figma_url: str, node_id: str) -> DesignTokens:
        """Fallback extraction when Figma MCP is not available.

        Args:
            figma_url: URL del archivo Figma.
            node_id: ID del node.

        Returns:
            Empty DesignTokens with warning.
        """
        logger.warning("Figma MCP not available, cannot extract design tokens")
        logger.warning("figma_url: %s, node_id: %s", figma_url, node_id)

        tokens = DesignTokens()
        # Return empty tokens - the agent will report missing tokens

        return tokens

    def _parse_file_key(self, figma_url: str) -> str | None:
        """Parse file key from Figma URL.

        Args:
            figma_url: URL del archivo Figma.

        Returns:
            File key o None si no se puede parsear.
        """
        # URL format: https://www.figma.com/file/<file_key>/<title>
        if "figma.com/file/" in figma_url:
            parts = figma_url.split("figma.com/file/")[1].split("/")
            if parts:
                return parts[0]

        return None

    def _extract_colors_from_node(self, node_data: dict) -> list[ColorToken]:
        """Extract color tokens from Figma node data.

        Args:
            node_data: Data del node desde Figma API.

        Returns:
            Lista de ColorToken.
        """
        colors: list[ColorToken] = []

        # Check for fills
        fills = node_data.get("fills", [])
        for idx, fill in enumerate(fills):
            if fill.get("type") == "solid":
                color_data = fill.get("color", {})
                opacity = fill.get("opacity", 1.0)
                hex_value = self._color_to_hex(color_data)

                colors.append(
                    ColorToken(
                        name=f"color/{idx}",
                        hex_value=hex_value,
                        opacity=opacity,
                        fill_type="solid",
                    )
                )

        # Check for strokes
        strokes = node_data.get("strokes", [])
        for idx, stroke in enumerate(strokes):
            if stroke.get("type") == "solid":
                color_data = stroke.get("color", {})
                opacity = stroke.get("opacity", 1.0)
                hex_value = self._color_to_hex(color_data)

                colors.append(
                    ColorToken(
                        name=f"stroke/{idx}",
                        hex_value=hex_value,
                        opacity=opacity,
                        fill_type="solid",
                    )
                )

        return colors

    def _extract_typography_from_node(self, node_data: dict) -> list[TypographyToken]:
        """Extract typography tokens from Figma node data.

        Args:
            node_data: Data del node desde Figma API.

        Returns:
            Lista de TypographyToken.
        """
        typography: list[TypographyToken] = []

        # Check for text children with typography
        text_children = [c for c in node_data.get("children", []) if c.get("type") == "TEXT"]

        for idx, text in enumerate(text_children):
            style = text.get("style", {})

            typography.append(
                TypographyToken(
                    name=f"text/{idx}",
                    font_family=style.get("fontFamily", "Inter"),
                    font_size=style.get("fontSize", 16),
                    font_weight=style.get("fontWeight", 400),
                    line_height=style.get("lineHeightPx", 24),
                    letter_spacing=style.get("letterSpacing", 0),
                )
            )

        return typography

    def _extract_spacing_from_node(self, node_data: dict) -> list[SpacingToken]:
        """Extract spacing tokens from Figma node data.

        Args:
            node_data: Data del node desde Figma API.

        Returns:
            Lista de SpacingToken.
        """
        spacing: list[SpacingToken] = []

        # Auto-layout spacing
        if node_data.get("layoutMode") in ["HORIZONTAL", "VERTICAL"]:
            item_spacing = node_data.get("itemSpacing", 0)
            if item_spacing > 0:
                spacing.append(SpacingToken(name=f"gap/{item_spacing}", value=item_spacing))

        # Padding from absoluteBoundingBox or padding
        padding = node_data.get("padding", {})
        if padding:
            for side, value in padding.items():
                if value > 0:
                    spacing.append(SpacingToken(name=f"padding-{side}/{value}", value=value))

        # Custom spacing values
        for i in [4, 8, 12, 16, 20, 24, 32, 40, 48, 64]:
            spacing.append(SpacingToken(name=str(i), value=float(i)))

        return spacing

    def _extract_effects_from_node(self, node_data: dict) -> list[EffectToken]:
        """Extract effect tokens (shadows, blurs) from Figma node data.

        Args:
            node_data: Data del node desde Figma API.

        Returns:
            Lista de EffectToken.
        """
        effects: list[EffectToken] = []

        effects_data = node_data.get("effects", [])

        for idx, effect in enumerate(effects_data):
            effect_type = effect.get("type", "unknown")

            if effect_type == "DROP_SHADOW":
                color_data = effect.get("color", {})
                hex_color = self._color_to_hex(color_data)

                effects.append(
                    EffectToken(
                        name=f"shadow/{idx}",
                        effect_type="shadow",
                        offset_x=effect.get("offset", {}).get("x", 0),
                        offset_y=effect.get("offset", {}).get("y", 0),
                        blur=effect.get("radius", 0),
                        spread=effect.get("spread", 0),
                        color=hex_color,
                        opacity=color_data.get("a", 1.0),
                    )
                )

        return effects

    def _extract_borders_from_node(self, node_data: dict) -> list[BorderToken]:
        """Extract border tokens from Figma node data.

        Args:
            node_data: Data del node desde Figma API.

        Returns:
            Lista de BorderToken.
        """
        borders: list[BorderToken] = []

        strokes = node_data.get("strokes", [])
        for idx, stroke in enumerate(strokes):
            color_data = stroke.get("color", {})
            hex_color = self._color_to_hex(color_data)

            borders.append(
                BorderToken(
                    name=f"border/{idx}",
                    width=node_data.get("strokeWeight", 1),
                    style="solid",  # Figma uses solid/dashed/etc
                    color=hex_color,
                )
            )

        return borders

    def _color_to_hex(self, color_data: dict) -> str:
        """Convert Figma color (RGBA 0-1) to hex string.

        Args:
            color_data: Dict con r, g, b, a en rango 0-1.

        Returns:
            Hex string formato "#RRGGBB".
        """
        r = int(color_data.get("r", 0) * 255)
        g = int(color_data.get("g", 0) * 255)
        b = int(color_data.get("b", 0) * 255)

        return f"#{r:02X}{g:02X}{b:02X}"


def extract_design_tokens_from_node(node_data: dict, node_name: str = "root") -> DesignTokens:
    """Extract all design tokens from a Figma node data structure.

    Args:
        node_data: Raw node data from Figma API.
        node_name: Name identifier for this node.

    Returns:
        DesignTokens con todos los tokens extraidos.
    """
    extractor = FigmaSnapshotExtractor()

    tokens = DesignTokens()

    # Extract all token types
    tokens.colors = extractor._extract_colors_from_node(node_data)
    tokens.typography = extractor._extract_typography_from_node(node_data)
    tokens.spacing = extractor._extract_spacing_from_node(node_data)
    tokens.effects = extractor._extract_effects_from_node(node_data)
    tokens.borders = extractor._extract_borders_from_node(node_data)

    return tokens


def compute_diff(
    design_tokens: DesignTokens,
    implementation_tokens: dict,
) -> list[dict]:
    """Compute diff between design tokens and implementation CSS.

    Args:
        design_tokens: Tokens extraidos de Figma.
        implementation_tokens: CSS computado del browser.

    Returns:
        Lista de dicts con diferencias encontradas.
    """
    diff_items: list[dict] = []

    # Create lookup maps for implementation tokens
    impl_colors = {c["name"]: c for c in implementation_tokens.get("colors", [])}
    impl_typography = {t["name"]: t for t in implementation_tokens.get("typography", [])}

    # Compare colors
    for color in design_tokens.colors:
        if color.name in impl_colors:
            impl_hex = impl_colors[color.name].get("hex", "")
            if color.hex_value.upper() != impl_hex.upper():
                diff_items.append(
                    {
                        "category": "colors",
                        "token": color.name,
                        "figma_value": color.hex_value,
                        "implementation_value": impl_hex,
                        "severity": "high",
                    }
                )

    # Compare typography
    for typo in design_tokens.typography:
        if typo.name in impl_typography:
            impl = impl_typography[typo.name]
            mismatches = []

            if typo.font_family != impl.get("fontFamily", ""):
                mismatches.append(f"font-family: {impl.get('fontFamily', 'N/A')}")
            if typo.font_size != impl.get("fontSize", 0):
                mismatches.append(f"font-size: {impl.get('fontSize', 'N/A')}px")

            if mismatches:
                diff_items.append(
                    {
                        "category": "typography",
                        "token": typo.name,
                        "figma_value": f"{typo.font_family} {typo.font_size}px",
                        "implementation_value": "; ".join(mismatches),
                        "severity": "medium",
                    }
                )

    return diff_items


def main() -> DesignTokens:
    """CLI entry point for figma_snapshot agent."""
    import sys
    figma_url = sys.argv[1] if len(sys.argv) > 1 else ""
    node_id = sys.argv[2] if len(sys.argv) > 2 else ""
    extractor = FigmaSnapshotExtractor()
    return extractor.extract_tokens(figma_url, node_id)


if __name__ == "__main__":
    import json
    result = main()
    print(json.dumps({"tokens_extracted": len(result.colors)}, default=str))