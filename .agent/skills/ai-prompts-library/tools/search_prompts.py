#!/usr/bin/env python3
"""
AI Prompts Library - Buscador y gestor de prompts
Ecosistema Antigravity v2.0
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

# Ruta base de la biblioteca
BASE_PATH = Path(__file__).parent.parent

# Proveedores disponibles
PROVIDERS = {
    "anthropic": "Claude (Anthropic)",
    "openai": "GPT, o3, o4 (OpenAI)",
    "google": "Gemini (Google)",
    "xai": "Grok (xAI)",
    "perplexity": "Perplexity AI",
    "proton": "Proton AI",
    "misc": "Otros (Warp, Raycast, Notion, etc.)",
}


def get_all_prompts() -> list[dict]:
    """Obtiene todos los prompts de la biblioteca."""
    prompts = []

    for provider in PROVIDERS:
        provider_path = BASE_PATH / provider
        if not provider_path.exists():
            continue

        for file_path in provider_path.rglob("*.md"):
            if file_path.name == "readme.md":
                continue
            prompts.append(
                {
                    "provider": provider,
                    "provider_name": PROVIDERS[provider],
                    "filename": file_path.name,
                    "path": str(file_path.relative_to(BASE_PATH)),
                    "full_path": str(file_path),
                    "size_kb": round(file_path.stat().st_size / 1024, 2),
                }
            )

        for file_path in provider_path.rglob("*.txt"):
            prompts.append(
                {
                    "provider": provider,
                    "provider_name": PROVIDERS[provider],
                    "filename": file_path.name,
                    "path": str(file_path.relative_to(BASE_PATH)),
                    "full_path": str(file_path),
                    "size_kb": round(file_path.stat().st_size / 1024, 2),
                }
            )

    return prompts


def search_prompts(query: str, provider: str | None = None) -> list[dict]:
    """Busca prompts por palabra clave."""
    prompts = get_all_prompts()
    results = []

    query_lower = query.lower()

    for prompt in prompts:
        # Filtrar por proveedor si se especifica
        if provider and prompt["provider"] != provider:
            continue

        # Buscar en nombre de archivo
        if query_lower in prompt["filename"].lower():
            results.append(prompt)
            continue

        # Buscar en contenido
        try:
            with open(prompt["full_path"], encoding="utf-8") as f:
                content = f.read().lower()
                if query_lower in content:
                    results.append(prompt)
        except Exception:
            pass

    return results


def list_by_provider(provider: str) -> list[dict]:
    """Lista todos los prompts de un proveedor."""
    prompts = get_all_prompts()
    return [p for p in prompts if p["provider"] == provider]


def export_catalog(output_path: str) -> dict:
    """Exporta el catálogo completo a JSON."""
    prompts = get_all_prompts()

    catalog = {
        "metadata": {
            "total_prompts": len(prompts),
            "providers": list(PROVIDERS.keys()),
            "generated_at": datetime.now().isoformat(),
            "source": "https://github.com/asgeirtj/system_prompts_leaks",
        },
        "by_provider": {},
        "prompts": prompts,
    }

    # Agrupar por proveedor
    for provider in PROVIDERS:
        provider_prompts = [p for p in prompts if p["provider"] == provider]
        catalog["by_provider"][provider] = {
            "name": PROVIDERS[provider],
            "count": len(provider_prompts),
            "files": [p["filename"] for p in provider_prompts],
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    return catalog


def read_prompt(path: str) -> str:
    """Lee el contenido de un prompt."""
    full_path = BASE_PATH / path
    if not full_path.exists():
        # Intentar buscar en la ruta completa
        if Path(path).exists():
            full_path = Path(path)
        else:
            raise FileNotFoundError(f"Prompt no encontrado: {path}")

    with open(full_path, encoding="utf-8") as f:
        return f.read()


def print_results(results: list[dict], show_content: bool = False):
    """Imprime resultados de búsqueda."""
    if not results:
        print("No se encontraron resultados.")
        return

    print(f"\n{'=' * 60}")
    print(f"Encontrados: {len(results)} prompts")
    print(f"{'=' * 60}\n")

    for i, prompt in enumerate(results, 1):
        print(f"{i}. [{prompt['provider'].upper()}] {prompt['filename']}")
        print(f"   Ruta: {prompt['path']}")
        print(f"   Tamaño: {prompt['size_kb']} KB")

        if show_content:
            print("\n   --- Contenido (primeros 500 chars) ---")
            content = read_prompt(prompt["full_path"])[:500]
            for line in content.split("\n"):
                print(f"   {line}")
            print("   --- Fin ---\n")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="AI Prompts Library - Buscador de system prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python search_prompts.py "memory"              # Buscar por palabra
  python search_prompts.py --provider openai     # Listar por proveedor
  python search_prompts.py --list                # Listar todos
  python search_prompts.py --export catalog.json # Exportar catálogo
  python search_prompts.py --stats               # Ver estadísticas
        """,
    )

    parser.add_argument("query", nargs="?", help="Término de búsqueda")
    parser.add_argument("--provider", "-p", choices=PROVIDERS.keys(), help="Filtrar por proveedor")
    parser.add_argument("--list", "-l", action="store_true", help="Listar todos los prompts")
    parser.add_argument("--export", "-e", metavar="FILE", help="Exportar catálogo a JSON")
    parser.add_argument("--stats", "-s", action="store_true", help="Mostrar estadísticas")
    parser.add_argument(
        "--content", "-c", action="store_true", help="Mostrar preview del contenido"
    )
    parser.add_argument("--read", "-r", metavar="PATH", help="Leer un prompt específico")

    args = parser.parse_args()

    # Estadísticas
    if args.stats:
        prompts = get_all_prompts()
        print("\n" + "=" * 50)
        print("📊 ESTADÍSTICAS DE LA BIBLIOTECA")
        print("=" * 50)
        print(f"\nTotal de prompts: {len(prompts)}")
        print("\nPor proveedor:")
        for provider, name in PROVIDERS.items():
            count = len([p for p in prompts if p["provider"] == provider])
            if count > 0:
                print(f"  • {name}: {count}")
        total_size = sum(p["size_kb"] for p in prompts)
        print(f"\nTamaño total: {total_size:.2f} KB")
        return

    # Exportar catálogo
    if args.export:
        catalog = export_catalog(args.export)
        print(f"✅ Catálogo exportado a: {args.export}")
        print(f"   Total: {catalog['metadata']['total_prompts']} prompts")
        return

    # Leer prompt específico
    if args.read:
        try:
            content = read_prompt(args.read)
            print(content)
        except FileNotFoundError as e:
            print(f"❌ {e}")
        return

    # Listar todos o por proveedor
    if args.list or (args.provider and not args.query):
        if args.provider:
            results = list_by_provider(args.provider)
            print(f"\n📁 Prompts de {PROVIDERS[args.provider]}:")
        else:
            results = get_all_prompts()
            print("\n📁 Todos los prompts:")
        print_results(results, args.content)
        return

    # Búsqueda
    if args.query:
        results = search_prompts(args.query, args.provider)
        print(f"\n🔍 Búsqueda: '{args.query}'")
        if args.provider:
            print(f"   Filtrado por: {PROVIDERS[args.provider]}")
        print_results(results, args.content)
        return

    # Sin argumentos, mostrar ayuda
    parser.print_help()


if __name__ == "__main__":
    main()
