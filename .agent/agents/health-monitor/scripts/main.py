"""health-monitor — Dashboard de salud general del proyecto."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (  # noqa: E402
    detect_languages,
    llm_summarize,
    main_wrapper,
    run_command,
)

SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "_archive",
    ".agent - copia",
}

# Patterns that indicate hardcoded secrets
SECRET_PATTERNS = [
    (
        r"""(?:api[_-]?key|apikey|secret|token|password|passwd|pwd)\s*[=:]\s*['"][A-Za-z0-9+/=_\-]{16,}['"]""",
        "hardcoded_secret",
    ),
    (r"""(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36})""", "api_key_pattern"),
    (r"""PRIVATE[_ ]KEY.*?-----BEGIN""", "private_key"),
]


def _check_security(root: Path, langs: list[str]) -> dict:
    """Quick security scan: grep for hardcoded secrets."""
    findings: list[dict] = []
    extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".toml", ".yaml", ".yml", ".json"}
    # Exclude known safe patterns
    safe_files = {".env.example", "package-lock.json", "Cargo.lock"}

    file_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn in safe_files:
                continue
            ext = Path(fn).suffix.lower()
            if ext not in extensions:
                continue
            full = Path(dirpath) / fn
            try:
                content = full.read_text(encoding="utf-8", errors="ignore")[:20000]
                for pattern, issue_type in SECRET_PATTERNS:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        # Skip if it looks like an env var reference
                        ctx = content[max(0, match.start() - 20) : match.end() + 20]
                        if "os.environ" in ctx or "process.env" in ctx or "env::" in ctx:
                            continue
                        findings.append(
                            {
                                "file": str(full.relative_to(root)),
                                "issue": issue_type,
                                "severity": "critical",
                            }
                        )
            except OSError:
                pass
            file_count += 1
            if file_count > 500:
                break
        if file_count > 500:
            break

    # Deduplicate by file
    seen = set()
    unique: list[dict] = []
    for f in findings:
        if f["file"] not in seen:
            seen.add(f["file"])
            unique.append(f)

    critical_count = len(unique)
    return {
        "check": "security",
        "passed": critical_count == 0,
        "critical_issues": critical_count,
        "findings": unique[:10],
        "score": 25 if critical_count == 0 else max(0, 25 - critical_count * 5),
    }


def _check_tests(root: Path, langs: list[str]) -> dict:
    """Check if tests pass."""
    test_result = {"check": "tests", "passed": False, "detail": "", "score": 0}

    if "python" in langs:
        result = run_command(
            [sys.executable, "-m", "pytest", "--co", "-q"],
            cwd=root,
            timeout=30,
        )
        if result["ok"]:
            # --co just collects tests; if it exits 0, tests are at least collectible
            test_count_match = re.search(r"(\d+) tests? collected", result["stdout"])
            count = int(test_count_match.group(1)) if test_count_match else 0
            test_result["detail"] = f"Python: {count} tests collected"
            # Actually run a quick test
            quick = run_command(
                [sys.executable, "-m", "pytest", "-x", "-q", "--timeout=30"],
                cwd=root,
                timeout=60,
            )
            test_result["passed"] = quick["ok"]
            test_result["detail"] += f" — {'PASS' if quick['ok'] else 'FAIL'}"
            test_result["score"] = 30 if quick["ok"] else 10
            return test_result

    if "typescript" in langs:
        # Check for test script in package.json
        pkg = root / "package.json"
        if pkg.exists():
            result = run_command(["npm", "test", "--", "--run"], cwd=root, timeout=60)
            test_result["passed"] = result["ok"]
            test_result["detail"] = f"TypeScript: {'PASS' if result['ok'] else 'FAIL'}"
            test_result["score"] = 30 if result["ok"] else 10
            return test_result

    test_result["detail"] = "No test framework detected"
    test_result["score"] = 0
    return test_result


def _check_dependencies(root: Path, langs: list[str]) -> dict:
    """Check for dependency vulnerabilities."""
    dep_result = {
        "check": "dependencies",
        "passed": True,
        "detail": "",
        "vulnerabilities": 0,
        "score": 20,
    }

    if "python" in langs:
        result = run_command(
            [sys.executable, "-m", "pip_audit", "--format=json", "--progress-spinner=off"],
            cwd=root,
            timeout=60,
        )
        if result["ok"]:
            try:
                import json

                vulns = json.loads(result["stdout"])
                vuln_count = len(vulns) if isinstance(vulns, list) else 0
                dep_result["vulnerabilities"] = vuln_count
                dep_result["passed"] = vuln_count == 0
                dep_result["detail"] = f"pip-audit: {vuln_count} vulnerabilities"
                dep_result["score"] = 20 if vuln_count == 0 else max(0, 20 - vuln_count * 3)
            except Exception:
                dep_result["detail"] = "pip-audit: parse error"
        elif "command not found" in result["stderr"]:
            dep_result["detail"] = "pip-audit not installed"
            dep_result["score"] = 15  # Partial credit

    if "typescript" in langs:
        result = run_command(["npm", "audit", "--json"], cwd=root, timeout=30)
        try:
            import json

            data = json.loads(result["stdout"])
            vuln_count = data.get("metadata", {}).get("vulnerabilities", {}).get("total", 0)
            if isinstance(vuln_count, int) and vuln_count > 0:
                dep_result["vulnerabilities"] += vuln_count
                dep_result["passed"] = False
                dep_result["detail"] += f" | npm audit: {vuln_count} vulnerabilities"
                dep_result["score"] = max(0, dep_result["score"] - vuln_count * 2)
        except Exception:
            pass

    if not dep_result["detail"]:
        dep_result["detail"] = "No dependency audit tool available"
        dep_result["score"] = 15

    return dep_result


def _check_linter(root: Path, langs: list[str]) -> dict:
    """Run linter and check for issues."""
    lint_result = {"check": "linter", "passed": False, "detail": "", "issue_count": 0, "score": 0}

    if "python" in langs:
        result = run_command(
            ["ruff", "check", "--statistics", "--quiet", str(root / ".agent")],
            cwd=root,
            timeout=30,
        )
        if result["ok"]:
            lint_result["passed"] = True
            lint_result["detail"] = "ruff: clean"
            lint_result["score"] = 15
        elif "command not found" not in result["stderr"]:
            # Count issues
            lines = [l for l in result["stdout"].split("\n") if l.strip()]
            lint_result["issue_count"] = len(lines)
            lint_result["detail"] = f"ruff: {len(lines)} issues"
            lint_result["score"] = max(0, 15 - len(lines))
        else:
            lint_result["detail"] = "ruff not installed"
            lint_result["score"] = 10

    elif "typescript" in langs:
        # Try tsc
        result = run_command(["npx", "tsc", "--noEmit"], cwd=root, timeout=60)
        if result["ok"]:
            lint_result["passed"] = True
            lint_result["detail"] = "tsc: clean"
            lint_result["score"] = 15
        else:
            errors = result["stdout"].count("error TS")
            lint_result["issue_count"] = errors
            lint_result["detail"] = f"tsc: {errors} errors"
            lint_result["score"] = max(0, 15 - errors)

    else:
        lint_result["detail"] = "No linter available"
        lint_result["score"] = 10

    return lint_result


def _check_docs(root: Path) -> dict:
    """Check if project has documentation."""
    doc_files = [
        "README.md",
        "CLAUDE.md",
        "docs/",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "ESTADO_PROYECTO.md",
    ]
    found: list[str] = []
    for df in doc_files:
        p = root / df
        if p.exists():
            found.append(df)

    has_docs = len(found) >= 2
    return {
        "check": "documentation",
        "passed": has_docs,
        "detail": f"Found: {', '.join(found)}" if found else "No documentation files",
        "score": min(10, len(found) * 3),
    }


def _format_dashboard(checks: list[dict], total_score: int) -> str:
    """Format as a text dashboard."""
    lines = [
        f"HEALTH SCORE: {total_score}/100",
        "",
        "Check | Status | Score | Detail",
        "------|--------|-------|-------",
    ]
    for c in checks:
        status = "PASS" if c["passed"] else "FAIL"
        lines.append(f"{c['check']} | {status} | {c['score']} | {c.get('detail', '')}")

    return "\n".join(lines)


def execute(task: str, root: Path) -> dict:
    """Execute health monitoring."""
    langs = detect_languages(root)

    # Run all checks inline
    security = _check_security(root, langs)
    tests = _check_tests(root, langs)
    deps = _check_dependencies(root, langs)
    linter = _check_linter(root, langs)
    docs = _check_docs(root)

    checks = [tests, security, deps, linter, docs]
    total_score = sum(c["score"] for c in checks)

    # Determine overall status
    if total_score >= 80:
        status = "success"
    elif total_score >= 50:
        status = "warning"
    else:
        status = "error"

    raw_data = {
        "languages": langs,
        "total_score": total_score,
        "max_score": 100,
        "checks": checks,
    }

    dashboard = _format_dashboard(checks, total_score)
    llm_result = llm_summarize(
        dashboard,
        "Eres un CTO haciendo revisión de salud de un proyecto de software. "
        "Genera un dashboard ejecutivo: score general, qué está bien, qué necesita atención, "
        "y top 3 acciones recomendadas. Responde en español, formato conciso tipo reporte.",
    )

    if llm_result:
        return {"status": status, "summary": llm_result, "raw": raw_data, "llm_used": "auto"}

    return {"status": status, "summary": dashboard, "raw": raw_data, "llm_used": "none"}


if __name__ == "__main__":
    main_wrapper("health-monitor", execute)
