#!/usr/bin/env python3
"""
Enhanced Context7 Integration

Mejoras sobre la integración básica:
1. Cache inteligente con TTL configurable
2. Auto-detección de librerías en queries de agentes
3. Integración con UnifiedMemory para persistir documentación
4. Resolución automática de libraryId
5. Prefetch de documentación para dependencias del proyecto
6. Rate limiting y retry logic

Usage:
    enhancer = Context7Enhancer()

    # Auto-detect and fetch
    docs = await enhancer.auto_fetch("How do I use middleware in Next.js?")

    # Prefetch project dependencies
    await enhancer.prefetch_project_deps("./package.json")

    # Search cached docs
    results = enhancer.search_cache("authentication")
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("antigravity.context7_enhanced")


@dataclass
class CachedDoc:
    """Cached documentation entry."""

    library_id: str
    query: str
    content: str
    code_examples: list
    fetched_at: str
    expires_at: str
    hit_count: int = 0
    last_accessed: str = ""

    def is_expired(self) -> bool:
        return datetime.now().isoformat() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "library_id": self.library_id,
            "query": self.query,
            "content": self.content,
            "code_examples": self.code_examples,
            "fetched_at": self.fetched_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CachedDoc":
        return cls(**data)


# Extended library mapping (more comprehensive)
EXTENDED_LIBRARY_MAP = {
    # Frontend Frameworks
    "react": "/facebook/react",
    "next.js": "/vercel/next.js",
    "nextjs": "/vercel/next.js",
    "next": "/vercel/next.js",
    "vue": "/vuejs/vue",
    "vue.js": "/vuejs/vue",
    "nuxt": "/nuxt/nuxt",
    "nuxt.js": "/nuxt/nuxt",
    "angular": "/angular/angular",
    "svelte": "/sveltejs/svelte",
    "sveltekit": "/sveltejs/kit",
    "solid": "/solidjs/solid",
    "solidjs": "/solidjs/solid",
    "qwik": "/QwikDev/qwik",
    "astro": "/withastro/astro",
    "remix": "/remix-run/remix",
    # UI Libraries
    "tailwind": "/tailwindlabs/tailwindcss",
    "tailwindcss": "/tailwindlabs/tailwindcss",
    "shadcn": "/shadcn-ui/ui",
    "radix": "/radix-ui/primitives",
    "chakra": "/chakra-ui/chakra-ui",
    "mui": "/mui/material-ui",
    "material-ui": "/mui/material-ui",
    "ant-design": "/ant-design/ant-design",
    "antd": "/ant-design/ant-design",
    # State Management
    "redux": "/reduxjs/redux",
    "zustand": "/pmndrs/zustand",
    "jotai": "/pmndrs/jotai",
    "recoil": "/facebookexperimental/Recoil",
    "mobx": "/mobxjs/mobx",
    "tanstack-query": "/TanStack/query",
    "react-query": "/TanStack/query",
    "swr": "/vercel/swr",
    # Backend Python
    "fastapi": "/tiangolo/fastapi",
    "django": "/django/django",
    "flask": "/pallets/flask",
    "pydantic": "/pydantic/pydantic",
    "sqlalchemy": "/sqlalchemy/sqlalchemy",
    "alembic": "/sqlalchemy/alembic",
    "celery": "/celery/celery",
    "httpx": "/encode/httpx",
    "aiohttp": "/aio-libs/aiohttp",
    "starlette": "/encode/starlette",
    "uvicorn": "/encode/uvicorn",
    # Backend Node
    "express": "/expressjs/express",
    "nestjs": "/nestjs/nest",
    "nest": "/nestjs/nest",
    "hono": "/honojs/hono",
    "fastify": "/fastify/fastify",
    "koa": "/koajs/koa",
    "trpc": "/trpc/trpc",
    "graphql": "/graphql/graphql-js",
    # Database & ORM
    "prisma": "/prisma/prisma",
    "drizzle": "/drizzle-team/drizzle-orm",
    "typeorm": "/typeorm/typeorm",
    "sequelize": "/sequelize/sequelize",
    "mongodb": "/mongodb/docs",
    "mongoose": "/Automattic/mongoose",
    "supabase": "/supabase/supabase",
    "postgres": "/postgres/postgres",
    "redis": "/redis/redis",
    # Rust
    "tauri": "/tauri-apps/tauri",
    "axum": "/tokio-rs/axum",
    "actix": "/actix/actix-web",
    "tokio": "/tokio-rs/tokio",
    "serde": "/serde-rs/serde",
    "diesel": "/diesel-rs/diesel",
    # Testing
    "playwright": "/microsoft/playwright",
    "jest": "/jestjs/jest",
    "vitest": "/vitest-dev/vitest",
    "pytest": "/pytest-dev/pytest",
    "cypress": "/cypress-io/cypress",
    "testing-library": "/testing-library/react-testing-library",
    # DevOps & Infrastructure
    "docker": "/docker/docs",
    "kubernetes": "/kubernetes/kubernetes",
    "k8s": "/kubernetes/kubernetes",
    "terraform": "/hashicorp/terraform",
    "pulumi": "/pulumi/pulumi",
    "ansible": "/ansible/ansible",
    # AI/ML
    "langchain": "/langchain-ai/langchain",
    "openai": "/openai/openai-python",
    "anthropic": "/anthropics/anthropic-sdk-python",
    "llamaindex": "/run-llama/llama_index",
    "transformers": "/huggingface/transformers",
    "pytorch": "/pytorch/pytorch",
    "tensorflow": "/tensorflow/tensorflow",
    # Build Tools
    "vite": "/vitejs/vite",
    "webpack": "/webpack/webpack",
    "esbuild": "/evanw/esbuild",
    "turbo": "/vercel/turbo",
    "turborepo": "/vercel/turbo",
    "nx": "/nrwl/nx",
    # Auth & Security
    "auth.js": "/nextauthjs/next-auth",
    "next-auth": "/nextauthjs/next-auth",
    "clerk": "/clerkinc/javascript",
    "lucia": "/lucia-auth/lucia",
    "passport": "/jaredhanson/passport",
    # Misc
    "zod": "/colinhacks/zod",
    "date-fns": "/date-fns/date-fns",
    "dayjs": "/iamkun/dayjs",
    "lodash": "/lodash/lodash",
    "axios": "/axios/axios",
    "socket.io": "/socketio/socket.io",
}


# Patterns to detect library mentions in queries
LIBRARY_PATTERNS = [
    # Direct mentions
    r"\b(react|vue|angular|svelte|next\.?js|nuxt|astro)\b",
    r"\b(express|fastapi|django|flask|nestjs|hono)\b",
    r"\b(prisma|drizzle|typeorm|sequelize|mongodb|supabase)\b",
    r"\b(tailwind|shadcn|chakra|mui|material-ui)\b",
    r"\b(playwright|jest|vitest|pytest|cypress)\b",
    r"\b(docker|kubernetes|terraform|pulumi)\b",
    r"\b(langchain|openai|anthropic|llamaindex)\b",
    r"\b(vite|webpack|esbuild|turbo)\b",
    r"\b(zod|pydantic|yup)\b",
    # Common patterns
    r"(?:using|with|in)\s+(\w+(?:\.\w+)?)",
    r"(\w+(?:\.\w+)?)\s+(?:documentation|docs|api)",
    r"how\s+(?:do|to|can)\s+(?:I|we)?\s*(?:use)?\s*(\w+)",
]


class Context7Enhancer:
    """
    Enhanced Context7 integration with intelligent caching and auto-detection.
    """

    def __init__(
        self,
        storage_path: Path | None = None,
        cache_ttl_hours: int = 24,
        api_key: str | None = None,
    ):
        if storage_path is None:
            storage_path = Path.home() / ".antigravity" / "context7_cache"

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.api_key = api_key or os.environ.get("CONTEXT7_API_KEY")

        self._cache: dict[str, CachedDoc] = {}
        self._load_cache()

        logger.info(f"Context7Enhancer initialized with {len(self._cache)} cached docs")

    def _cache_key(self, library_id: str, query: str) -> str:
        """Generate cache key."""
        content = f"{library_id}:{query.lower().strip()}"
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

    def _load_cache(self):
        """Load cache from disk."""
        cache_file = self.storage_path / "cache.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                for key, doc_data in data.items():
                    doc = CachedDoc.from_dict(doc_data)
                    if not doc.is_expired():
                        self._cache[key] = doc
                logger.debug(f"Loaded {len(self._cache)} cached docs")
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")

    def _save_cache(self):
        """Save cache to disk."""
        cache_file = self.storage_path / "cache.json"
        data = {key: doc.to_dict() for key, doc in self._cache.items() if not doc.is_expired()}
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def resolve_library(self, name: str) -> str | None:
        """Resolve library name to Context7 ID."""
        name_lower = name.lower().strip()

        # Direct lookup
        if name_lower in EXTENDED_LIBRARY_MAP:
            return EXTENDED_LIBRARY_MAP[name_lower]

        # Try with common suffixes removed
        for suffix in [".js", ".ts", ".py"]:
            if name_lower.endswith(suffix):
                base = name_lower[: -len(suffix)]
                if base in EXTENDED_LIBRARY_MAP:
                    return EXTENDED_LIBRARY_MAP[base]

        return None

    def detect_libraries(self, text: str) -> list[str]:
        """
        Detect library mentions in text.

        Returns list of detected library IDs.
        """
        detected = set()
        text_lower = text.lower()

        # Direct keyword matching
        for name, lib_id in EXTENDED_LIBRARY_MAP.items():
            if name in text_lower:
                detected.add(lib_id)

        # Pattern matching
        for pattern in LIBRARY_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                candidate: str
                if isinstance(match, tuple):
                    parts: list[str] = [str(part) for part in match if part]
                    candidate = parts[0] if parts else ""
                else:
                    candidate = str(match) if match is not None else ""
                if not candidate:
                    continue
                resolved_id = self.resolve_library(candidate)
                if resolved_id:
                    detected.add(resolved_id)

        return list(detected)

    async def fetch_docs(
        self, library_id: str, query: str, max_tokens: int = 5000, use_cache: bool = True
    ) -> CachedDoc:
        """
        Fetch documentation with caching.
        """
        cache_key = self._cache_key(library_id, query)

        # Check cache
        if use_cache and cache_key in self._cache:
            doc = self._cache[cache_key]
            if not doc.is_expired():
                doc.hit_count += 1
                doc.last_accessed = datetime.now().isoformat()
                self._save_cache()
                logger.debug(f"Cache hit for {library_id}: {query[:30]}...")
                return doc

        # Fetch from Context7
        content, code_examples = await self._fetch_from_context7(library_id, query, max_tokens)

        # Create cache entry
        now = datetime.now()
        doc = CachedDoc(
            library_id=library_id,
            query=query,
            content=content,
            code_examples=code_examples,
            fetched_at=now.isoformat(),
            expires_at=(now + self.cache_ttl).isoformat(),
            hit_count=1,
            last_accessed=now.isoformat(),
        )

        # Store in cache
        self._cache[cache_key] = doc
        self._save_cache()

        return doc

    async def _fetch_from_context7(
        self, library_id: str, query: str, max_tokens: int
    ) -> tuple[str, list[str]]:
        """Fetch from Context7 REST API v2."""
        params = {
            "libraryId": library_id,
            "query": query,
            "type": "json",
        }
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://context7.com/api/v2/context",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()

            content, code_examples = self._normalize_context_response(response.text, max_tokens)
            if content.strip():
                return content, code_examples
            logger.warning("Context7 respondió vacío para %s", library_id)
            return self._get_fallback_content(library_id, query), []
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Context7 HTTP %s para %s: %s",
                e.response.status_code,
                library_id,
                e.response.text[:200],
            )
            return self._get_fallback_content(library_id, query), []
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning("Context7 request error: %s", e)
            return self._get_fallback_content(library_id, query), []

    @staticmethod
    def _process_code_list(
        code_list: list,
        lines: list[str],
        code_examples: list[str],
    ) -> None:
        """Procesa una lista de bloques de código y los agrega a lines/code_examples.

        Args:
            code_list: Lista de dicts con 'code' y 'language'.
            lines: Lista acumuladora de líneas de texto.
            code_examples: Lista acumuladora de ejemplos de código.
        """
        for code_item in code_list:
            code = code_item.get("code", "")
            language = code_item.get("language", "")
            if not code:
                continue
            fenced = f"```{language}\n{code}\n```" if language else f"```\n{code}\n```"
            lines.append(fenced)
            code_examples.append(code)

    def _normalize_dict_payload(
        self,
        payload: dict,
        lines: list[str],
        code_examples: list[str],
        max_chars: int,
    ) -> tuple[str, list[str]] | None:
        """Normaliza un payload dict de Context7.

        Args:
            payload: Dict con la respuesta JSON.
            lines: Lista acumuladora de líneas.
            code_examples: Lista acumuladora de ejemplos.
            max_chars: Máximo de caracteres.

        Returns:
            Tupla (content, examples) si se resolvió directamente, None si se debe continuar.
        """
        # Variante MCP/SDK
        docs = payload.get("documentation")
        if isinstance(docs, str):
            content = docs[:max_chars]
            return content, self._extract_code_examples(content)

        # Variante REST v2 — snippets
        snippets = payload.get("codeSnippets", [])
        if isinstance(snippets, list):
            for snippet in snippets:
                title = snippet.get("codeTitle", "")
                if title:
                    lines.append(f"## {title}")
                self._process_code_list(snippet.get("codeList", []), lines, code_examples)

        # Secciones de texto
        text_sections = payload.get("sections") or payload.get("results")
        if isinstance(text_sections, list):
            for section in text_sections:
                title = section.get("title", "")
                content = section.get("content", "")
                if title:
                    lines.append(f"## {title}")
                if content:
                    lines.append(content)

        return None

    def _normalize_list_payload(
        self,
        payload: list,
        lines: list[str],
        code_examples: list[str],
    ) -> None:
        """Normaliza un payload lista de Context7.

        Args:
            payload: Lista de dicts con snippets/documentos.
            lines: Lista acumuladora de líneas.
            code_examples: Lista acumuladora de ejemplos.
        """
        for item in payload:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("codeTitle") or ""
            content = item.get("content") or ""
            if title:
                lines.append(f"## {title}")
            if content:
                lines.append(content)
            code_list = item.get("codeList", [])
            if isinstance(code_list, list):
                self._process_code_list(code_list, lines, code_examples)

    def _normalize_context_response(self, raw_text: str, max_tokens: int) -> tuple[str, list[str]]:
        """Normaliza la respuesta JSON/TXT de Context7 a texto + ejemplos."""
        max_chars = max_tokens * 4
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            content = raw_text[:max_chars]
            return content, self._extract_code_examples(content)

        lines: list[str] = []
        code_examples: list[str] = []

        if isinstance(payload, dict):
            early_result = self._normalize_dict_payload(payload, lines, code_examples, max_chars)
            if early_result is not None:
                return early_result
        elif isinstance(payload, list):
            self._normalize_list_payload(payload, lines, code_examples)

        content = "\n\n".join(lines).strip()[:max_chars]
        if not code_examples:
            code_examples = self._extract_code_examples(content)
        return content, code_examples

    def _extract_code_examples(self, content: str) -> list[str]:
        """Extract code blocks from content."""
        examples: list[str] = []
        in_code = False
        current_code: list[str] = []

        for line in content.split("\n"):
            if line.startswith("```"):
                if in_code:
                    examples.append("\n".join(current_code))
                    current_code = []
                in_code = not in_code
            elif in_code:
                current_code.append(line)

        return examples

    def _get_fallback_content(self, library_id: str, query: str) -> str:
        """Generate fallback content."""
        return f"""
# Documentation for {library_id}

Query: {query}

**Note**: Real-time documentation fetch failed.

## Suggestions:
1. Verify network connectivity
2. Ensure CONTEXT7_API_KEY is configured
3. Validate the library ID format (/org/project)

## Alternative Resources:
- GitHub: https://github.com{library_id}
- Context7: https://context7.com
"""

    async def auto_fetch(
        self, text: str, max_results: int = 3, max_tokens: int = 3000
    ) -> list[CachedDoc]:
        """
        Auto-detect libraries in text and fetch relevant documentation.
        """
        detected = self.detect_libraries(text)

        if not detected:
            logger.info("No libraries detected in query")
            return []

        # Limit to max_results
        to_fetch = detected[:max_results]
        logger.info(f"Auto-detected libraries: {to_fetch}")

        # Fetch in parallel
        tasks = [self.fetch_docs(lib_id, text, max_tokens) for lib_id in to_fetch]

        results: list[CachedDoc | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Filter out errors
        docs: list[CachedDoc] = [r for r in results if isinstance(r, CachedDoc)]
        return docs

    def _resolve_deps_from_package_json(self, package_json_path: str) -> list[tuple[str, str]]:
        """Resuelve los library IDs de las dependencias de un package.json.

        Args:
            package_json_path: Ruta al archivo package.json.

        Returns:
            Lista de tuplas (nombre_dependencia, library_id) resueltas.
        """
        resolved: list[tuple[str, str]] = []
        package_path = Path(package_json_path)
        if not package_path.exists():
            return resolved
        try:
            pkg = json.loads(package_path.read_text(encoding="utf-8"))
            for dep in list(pkg.get("dependencies", {}).keys()) + list(
                pkg.get("devDependencies", {}).keys()
            ):
                lib_id = self.resolve_library(dep)
                if lib_id:
                    resolved.append((dep, lib_id))
        except Exception as e:
            logger.error(f"Failed to parse package.json: {e}")
        return resolved

    def _resolve_deps_from_pyproject(self, pyproject_path: str) -> list[tuple[str, str]]:
        """Resuelve los library IDs de las dependencias de un pyproject.toml.

        Args:
            pyproject_path: Ruta al archivo pyproject.toml.

        Returns:
            Lista de tuplas (nombre_dependencia, library_id) resueltas.
        """
        resolved: list[tuple[str, str]] = []
        pyproject = Path(pyproject_path)
        if not pyproject.exists():
            return resolved
        try:
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                for dep in data.get("project", {}).get("dependencies", []):
                    dep_name = dep.split("[")[0].split(">=")[0].split("==")[0].strip()
                    lib_id = self.resolve_library(dep_name)
                    if lib_id:
                        resolved.append((dep_name, lib_id))
        except ImportError:
            logger.warning("tomllib not available, skipping pyproject.toml")
        return resolved

    async def _fetch_deps_docs(
        self, deps_to_fetch: list[tuple[str, str]], results: dict[str, list[Any]]
    ) -> None:
        """Descarga docs de las dependencias con rate limiting, mutando results.

        Args:
            deps_to_fetch: Lista de tuplas (nombre, library_id) a descargar.
            results: Diccionario de resultados a poblar in-place ("fetched"/"errors").
        """
        for dep_name, lib_id in deps_to_fetch[:20]:  # Limit to 20
            try:
                await self.fetch_docs(lib_id, "overview getting started", max_tokens=2000)
                results["fetched"].append(dep_name)
                await asyncio.sleep(0.5)  # Rate limiting
            except Exception as e:
                results["errors"].append((dep_name, str(e)))

    async def prefetch_project_deps(
        self, package_json_path: str, pyproject_path: str | None = None
    ) -> dict:
        """
        Prefetch documentation for project dependencies.
        """
        results: dict[str, list[Any]] = {"fetched": [], "skipped": [], "errors": []}

        deps_to_fetch = self._resolve_deps_from_package_json(package_json_path)
        if pyproject_path:
            deps_to_fetch += self._resolve_deps_from_pyproject(pyproject_path)

        logger.info(f"Found {len(deps_to_fetch)} dependencies to prefetch")

        await self._fetch_deps_docs(deps_to_fetch, results)

        return results

    def search_cache(self, query: str, limit: int = 10) -> list[CachedDoc]:
        """
        Search cached documentation.
        """
        query_lower = query.lower()
        results = []

        for doc in self._cache.values():
            if doc.is_expired():
                continue

            # Score by relevance
            score = 0
            if query_lower in doc.query.lower():
                score += 2
            if query_lower in doc.content.lower():
                score += 1
            if query_lower in doc.library_id.lower():
                score += 1

            if score > 0:
                results.append((score, doc))

        # Sort by score
        results.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in results[:limit]]

    def get_stats(self) -> dict:
        """Get cache statistics."""
        valid_docs = [d for d in self._cache.values() if not d.is_expired()]
        total_hits = sum(d.hit_count for d in valid_docs)

        return {
            "total_cached": len(valid_docs),
            "total_hits": total_hits,
            "libraries_covered": len({d.library_id for d in valid_docs}),
            "storage_path": str(self.storage_path),
            "known_libraries": len(EXTENDED_LIBRARY_MAP),
        }

    def clear_cache(self, expired_only: bool = True):
        """Clear cache."""
        if expired_only:
            self._cache = {k: v for k, v in self._cache.items() if not v.is_expired()}
        else:
            self._cache.clear()
        self._save_cache()


# Singleton instance
_enhancer_instance: Context7Enhancer | None = None


def get_context7_enhancer(storage_path: Path | None = None) -> Context7Enhancer:
    """Get or create the Context7 enhancer instance."""
    global _enhancer_instance
    if _enhancer_instance is None:
        _enhancer_instance = Context7Enhancer(storage_path)
    return _enhancer_instance


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate enhanced Context7 integration."""
    enhancer = Context7Enhancer()

    print("=== Context7 Enhanced Demo ===\n")

    # Test library detection
    test_queries = [
        "How do I use middleware in Next.js?",
        "FastAPI dependency injection with Pydantic",
        "Playwright test automation best practices",
        "React hooks and Zustand state management",
    ]

    for query in test_queries:
        detected = enhancer.detect_libraries(query)
        print(f"Query: {query}")
        print(f"  Detected: {detected}\n")

    # Test auto-fetch (uses cache or fallback)
    print("=== Auto-fetch Test ===")
    docs = await enhancer.auto_fetch("How to set up authentication in Next.js?")
    for doc in docs:
        print(f"  Library: {doc.library_id}")
        print(f"  Content preview: {doc.content[:100]}...")
        print()

    # Stats
    print("=== Cache Stats ===")
    stats = enhancer.get_stats()
    print(f"  Cached docs: {stats['total_cached']}")
    print(f"  Total hits: {stats['total_hits']}")
    print(f"  Known libraries: {stats['known_libraries']}")


if __name__ == "__main__":
    asyncio.run(demo())
