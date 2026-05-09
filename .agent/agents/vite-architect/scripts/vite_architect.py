#!/usr/bin/env python3
"""
Vite Architect - Diseña configuraciones y arquitecturas para proyectos Vite.

Especializado en:
- Configuración de vite.config.ts
- Estructura de proyectos Vite
- Integración con frameworks (React, Vue, Svelte)
- Optimización de builds

Uso:
    python vite_architect.py "Configurar proyecto React con TypeScript"
    python vite_architect.py --analyze ./vite.config.ts
    python vite_architect.py --template react-ts
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.vite-architect")


@dataclass
class ViteConfig:
    """Configuración de Vite."""

    framework: str
    typescript: bool = True
    plugins: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    env_prefix: str = "VITE_"
    build_options: dict = field(default_factory=dict)
    server_options: dict = field(default_factory=dict)
    css_options: dict = field(default_factory=dict)


@dataclass
class ProjectStructure:
    """Estructura de proyecto Vite."""

    name: str
    framework: str
    directories: dict
    config_files: list[str]
    dependencies: dict[str, str]
    dev_dependencies: dict[str, str]


# Templates de proyectos
PROJECT_TEMPLATES = {
    "react-ts": {
        "name": "React + TypeScript",
        "framework": "react",
        "directories": {
            "src": {
                "components": ["App.tsx"],
                "hooks": [],
                "utils": [],
                "styles": ["index.css"],
                "main.tsx": None,
                "vite-env.d.ts": None,
            },
            "public": ["favicon.ico"],
        },
        "config_files": ["vite.config.ts", "tsconfig.json", "tsconfig.node.json"],
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
        },
        "dev_dependencies": {
            "@types/react": "^18.2.0",
            "@types/react-dom": "^18.2.0",
            "@vitejs/plugin-react": "^4.2.0",
            "typescript": "^5.3.0",
            "vite": "^5.0.0",
        },
        "plugins": ["@vitejs/plugin-react"],
    },
    "react-swc": {
        "name": "React + SWC (más rápido)",
        "framework": "react",
        "directories": {
            "src": {
                "components": ["App.tsx"],
                "main.tsx": None,
            },
        },
        "config_files": ["vite.config.ts", "tsconfig.json"],
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
        },
        "dev_dependencies": {
            "@vitejs/plugin-react-swc": "^3.5.0",
            "typescript": "^5.3.0",
            "vite": "^5.0.0",
        },
        "plugins": ["@vitejs/plugin-react-swc"],
    },
    "vue-ts": {
        "name": "Vue 3 + TypeScript",
        "framework": "vue",
        "directories": {
            "src": {
                "components": ["HelloWorld.vue"],
                "App.vue": None,
                "main.ts": None,
            },
        },
        "config_files": ["vite.config.ts", "tsconfig.json"],
        "dependencies": {
            "vue": "^3.4.0",
        },
        "dev_dependencies": {
            "@vitejs/plugin-vue": "^4.5.0",
            "typescript": "^5.3.0",
            "vue-tsc": "^1.8.0",
            "vite": "^5.0.0",
        },
        "plugins": ["@vitejs/plugin-vue"],
    },
    "svelte-ts": {
        "name": "Svelte + TypeScript",
        "framework": "svelte",
        "directories": {
            "src": {
                "lib": ["Counter.svelte"],
                "App.svelte": None,
                "main.ts": None,
            },
        },
        "config_files": ["vite.config.ts", "svelte.config.js", "tsconfig.json"],
        "dependencies": {},
        "dev_dependencies": {
            "@sveltejs/vite-plugin-svelte": "^3.0.0",
            "svelte": "^4.2.0",
            "svelte-check": "^3.6.0",
            "typescript": "^5.3.0",
            "vite": "^5.0.0",
        },
        "plugins": ["@sveltejs/vite-plugin-svelte"],
    },
    "vanilla-ts": {
        "name": "Vanilla TypeScript",
        "framework": "vanilla",
        "directories": {
            "src": {
                "main.ts": None,
                "style.css": None,
            },
        },
        "config_files": ["vite.config.ts", "tsconfig.json"],
        "dependencies": {},
        "dev_dependencies": {
            "typescript": "^5.3.0",
            "vite": "^5.0.0",
        },
        "plugins": [],
    },
    "library": {
        "name": "Librería con build",
        "framework": "library",
        "directories": {
            "src": {
                "index.ts": None,
                "lib": [],
            },
            "dist": [],
        },
        "config_files": ["vite.config.ts", "tsconfig.json", "tsconfig.build.json"],
        "dependencies": {},
        "dev_dependencies": {
            "typescript": "^5.3.0",
            "vite": "^5.0.0",
            "vite-plugin-dts": "^3.6.0",
        },
        "plugins": ["vite-plugin-dts"],
        "build_options": {
            "lib": True,
            "formats": ["es", "cjs"],
        },
    },
}

# Plugins populares
POPULAR_PLUGINS = {
    "pwa": {
        "package": "vite-plugin-pwa",
        "description": "Progressive Web App",
        "config": "VitePWA()",
    },
    "compression": {
        "package": "vite-plugin-compression",
        "description": "Compresión gzip/brotli",
        "config": "compression()",
    },
    "imagemin": {
        "package": "vite-plugin-imagemin",
        "description": "Optimización de imágenes",
        "config": "viteImagemin()",
    },
    "legacy": {
        "package": "@vitejs/plugin-legacy",
        "description": "Soporte para browsers antiguos",
        "config": "legacy({ targets: ['defaults'] })",
    },
    "checker": {
        "package": "vite-plugin-checker",
        "description": "TypeScript/ESLint checking",
        "config": "checker({ typescript: true })",
    },
    "inspect": {
        "package": "vite-plugin-inspect",
        "description": "Inspeccionar transformaciones",
        "config": "Inspect()",
    },
    "visualizer": {
        "package": "rollup-plugin-visualizer",
        "description": "Visualizar bundle",
        "config": "visualizer()",
    },
}


class ViteArchitect:
    """
    Arquitecto especializado en proyectos Vite.

    Capacidades:
    - Diseñar configuraciones óptimas
    - Analizar proyectos existentes
    - Recomendar plugins
    - Generar estructuras de proyecto
    """

    def __init__(self):
        self.templates = PROJECT_TEMPLATES
        self.plugins = POPULAR_PLUGINS

    def analyze_config(self, config_path: Path) -> dict:
        """Analiza un archivo vite.config existente."""
        analysis = {
            "path": str(config_path),
            "exists": config_path.exists(),
            "plugins": [],
            "aliases": [],
            "build_options": [],
            "issues": [],
            "recommendations": [],
        }

        if not config_path.exists():
            analysis["issues"].append("Archivo de configuración no encontrado")
            return analysis

        content = config_path.read_text(errors="ignore")

        # Detectar plugins
        plugin_matches = re.findall(r"(\w+)\(\s*\{?", content)
        known_plugins = ["react", "vue", "svelte", "legacy", "pwa", "compression"]
        for match in plugin_matches:
            if any(kp in match.lower() for kp in known_plugins):
                analysis["plugins"].append(match)

        # Detectar aliases
        alias_matches = re.findall(r"['\"](@?\w+)['\"]:\s*(?:path\.)?resolve", content)
        analysis["aliases"].extend(alias_matches)

        # Detectar opciones de build
        if "build:" in content:
            if "rollupOptions" in content:
                analysis["build_options"].append("rollupOptions configurado")
            if "target" in content:
                analysis["build_options"].append("target específico")
            if "minify" in content:
                analysis["build_options"].append("minificación personalizada")

        # Detectar problemas
        if "require(" in content:
            analysis["issues"].append("⚠️ Uso de require() - usar import ESM")

        if not analysis["plugins"]:
            analysis["issues"].append("⚠️ No se detectaron plugins")

        # Recomendaciones
        if "compression" not in str(analysis["plugins"]).lower():
            analysis["recommendations"].append("Considerar vite-plugin-compression para producción")

        if "visualizer" not in str(analysis["plugins"]).lower():
            analysis["recommendations"].append(
                "Considerar rollup-plugin-visualizer para analizar bundle"
            )

        return analysis

    def generate_config(self, config: ViteConfig) -> str:
        """Genera contenido de vite.config.ts."""
        imports = ["import { defineConfig } from 'vite';"]
        plugins_code = []

        # Imports de plugins según framework
        if config.framework == "react":
            imports.append("import react from '@vitejs/plugin-react';")
            plugins_code.append("react()")
        elif config.framework == "react-swc":
            imports.append("import react from '@vitejs/plugin-react-swc';")
            plugins_code.append("react()")
        elif config.framework == "vue":
            imports.append("import vue from '@vitejs/plugin-vue';")
            plugins_code.append("vue()")
        elif config.framework == "svelte":
            imports.append("import { svelte } from '@sveltejs/vite-plugin-svelte';")
            plugins_code.append("svelte()")

        # Plugins adicionales
        for plugin in config.plugins:
            if plugin in self.plugins:
                p = self.plugins[plugin]
                imports.append(f"import {plugin} from '{p['package']}';")
                plugins_code.append(p["config"])

        # Aliases
        aliases_code = ""
        if config.aliases:
            imports.append("import path from 'path';")
            alias_entries = []
            for alias, target in config.aliases.items():
                alias_entries.append(f"      '{alias}': path.resolve(__dirname, '{target}')")
            aliases_code = f"""
    resolve: {{
      alias: {{
{chr(10).join(alias_entries)}
      }}
    }},"""

        # Server options
        server_code = ""
        if config.server_options:
            opts = []
            for key, value in config.server_options.items():
                if isinstance(value, bool):
                    opts.append(f"      {key}: {str(value).lower()}")
                elif isinstance(value, int):
                    opts.append(f"      {key}: {value}")
                else:
                    opts.append(f"      {key}: '{value}'")
            server_code = f"""
    server: {{
{chr(10).join(opts)}
    }},"""

        # Build options
        build_code = ""
        if config.build_options:
            build_code = """
    build: {
      // Configuración de build personalizada
    },"""

        # Generar config completa
        plugins_str = ",\n      ".join(plugins_code)

        return f"""{chr(10).join(imports)}

export default defineConfig({{
    plugins: [
      {plugins_str}
    ],{aliases_code}{server_code}{build_code}
}});
"""

    def create_project_structure(self, template_name: str) -> ProjectStructure:
        """Crea estructura de proyecto basada en template."""
        if template_name not in self.templates:
            template_name = "react-ts"

        template = self.templates[template_name]

        return ProjectStructure(
            name=template["name"],
            framework=template["framework"],
            directories=template["directories"],
            config_files=template["config_files"],
            dependencies=template.get("dependencies", {}),
            dev_dependencies=template.get("dev_dependencies", {}),
        )

    def print_analysis(self, analysis: dict) -> None:
        """Imprime análisis de forma legible."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS DE CONFIGURACIÓN VITE")
        print(f"{'=' * 60}")
        print(f"\n📄 Archivo: {analysis['path']}")
        print(f"✅ Existe: {'Sí' if analysis['exists'] else 'No'}")

        if analysis["plugins"]:
            print("\n🔌 Plugins detectados:")
            for p in analysis["plugins"]:
                print(f"   - {p}")

        if analysis["aliases"]:
            print("\n🔗 Aliases configurados:")
            for a in analysis["aliases"]:
                print(f"   - {a}")

        if analysis["build_options"]:
            print("\n🏗️ Opciones de build:")
            for opt in analysis["build_options"]:
                print(f"   - {opt}")

        if analysis["issues"]:
            print("\n⚠️ Problemas:")
            for issue in analysis["issues"]:
                print(f"   {issue}")

        if analysis["recommendations"]:
            print("\n💡 Recomendaciones:")
            for rec in analysis["recommendations"]:
                print(f"   - {rec}")

        print(f"\n{'=' * 60}\n")

    def print_structure(self, structure: ProjectStructure) -> None:
        """Imprime estructura de proyecto."""
        print(f"\n{'=' * 60}")
        print(f"ESTRUCTURA DE PROYECTO: {structure.name}")
        print(f"{'=' * 60}")
        print(f"\n📦 Framework: {structure.framework}")

        print("\n📁 Directorios:")
        self._print_dirs(structure.directories, indent=3)

        print("\n⚙️ Archivos de configuración:")
        for f in structure.config_files:
            print(f"   - {f}")

        if structure.dependencies:
            print("\n📦 Dependencias:")
            for pkg, ver in structure.dependencies.items():
                print(f"   - {pkg}: {ver}")

        if structure.dev_dependencies:
            print("\n🔧 Dev Dependencies:")
            for pkg, ver in list(structure.dev_dependencies.items())[:5]:
                print(f"   - {pkg}: {ver}")
            if len(structure.dev_dependencies) > 5:
                print(f"   ... y {len(structure.dev_dependencies) - 5} más")

        print(f"\n{'=' * 60}\n")

    def _print_dirs(self, dirs: dict, indent: int = 0) -> None:
        """Imprime directorios recursivamente."""
        for key, value in dirs.items():
            prefix = " " * indent
            if isinstance(value, dict):
                print(f"{prefix}📁 {key}/")
                self._print_dirs(value, indent + 3)
            elif isinstance(value, list):
                print(f"{prefix}📁 {key}/")
                for item in value:
                    print(f"{prefix}   📄 {item}")
            else:
                print(f"{prefix}📄 {key}")

    def list_templates(self) -> None:
        """Lista templates disponibles."""
        print(f"\n{'=' * 60}")
        print("TEMPLATES DE PROYECTOS VITE")
        print(f"{'=' * 60}\n")

        for key, template in self.templates.items():
            print(f"📦 {key}")
            print(f"   {template['name']}")
            print(f"   Plugins: {', '.join(template.get('plugins', ['ninguno']))}")
            print()

        print(f"{'=' * 60}\n")

    def list_plugins(self) -> None:
        """Lista plugins populares."""
        print(f"\n{'=' * 60}")
        print("PLUGINS POPULARES DE VITE")
        print(f"{'=' * 60}\n")

        for key, plugin in self.plugins.items():
            print(f"🔌 {key}")
            print(f"   Paquete: {plugin['package']}")
            print(f"   {plugin['description']}")
            print()

        print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Vite Architect - Diseña configuraciones de Vite")
    parser.add_argument("task", nargs="?", help="Descripción del proyecto a configurar")
    parser.add_argument("--analyze", "-a", type=Path, help="Analizar vite.config existente")
    parser.add_argument("--template", "-t", default="react-ts", help="Template a usar")
    parser.add_argument("--list-templates", "-l", action="store_true", help="Listar templates")
    parser.add_argument(
        "--list-plugins", "-p", action="store_true", help="Listar plugins populares"
    )
    parser.add_argument(
        "--generate-config", "-g", action="store_true", help="Generar vite.config.ts"
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    architect = ViteArchitect()

    if args.list_templates:
        architect.list_templates()
        return 0

    if args.list_plugins:
        architect.list_plugins()
        return 0

    if args.analyze:
        analysis = architect.analyze_config(args.analyze)
        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            architect.print_analysis(analysis)
        return 0

    if args.generate_config:
        config = ViteConfig(
            framework=args.template.split("-")[0] if "-" in args.template else args.template,
            typescript=True,
            aliases={"@": "./src"},
        )
        code = architect.generate_config(config)
        print(code)
        return 0

    if args.task or args.template:
        structure = architect.create_project_structure(args.template)
        if args.json:
            print(json.dumps(asdict(structure), indent=2))
        else:
            architect.print_structure(structure)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
