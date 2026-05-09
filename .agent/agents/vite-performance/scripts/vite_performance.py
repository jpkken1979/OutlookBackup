#!/usr/bin/env python3
"""
Vite Performance - Especialista en optimización de rendimiento para Vite.

Especializado en:
- Análisis de bundle size
- Code splitting
- Tree shaking
- Lazy loading
- Optimización de assets

Uso:
    python vite_performance.py --analyze ./dist/
    python vite_performance.py "Optimizar bundle de 2MB"
    python vite_performance.py --check-deps ./package.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.vite-performance")


@dataclass
class BundleAnalysis:
    """Análisis de bundle."""

    total_size_kb: float
    js_size_kb: float
    css_size_kb: float
    assets_size_kb: float
    chunks: list[dict]
    largest_files: list[dict]
    issues: list[str]
    recommendations: list[str]


@dataclass
class DependencyAnalysis:
    """Análisis de dependencias."""

    total_deps: int
    large_deps: list[dict]
    duplicate_deps: list[str]
    unused_potential: list[str]
    recommendations: list[str]


# Umbrales de rendimiento
PERFORMANCE_THRESHOLDS = {
    "initial_js_kb": 200,  # JS inicial máximo recomendado
    "initial_css_kb": 50,  # CSS inicial máximo recomendado
    "total_bundle_kb": 500,  # Bundle total máximo
    "single_chunk_kb": 250,  # Chunk individual máximo
    "image_kb": 100,  # Imagen individual máxima
}

# Dependencias conocidas por ser grandes
LARGE_DEPS = {
    "moment": {"size_kb": 300, "alternative": "dayjs, date-fns"},
    "lodash": {"size_kb": 70, "alternative": "lodash-es (tree-shakeable)"},
    "jquery": {"size_kb": 90, "alternative": "vanilla JS"},
    "axios": {"size_kb": 14, "alternative": "fetch nativo, ky"},
    "uuid": {"size_kb": 10, "alternative": "crypto.randomUUID()"},
    "underscore": {"size_kb": 20, "alternative": "lodash-es o nativo"},
    "chart.js": {"size_kb": 200, "alternative": "chart.js/auto con tree-shaking"},
    "antd": {"size_kb": 1500, "alternative": "importar solo componentes usados"},
    "material-ui": {"size_kb": 500, "alternative": "importar solo componentes usados"},
}

# Optimizaciones de Vite
VITE_OPTIMIZATIONS = {
    "manual_chunks": {
        "description": "Dividir vendors en chunks separados",
        "config": """
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        vendor: ['react', 'react-dom'],
        utils: ['lodash-es', 'date-fns'],
      }
    }
  }
}""",
    },
    "dynamic_imports": {
        "description": "Lazy loading de rutas/componentes",
        "config": """
// React
const MyComponent = lazy(() => import('./MyComponent'));

// Vue
const MyComponent = () => import('./MyComponent.vue');
""",
    },
    "css_code_split": {
        "description": "CSS por chunk separado",
        "config": """
build: {
  cssCodeSplit: true,
}""",
    },
    "minify_options": {
        "description": "Opciones de minificación",
        "config": """
build: {
  minify: 'terser',
  terserOptions: {
    compress: {
      drop_console: true,
      drop_debugger: true,
    },
  },
}""",
    },
    "compression": {
        "description": "Compresión gzip/brotli",
        "config": """
// vite-plugin-compression
import compression from 'vite-plugin-compression';

plugins: [
  compression({ algorithm: 'gzip' }),
  compression({ algorithm: 'brotliCompress', ext: '.br' }),
]""",
    },
    "image_optimization": {
        "description": "Optimizar imágenes",
        "config": """
// vite-plugin-imagemin
import viteImagemin from 'vite-plugin-imagemin';

plugins: [
  viteImagemin({
    gifsicle: { optimizationLevel: 3 },
    mozjpeg: { quality: 80 },
    pngquant: { quality: [0.7, 0.9] },
    webp: { quality: 80 },
  }),
]""",
    },
    "preload": {
        "description": "Preload de módulos críticos",
        "config": """
// En HTML o como plugin
<link rel="modulepreload" href="/assets/vendor.js">
""",
    },
    "externals": {
        "description": "Externalizar deps grandes a CDN",
        "config": """
build: {
  rollupOptions: {
    external: ['react', 'react-dom'],
    output: {
      globals: {
        react: 'React',
        'react-dom': 'ReactDOM',
      }
    }
  }
}""",
    },
}


class VitePerformance:
    """
    Especialista en optimización de rendimiento para Vite.

    Capacidades:
    - Analizar tamaño de bundles
    - Detectar dependencias problemáticas
    - Recomendar optimizaciones
    - Generar configuraciones optimizadas
    """

    def __init__(self):
        self.thresholds = PERFORMANCE_THRESHOLDS
        self.large_deps = LARGE_DEPS
        self.optimizations = VITE_OPTIMIZATIONS

    def analyze_dist(self, dist_path: Path) -> BundleAnalysis:
        """Analiza carpeta dist generada por Vite."""
        analysis = BundleAnalysis(
            total_size_kb=0,
            js_size_kb=0,
            css_size_kb=0,
            assets_size_kb=0,
            chunks=[],
            largest_files=[],
            issues=[],
            recommendations=[],
        )

        if not dist_path.exists():
            analysis.issues.append(f"Carpeta no encontrada: {dist_path}")
            return analysis

        files_info = []

        for file in dist_path.rglob("*"):
            if file.is_file():
                size_kb = file.stat().st_size / 1024
                ext = file.suffix.lower()

                files_info.append(
                    {
                        "path": str(file.relative_to(dist_path)),
                        "size_kb": round(size_kb, 2),
                        "type": ext,
                    }
                )

                analysis.total_size_kb += size_kb

                if ext in [".js", ".mjs"]:
                    analysis.js_size_kb += size_kb
                    analysis.chunks.append(
                        {
                            "name": file.name,
                            "size_kb": round(size_kb, 2),
                        }
                    )
                elif ext == ".css":
                    analysis.css_size_kb += size_kb
                elif ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]:
                    analysis.assets_size_kb += size_kb

        # Ordenar por tamaño
        files_info.sort(key=lambda x: x["size_kb"], reverse=True)
        analysis.largest_files = files_info[:10]
        analysis.chunks.sort(key=lambda x: x["size_kb"], reverse=True)

        # Redondear totales
        analysis.total_size_kb = round(analysis.total_size_kb, 2)
        analysis.js_size_kb = round(analysis.js_size_kb, 2)
        analysis.css_size_kb = round(analysis.css_size_kb, 2)
        analysis.assets_size_kb = round(analysis.assets_size_kb, 2)

        # Detectar issues
        if analysis.js_size_kb > self.thresholds["initial_js_kb"]:
            analysis.issues.append(
                f"⚠️ JS ({analysis.js_size_kb}KB) excede recomendado ({self.thresholds['initial_js_kb']}KB)"
            )
            analysis.recommendations.append("Implementar code splitting con dynamic imports")

        if analysis.css_size_kb > self.thresholds["initial_css_kb"]:
            analysis.issues.append(
                f"⚠️ CSS ({analysis.css_size_kb}KB) excede recomendado ({self.thresholds['initial_css_kb']}KB)"
            )
            analysis.recommendations.append("Considerar PurgeCSS o CSS-in-JS")

        # Chunks grandes
        for chunk in analysis.chunks:
            if chunk["size_kb"] > self.thresholds["single_chunk_kb"]:
                analysis.issues.append(f"⚠️ Chunk grande: {chunk['name']} ({chunk['size_kb']}KB)")
                analysis.recommendations.append(f"Dividir {chunk['name']} en chunks más pequeños")

        # Recomendaciones generales
        if not any("vendor" in c["name"] for c in analysis.chunks):
            analysis.recommendations.append("Considerar separar vendors en chunk aparte")

        if analysis.total_size_kb > self.thresholds["total_bundle_kb"]:
            analysis.recommendations.append("Habilitar compresión gzip/brotli")
            analysis.recommendations.append("Considerar externalizar deps grandes a CDN")

        return analysis

    def analyze_dependencies(self, package_json: Path) -> DependencyAnalysis:
        """Analiza dependencias en package.json."""
        analysis = DependencyAnalysis(
            total_deps=0,
            large_deps=[],
            duplicate_deps=[],
            unused_potential=[],
            recommendations=[],
        )

        if not package_json.exists():
            return analysis

        with open(package_json) as f:
            pkg = json.load(f)

        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        analysis.total_deps = len(all_deps)

        # Buscar deps grandes conocidas
        for dep_name, dep_info in self.large_deps.items():
            if dep_name in all_deps:
                analysis.large_deps.append(
                    {
                        "name": dep_name,
                        "estimated_size_kb": dep_info["size_kb"],
                        "alternative": dep_info["alternative"],
                    }
                )

        # Buscar duplicados potenciales
        dep_names = list(all_deps.keys())
        if "lodash" in dep_names and "lodash-es" in dep_names:
            analysis.duplicate_deps.append("lodash + lodash-es (usar solo lodash-es)")
        if "moment" in dep_names and "dayjs" in dep_names:
            analysis.duplicate_deps.append("moment + dayjs (usar solo dayjs)")

        # Generar recomendaciones
        for large_dep in analysis.large_deps:
            analysis.recommendations.append(
                f"Considerar reemplazar {large_dep['name']} (~{large_dep['estimated_size_kb']}KB) "
                f"por {large_dep['alternative']}"
            )

        if analysis.total_deps > 50:
            analysis.recommendations.append(
                f"Alto número de dependencias ({analysis.total_deps}). Revisar si todas son necesarias."
            )

        return analysis

    def print_bundle_analysis(self, analysis: BundleAnalysis) -> None:
        """Imprime análisis de bundle."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS DE BUNDLE VITE")
        print(f"{'=' * 60}")

        print("\n📊 Tamaños:")
        print(f"   Total: {analysis.total_size_kb} KB")
        print(f"   JS:    {analysis.js_size_kb} KB")
        print(f"   CSS:   {analysis.css_size_kb} KB")
        print(f"   Assets: {analysis.assets_size_kb} KB")

        if analysis.chunks:
            print(f"\n📦 Chunks JS ({len(analysis.chunks)}):")
            for chunk in analysis.chunks[:5]:
                bar = "█" * int(chunk["size_kb"] / 20)
                print(f"   {chunk['name']}: {chunk['size_kb']} KB {bar}")

        if analysis.largest_files:
            print("\n📁 Archivos más grandes:")
            for f in analysis.largest_files[:5]:
                print(f"   {f['path']}: {f['size_kb']} KB")

        if analysis.issues:
            print("\n⚠️ Problemas detectados:")
            for issue in analysis.issues:
                print(f"   {issue}")

        if analysis.recommendations:
            print("\n💡 Recomendaciones:")
            for rec in analysis.recommendations:
                print(f"   - {rec}")

        print(f"\n{'=' * 60}\n")

    def print_dep_analysis(self, analysis: DependencyAnalysis) -> None:
        """Imprime análisis de dependencias."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS DE DEPENDENCIAS")
        print(f"{'=' * 60}")

        print(f"\n📦 Total dependencias: {analysis.total_deps}")

        if analysis.large_deps:
            print("\n🐘 Dependencias grandes detectadas:")
            for dep in analysis.large_deps:
                print(f"   - {dep['name']} (~{dep['estimated_size_kb']} KB)")
                print(f"     Alternativa: {dep['alternative']}")

        if analysis.duplicate_deps:
            print("\n🔄 Posibles duplicados:")
            for dup in analysis.duplicate_deps:
                print(f"   - {dup}")

        if analysis.recommendations:
            print("\n💡 Recomendaciones:")
            for rec in analysis.recommendations:
                print(f"   - {rec}")

        print(f"\n{'=' * 60}\n")

    def list_optimizations(self) -> None:
        """Lista optimizaciones disponibles."""
        print(f"\n{'=' * 60}")
        print("OPTIMIZACIONES DE VITE")
        print(f"{'=' * 60}\n")

        for key, opt in self.optimizations.items():
            print(f"🚀 {key}")
            print(f"   {opt['description']}")
            print()

        print("Usa --show-config <optimization> para ver la configuración")
        print(f"\n{'=' * 60}\n")

    def show_optimization_config(self, opt_name: str) -> None:
        """Muestra configuración de una optimización."""
        if opt_name not in self.optimizations:
            print(f"Optimización no encontrada: {opt_name}")
            print(f"Disponibles: {', '.join(self.optimizations.keys())}")
            return

        opt = self.optimizations[opt_name]
        print(f"\n{'=' * 60}")
        print(f"CONFIGURACIÓN: {opt_name}")
        print(f"{'=' * 60}")
        print(f"\n{opt['description']}\n")
        print("```javascript")
        print(opt["config"])
        print("```")
        print(f"\n{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Vite Performance - Optimización de rendimiento")
    parser.add_argument("task", nargs="?", help="Descripción de la optimización a realizar")
    parser.add_argument("--analyze", "-a", type=Path, help="Analizar carpeta dist")
    parser.add_argument("--check-deps", "-d", type=Path, help="Analizar package.json")
    parser.add_argument("--list", "-l", action="store_true", help="Listar optimizaciones")
    parser.add_argument("--show-config", "-s", help="Mostrar config de optimización")
    parser.add_argument("--json", "-j", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    perf = VitePerformance()

    if args.list:
        perf.list_optimizations()
        return 0

    if args.show_config:
        perf.show_optimization_config(args.show_config)
        return 0

    if args.analyze:
        analysis = perf.analyze_dist(args.analyze)
        if args.json:
            print(
                json.dumps(
                    {
                        "total_size_kb": analysis.total_size_kb,
                        "js_size_kb": analysis.js_size_kb,
                        "css_size_kb": analysis.css_size_kb,
                        "chunks": analysis.chunks,
                        "issues": analysis.issues,
                        "recommendations": analysis.recommendations,
                    },
                    indent=2,
                )
            )
        else:
            perf.print_bundle_analysis(analysis)
        return 0

    if args.check_deps:
        analysis = perf.analyze_dependencies(args.check_deps)
        if args.json:
            print(
                json.dumps(
                    {
                        "total_deps": analysis.total_deps,
                        "large_deps": analysis.large_deps,
                        "recommendations": analysis.recommendations,
                    },
                    indent=2,
                )
            )
        else:
            perf.print_dep_analysis(analysis)
        return 0

    if args.task:
        print(f"Analizando tarea: {args.task}")
        perf.list_optimizations()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
