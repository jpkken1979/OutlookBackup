"""ce-figma-design-sync agent entry point.

Design-to-code synchronization agent that compares Figma designs
with web implementations and generates CSS/Tailwind patches.
"""
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from models import ColorToken, DesignTokens, DiffItem, SyncResult

logger = logging.getLogger(__name__)


def parse_input(input_str: str) -> dict:
    """Parse agent input string into parameters.

    Args:
        input_str: Input string with format "figma_url=<url> node_id=<id> implementation_url=<url>"

    Returns:
        dict con los parametros extraidos.
    """
    params = {
        "figma_url": "",
        "node_id": "",
        "implementation_url": "",
        "css_selector": "",
    }

    for part in input_str.split():
        if part.startswith("figma_url="):
            params["figma_url"] = part[10:]
        elif part.startswith("node_id="):
            params["node_id"] = part[8:]
        elif part.startswith("implementation_url="):
            params["implementation_url"] = part[19:]
        elif part.startswith("css_selector="):
            params["css_selector"] = part[13:]

    return params


def extract_design_tokens(
    figma_url: str,
    node_id: str,
) -> DesignTokens:
    """Extract design tokens from Figma.

    Args:
        figma_url: URL del archivo Figma.
        node_id: ID del node a extraer.

    Returns:
        DesignTokens con los tokens extraidos.
    """
    logger.info("Extracting design tokens from Figma: %s, node: %s", figma_url, node_id)

    # Import here to avoid circular imports and allow lazy loading
    try:
        from scripts.figma_snapshot import FigmaSnapshotExtractor

        extractor = FigmaSnapshotExtractor()
        tokens = extractor.extract_tokens(figma_url, node_id)
        return tokens
    except ImportError:
        # Fallback when running as standalone script with agent/ as cwd
        import scripts.figma_snapshot as fs_module

        extractor = fs_module.FigmaSnapshotExtractor()
        tokens = extractor.extract_tokens(figma_url, node_id)
        return tokens


def capture_implementation(
    implementation_url: str,
    css_selector: str | None = None,
) -> dict:
    """Capture implementation details via agent-browser.

    Args:
        implementation_url: URL de la implementacion.
        css_selector: Selector CSS opcional para area especifica.

    Returns:
        dict con CSS computado del browser.
    """
    logger.info("Capturing implementation from: %s", implementation_url)

    # Placeholder: agent-browser CLI integration
    # In production, this would call:
    # agent-browser evaluate --url <url> --script "getComputedStyle(element)"
    # For now, return empty structure
    return {
        "colors": [],
        "typography": [],
        "spacing": [],
        "effects": [],
        "borders": [],
    }


def compare_tokens(
    design_tokens: DesignTokens,
    implementation_css: dict,
) -> list[DiffItem]:
    """Compare design tokens with implementation CSS.

    Args:
        design_tokens: Tokens extraidos de Figma.
        implementation_css: CSS computado del browser.

    Returns:
        Lista de DiffItem con las diferencias encontradas.
    """
    logger.info("Comparing design tokens with implementation CSS")

    diff_items: list[DiffItem] = []

    # Compare colors
    impl_colors = {c["name"]: c for c in implementation_css.get("colors", [])}
    for token in design_tokens.colors:
        if token.name in impl_colors:
            impl_color = impl_colors[token.name]
            if token.hex_value.upper() != impl_color.get("hex", "").upper():
                diff_items.append(
                    DiffItem(
                        category="colors",
                        token_name=token.name,
                        figma_value=token.hex_value,
                        implementation_value=impl_color.get("hex", "not found"),
                        severity="high",
                        selector=f".{token.name.replace('/', '-').replace('_', '-')}",
                        property_name="background-color",
                        suggested_value=token.hex_value,
                    )
                )

    # Compare typography
    impl_typography = {t["name"]: t for t in implementation_css.get("typography", [])}
    for token in design_tokens.typography:
        if token.name in impl_typography:
            impl_type = impl_typography[token.name]
            mismatches = []

            if token.font_family != impl_type.get("fontFamily", ""):
                mismatches.append(f"font-family: {impl_type.get('fontFamily', 'N/A')} vs {token.font_family}")
            if token.font_size != impl_type.get("fontSize", 0):
                mismatches.append(f"font-size: {impl_type.get('fontSize', 'N/A')}px vs {token.font_size}px")

            if mismatches:
                diff_items.append(
                    DiffItem(
                        category="typography",
                        token_name=token.name,
                        figma_value=f"{token.font_family} {token.font_size}px",
                        implementation_value="; ".join(mismatches),
                        severity="medium",
                        selector=f".{token.name.replace('/', '-').replace('_', '-')}",
                        property_name="font",
                        suggested_value=f"{token.font_family} {token.font_size}px",
                    )
                )

    # Compare spacing
    impl_spacing = {s["name"]: s for s in implementation_css.get("spacing", [])}
    for token in design_tokens.spacing:
        if token.name in impl_spacing:
            impl_val = impl_spacing[token.name].get("value", 0)
            if token.value != impl_val:
                diff_items.append(
                    DiffItem(
                        category="spacing",
                        token_name=token.name,
                        figma_value=str(token.value),
                        implementation_value=str(impl_val),
                        severity="medium",
                        selector=f".{token.name.replace('/', '-').replace('_', '-')}",
                        property_name="gap",
                        suggested_value=f"{token.value}px",
                    )
                )

    # Compare effects (shadows)
    impl_effects = {e["name"]: e for e in implementation_css.get("effects", [])}
    for token in design_tokens.effects:
        if token.name in impl_effects:
            impl_eff = impl_effects[token.name]
            mismatches = []

            impl_blur = impl_eff.get("blur", 0)
            if token.blur != impl_blur:
                mismatches.append(f"blur: {impl_blur}px vs {token.blur}px")

            impl_offset_x = impl_eff.get("offsetX", 0)
            if token.offset_x != impl_offset_x:
                mismatches.append(f"offset-x: {impl_offset_x}px vs {token.offset_x}px")

            impl_offset_y = impl_eff.get("offsetY", 0)
            if token.offset_y != impl_offset_y:
                mismatches.append(f"offset-y: {impl_offset_y}px vs {token.offset_y}px")

            if mismatches:
                diff_items.append(
                    DiffItem(
                        category="effects",
                        token_name=token.name,
                        figma_value=f"shadow({token.offset_x},{token.offset_y},{token.blur})",
                        implementation_value="; ".join(mismatches),
                        severity="high",
                        selector=f".{token.name.replace('/', '-').replace('_', '-')}",
                        property_name="box-shadow",
                        suggested_value=f"{token.offset_x}px {token.offset_y}px {token.blur}px {token.color}",
                    )
                )

    # Compare borders
    impl_borders = {b["name"]: b for b in implementation_css.get("borders", [])}
    for token in design_tokens.borders:
        if token.name in impl_borders:
            impl_bor = impl_borders[token.name]
            mismatches = []

            impl_width = impl_bor.get("width", 0)
            if token.width != impl_width:
                mismatches.append(f"width: {impl_width}px vs {token.width}px")

            impl_style = impl_bor.get("style", "")
            if token.style != impl_style:
                mismatches.append(f"style: {impl_style} vs {token.style}")

            impl_color = impl_bor.get("color", "")
            if token.color.upper() != impl_color.upper():
                mismatches.append(f"color: {impl_color} vs {token.color}")

            if mismatches:
                diff_items.append(
                    DiffItem(
                        category="borders",
                        token_name=token.name,
                        figma_value=f"{token.width}px {token.style} {token.color}",
                        implementation_value="; ".join(mismatches),
                        severity="medium",
                        selector=f".{token.name.replace('/', '-').replace('_', '-')}",
                        property_name="border",
                        suggested_value=f"{token.width}px {token.style} {token.color}",
                    )
                )

    return diff_items


def generate_css_patch(diff_items: list[DiffItem]) -> str:
    """Generate CSS snippet from diff items.

    Args:
        diff_items: Lista de diferencias a corregir.

    Returns:
        String con codigo CSS sugerido.
    """
    logger.info("Generating CSS patch for %d diff items", len(diff_items))

    css_lines = ["/* ce-figma-design-sync: Generated CSS patches */", ""]

    for item in diff_items:
        if item.selector:
            css_lines.append(f"{item.selector} {{")
            if item.property_name and item.suggested_value:
                css_lines.append(f"  {item.property_name}: {item.suggested_value};")
            css_lines.append(f"}}  /* severity: {item.severity}, diff: {item.token_name} */")
            css_lines.append("")

    return "\n".join(css_lines)


def run(input_str: str) -> dict:
    """Run ce-figma-design-sync sync operation.

    Args:
        input_str: Parametros de sincronizacion.
            Format: "figma_url=<url> node_id=<id> implementation_url=<url> [css_selector=<selector>]"

    Returns:
        dict con resultado de sincronizacion.
    """
    logger.info("Starting ce-figma-design-sync sync")
    logger.info("Input: %s", input_str)

    # Parse input
    params = parse_input(input_str)
    figma_url = params["figma_url"]
    node_id = params["node_id"]
    implementation_url = params["implementation_url"]
    css_selector = params["css_selector"]

    if not figma_url or not implementation_url:
        return {
            "status": "failed",
            "error": "figma_url and implementation_url are required",
            "figma_url": figma_url,
            "implementation_url": implementation_url,
        }

    result = SyncResult(
        status="completed",
        figma_url=figma_url,
        implementation_url=implementation_url,
    )

    try:
        # Phase 1: Extract design tokens from Figma
        design_tokens = extract_design_tokens(figma_url, node_id)
        logger.info(
            "Extracted %d colors, %d typography, %d spacing tokens",
            len(design_tokens.colors),
            len(design_tokens.typography),
            len(design_tokens.spacing),
        )

        # Phase 2: Capture implementation CSS
        implementation_css = capture_implementation(implementation_url, css_selector)

        # Phase 3: Compare tokens
        diff_items = compare_tokens(design_tokens, implementation_css)
        result.diff_items = diff_items
        result.tokens_mismatched = len(diff_items)

        # Calculate matched tokens (rough estimate)
        total_design_tokens = (
            len(design_tokens.colors)
            + len(design_tokens.typography)
            + len(design_tokens.spacing)
            + len(design_tokens.effects)
            + len(design_tokens.borders)
        )
        result.tokens_matched = total_design_tokens - result.tokens_mismatched

        # Phase 4: Generate CSS patch
        result.css_snippet = generate_css_patch(diff_items)

        logger.info(
            "Sync completed: %d matched, %d mismatched, %d missing",
            result.tokens_matched,
            result.tokens_mismatched,
            result.tokens_missing,
        )

    except Exception as e:
        logger.error("Sync failed: %s", str(e))
        result.status = "failed"
        result.errors.append(str(e))

    return result.to_dict()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )
    input_data = sys.argv[1] if len(sys.argv) > 1 else ""
    result = run(input_data)
    print(json.dumps(result, indent=2, default=str))
