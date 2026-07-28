"""Scout determinista de capacidades duplicadas (skills + agentes).

Mapea cada skill (`.agent/skills/`, `.agent/skills-custom/`) y agente
(`.agent/agents/`) por su `name` + `description` (frontmatter YAML) y agrupa
candidatos a near-duplicate por similitud Jaccard de tokens. No consume tokens
de modelo: es puro filesystem + set theory. Sirve para dimensionar el problema
antes de lanzar una verificacion profunda con subagentes.

Uso:
    python .agent/scripts/detect_duplicate_capabilities.py
    python .agent/scripts/detect_duplicate_capabilities.py --threshold 0.6 --top 100

Origen: auditoria de ecosistema 2026-06-04 (detecto 16 skills duplicados de 802).
"""

from __future__ import annotations

import argparse
import re
from itertools import combinations
from pathlib import Path

ROOT = Path(".agent")

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "to",
        "of",
        "in",
        "on",
        "with",
        "by",
        "using",
        "use",
        "when",
        "this",
        "that",
        "you",
        "your",
        "is",
        "are",
        "be",
        "as",
        "it",
        "at",
        "from",
        "into",
        "agent",
        "skill",
        "que",
        "para",
        "con",
        "los",
        "las",
        "una",
        "del",
        "el",
        "la",
        "en",
    }
)


def parse_frontmatter(text: str) -> tuple[str | None, str | None]:
    """Extrae ``name`` y ``description`` del frontmatter YAML (o de las primeras lineas).

    Args:
        text: Contenido del archivo SKILL.md o IDENTITY.md.

    Returns:
        Tupla ``(name, description)``; cada campo es ``None`` si no se encontro.
    """
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    block = m.group(1) if m else text[:800]
    nm = re.search(r"^name:\s*(.+)$", block, re.MULTILINE)
    dm = re.search(r"^description:\s*(.+)$", block, re.MULTILINE)
    name = nm.group(1).strip().strip("\"'") if nm else None
    desc = dm.group(1).strip().strip("\"'") if dm else None
    return name, desc


def _tokens(s: str) -> set[str]:
    """Tokeniza a un set de palabras significativas (sin stopwords, len > 2)."""
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Similitud Jaccard entre dos sets de tokens."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def collect_items(root: Path) -> list[tuple[str, str, str, str]]:
    """Recolecta (kind, dir, name, description) de skills, custom y agentes.

    Args:
        root: Directorio ``.agent``.

    Returns:
        Lista de tuplas con metadata de cada capacidad encontrada.
    """
    items: list[tuple[str, str, str, str]] = []
    for base, kind, fname in [
        ("skills", "skill", "SKILL.md"),
        ("skills-custom", "custom", "SKILL.md"),
        ("agents", "agent", "IDENTITY.md"),
    ]:
        d = root / base
        if not d.is_dir():
            continue
        for sub in sorted(d.iterdir()):
            if not sub.is_dir() or sub.name.startswith(("_", ".")):
                continue
            f = sub / fname
            if f.is_file():
                name, desc = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                items.append((kind, sub.name, name or sub.name, desc or ""))
    return items


def find_candidates(
    items: list[tuple[str, str, str, str]], threshold: float
) -> list[tuple[float, tuple, tuple]]:
    """Devuelve pares candidatos a duplicado con Jaccard >= threshold, ordenados desc."""
    feats = [_tokens(f"{dirn} {name} {desc}") for (_k, dirn, name, desc) in items]
    pairs: list[tuple[float, tuple, tuple]] = []
    for i, j in combinations(range(len(items)), 2):
        s = _jaccard(feats[i], feats[j])
        if s >= threshold:
            pairs.append((round(s, 3), items[i], items[j]))
    pairs.sort(key=lambda x: x[0], reverse=True)
    return pairs


def main() -> None:
    """Entry point CLI."""
    ap = argparse.ArgumentParser(description="Scout de capacidades duplicadas del ecosistema.")
    ap.add_argument("--threshold", type=float, default=0.55, help="Umbral Jaccard (default 0.55).")
    ap.add_argument("--top", type=int, default=70, help="Cuantos pares mostrar (default 70).")
    ap.add_argument("--root", type=Path, default=ROOT, help="Directorio .agent (default ./.agent).")
    args = ap.parse_args()

    items = collect_items(args.root)
    by_kind: dict[str, int] = {}
    for k, *_ in items:
        by_kind[k] = by_kind.get(k, 0) + 1

    pairs = find_candidates(items, args.threshold)
    print(f"TOTAL items con metadata: {len(items)}  ->  {by_kind}")
    print(f"Pares candidatos a duplicado (jaccard >= {args.threshold}): {len(pairs)}")
    print()
    for s, a, b in pairs[: args.top]:
        print(f"  {s}  [{a[0]}] {a[1]}  <->  [{b[0]}] {b[1]}")


if __name__ == "__main__":
    main()
