"""LLM-powered contextual suggestions for /shu command dimensions.

Provides the ShuSuggestionEngine that calls the Antigravity gateway proxy
to generate short, useful suggestions for each /shu question dimension
based on the user's goal, category, and optional partial answer.
"""

import asyncio
import json
import logging
import time
from pathlib import Path

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

SHU_DIMENSIONS: list[str] = [
    "context",
    "scope",
    "constraints",
    "validation",
    "priority",
    "historical",
]

SHU_QUESTIONS_MAP: dict[str, dict[str, str]] = {
    "context": {
        "label": "Contexto",
        "description": "¿Cuál es el estado actual y qué problema estás resolviendo?",
        "good_patterns": (
            "Mencionar el estado actual del sistema, el problema concreto que se resuelve "
            "y la motivación del cambio."
        ),
        "example": (
            "Estoy refactorizando el módulo de memoria para reducir acoplamiento. "
            "Actualmente tiene 3 dependencias circulares que dificultan los tests."
        ),
    },
    "scope": {
        "label": "Alcance",
        "description": "¿Qué archivos, módulos o sistemas están en scope de esta tarea?",
        "good_patterns": (
            "Listar rutas o módulos concretos incluidos, y mencionar explícitamente "
            "lo que queda fuera del scope."
        ),
        "example": (
            "Solo nexus-app/src/hooks/useMemoryData.ts y "
            "nexus-app/src/components/Memory/. Sin tocar el backend Rust."
        ),
    },
    "constraints": {
        "label": "Restricciones",
        "description": "¿Qué NO se puede cambiar, romper o modificar?",
        "good_patterns": (
            "Enumerar APIs públicas que deben mantenerse, archivos intocables, "
            "convenciones de código obligatorias o decisiones previas que no se revisan."
        ),
        "example": (
            "No cambiar la firma de useMemoryData. No commitear .env. "
            "Mantener compatibilidad con Tauri 2 IPC."
        ),
    },
    "validation": {
        "label": "Validación",
        "description": "¿Cómo vas a verificar que la tarea quedó bien?",
        "good_patterns": (
            "Criterios concretos y verificables: tests que deben pasar, "
            "comandos a ejecutar, métricas o comportamiento observable esperado."
        ),
        "example": (
            "npm test pasa sin errores TypeScript. Build exitoso. "
            "El panel de Memoria muestra datos correctamente en runtime."
        ),
    },
    "priority": {
        "label": "Prioridad",
        "description": "¿Qué es lo más importante? ¿Qué puede quedar para después?",
        "good_patterns": (
            "Diferenciar lo crítico (debe quedar en esta sesión) de lo opcional "
            "(puede quedar como pendiente). Ayuda a focalizar el esfuerzo."
        ),
        "example": (
            "Prioridad 1: que los tests pasen. "
            "Prioridad 2: refactor de estilo. "
            "Puede quedar para después: optimizar performance."
        ),
    },
    "historical": {
        "label": "Histórico",
        "description": (
            "¿Hay decisiones previas, bugs conocidos o contexto de sesiones anteriores relevante?"
        ),
        "good_patterns": (
            "Mencionar sesiones pasadas, bugfixes previos, decisiones de arquitectura "
            "ya tomadas o anti-patrones conocidos que afectan esta tarea."
        ),
        "example": (
            "La sesión 2026-06-12 resolvió el race condition en useAgentBus. "
            "Hay un bugfix en memory.rs commit ddc1f91c que no debe revertirse."
        ),
    },
}

CACHE_TTL_SECONDS: int = 604800  # 7 días

LLM_SUGGESTIONS_PROMPT: str = """Sos un asistente experto en ayudar a programadores a responder preguntas de clarificación para tareas de desarrollo de software.

El usuario está respondiendo la dimensión "{dimension_label}" del protocolo /shu.
Pregunta: {dimension_description}

Goal del usuario: {goal}
Categoría: {category}
{partial_answer_section}

Patrones de buena respuesta para esta dimensión:
{good_patterns}

Ejemplo de respuesta fuerte:
{example}

Tu tarea: generá una sugerencia concisa y concreta de 1-3 oraciones que ayude al usuario a completar esta dimensión específica para SU goal y categoría.
- Sé específico al contexto del usuario, no genérico
- No repitas la pregunta
- No uses markdown, solo texto plano
- Máximo 300 caracteres
- En español rioplatense"""


# ──────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────


class ShuSuggestionEngine:
    """Generates LLM-powered suggestions for /shu question dimensions.

    Uses the Antigravity gateway proxy at :4747 to call the configured LLM
    and returns short contextual suggestions. Results are cached locally for
    7 days to avoid redundant LLM calls.

    Args:
        gateway_url: Base URL of the Antigravity gateway proxy.
        cache_dir: Directory for suggestion cache. Defaults to ~/.antigravity/shu/
    """

    def __init__(
        self,
        gateway_url: str = "http://127.0.0.1:4747/claudeproxy",
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize the suggestion engine.

        Args:
            gateway_url: URL of the LLM proxy endpoint.
            cache_dir: Cache directory path. Defaults to ~/.antigravity/shu/
        """
        self.gateway_url = gateway_url
        if cache_dir is None:
            cache_dir = Path.home() / ".antigravity" / "shu"
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "suggestion_cache.json"
        self._cache: dict[str, dict] = {}
        self._cache_loaded = False

    # ── Cache management ───────────────────────────────────────

    def _load_cache(self) -> None:
        """Load suggestion cache from disk.

        Silently ignores missing or malformed cache files.
        """
        if self._cache_loaded:
            return
        self._cache = {}
        if self.cache_file.exists():
            try:
                raw = self.cache_file.read_text(encoding="utf-8")
                self._cache = json.loads(raw)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("No se pudo cargar el cache de sugerencias: %s", exc)
        self._cache_loaded = True

    def _save_cache(self) -> None:
        """Persist suggestion cache to disk.

        Creates the cache directory if it does not exist.
        """
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("No se pudo guardar el cache de sugerencias: %s", exc)

    def _is_cache_valid(self, timestamp: float) -> bool:
        """Return True if the cache entry is within TTL.

        Args:
            timestamp: Unix timestamp when the entry was cached.

        Returns:
            True if the entry is still valid (within 7 days).
        """
        return (time.time() - timestamp) < CACHE_TTL_SECONDS

    def _cache_key(self, goal: str, category: str, dimension: str) -> str:
        """Build a cache key from goal, category and dimension.

        Args:
            goal: User's stated goal.
            category: Task category.
            dimension: Shu dimension name.

        Returns:
            Cache key string in format 'goal#category#dimension'.
        """
        return f"{goal}#{category}#{dimension}"

    # ── LLM call ───────────────────────────────────────────────

    def _call_llm_sync(self, prompt: str, timeout: float = 5.0) -> str:
        """Call the gateway LLM proxy synchronously.

        Args:
            prompt: The full prompt to send.
            timeout: Request timeout in seconds.

        Returns:
            LLM response text, or "no suggestion available" on error.
        """
        payload = json.dumps(
            {
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 150,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            self.gateway_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": "proxy-passthrough",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                # Anthropic response format
                content = data.get("content", [])
                if content and isinstance(content, list):
                    text = content[0].get("text", "").strip()
                    # Truncate to 300 chars
                    return text[:300] if text else "no suggestion available"
                return "no suggestion available"
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            logger.debug("LLM call failed: %s", exc)
            return "no suggestion available"
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.debug("LLM response parse error: %s", exc)
            return "no suggestion available"

    # ── Public API ─────────────────────────────────────────────

    def suggest_for_dimension(
        self,
        dimension: str,
        goal: str,
        category: str,
        current_answer: str = "",
    ) -> str:
        """Generate a contextual suggestion for a single /shu dimension.

        Checks the local cache first. If no valid cache entry exists, calls
        the LLM proxy and stores the result.

        Args:
            dimension: One of the 6 /shu dimensions (context, scope, etc.).
            goal: User's stated goal for the task.
            category: Task category (e.g. "analysis", "refactor").
            current_answer: Optional partial answer already written by the user.

        Returns:
            Suggestion string (max 300 chars) or "no suggestion available".
        """
        if dimension not in SHU_QUESTIONS_MAP:
            return "no suggestion available"

        self._load_cache()
        key = self._cache_key(goal, category, dimension)

        # Cache hit
        if key in self._cache:
            entry = self._cache[key]
            if self._is_cache_valid(entry.get("timestamp", 0.0)):
                return entry.get("suggestion", "no suggestion available")

        # Build prompt
        dim_info = SHU_QUESTIONS_MAP[dimension]
        partial_section = (
            f"\nRespuesta parcial del usuario: {current_answer}" if current_answer.strip() else ""
        )
        prompt = LLM_SUGGESTIONS_PROMPT.format(
            dimension_label=dim_info["label"],
            dimension_description=dim_info["description"],
            goal=goal,
            category=category,
            partial_answer_section=partial_section,
            good_patterns=dim_info["good_patterns"],
            example=dim_info["example"],
        )

        suggestion = self._call_llm_sync(prompt, timeout=5.0)

        # Store in cache
        self._cache[key] = {
            "suggestion": suggestion,
            "timestamp": time.time(),
        }
        self._save_cache()

        return suggestion

    async def suggest_for_all_dimensions(
        self,
        goal: str,
        category: str,
    ) -> dict[str, str]:
        """Generate suggestions for all 6 /shu dimensions in parallel.

        Uses asyncio to run all 6 LLM calls concurrently. Falls back
        gracefully if any individual call fails.

        Args:
            goal: User's stated goal for the task.
            category: Task category.

        Returns:
            Dict mapping dimension name to suggestion string.
        """
        loop = asyncio.get_event_loop()

        async def fetch_one(dimension: str) -> tuple[str, str]:
            def run() -> str:
                return self.suggest_for_dimension(dimension, goal, category)

            suggestion = await loop.run_in_executor(None, run)
            return dimension, suggestion

        tasks = [fetch_one(dim) for dim in SHU_DIMENSIONS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: dict[str, str] = {}
        for dim, item in zip(SHU_DIMENSIONS, results, strict=True):
            if isinstance(item, BaseException):
                logger.warning("Error fetching suggestion for %s: %s", dim, item)
                output[dim] = "no suggestion available"
            else:
                _, suggestion = item
                output[dim] = suggestion

        return output
