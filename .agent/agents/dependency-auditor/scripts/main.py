"""dependency-auditor agent — audita dependencias en busca de vulnerabilidades conocidas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (  # noqa: E402
    llm_summarize,
    main_wrapper,
    run_command,
)


def _run_pip_audit(root: Path) -> dict:
    """Run pip-audit for Python dependencies."""
    has_python = (root / "pyproject.toml").exists() or (root / "requirements.txt").exists()
    if not has_python:
        return {
            "tool": "pip-audit",
            "skipped": True,
            "reason": "no pyproject.toml or requirements.txt",
        }

    result = run_command(["pip-audit", "--format=json"], cwd=root, timeout=120)
    if result["code"] == -2:
        # Try python -m pip_audit
        result = run_command(
            [sys.executable, "-m", "pip_audit", "--format=json"], cwd=root, timeout=120
        )
        if result["code"] == -2:
            return {"tool": "pip-audit", "skipped": True, "reason": "pip-audit not installed"}

    vulns: list[dict] = []
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}

    try:
        data = json.loads(result["stdout"])
        if isinstance(data, dict):
            items = data.get("dependencies", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []

        for dep in items:
            dep_vulns = dep.get("vulns", [])
            for v in dep_vulns:
                vuln_entry = {
                    "package": dep.get("name", "unknown"),
                    "version": dep.get("version", "?"),
                    "vuln_id": v.get("id", "?"),
                    "description": v.get("description", "")[:200],
                    "fix_versions": v.get("fix_versions", []),
                }
                vulns.append(vuln_entry)
                # pip-audit doesn't always provide severity, count all as "unknown"
                severity_counts["unknown"] += 1
    except (json.JSONDecodeError, KeyError):
        # Non-JSON output — parse text
        for line in result["stdout"].splitlines():
            if line.strip() and not line.startswith("Name"):
                vulns.append({"raw_line": line.strip()})

    return {
        "tool": "pip-audit",
        "skipped": False,
        "ok": result["ok"],
        "vuln_count": len(vulns),
        "severity_counts": severity_counts,
        "vulnerabilities": vulns[:100],
        "raw_stderr": result["stderr"][:2000] if result["stderr"] else "",
    }


def _run_npm_audit(root: Path) -> dict:
    """Run npm audit for Node.js dependencies."""
    # Find package.json files (check root and common subdirs)
    pkg_json = root / "package.json"
    if not pkg_json.exists():
        subdirs = [root / d for d in ["nexus-app", "src", "frontend", "backend"]]
        found = False
        for d in subdirs:
            if (d / "package.json").exists():
                root = d
                found = True
                break
        if not found:
            return {"tool": "npm-audit", "skipped": True, "reason": "no package.json found"}

    result = run_command(["npm", "audit", "--json"], cwd=root, timeout=120)
    if result["code"] == -2:
        return {"tool": "npm-audit", "skipped": True, "reason": "npm not installed"}

    vulns: list[dict] = []
    severity_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0}
    total = 0

    try:
        data = json.loads(result["stdout"])
        # npm audit v7+ format
        if "vulnerabilities" in data:
            for name, info in data["vulnerabilities"].items():
                sev = info.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
                vulns.append(
                    {
                        "package": name,
                        "severity": sev,
                        "via": str(info.get("via", ""))[:200],
                        "fix_available": info.get("fixAvailable", False),
                        "range": info.get("range", ""),
                    }
                )
            meta = data.get("metadata", {}).get("vulnerabilities", {})
            total = sum(meta.values()) if meta else len(vulns)
        # npm audit v6 format
        elif "advisories" in data:
            for _id, adv in data["advisories"].items():
                sev = adv.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
                vulns.append(
                    {
                        "package": adv.get("module_name", "unknown"),
                        "severity": sev,
                        "title": adv.get("title", ""),
                        "url": adv.get("url", ""),
                    }
                )
            total = len(vulns)
    except (json.JSONDecodeError, KeyError):
        # Non-JSON — exit code 1 just means vulns found
        pass

    return {
        "tool": "npm-audit",
        "skipped": False,
        "ok": result["ok"],
        "vuln_count": total or len(vulns),
        "severity_counts": severity_counts,
        "vulnerabilities": vulns[:100],
        "raw_stderr": result["stderr"][:2000] if result["stderr"] else "",
    }


def _run_cargo_audit(root: Path) -> dict:
    """Run cargo audit for Rust dependencies."""
    cargo_toml = root / "Cargo.toml"
    if not cargo_toml.exists():
        cargo_files = list(root.rglob("Cargo.toml"))
        if not cargo_files:
            return {"tool": "cargo-audit", "skipped": True, "reason": "no Cargo.toml found"}
        root = cargo_files[0].parent

    result = run_command(["cargo", "audit", "--json"], cwd=root, timeout=120)
    if result["code"] == -2:
        return {"tool": "cargo-audit", "skipped": True, "reason": "cargo-audit not installed"}

    vulns: list[dict] = []
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    try:
        data = json.loads(result["stdout"])
        for vuln in data.get("vulnerabilities", {}).get("list", []):
            adv = vuln.get("advisory", {})
            vuln_entry = {
                "package": vuln.get("package", {}).get("name", "unknown"),
                "version": vuln.get("package", {}).get("version", "?"),
                "advisory_id": adv.get("id", "?"),
                "title": adv.get("title", ""),
                "url": adv.get("url", ""),
            }
            vulns.append(vuln_entry)
    except (json.JSONDecodeError, KeyError):
        # Count lines with "Crate:" as vulns
        for line in result["stdout"].splitlines():
            if "Crate:" in line or "RUSTSEC" in line:
                vulns.append({"raw_line": line.strip()})

    return {
        "tool": "cargo-audit",
        "skipped": False,
        "ok": result["ok"],
        "vuln_count": len(vulns),
        "severity_counts": severity_counts,
        "vulnerabilities": vulns[:100],
        "raw_stderr": result["stderr"][:2000] if result["stderr"] else "",
    }


def execute(task: str, root: Path) -> dict:
    """Run dependency audit across all detected package managers."""
    results: list[dict] = []

    results.append(_run_pip_audit(root))
    results.append(_run_npm_audit(root))
    results.append(_run_cargo_audit(root))

    # Aggregate
    total_vulns = sum(r.get("vuln_count", 0) for r in results if not r.get("skipped"))
    tools_run = [r["tool"] for r in results if not r.get("skipped")]
    tools_skipped = [r["tool"] for r in results if r.get("skipped")]

    raw = {
        "tools_run": tools_run,
        "tools_skipped": tools_skipped,
        "total_vulnerabilities": total_vulns,
        "results": results,
    }

    # Build summary for LLM
    summary_parts = [
        f"Dependency Audit — {total_vulns} vulnerabilidades encontradas",
        f"Tools ejecutadas: {', '.join(tools_run) or 'ninguna'}",
        f"Tools omitidas: {', '.join(tools_skipped) or 'ninguna'}",
        "",
    ]
    for r in results:
        if r.get("skipped"):
            summary_parts.append(f"[{r['tool']}] Omitido: {r.get('reason')}")
            continue
        summary_parts.append(f"[{r['tool']}] {r.get('vuln_count', 0)} vulnerabilidades")
        sev = r.get("severity_counts", {})
        if sev:
            summary_parts.append(f"  Severidad: {sev}")
        for v in r.get("vulnerabilities", [])[:15]:
            if "raw_line" in v:
                summary_parts.append(f"  - {v['raw_line']}")
            else:
                pkg = v.get("package", "?")
                vid = v.get("vuln_id", v.get("advisory_id", v.get("title", "?")))
                summary_parts.append(f"  - {pkg}: {vid}")

    raw_text = "\n".join(summary_parts)

    llm_result = llm_summarize(
        raw_text,
        "Eres un experto en seguridad de dependencias. Analiza estos resultados de auditoría. "
        "Identifica cuáles vulnerabilidades son críticas y deben resolverse inmediatamente. "
        "Sugiere acciones concretas (actualizar, parchear, reemplazar). "
        "Responde en español.",
    )

    if llm_result:
        return {"status": "success", "summary": llm_result, "raw": raw, "llm_used": "auto"}

    # Fallback
    status = "warning" if total_vulns > 0 else "success"
    fallback_lines = [f"Dependency Audit — {total_vulns} vulnerabilidades"]
    for r in results:
        if r.get("skipped"):
            fallback_lines.append(f"\n[{r['tool']}] Omitido: {r.get('reason')}")
        else:
            fallback_lines.append(f"\n[{r['tool']}] {r.get('vuln_count', 0)} vulnerabilidades:")
            for v in r.get("vulnerabilities", [])[:20]:
                if "raw_line" in v:
                    fallback_lines.append(f"  - {v['raw_line']}")
                else:
                    fallback_lines.append(
                        f"  - {v.get('package', '?')}: {v.get('vuln_id', v.get('title', '?'))}"
                    )

    return {"status": status, "summary": "\n".join(fallback_lines), "raw": raw, "llm_used": "none"}


if __name__ == "__main__":
    main_wrapper("dependency-auditor", execute)
