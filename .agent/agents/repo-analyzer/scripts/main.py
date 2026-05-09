"""repo-analyzer — Analiza estructura, metricas y salud del repositorio."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (
    detect_languages,
    llm_summarize,
    main_wrapper,
)

AGENT_NAME = "repo-analyzer"

SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
}


def _iter_files(root: Path) -> list[Path]:
    """Walk tree collecting all files, skipping heavy dirs."""
    results: list[Path] = []
    try:
        for item in root.iterdir():
            if item.name in SKIP_DIRS or item.name.startswith("."):
                continue
            if item.is_dir():
                results.extend(_iter_files(item))
            elif item.is_file():
                results.append(item)
    except (PermissionError, OSError):
        pass
    return results


def _count_by_extension(files: list[Path]) -> dict[str, int]:
    """Count files by extension."""
    counts: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower() or "(no ext)"
        counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _count_lines(files: list[Path], extensions: set[str]) -> int:
    """Count total lines of code for given extensions."""
    total = 0
    for f in files:
        if f.suffix.lower() in extensions:
            try:
                total += len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            except (OSError, PermissionError):
                pass
    return total


def _detect_frameworks(root: Path) -> list[str]:
    """Detect frameworks from config files."""
    frameworks: list[str] = []

    # package.json
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            fw_map = {
                "react": "React",
                "vue": "Vue",
                "angular": "Angular",
                "next": "Next.js",
                "nuxt": "Nuxt",
                "svelte": "Svelte",
                "express": "Express",
                "fastify": "Fastify",
                "grammy": "grammy",
                "vite": "Vite",
                "vitest": "Vitest",
                "jest": "Jest",
                "tailwindcss": "Tailwind CSS",
                "typescript": "TypeScript",
                "@tauri-apps/api": "Tauri",
            }
            for key, name in fw_map.items():
                if key in deps:
                    frameworks.append(name)
        except (json.JSONDecodeError, OSError):
            pass

    # Also check nested package.json files (monorepo)
    for sub_pkg in root.rglob("package.json"):
        if "node_modules" in str(sub_pkg) or sub_pkg == pkg:
            continue
        try:
            data = json.loads(sub_pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "@tauri-apps/api" in deps and "Tauri" not in frameworks:
                frameworks.append("Tauri")
        except (json.JSONDecodeError, OSError):
            pass

    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            py_fws = {
                "fastapi": "FastAPI",
                "django": "Django",
                "flask": "Flask",
                "pydantic": "Pydantic",
                "pytest": "pytest",
                "ruff": "Ruff",
                "aiohttp": "aiohttp",
                "crewai": "CrewAI",
            }
            for key, name in py_fws.items():
                if key in content.lower() and name not in frameworks:
                    frameworks.append(name)
        except OSError:
            pass

    # Cargo.toml
    cargo = root / "Cargo.toml"
    if not cargo.exists():
        # Check subdirs
        for c in root.rglob("Cargo.toml"):
            if "target" not in str(c):
                cargo = c
                break
    if cargo.exists():
        frameworks.append("Rust/Cargo")
        try:
            content = cargo.read_text(encoding="utf-8")
            if "tauri" in content.lower():
                if "Tauri" not in frameworks:
                    frameworks.append("Tauri")
        except OSError:
            pass

    return frameworks


def _check_presence(root: Path) -> dict[str, bool]:
    """Check for presence of important project elements."""
    checks: dict[str, bool] = {}

    # CI/CD
    checks["ci_github"] = (root / ".github" / "workflows").is_dir()
    checks["ci_gitlab"] = (root / ".gitlab-ci.yml").is_file()
    checks["ci_any"] = checks["ci_github"] or checks["ci_gitlab"]

    # Docs
    checks["readme"] = (root / "README.md").is_file() or (root / "readme.md").is_file()
    checks["claude_md"] = (root / "CLAUDE.md").is_file()
    checks["docs_dir"] = (root / "docs").is_dir()

    # Tests
    checks["tests_dir"] = (
        (root / "tests").is_dir() or (root / "test").is_dir() or (root / "__tests__").is_dir()
    )
    # Also check for test files in any subdir
    test_files = list(root.rglob("*.test.ts"))[:1] + list(root.rglob("test_*.py"))[:1]
    checks["test_files"] = bool(test_files) or checks["tests_dir"]

    # Linting
    checks["eslint"] = any(
        [
            (root / ".eslintrc.js").exists(),
            (root / ".eslintrc.json").exists(),
            (root / "eslint.config.js").exists(),
            (root / "eslint.config.mjs").exists(),
        ]
    )
    checks["ruff"] = (
        "ruff" in (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        if (root / "pyproject.toml").exists()
        else False
    )

    checks["linting_any"] = checks["eslint"] or checks["ruff"]

    # Docker
    checks["docker"] = (root / "Dockerfile").is_file() or (root / "docker-compose.yml").is_file()

    # Git
    checks["git"] = (root / ".git").is_dir()

    # Type checking
    checks["mypy"] = (
        "mypy" in (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        if (root / "pyproject.toml").exists()
        else False
    )
    checks["tsconfig"] = bool(list(root.rglob("tsconfig.json"))[:1])

    return checks


def _health_score(checks: dict[str, bool], has_code: bool) -> int:
    """Calculate health score 0-100."""
    if not has_code:
        return 0

    score = 30  # base: has code

    # Tests (+20)
    if checks.get("test_files"):
        score += 20

    # Documentation (+15)
    if checks.get("readme"):
        score += 10
    if checks.get("docs_dir") or checks.get("claude_md"):
        score += 5

    # CI/CD (+15)
    if checks.get("ci_any"):
        score += 15

    # Linting (+10)
    if checks.get("linting_any"):
        score += 10

    # Docker (+5)
    if checks.get("docker"):
        score += 5

    # Type checking (+5)
    if checks.get("mypy") or checks.get("tsconfig"):
        score += 5

    return min(score, 100)


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)
    all_files = _iter_files(root)
    ext_counts = _count_by_extension(all_files)

    code_exts = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".rb",
        ".cpp",
        ".c",
        ".h",
    }
    total_loc = _count_lines(all_files, code_exts)

    frameworks = _detect_frameworks(root)
    checks = _check_presence(root)
    score = _health_score(checks, bool(all_files))

    raw = {
        "total_files": len(all_files),
        "total_loc": total_loc,
        "files_by_extension": dict(list(ext_counts.items())[:25]),
        "languages": languages,
        "frameworks": frameworks,
        "checks": checks,
        "health_score": score,
    }

    # LLM summary
    data_for_llm = (
        f"Repository: {root.name}\n"
        f"Total files: {len(all_files)}, Lines of code: {total_loc}\n"
        f"Languages: {', '.join(languages)}\n"
        f"Frameworks: {', '.join(frameworks) if frameworks else 'none detected'}\n"
        f"Top extensions: {', '.join(f'{k}({v})' for k, v in list(ext_counts.items())[:10])}\n"
        f"Health score: {score}/100\n"
        f"Checks: {json.dumps(checks, indent=2)}\n"
    )

    prompt = (
        "Genera un reporte ejecutivo breve de la salud de este repositorio. "
        "Incluye: resumen de stack tecnologico, fortalezas, debilidades y "
        "recomendaciones concretas para mejorar. Responde en español."
    )

    summary = llm_summarize(data_for_llm, prompt)
    llm_used = "auto"

    if not summary:
        llm_used = "none"
        summary = (
            f"Repositorio: {root.name}\n"
            f"Archivos: {len(all_files)} | Lineas de codigo: {total_loc}\n"
            f"Lenguajes: {', '.join(languages)}\n"
            f"Frameworks: {', '.join(frameworks) if frameworks else 'ninguno detectado'}\n"
            f"Health score: {score}/100\n\n"
            f"Presencia:\n"
        )
        for k, v in checks.items():
            icon = "[OK]" if v else "[--]"
            summary += f"  {icon} {k}\n"

    status = "success" if score >= 50 else "warning"

    return {
        "status": status,
        "summary": summary,
        "raw": raw,
        "llm_used": llm_used,
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)
