#!/usr/bin/env python3
"""Triage deterministico de proyectos bajo Jpkken1979/ para due diligence.

Clasifica cada carpeta como activo / candidato-duplicado / backup-o-vault /
sin-senal, sin usar IA: solo nombre, presencia de archivos senal y actividad
git. Uso:

    py .agent/scripts/due_diligence_triage.py --root "C:/Users/kenji/Github/Jpkken1979" --out docs/due-diligence/_triage-results.md
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

_NOISE_SUBSTRINGS = ("backup", "nousar", "obsidian", "_screenshots")


def _matches_noise_pattern(name: str) -> bool:
    """True si el nombre de carpeta indica backup/test/vault/asset, no proyecto."""
    lowered = name.lower()
    if lowered.endswith("test"):
        return True
    return any(substring in lowered for substring in _NOISE_SUBSTRINGS)


FAMILY_PATTERNS: dict[str, list[str]] = {
    "rireki": ["rireki"],
    "kintai": ["kintai"],
    "apartment": ["apartementos", "apartment"],
    "kobetsu": ["kobetsu"],
    "paginaweb": ["paginaweb"],
    "arari": ["arari-pro", "arari_pro"],
}


def detect_family(name: str) -> str | None:
    """Devuelve la familia de nombres duplicados a la que pertenece, o None."""
    lowered = name.lower()
    for family, keywords in FAMILY_PATTERNS.items():
        if any(keyword in lowered for keyword in keywords):
            return family
    return None


_SIGNAL_FILES = ("README.md", "CLAUDE.md", "package.json", "pyproject.toml")


def has_project_signals(repo_path: Path) -> bool:
    """True si la carpeta tiene al menos un archivo senal de proyecto real."""
    return any((repo_path / filename).exists() for filename in _SIGNAL_FILES)


def classify_repo(
    name: str,
    has_signals: bool,
    family: str | None,
    is_most_recent_in_family: bool,
) -> str:
    """Clasifica una carpeta: activo / candidato-duplicado / backup-o-vault / sin-senal."""
    if _matches_noise_pattern(name):
        return "backup-o-vault"
    if not has_signals:
        return "sin-senal"
    if family and not is_most_recent_in_family:
        return "candidato-duplicado"
    return "activo"


def get_last_commit_date(repo_path: Path) -> str | None:
    """Timestamp ISO 8601 del ultimo commit o None si no es repo git / sin commits.

    Se usa el timestamp completo (no solo la fecha) para poder desempatar
    entre miembros de una misma familia de nombres duplicados que comparten
    el mismo dia de actividad (ej. tras una sincronizacion masiva).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%cI"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    output = result.stdout.strip()
    return output or None


def scan_repos(root: Path) -> list[dict]:
    """Escanea las subcarpetas directas de root y las clasifica."""
    entries = []
    for child in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        name = child.name
        entries.append(
            {
                "name": name,
                "path": str(child),
                "family": detect_family(name),
                "has_signals": has_project_signals(child),
                "last_commit": get_last_commit_date(child),
            }
        )

    # Resolver "mas reciente" por familia (None se trata como el mas viejo).
    # Los miembros ruido (backup/test/vault) no compiten por este puesto: un
    # clon "test" mas nuevo no debe desplazar al miembro genuino de la familia.
    most_recent_by_family: dict[str, str] = {}
    for entry in entries:
        family = entry["family"]
        if not family or _matches_noise_pattern(entry["name"]):
            continue
        current_best = most_recent_by_family.get(family)
        candidate = entry["last_commit"] or ""
        if current_best is None or candidate > current_best:
            most_recent_by_family[family] = candidate

    results = []
    for entry in entries:
        family = entry["family"]
        is_most_recent = True
        if family:
            is_most_recent = (entry["last_commit"] or "") == most_recent_by_family.get(family, "")
        classification = classify_repo(
            entry["name"],
            has_signals=entry["has_signals"],
            family=family,
            is_most_recent_in_family=is_most_recent,
        )
        results.append({**entry, "classification": classification})
    return results


def render_table(results: list[dict]) -> str:
    """Tabla markdown ordenada por clasificacion y luego por actividad reciente."""
    order = {"activo": 0, "candidato-duplicado": 1, "sin-senal": 2, "backup-o-vault": 3}
    ordered = sorted(
        results,
        key=lambda r: (order.get(r["classification"], 9), r["last_commit"] or ""),
        reverse=False,
    )
    lines = [
        "| Carpeta | Clasificación | Familia | Última actividad | Señales |",
        "|---|---|---|---|---|",
    ]
    for r in ordered:
        display_date = r["last_commit"][:10] if r["last_commit"] else "sin git"
        lines.append(
            f"| {r['name']} | {r['classification']} | {r['family'] or '-'} "
            f"| {display_date} | {'sí' if r['has_signals'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Triage deterministico de repos para due diligence."
    )
    parser.add_argument("--root", required=True, help="Carpeta raiz a escanear (ej. Jpkken1979/)")
    parser.add_argument("--out", required=True, help="Archivo markdown de salida")
    args = parser.parse_args()

    root = Path(args.root)
    results = scan_repos(root)
    table = render_table(results)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Triage de due diligence — {root}\n\nTotal de carpetas escaneadas: {len(results)}\n\n"
    )
    out_path.write_text(header + table, encoding="utf-8")
    print(f"Triage escrito en {out_path} ({len(results)} carpetas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
