"""code-reviewer agent — revisa código buscando errores, code smells y mejoras."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (  # noqa: E402
    detect_languages,
    llm_summarize,
    main_wrapper,
    run_command,
)


def _run_ruff(root: Path) -> dict:
    """Run ruff check on Python files."""
    result = run_command(["ruff", "check", "."], cwd=root, timeout=120)
    if result["code"] == -2:
        return {"tool": "ruff", "skipped": True, "reason": "ruff not installed"}
    lines = result["stdout"].strip().splitlines()
    error_count = 0
    warning_count = 0
    issues: list[str] = []
    for line in lines:
        if line.strip():
            issues.append(line)
            upper = line.upper()
            if "E" in upper.split(":")[0] if ":" in upper else False:
                error_count += 1
            else:
                warning_count += 1
    return {
        "tool": "ruff",
        "skipped": False,
        "ok": result["ok"],
        "issue_count": len(issues),
        "issues": issues[:100],
        "errors": error_count,
        "warnings": warning_count,
        "raw_stderr": result["stderr"][:2000] if result["stderr"] else "",
    }


def _run_tsc(root: Path) -> dict:
    """Run TypeScript compiler in noEmit mode."""
    # Find tsconfig files
    tsconfigs = list(root.rglob("tsconfig*.json"))
    if not tsconfigs:
        return {"tool": "tsc", "skipped": True, "reason": "no tsconfig found"}

    result = run_command(["npx", "tsc", "--noEmit"], cwd=root, timeout=180)
    if result["code"] == -2:
        return {"tool": "tsc", "skipped": True, "reason": "npx/tsc not available"}

    lines = result["stdout"].strip().splitlines()
    error_lines = [l for l in lines if "error TS" in l]
    return {
        "tool": "tsc",
        "skipped": False,
        "ok": result["ok"],
        "issue_count": len(error_lines),
        "issues": error_lines[:100],
        "raw_stderr": result["stderr"][:2000] if result["stderr"] else "",
    }


def _run_cargo_check(root: Path) -> dict:
    """Run cargo check on Rust projects."""
    cargo_toml = root / "Cargo.toml"
    if not cargo_toml.exists():
        # Check subdirectories
        cargo_files = list(root.rglob("Cargo.toml"))
        if not cargo_files:
            return {"tool": "cargo", "skipped": True, "reason": "no Cargo.toml found"}
        check_dir = cargo_files[0].parent
    else:
        check_dir = root

    result = run_command(["cargo", "check", "--message-format=short"], cwd=check_dir, timeout=300)
    if result["code"] == -2:
        return {"tool": "cargo", "skipped": True, "reason": "cargo not installed"}

    combined = result["stdout"] + "\n" + result["stderr"]
    error_lines = [l for l in combined.splitlines() if "error" in l.lower() and "::" not in l]
    warning_lines = [
        l for l in combined.splitlines() if "warning" in l.lower() and "generated" not in l.lower()
    ]
    return {
        "tool": "cargo",
        "skipped": False,
        "ok": result["ok"],
        "issue_count": len(error_lines) + len(warning_lines),
        "errors": len(error_lines),
        "warnings": len(warning_lines),
        "issues": (error_lines + warning_lines)[:100],
    }


def execute(task: str, root: Path) -> dict:
    """Run code review checks across detected languages."""
    langs = detect_languages(root)
    results: list[dict] = []

    if "python" in langs:
        results.append(_run_ruff(root))

    if "typescript" in langs or "javascript" in langs:
        results.append(_run_tsc(root))

    if "rust" in langs:
        results.append(_run_cargo_check(root))

    if not results:
        results.append(
            {"tool": "none", "skipped": True, "reason": "no supported languages detected"}
        )

    # Count totals
    total_issues = sum(r.get("issue_count", 0) for r in results if not r.get("skipped"))
    tools_run = [r["tool"] for r in results if not r.get("skipped")]
    tools_skipped = [r["tool"] for r in results if r.get("skipped")]

    raw = {
        "languages": langs,
        "tools_run": tools_run,
        "tools_skipped": tools_skipped,
        "total_issues": total_issues,
        "results": results,
    }

    # Build summary text for LLM
    summary_parts = [f"Lenguajes: {', '.join(langs)}", f"Issues totales: {total_issues}"]
    for r in results:
        if r.get("skipped"):
            summary_parts.append(f"  {r['tool']}: omitido ({r.get('reason', 'N/A')})")
        else:
            summary_parts.append(f"  {r['tool']}: {r.get('issue_count', 0)} issues")
            for issue in r.get("issues", [])[:10]:
                summary_parts.append(f"    - {issue}")

    raw_text = "\n".join(summary_parts)

    llm_result = llm_summarize(
        raw_text,
        "Eres un code reviewer experto. Analiza estos resultados de linting/compilación. "
        "Prioriza los issues más importantes, clasifícalos por severidad y sugiere fixes concretos. "
        "Responde en español.",
    )

    if llm_result:
        return {"status": "success", "summary": llm_result, "raw": raw, "llm_used": "auto"}

    # Fallback: formatted text
    fallback_lines = [f"Code Review — {total_issues} issues encontrados"]
    fallback_lines.append(f"Lenguajes detectados: {', '.join(langs)}")
    for r in results:
        if r.get("skipped"):
            fallback_lines.append(f"\n[{r['tool']}] Omitido: {r.get('reason')}")
        else:
            fallback_lines.append(f"\n[{r['tool']}] {r.get('issue_count', 0)} issues:")
            for issue in r.get("issues", [])[:20]:
                fallback_lines.append(f"  - {issue}")

    return {
        "status": "success",
        "summary": "\n".join(fallback_lines),
        "raw": raw,
        "llm_used": "none",
    }


if __name__ == "__main__":
    main_wrapper("code-reviewer", execute)
