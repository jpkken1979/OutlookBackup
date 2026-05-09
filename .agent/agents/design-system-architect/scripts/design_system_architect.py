#!/usr/bin/env python3
"""
Design System Architect - Diseña y gestiona sistemas de diseño.

Especializado en:
- Tokens de diseño (colores, tipografía, espaciado)
- Componentes reutilizables
- Documentación de patrones
- Integración con herramientas (Figma, Storybook)

Uso:
    python design_system_architect.py "Crear design system para SaaS"
    python design_system_architect.py --generate-tokens
    python design_system_architect.py --analyze ./src/styles/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DesignToken:
    """Token de diseño."""

    name: str
    value: str
    category: str  # color, spacing, typography, shadow, etc.
    description: str = ""


@dataclass
class Component:
    """Componente del design system."""

    name: str
    category: str  # button, input, card, etc.
    variants: list[str]
    props: list[dict]
    tokens_used: list[str]


@dataclass
class DesignSystemSpec:
    """Especificación de design system."""

    name: str
    tokens: dict[str, list[DesignToken]]
    components: list[Component]
    breakpoints: dict[str, str]
    typography_scale: dict[str, dict]


# Tokens predefinidos
DEFAULT_TOKENS = {
    "colors": {
        "primary": {
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
        },
        "neutral": {
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
        },
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#ef4444",
    },
    "spacing": {
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
        "24": "6rem",
    },
    "typography": {
        "fontFamily": {
            "sans": "Inter, system-ui, sans-serif",
            "mono": "JetBrains Mono, monospace",
        },
        "fontSize": {
            "xs": "0.75rem",
            "sm": "0.875rem",
            "base": "1rem",
            "lg": "1.125rem",
            "xl": "1.25rem",
            "2xl": "1.5rem",
            "3xl": "1.875rem",
            "4xl": "2.25rem",
        },
        "fontWeight": {
            "normal": "400",
            "medium": "500",
            "semibold": "600",
            "bold": "700",
        },
        "lineHeight": {
            "tight": "1.25",
            "normal": "1.5",
            "relaxed": "1.75",
        },
    },
    "shadows": {
        "sm": "0 1px 2px 0 rgb(0 0 0 / 0.05)",
        "md": "0 4px 6px -1px rgb(0 0 0 / 0.1)",
        "lg": "0 10px 15px -3px rgb(0 0 0 / 0.1)",
        "xl": "0 20px 25px -5px rgb(0 0 0 / 0.1)",
    },
    "radius": {
        "none": "0",
        "sm": "0.125rem",
        "md": "0.375rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px",
    },
}

# Breakpoints
DEFAULT_BREAKPOINTS = {
    "sm": "640px",
    "md": "768px",
    "lg": "1024px",
    "xl": "1280px",
    "2xl": "1536px",
}


class DesignSystemArchitect:
    """
    Arquitecto de sistemas de diseño.

    Capacidades:
    - Generar tokens de diseño
    - Crear especificaciones de componentes
    - Exportar a CSS/SCSS/JSON
    - Analizar sistemas existentes
    """

    def __init__(self):
        self.default_tokens = DEFAULT_TOKENS
        self.breakpoints = DEFAULT_BREAKPOINTS

    def generate_tokens_css(self, tokens: dict = None) -> str:
        """Genera CSS custom properties."""
        tokens = tokens or self.default_tokens
        css_lines = [":root {"]

        def add_tokens(obj: dict, prefix: str = ""):
            for key, value in obj.items():
                if isinstance(value, dict):
                    add_tokens(value, f"{prefix}{key}-")
                else:
                    css_lines.append(f"  --{prefix}{key}: {value};")

        add_tokens(tokens)
        css_lines.append("}")

        return "\n".join(css_lines)

    def generate_tokens_scss(self, tokens: dict = None) -> str:
        """Genera variables SCSS."""
        tokens = tokens or self.default_tokens
        scss_lines = []

        def add_tokens(obj: dict, prefix: str = "$"):
            for key, value in obj.items():
                if isinstance(value, dict):
                    add_tokens(value, f"{prefix}{key}-")
                else:
                    scss_lines.append(f"{prefix}{key}: {value};")

        add_tokens(tokens)

        return "\n".join(scss_lines)

    def generate_tokens_json(self, tokens: dict = None) -> str:
        """Genera tokens en formato JSON."""
        tokens = tokens or self.default_tokens
        return json.dumps(tokens, indent=2)

    def generate_tokens_ts(self, tokens: dict = None) -> str:
        """Genera tokens en TypeScript."""
        tokens = tokens or self.default_tokens

        return f"""// Design System Tokens
// Auto-generated - Do not edit manually

export const tokens = {json.dumps(tokens, indent=2)} as const;

export type ColorToken = keyof typeof tokens.colors;
export type SpacingToken = keyof typeof tokens.spacing;
export type FontSizeToken = keyof typeof tokens.typography.fontSize;
"""

    def analyze_styles(self, styles_path: Path) -> dict:
        """Analiza estilos existentes."""
        analysis = {
            "files": [],
            "colors_found": set(),
            "spacing_values": set(),
            "font_sizes": set(),
            "issues": [],
            "recommendations": [],
        }

        if not styles_path.exists():
            analysis["issues"].append(f"Path no encontrado: {styles_path}")
            return analysis

        # Buscar archivos CSS/SCSS
        for ext in ["*.css", "*.scss", "*.less"]:
            for file in styles_path.rglob(ext):
                analysis["files"].append(str(file))

                content = file.read_text(errors="ignore")

                # Extraer colores hex
                hex_colors = re.findall(r"#[0-9a-fA-F]{3,6}\b", content)
                analysis["colors_found"].update(hex_colors)

                # Extraer valores de spacing
                spacing = re.findall(r":\s*(\d+(?:\.\d+)?(?:px|rem|em))", content)
                analysis["spacing_values"].update(spacing)

                # Extraer font sizes
                font_sizes = re.findall(r"font-size:\s*(\d+(?:\.\d+)?(?:px|rem|em))", content)
                analysis["font_sizes"].update(font_sizes)

        # Convertir sets a listas
        analysis["colors_found"] = list(analysis["colors_found"])
        analysis["spacing_values"] = list(analysis["spacing_values"])
        analysis["font_sizes"] = list(analysis["font_sizes"])

        # Detectar issues
        if len(analysis["colors_found"]) > 20:
            analysis["issues"].append(
                f"Demasiados colores únicos ({len(analysis['colors_found'])})"
            )
            analysis["recommendations"].append("Consolidar en una paleta de colores")

        if len(analysis["spacing_values"]) > 15:
            analysis["issues"].append(
                f"Valores de spacing inconsistentes ({len(analysis['spacing_values'])})"
            )
            analysis["recommendations"].append("Usar escala de spacing consistente")

        # Recomendar tokens
        if not any("var(--" in c for c in analysis.get("colors_found", [])):
            analysis["recommendations"].append("Considerar usar CSS custom properties")

        return analysis

    def create_component_spec(
        self,
        name: str,
        category: str,
        variants: list[str] = None,
        props: list[dict] = None,
    ) -> Component:
        """Crea especificación de componente."""
        return Component(
            name=name,
            category=category,
            variants=variants or ["default", "primary", "secondary"],
            props=props or [],
            tokens_used=[],
        )

    def print_analysis(self, analysis: dict) -> None:
        """Imprime análisis."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS DE ESTILOS")
        print(f"{'=' * 60}")

        print(f"\n📁 Archivos analizados: {len(analysis['files'])}")

        if analysis["colors_found"]:
            print(f"\n🎨 Colores encontrados ({len(analysis['colors_found'])}):")
            for color in analysis["colors_found"][:10]:
                print(f"   {color}")
            if len(analysis["colors_found"]) > 10:
                print(f"   ... y {len(analysis['colors_found']) - 10} más")

        if analysis["spacing_values"]:
            print(f"\n📏 Valores de spacing ({len(analysis['spacing_values'])}):")
            for val in sorted(analysis["spacing_values"])[:10]:
                print(f"   {val}")

        if analysis["font_sizes"]:
            print(f"\n🔤 Font sizes ({len(analysis['font_sizes'])}):")
            for size in analysis["font_sizes"]:
                print(f"   {size}")

        if analysis["issues"]:
            print("\n⚠️ Problemas:")
            for issue in analysis["issues"]:
                print(f"   - {issue}")

        if analysis["recommendations"]:
            print("\n💡 Recomendaciones:")
            for rec in analysis["recommendations"]:
                print(f"   - {rec}")

        print(f"\n{'=' * 60}\n")

    def print_tokens(self) -> None:
        """Imprime tokens disponibles."""
        print(f"\n{'=' * 60}")
        print("TOKENS DE DISEÑO")
        print(f"{'=' * 60}\n")

        for category, values in self.default_tokens.items():
            print(f"📦 {category}")
            if isinstance(values, dict):
                for key in list(values.keys())[:5]:
                    print(
                        f"   {key}: {values[key] if not isinstance(values[key], dict) else '...'}"
                    )
            print()

        print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Design System Architect - Diseña sistemas de diseño"
    )
    parser.add_argument("task", nargs="?", help="Descripción del sistema a crear")
    parser.add_argument(
        "--generate-tokens",
        "-g",
        choices=["css", "scss", "json", "ts"],
        help="Generar tokens en formato",
    )
    parser.add_argument("--analyze", "-a", type=Path, help="Analizar estilos existentes")
    parser.add_argument(
        "--list-tokens", "-l", action="store_true", help="Listar tokens disponibles"
    )

    args = parser.parse_args()
    architect = DesignSystemArchitect()

    if args.list_tokens:
        architect.print_tokens()
        return 0

    if args.generate_tokens:
        if args.generate_tokens == "css":
            print(architect.generate_tokens_css())
        elif args.generate_tokens == "scss":
            print(architect.generate_tokens_scss())
        elif args.generate_tokens == "json":
            print(architect.generate_tokens_json())
        elif args.generate_tokens == "ts":
            print(architect.generate_tokens_ts())
        return 0

    if args.analyze:
        analysis = architect.analyze_styles(args.analyze)
        architect.print_analysis(analysis)
        return 0

    if args.task:
        print(f"Creando design system para: {args.task}")
        architect.print_tokens()
        print("Usa --generate-tokens <formato> para exportar tokens")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
