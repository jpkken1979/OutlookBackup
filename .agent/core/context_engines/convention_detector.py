"""Conventions auto-detector for the Antigravity ecosystem.

Detects framework, test framework, naming conventions, and project-specific
rules by scanning common manifest files (package.json, pyproject.toml, Cargo.toml,
tsconfig.json, etc.) and writing the result to
`~/.antigravity/context/conventions.json`.

This cache is consumed by Context Engines to enrich the prompt without
requiring the agent to scan the whole repo on every session.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Cache de conventions por repo_root ───────────────────────────────────────
# Estructura: {repo_root_str: (timestamp_monotonic, result_dict)}
# TTL de 30 minutos para evitar re-escaneos en sesiones largas.

_CONVENTIONS_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS: float = 30 * 60  # 30 minutos


def clear_conventions_cache() -> None:
    """Limpia el cache de convenciones (útil para tests y recargas forzadas).

    Returns:
        None
    """
    _CONVENTIONS_CACHE.clear()


# ── Output path ──────────────────────────────────────────────────────────────

DEFAULT_OUTPUT: Path = Path.home() / ".antigravity" / "context" / "conventions.json"

# ── Marker patterns for auto-detection ─────────────────────────────────────

_TEST_DIR_PATTERNS = [
    ("tests/", "pytest"),
    ("test/", "pytest"),
    ("__tests__/", "jest"),
    ("src/__tests__/", "jest"),
    ("spec/", "jasmine"),
    ("Specs/", "xctest"),
    ("Test/", "xctest"),
]

_FRAMEWORK_PATTERNS: list[tuple[str, list[str], str]] = [
    ("pyproject.toml", ["fastapi"], "fastapi"),
    ("pyproject.toml", ["fastapi"], "fastapi"),
    ("package.json", ["react", "react-dom"], "react"),
    ("package.json", ["next"], "next"),
    ("package.json", ["vue"], "vue"),
    ("package.json", ["angular"], "angular"),
    ("Cargo.toml", ["tauri"], "tauri"),
    ("Cargo.toml", ["axum"], "axum"),
    ("go.mod", [], "go"),
    ("Gemfile", [], "rails"),
]

_NAMING_PATTERNS: list[tuple[str, str]] = [
    ("pyproject.toml", "snake_case"),
    ("*.py", "snake_case"),
    ("*.ts", "camelCase"),
    ("*.tsx", "camelCase"),
    ("*.js", "camelCase"),
    ("*.rs", "snake_case"),
    ("*.go", "snake_case"),
]

_LANGUAGE_FILES: list[tuple[str, list[str]]] = [
    ("pyproject.toml", ["python"]),
    ("Cargo.toml", ["rust"]),
    ("go.mod", ["go"]),
    ("package.json", ["typescript", "javascript"]),
    ("package-lock.json", ["javascript"]),
    ("pom.xml", ["java"]),
    ("build.gradle", ["kotlin", "groovy"]),
]

# ── Hard-coded conventions known for this ecosystem ─────────────────────────

OPENANTIGRAVITY_CONVENTIONS: list[str] = [
    "tests van en tests/ no __tests__",
    "type hints obligatorios en todas las funciones Python",
    "commits en español, formato convencional (feat, fix, chore...)",
    "variables y funciones en inglés, respuestas en español",
    "MCP-first: buscar capacidades via MCP antes de lectura directa",
    "Session End hook genera auto_discovery_*.md en .claude/memory/",
    "Brain Network para conocimiento estructurado con cross-refs",
    "4 capas: Directiva, Contexto, Ejecución, Observabilidad",
]

# ── Core detector ────────────────────────────────────────────────────────────


def _detect_languages(repo_root: Path) -> list[str]:
    """Detecta los lenguajes del proyecto por presencia de manifests.

    Args:
        repo_root: Ruta a la raíz del proyecto.

    Returns:
        Lista de lenguajes detectados, sin duplicados y en orden de aparición.
    """
    languages: list[str] = []
    for manifest, langs in _LANGUAGE_FILES:
        if (repo_root / manifest).is_file():
            for lang in langs:
                if lang not in languages:
                    languages.append(lang)
    return languages


def _detect_framework(repo_root: Path) -> list[str]:
    """Detecta los frameworks del proyecto leyendo los manifests.

    Args:
        repo_root: Ruta a la raíz del proyecto.

    Returns:
        Lista de frameworks detectados, sin duplicados y en orden de aparición.
    """
    framework: list[str] = []
    for manifest, keywords, fw in _FRAMEWORK_PATTERNS:
        manifest_path = repo_root / manifest
        if not manifest_path.is_file():
            continue
        try:
            content = manifest_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(kw in content for kw in keywords) and fw not in framework:
            framework.append(fw)
    return framework


def _detect_test_framework(repo_root: Path) -> str:
    """Detecta el test framework del proyecto por directorios y pyproject.

    Args:
        repo_root: Ruta a la raíz del proyecto.

    Returns:
        Nombre del test framework detectado, o ``"unknown"``.
    """
    test_framework = "unknown"
    for marker, tf in _TEST_DIR_PATTERNS:
        if (repo_root / marker).exists():
            for candidate in ["tests", "test", "__tests__", "src/__tests__"]:
                if (repo_root / candidate).is_dir():
                    test_framework = tf
                    break
        if test_framework != "unknown":
            break

    # Pytest override (this repo uses pytest explicitly)
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            if "pytest" in pyproject.read_text(encoding="utf-8", errors="ignore"):
                test_framework = "pytest"
        except OSError:
            pass
    return test_framework


def _detect_naming_convention(repo_root: Path) -> str:
    """Detecta la convención de nombres según los manifests presentes.

    Args:
        repo_root: Ruta a la raíz del proyecto.

    Returns:
        ``"snake_case"``, ``"camelCase"`` o ``"unknown"``.
    """
    if (repo_root / "pyproject.toml").is_file() or (repo_root / "setup.py").is_file():
        return "snake_case"
    if (repo_root / "package.json").is_file():
        return "camelCase"
    if (repo_root / "Cargo.toml").is_file():
        return "snake_case"
    return "unknown"


def _detect_repo_conventions(repo_root: Path) -> list[str]:
    """Detecta convenciones específicas del repo (reglas, configs, hooks).

    Args:
        repo_root: Ruta a la raíz del proyecto.

    Returns:
        Lista de etiquetas de convenciones detectadas, sin duplicados.
    """
    convention_markers: list[tuple[str, str]] = [
        (".claude/rules/auto-save-triggers.md", "auto-save triggers activos"),
        ("docs/rules-reference/context-engines.md", "context engines configurados"),
        (".agent/brain/", "brain network activo"),
        ("makefile", "soporta make para tasks"),
        (".pre-commit-config.yaml", "pre-commit hooks activos"),
        (".claude/hooks/", "hooks de sesion personalizados"),
        (".mcp.json", "MCP servers configurados"),
    ]
    detected: list[str] = []
    for marker, label in convention_markers:
        if (repo_root / marker).exists() and label not in detected:
            detected.append(label)
    return detected


def detect_conventions(repo_root: Path | str | None = None) -> dict:
    """Scan the repo and return a conventions dict, con cache TTL de 30 min.

    El resultado se cachea por repo_root normalizado. Llamadas subsecuentes
    dentro del TTL devuelven la entrada cacheada sin re-escanear el disco.
    Usar clear_conventions_cache() para invalidar manualmente (ej. en tests).

    Args:
        repo_root: Path to the project root. Defaults to CWD.

    Returns:
        Dict with project metadata, framework, test_framework, naming_convention,
        and a list of detected conventions.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    else:
        repo_root = Path(repo_root)

    cache_key = str(repo_root)
    now = time.monotonic()

    # Retornar entrada cacheada si está fresca
    if cache_key in _CONVENTIONS_CACHE:
        ts, cached_result = _CONVENTIONS_CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            logger.debug("detect_conventions: cache hit para %s", cache_key)
            return cached_result

    languages = _detect_languages(repo_root)
    framework = _detect_framework(repo_root)
    test_framework = _detect_test_framework(repo_root)
    naming_convention = _detect_naming_convention(repo_root)

    conventions: list[str] = list(OPENANTIGRAVITY_CONVENTIONS)
    for label in _detect_repo_conventions(repo_root):
        if label not in conventions:
            conventions.append(label)

    framework_str = "+".join(framework) if framework else "unknown"
    languages_str = ",".join(languages) if languages else "unknown"

    result = {
        "project": repo_root.name,
        "languages": languages_str,
        "framework": framework_str,
        "test_framework": test_framework,
        "naming_convention": naming_convention,
        "conventions": conventions,
        "scan_root": str(repo_root),
    }

    _CONVENTIONS_CACHE[cache_key] = (now, result)
    return result


def save_conventions(
    data: dict,
    output_path: Path | None = None,
) -> Path:
    """Persist conventions to the JSON cache file.

    Creates parent directories if they don't exist.
    """
    if output_path is None:
        output_path = DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Conventions saved to %s", output_path)
    return output_path


def load_conventions(
    output_path: Path | None = None,
) -> dict | None:
    """Load cached conventions, or None if cache is missing or invalid."""
    if output_path is None:
        output_path = DEFAULT_OUTPUT
    if not output_path.is_file():
        return None
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load conventions from %s: %s", output_path, exc)
        return None


def detect_and_save(repo_root: Path | str | None = None) -> dict:
    """Convenience: detect + save in one call."""
    data = detect_conventions(repo_root)
    save_conventions(data)
    return data


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-detect codebase conventions and save to JSON cache.",
    )
    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        default=None,
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path (default: ~/.antigravity/context/conventions.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout instead of saving",
    )
    args = parser.parse_args()

    data = detect_conventions(args.repo)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        path = save_conventions(data, Path(args.output) if args.output else None)
        print(f"Conventions saved to: {path}")
        print(f"  project: {data['project']}")
        print(f"  framework: {data['framework']}")
        print(f"  test_framework: {data['test_framework']}")
        print(f"  naming_convention: {data['naming_convention']}")
        print(f"  conventions ({len(data['conventions'])}):")
        for c in data["conventions"]:
            print(f"    - {c}")
