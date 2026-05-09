"""
Context Compressor Skill — Comprime contexto largo manteniendo información relevante.

Uso:
    python main.py --task "texto largo aqui"
    python main.py --task "..." --target-ratio 0.20
    python main.py --task "..." --json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field


DEFAULT_TARGET_RATIO = 0.20

# Patrones para detectar cada categoría de información
FACT_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(v\d+\.\d+[\.\d]*)\b"),  # versiones (v1.2.3)
    re.compile(r"\b(\d{1,5}\.\d{1,5}\.\d{1,5})\b"),  # semver
    re.compile(r"\bhttps?://[^\s\"'<>]+"),  # URLs
    re.compile(r"\b([A-Z_]{2,}(?:_[A-Z0-9]+)+)\b"),  # ENV VARS
    re.compile(r"localhost:\d+"),  # hosts locales
    re.compile(r"(python|node|npm|rust|docker)\s+[\d.]+", re.IGNORECASE),  # versiones de tools
    re.compile(r"puerto?\s+\d+", re.IGNORECASE),  # puertos
    re.compile(r"\bport\s+\d+", re.IGNORECASE),
]

DECISION_PATTERNS: list[re.Pattern] = [
    re.compile(r"(decidimos?|elegimos?|optamos? por|usaremos?|implementaremos?)", re.IGNORECASE),
    re.compile(r"(se decid[eió]|queda\s+definido|acordamos?|confirmamos?)", re.IGNORECASE),
    re.compile(r"(mejor opci[oó]n|la soluci[oó]n es|approach elegido)", re.IGNORECASE),
    re.compile(r"(migrar\s+a|reemplazar\s+por|cambiar\s+de\s+\w+\s+a)", re.IGNORECASE),
    re.compile(r"(usar\s+\w+\s+como\s+(fallback|alternativa|reemplazo))", re.IGNORECASE),
]

TASK_PATTERNS: list[re.Pattern] = [
    re.compile(r"(pendiente|TODO|por hacer|falta|queda\s+por|hay que)", re.IGNORECASE),
    re.compile(
        r"(instalar|configurar|actualizar|migrar|implementar|crear|agregar)\s+\w", re.IGNORECASE
    ),
    re.compile(r"(próximo paso|next step|siguiente tarea|action item)", re.IGNORECASE),
    re.compile(r"(\[\s*\]\s+\w)", re.IGNORECASE),  # checkboxes sin marcar
]

ERROR_PATTERNS: list[re.Pattern] = [
    re.compile(r"(error|exception|traceback|bug|fallo|crash|failed)", re.IGNORECASE),
    re.compile(r"(ImportError|TypeError|ValueError|AttributeError|KeyError)", re.IGNORECASE),
    re.compile(r"(no funciona|no se puede|imposible|problema con|issue con)", re.IGNORECASE),
    re.compile(r"(WARN|WARNING|ERROR|CRITICAL)\b"),
]


@dataclass
class CompressedContext:
    """Contexto comprimido estructurado."""

    original_chars: int
    compressed_chars: int
    key_facts: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def compression_ratio(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return self.compressed_chars / self.original_chars


def extract_sentence_context(text: str, match: re.Match, window: int = 80) -> str:
    """Extrae la oración o fragmento alrededor de un match."""
    start = max(0, match.start() - window // 2)
    end = min(len(text), match.end() + window // 2)
    snippet = text[start:end].strip()
    # Limpiar líneas vacías múltiples
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet[:150]  # max 150 chars por fragmento


def deduplicate(items: list[str], max_items: int = 8) -> list[str]:
    """Elimina duplicados aproximados y limita cantidad."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = re.sub(r"\s+", " ", item.lower().strip())
        if normalized not in seen and len(result) < max_items:
            seen.add(normalized)
            result.append(item.strip())
    return result


def extract_key_facts(text: str) -> list[str]:
    """Extrae hechos clave: versiones, URLs, vars de entorno, hosts."""
    facts: list[str] = []
    for pattern in FACT_PATTERNS:
        for match in pattern.finditer(text):
            snippet = extract_sentence_context(text, match, window=60)
            if snippet:
                facts.append(snippet)
    return deduplicate(facts)


def extract_decisions(text: str) -> list[str]:
    """Extrae decisiones tomadas en el contexto."""
    decisions: list[str] = []
    lines = text.split("\n")
    for line in lines:
        for pattern in DECISION_PATTERNS:
            if pattern.search(line):
                clean = line.strip()
                if 10 < len(clean) < 200:
                    decisions.append(clean)
                break
    return deduplicate(decisions)


def extract_pending_tasks(text: str) -> list[str]:
    """Extrae tareas pendientes."""
    tasks: list[str] = []
    lines = text.split("\n")
    for line in lines:
        for pattern in TASK_PATTERNS:
            if pattern.search(line):
                clean = line.strip()
                if 10 < len(clean) < 200:
                    tasks.append(clean)
                break
    return deduplicate(tasks)


def extract_errors(text: str) -> list[str]:
    """Extrae errores y problemas mencionados."""
    errors: list[str] = []
    lines = text.split("\n")
    for line in lines:
        for pattern in ERROR_PATTERNS:
            if pattern.search(line):
                clean = line.strip()
                if 10 < len(clean) < 200:
                    errors.append(clean)
                break
    return deduplicate(errors, max_items=6)


def compress(text: str, target_ratio: float = DEFAULT_TARGET_RATIO) -> CompressedContext:
    """Comprime el texto extrayendo información estructurada."""
    original_chars = len(text)

    key_facts = extract_key_facts(text)
    decisions = extract_decisions(text)
    pending_tasks = extract_pending_tasks(text)
    errors = extract_errors(text)

    # Calcular tamaño comprimido aproximado
    all_items = key_facts + decisions + pending_tasks + errors
    compressed_chars = sum(len(item) + 3 for item in all_items)  # +3 para "- "

    return CompressedContext(
        original_chars=original_chars,
        compressed_chars=compressed_chars,
        key_facts=key_facts,
        decisions=decisions,
        pending_tasks=pending_tasks,
        errors=errors,
    )


def format_report(ctx: CompressedContext) -> str:
    """Formatea el contexto comprimido."""
    lines: list[str] = [
        "=== CONTEXT COMPRESSOR ===",
        f"Original: {ctx.original_chars:,} chars | "
        f"Comprimido: {ctx.compressed_chars:,} chars | "
        f"Ratio: {ctx.compression_ratio * 100:.1f}%",
        "",
    ]

    if ctx.key_facts:
        lines.append("HECHOS CLAVE:")
        lines.extend(f"  - {fact}" for fact in ctx.key_facts)
        lines.append("")

    if ctx.decisions:
        lines.append("DECISIONES TOMADAS:")
        lines.extend(f"  - {d}" for d in ctx.decisions)
        lines.append("")

    if ctx.pending_tasks:
        lines.append("TAREAS PENDIENTES:")
        lines.extend(f"  - {t}" for t in ctx.pending_tasks)
        lines.append("")

    if ctx.errors:
        lines.append("ERRORES/PROBLEMAS:")
        lines.extend(f"  - {e}" for e in ctx.errors)
        lines.append("")

    if not any([ctx.key_facts, ctx.decisions, ctx.pending_tasks, ctx.errors]):
        lines.append("No se encontro informacion estructurada relevante en el texto.")

    return "\n".join(lines)


def main() -> None:
    """Entry point del script."""
    parser = argparse.ArgumentParser(
        description="Comprime contexto largo manteniendo informacion relevante."
    )
    parser.add_argument("--task", required=True, help="El texto a comprimir")
    parser.add_argument(
        "--target-ratio",
        type=float,
        default=DEFAULT_TARGET_RATIO,
        help="Ratio de compresion objetivo (default: 0.20)",
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    args = parser.parse_args()

    ctx = compress(args.task, args.target_ratio)

    if args.json:
        output = {
            "original_chars": ctx.original_chars,
            "compressed_chars": ctx.compressed_chars,
            "compression_ratio": round(ctx.compression_ratio, 4),
            "key_facts": ctx.key_facts,
            "decisions": ctx.decisions,
            "pending_tasks": ctx.pending_tasks,
            "errors": ctx.errors,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_report(ctx))


if __name__ == "__main__":
    main()
