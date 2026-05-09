"""test-runner agent — ejecuta tests del proyecto y analiza resultados."""

from __future__ import annotations

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


def _detect_test_framework(root: Path, langs: list[str]) -> list[dict]:
    """Detect available test frameworks based on project files."""
    frameworks: list[dict] = []

    # Python: pytest
    if "python" in langs:
        has_pytest_config = (
            (root / "pyproject.toml").exists()
            or (root / "pytest.ini").exists()
            or (root / "setup.cfg").exists()
        )
        test_dirs = list(root.rglob("test_*.py"))[:1] or list(root.rglob("*_test.py"))[:1]
        if has_pytest_config or test_dirs:
            frameworks.append({"name": "pytest", "lang": "python"})

    # TypeScript/JS: vitest or jest
    if "typescript" in langs or "javascript" in langs:
        pkg_json = root / "package.json"
        if pkg_json.exists():
            try:
                import json

                pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
                scripts = pkg.get("scripts", {})
                deps = {**pkg.get("devDependencies", {}), **pkg.get("dependencies", {})}
                if "vitest" in deps or "vitest" in scripts.get("test", ""):
                    frameworks.append({"name": "vitest", "lang": "typescript", "cwd": str(root)})
                elif "jest" in deps or "jest" in scripts.get("test", ""):
                    frameworks.append({"name": "jest", "lang": "typescript", "cwd": str(root)})
            except Exception:
                pass

        # Check nexus-app subdirectory
        nexus_pkg = root / "nexus-app" / "package.json"
        if nexus_pkg.exists():
            try:
                import json

                pkg = json.loads(nexus_pkg.read_text(encoding="utf-8"))
                deps = {**pkg.get("devDependencies", {}), **pkg.get("dependencies", {})}
                if "vitest" in deps:
                    frameworks.append(
                        {"name": "vitest", "lang": "typescript", "cwd": str(root / "nexus-app")}
                    )
                elif "jest" in deps:
                    frameworks.append(
                        {"name": "jest", "lang": "typescript", "cwd": str(root / "nexus-app")}
                    )
            except Exception:
                pass

    # Rust: cargo test
    if "rust" in langs:
        cargo_toml = root / "Cargo.toml"
        if not cargo_toml.exists():
            cargo_files = list(root.rglob("Cargo.toml"))
            if cargo_files:
                frameworks.append(
                    {"name": "cargo-test", "lang": "rust", "cwd": str(cargo_files[0].parent)}
                )
        else:
            frameworks.append({"name": "cargo-test", "lang": "rust", "cwd": str(root)})

    return frameworks


def _run_pytest(root: Path) -> dict:
    """Run pytest and parse results."""
    result = run_command(
        [sys.executable, "-m", "pytest", "--tb=short", "-q", "--no-header"],
        cwd=root,
        timeout=300,
    )
    if result["code"] == -2:
        return {"framework": "pytest", "skipped": True, "reason": "pytest not installed"}

    output = result["stdout"] + "\n" + result["stderr"]
    passed = failed = errors = skipped = 0

    # Parse summary line: "5 passed, 2 failed, 1 error, 3 skipped"
    summary_match = re.search(
        r"(?:(\d+)\s+passed)?[,\s]*(?:(\d+)\s+failed)?[,\s]*(?:(\d+)\s+error)?[,\s]*(?:(\d+)\s+skipped)?",
        output,
    )
    if summary_match:
        passed = int(summary_match.group(1) or 0)
        failed = int(summary_match.group(2) or 0)
        errors = int(summary_match.group(3) or 0)
        skipped = int(summary_match.group(4) or 0)

    # Also try "X passed" etc individually
    for m in re.finditer(r"(\d+)\s+passed", output):
        passed = max(passed, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+failed", output):
        failed = max(failed, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+error", output):
        errors = max(errors, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+skipped", output):
        skipped = max(skipped, int(m.group(1)))

    # Capture failure details
    failure_details: list[str] = []
    in_failure = False
    for line in output.splitlines():
        if "FAILED" in line or "ERROR" in line:
            in_failure = True
            failure_details.append(line.strip())
        elif in_failure:
            if line.strip() and not line.startswith("="):
                failure_details.append(line.strip())
            else:
                in_failure = False

    return {
        "framework": "pytest",
        "skipped": False,
        "ok": result["ok"],
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped_tests": skipped,
        "total": passed + failed + errors + skipped,
        "failure_details": failure_details[:50],
        "raw_output": output[:5000],
    }


def _run_vitest(cwd: str | Path) -> dict:
    """Run vitest and parse results."""
    result = run_command(
        ["npx", "vitest", "run", "--reporter=verbose"],
        cwd=cwd,
        timeout=300,
    )
    if result["code"] == -2:
        return {"framework": "vitest", "skipped": True, "reason": "npx/vitest not available"}

    output = result["stdout"] + "\n" + result["stderr"]
    passed = failed = skipped = 0

    # Parse "Tests  X passed | Y failed | Z skipped"
    for m in re.finditer(r"(\d+)\s+passed", output):
        passed = max(passed, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+failed", output):
        failed = max(failed, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+skipped", output):
        skipped = max(skipped, int(m.group(1)))

    # Capture failure details
    failure_details: list[str] = []
    for line in output.splitlines():
        if "FAIL" in line or "AssertionError" in line or "Error:" in line:
            failure_details.append(line.strip())

    return {
        "framework": "vitest",
        "skipped": False,
        "ok": result["ok"],
        "passed": passed,
        "failed": failed,
        "errors": 0,
        "skipped_tests": skipped,
        "total": passed + failed + skipped,
        "failure_details": failure_details[:50],
        "raw_output": output[:5000],
        "cwd": str(cwd),
    }


def _run_jest(cwd: str | Path) -> dict:
    """Run jest and parse results."""
    result = run_command(
        ["npx", "jest", "--no-coverage", "--verbose"],
        cwd=cwd,
        timeout=300,
    )
    if result["code"] == -2:
        return {"framework": "jest", "skipped": True, "reason": "npx/jest not available"}

    output = result["stdout"] + "\n" + result["stderr"]
    passed = failed = skipped = 0

    # Parse "Tests: X passed, Y failed, Z skipped"
    for m in re.finditer(r"(\d+)\s+passed", output):
        passed = max(passed, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+failed", output):
        failed = max(failed, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+skipped", output):
        skipped = max(skipped, int(m.group(1)))

    failure_details: list[str] = []
    for line in output.splitlines():
        if "FAIL" in line or "●" in line:
            failure_details.append(line.strip())

    return {
        "framework": "jest",
        "skipped": False,
        "ok": result["ok"],
        "passed": passed,
        "failed": failed,
        "errors": 0,
        "skipped_tests": skipped,
        "total": passed + failed + skipped,
        "failure_details": failure_details[:50],
        "raw_output": output[:5000],
        "cwd": str(cwd),
    }


def _run_cargo_test(cwd: str | Path) -> dict:
    """Run cargo test and parse results."""
    result = run_command(
        ["cargo", "test", "--", "--format=terse"],
        cwd=cwd,
        timeout=300,
    )
    if result["code"] == -2:
        return {"framework": "cargo-test", "skipped": True, "reason": "cargo not installed"}

    output = result["stdout"] + "\n" + result["stderr"]
    passed = failed = ignored = 0

    # Parse "test result: ok. X passed; Y failed; Z ignored"
    m = re.search(r"(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored", output)
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2))
        ignored = int(m.group(3))

    failure_details: list[str] = []
    in_failure = False
    for line in output.splitlines():
        if "FAILED" in line or "panicked" in line:
            in_failure = True
            failure_details.append(line.strip())
        elif in_failure and line.strip():
            failure_details.append(line.strip())
            if line.strip().startswith("note:") or not line.strip():
                in_failure = False

    return {
        "framework": "cargo-test",
        "skipped": False,
        "ok": result["ok"],
        "passed": passed,
        "failed": failed,
        "errors": 0,
        "skipped_tests": ignored,
        "total": passed + failed + ignored,
        "failure_details": failure_details[:50],
        "raw_output": output[:5000],
        "cwd": str(cwd),
    }


def execute(task: str, root: Path) -> dict:
    """Detect and run tests across all frameworks."""
    langs = detect_languages(root)
    frameworks = _detect_test_framework(root, langs)

    if not frameworks:
        return {
            "status": "warning",
            "summary": "No se detectaron frameworks de testing en el proyecto.",
            "raw": {"languages": langs, "frameworks": []},
            "llm_used": "none",
        }

    results: list[dict] = []
    for fw in frameworks:
        name = fw["name"]
        cwd = fw.get("cwd", str(root))
        if name == "pytest":
            results.append(_run_pytest(root))
        elif name == "vitest":
            results.append(_run_vitest(cwd))
        elif name == "jest":
            results.append(_run_jest(cwd))
        elif name == "cargo-test":
            results.append(_run_cargo_test(cwd))

    # Aggregate
    total_passed = sum(r.get("passed", 0) for r in results if not r.get("skipped"))
    total_failed = sum(r.get("failed", 0) for r in results if not r.get("skipped"))
    total_errors = sum(r.get("errors", 0) for r in results if not r.get("skipped"))
    total_skipped = sum(r.get("skipped_tests", 0) for r in results if not r.get("skipped"))
    all_failures: list[str] = []
    for r in results:
        if not r.get("skipped"):
            all_failures.extend(r.get("failure_details", []))

    raw = {
        "languages": langs,
        "frameworks_detected": [fw["name"] for fw in frameworks],
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_errors": total_errors,
        "total_skipped": total_skipped,
        "results": results,
    }

    # Build summary for LLM
    summary_parts = [
        f"Test Results — {total_passed} passed, {total_failed} failed, "
        f"{total_errors} errors, {total_skipped} skipped",
        f"Frameworks: {', '.join(fw['name'] for fw in frameworks)}",
        "",
    ]
    for r in results:
        if r.get("skipped"):
            summary_parts.append(f"[{r['framework']}] Omitido: {r.get('reason')}")
            continue
        summary_parts.append(
            f"[{r['framework']}] {r.get('passed', 0)} passed, "
            f"{r.get('failed', 0)} failed, {r.get('errors', 0)} errors"
        )
        for detail in r.get("failure_details", [])[:10]:
            summary_parts.append(f"  FAIL: {detail}")

    raw_text = "\n".join(summary_parts)

    if total_failed > 0 or total_errors > 0:
        llm_result = llm_summarize(
            raw_text,
            "Eres un experto en testing de software. Analiza estos resultados de tests. "
            "Para cada fallo, identifica la causa probable y sugiere un fix concreto. "
            "Prioriza los fallos por impacto. Responde en español.",
        )
    else:
        llm_result = llm_summarize(
            raw_text,
            "Eres un experto en testing. Resume brevemente estos resultados exitosos "
            "y sugiere áreas que podrían necesitar más cobertura. Responde en español.",
        )

    if llm_result:
        status = "success" if total_failed == 0 and total_errors == 0 else "warning"
        return {"status": status, "summary": llm_result, "raw": raw, "llm_used": "auto"}

    # Fallback
    status = "success" if total_failed == 0 and total_errors == 0 else "warning"
    fallback_lines = [
        f"Test Runner — {total_passed + total_failed + total_errors + total_skipped} tests ejecutados",
        f"  Passed: {total_passed}",
        f"  Failed: {total_failed}",
        f"  Errors: {total_errors}",
        f"  Skipped: {total_skipped}",
    ]
    if all_failures:
        fallback_lines.append("\nDetalles de fallos:")
        for f in all_failures[:20]:
            fallback_lines.append(f"  - {f}")

    return {"status": status, "summary": "\n".join(fallback_lines), "raw": raw, "llm_used": "none"}


if __name__ == "__main__":
    main_wrapper("test-runner", execute)
