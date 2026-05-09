#!/usr/bin/env python3
"""
Context7 Documentation Fetcher

Obtiene documentación actualizada de librerías usando Context7 MCP.
Puede usarse como script standalone o importarse como módulo.

Uso:
    python context7.py "next.js middleware"
    python context7.py --library fastapi --query "dependency injection"
    python context7.py --resolve "react"
"""

import argparse
import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Context7Mode(Enum):
    """Modos de operación."""

    RESOLVE = "resolve"  # Resolver nombre a ID
    QUERY = "query"  # Obtener documentación
    SEARCH = "search"  # Buscar y obtener docs


@dataclass
class LibraryInfo:
    """Información de una librería."""

    name: str
    context7_id: str
    version: str | None = None
    trust_score: float = 0.0
    description: str = ""


@dataclass
class DocResult:
    """Resultado de documentación."""

    library_id: str
    query: str
    content: str
    code_examples: list
    source_urls: list
    tokens_used: int = 0

    def to_dict(self) -> dict:
        return {
            "library_id": self.library_id,
            "query": self.query,
            "content": self.content,
            "code_examples": self.code_examples,
            "source_urls": self.source_urls,
            "tokens_used": self.tokens_used,
        }


# Mapeo de librerías comunes a Context7 IDs
LIBRARY_MAP = {
    # Frontend
    "react": "/facebook/react",
    "next.js": "/vercel/next.js",
    "nextjs": "/vercel/next.js",
    "vue": "/vuejs/vue",
    "angular": "/angular/angular",
    "svelte": "/sveltejs/svelte",
    "tailwind": "/tailwindlabs/tailwindcss",
    "tailwindcss": "/tailwindlabs/tailwindcss",
    # Backend Python
    "fastapi": "/tiangolo/fastapi",
    "django": "/django/django",
    "flask": "/pallets/flask",
    "pydantic": "/pydantic/pydantic",
    # Backend Node
    "express": "/expressjs/express",
    "nestjs": "/nestjs/nest",
    "hono": "/honojs/hono",
    # Database
    "prisma": "/prisma/prisma",
    "drizzle": "/drizzle-team/drizzle-orm",
    "mongodb": "/mongodb/docs",
    "supabase": "/supabase/supabase",
    "postgres": "/postgres/postgres",
    # Rust
    "tauri": "/tauri-apps/tauri",
    "axum": "/tokio-rs/axum",
    "actix": "/actix/actix-web",
    # Testing
    "playwright": "/microsoft/playwright",
    "jest": "/jestjs/jest",
    "vitest": "/vitest-dev/vitest",
    "pytest": "/pytest-dev/pytest",
    # DevOps
    "docker": "/docker/docs",
    "kubernetes": "/kubernetes/kubernetes",
    "terraform": "/hashicorp/terraform",
    # AI/ML
    "langchain": "/langchain-ai/langchain",
    "openai": "/openai/openai-python",
    "anthropic": "/anthropics/anthropic-sdk-python",
}


class Context7Client:
    """
    Cliente para Context7 MCP.

    Puede usar el servidor MCP local o hacer llamadas directas.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("CONTEXT7_API_KEY")
        self.mcp_url = "https://mcp.context7.com/mcp"
        self._check_node()

    def _check_node(self):
        """Verifica que Node.js esté disponible."""
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True)
            version = result.stdout.strip()
            major = int(version.replace("v", "").split(".")[0])
            if major < 18:
                logger.warning(f"Node.js {version} detectado, se recomienda >= 18")
        except FileNotFoundError:
            logger.warning("Node.js no encontrado, algunas funciones pueden no estar disponibles")

    def resolve_library(self, name: str) -> LibraryInfo | None:
        """
        Resuelve un nombre de librería a su Context7 ID.

        Args:
            name: Nombre de la librería (ej: "react", "fastapi")

        Returns:
            LibraryInfo con el ID de Context7
        """
        # Primero buscar en mapa local
        name_lower = name.lower().strip()
        if name_lower in LIBRARY_MAP:
            return LibraryInfo(
                name=name,
                context7_id=LIBRARY_MAP[name_lower],
                trust_score=1.0,
                description=f"Documentación oficial de {name}",
            )

        # Si no está en el mapa, intentar formato estándar
        # Muchas librerías siguen el patrón /{owner}/{repo}
        logger.info(f"Librería '{name}' no en mapa local, usar resolve-library-id MCP")
        return None

    async def query_docs(
        self, library_id: str, query: str, max_tokens: int = 5000, topic: str | None = None
    ) -> DocResult:
        """
        Obtiene documentación de una librería.

        Args:
            library_id: Context7 ID (ej: "/vercel/next.js")
            query: Pregunta o tópico a buscar
            max_tokens: Límite de tokens en respuesta
            topic: Filtro de tópico opcional

        Returns:
            DocResult con la documentación
        """
        # Construir comando MCP
        args = [
            "npx",
            "-y",
            "@upstash/context7-mcp",
            "--query",
            query,
            "--library",
            library_id,
            "--max-tokens",
            str(max_tokens),
        ]

        if self.api_key:
            args.extend(["--api-key", self.api_key])

        if topic:
            args.extend(["--topic", topic])

        try:
            # Ejecutar MCP server como proceso
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                # Parsear respuesta
                content = result.stdout
                return DocResult(
                    library_id=library_id,
                    query=query,
                    content=content,
                    code_examples=self._extract_code_examples(content),
                    source_urls=[],
                    tokens_used=len(content.split()),
                )
            else:
                logger.error(f"Error ejecutando Context7: {result.stderr}")
                return self._fallback_docs(library_id, query)

        except subprocess.TimeoutExpired:
            logger.error("Timeout ejecutando Context7")
            return self._fallback_docs(library_id, query)
        except FileNotFoundError:
            logger.error("npx no encontrado")
            return self._fallback_docs(library_id, query)

    def _extract_code_examples(self, content: str) -> list:
        """Extrae ejemplos de código del contenido."""
        examples = []
        in_code = False
        current_code = []

        for line in content.split("\n"):
            if line.startswith("```"):
                if in_code:
                    examples.append("\n".join(current_code))
                    current_code = []
                in_code = not in_code
            elif in_code:
                current_code.append(line)

        return examples

    def _fallback_docs(self, library_id: str, query: str) -> DocResult:
        """Documentación de fallback cuando MCP no está disponible."""
        return DocResult(
            library_id=library_id,
            query=query,
            content=f"""
## Documentación no disponible

No se pudo obtener documentación de Context7 para {library_id}.

### Alternativas:
1. Verificar que Node.js >= 18 esté instalado
2. Obtener API key en https://context7.com/dashboard
3. Consultar documentación oficial directamente

### Links útiles:
- Context7: https://context7.com
- GitHub: https://github.com/upstash/context7
""",
            code_examples=[],
            source_urls=["https://context7.com"],
            tokens_used=0,
        )

    async def search_and_get_docs(
        self, library_name: str, query: str, max_tokens: int = 5000
    ) -> DocResult:
        """
        Busca librería y obtiene documentación en un solo paso.

        Args:
            library_name: Nombre de la librería
            query: Pregunta o tópico
            max_tokens: Límite de tokens

        Returns:
            DocResult con la documentación
        """
        # Resolver librería
        library = self.resolve_library(library_name)

        if library:
            return await self.query_docs(library.context7_id, query, max_tokens)
        else:
            # Intentar con nombre directo
            guessed_id = f"/{library_name.replace(' ', '-').lower()}"
            return await self.query_docs(guessed_id, query, max_tokens)


# Función de conveniencia para uso rápido
async def get_docs(library: str, query: str, api_key: str | None = None) -> str:
    """
    Obtiene documentación rápidamente.

    Args:
        library: Nombre de librería
        query: Pregunta
        api_key: API key opcional

    Returns:
        Contenido de documentación
    """
    client = Context7Client(api_key)
    result = await client.search_and_get_docs(library, query)
    return result.content


def main():
    parser = argparse.ArgumentParser(description="Context7 Documentation Fetcher")
    parser.add_argument("query", nargs="?", help="Pregunta o búsqueda (ej: 'next.js middleware')")
    parser.add_argument("--library", "-l", help="Nombre de librería específica")
    parser.add_argument("--resolve", "-r", help="Solo resolver nombre a Context7 ID")
    parser.add_argument(
        "--max-tokens", "-t", type=int, default=5000, help="Máximo de tokens en respuesta"
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--list-libraries", action="store_true", help="Listar librerías conocidas")

    args = parser.parse_args()

    # Listar librerías
    if args.list_libraries:
        print("\n=== Librerías Soportadas ===\n")
        for name, ctx_id in sorted(LIBRARY_MAP.items()):
            print(f"  {name:20} → {ctx_id}")
        print(f"\nTotal: {len(LIBRARY_MAP)} librerías")
        return

    # Resolver librería
    if args.resolve:
        client = Context7Client()
        info = client.resolve_library(args.resolve)
        if info:
            if args.json:
                print(
                    json.dumps(
                        {
                            "name": info.name,
                            "context7_id": info.context7_id,
                            "trust_score": info.trust_score,
                        },
                        indent=2,
                    )
                )
            else:
                print(f"\n{info.name} → {info.context7_id}")
        else:
            print(f"No se encontró: {args.resolve}")
        return

    # Buscar documentación
    if not args.query and not args.library:
        parser.print_help()
        return

    # Determinar librería y query
    if args.library:
        library = args.library
        query = args.query or "overview"
    else:
        # Intentar extraer librería del query
        parts = args.query.split()
        if parts[0].lower() in LIBRARY_MAP:
            library = parts[0]
            query = " ".join(parts[1:]) or "overview"
        else:
            library = parts[0]
            query = " ".join(parts[1:]) if len(parts) > 1 else "overview"

    # Ejecutar
    async def run():
        client = Context7Client()
        result = await client.search_and_get_docs(library, query, args.max_tokens)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"\n{'=' * 60}")
            print(f"CONTEXT7 DOCS: {library}")
            print(f"Query: {query}")
            print(f"{'=' * 60}\n")
            print(result.content)

            if result.code_examples:
                print(f"\n--- Ejemplos de código ({len(result.code_examples)}) ---")
                for i, example in enumerate(result.code_examples[:3], 1):
                    print(f"\nEjemplo {i}:")
                    print(example[:500] + "..." if len(example) > 500 else example)

            print(f"\n{'=' * 60}\n")

    asyncio.run(run())


if __name__ == "__main__":
    main()
