#!/usr/bin/env python3
"""
Audit de agentes - verifica completitud de los 128+ agentes.

Chequea en 2 niveles:
  - CORE (REQUIRED): IDENTITY.md + al menos un .py ejecutable
  - MCP  (OPCIONAL): agent.json + entry_point valido

El .py puede estar en scripts/ O en la raiz del agente (main.py, etc).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent / ".agent" / "agents"


def audit_agent(name: str, path: Path) -> dict:
    """Audit un solo agente."""
    core_issues: list[str] = []
    mcp_issues: list[str] = []
    files_found: list[str] = []

    # === CORE (required) ===
    identity = path / "IDENTITY.md"
    if identity.exists():
        files_found.append("IDENTITY.md")
    else:
        core_issues.append("FALTA IDENTITY.md")

    # Scripts check: puede estar en scripts/ o en la raiz
    scripts_dir = path / "scripts"
    root_pys = list(path.glob("*.py"))
    scripts_pys = list(scripts_dir.glob("*.py")) if scripts_dir.exists() else []
    has_py = bool(scripts_pys or root_pys)

    if scripts_dir.exists():
        files_found.append("scripts/")
        if scripts_pys:
            for p in scripts_pys:
                files_found.append(f"scripts/{p.name}")
        else:
            files_found.append("scripts/ (vacío)")

    if root_pys:
        for p in root_pys:
            files_found.append(f"{p.name}")

    if not has_py:
        core_issues.append("SIN .py ejecutable (no scripts/ ni root)")

    # memory/ logs/ (optional but good to have)
    if (path / "memory").exists():
        files_found.append("memory/")
    if (path / "logs").exists():
        files_found.append("logs/")

    # === MCP (optional) ===
    agent_json = path / "agent.json"
    has_mcp = agent_json.exists()
    if has_mcp:
        files_found.append("agent.json")
        try:
            data = json.loads(agent_json.read_text(encoding="utf-8"))
            entry = data.get("entry_point", "")
            if not entry:
                mcp_issues.append("agent.json sin entry_point")
            else:
                # entry_point puede ser "main.py", "scripts/foo.py", "foo.py"
                if "/" in entry:
                    ep_path = path / entry
                elif entry == "main.py" and (path / "main.py").exists():
                    ep_path = path / "main.py"
                elif (scripts_dir / entry).exists():
                    ep_path = scripts_dir / entry
                else:
                    ep_path = path / entry
                if not ep_path.exists():
                    mcp_issues.append(f"entry_point no existe: {entry}")
        except json.JSONDecodeError as e:
            mcp_issues.append(f"agent.json JSON invalido: {e}")

    return {
        "name": name,
        "path": str(path),
        "files": files_found,
        "core_ok": len(core_issues) == 0,
        "mcp_ok": len(mcp_issues) == 0,
        "core_issues": core_issues,
        "mcp_issues": mcp_issues,
    }


def run_audit() -> None:
    agents_dir = ROOT
    if not agents_dir.exists():
        print(f"ERROR: {agents_dir} no existe")
        sys.exit(1)

    all_results: list[dict] = []
    total = 0
    core_ok = 0
    mcp_ok = 0
    core_fail = 0
    mcp_fail = 0

    for entry in sorted(agents_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in ("__pycache__", "_archive", "_backup"):
            continue
        total += 1
        result = audit_agent(entry.name, entry)
        all_results.append(result)
        if result["core_ok"]:
            core_ok += 1
        else:
            core_fail += 1
        if result["mcp_ok"]:
            mcp_ok += 1
        else:
            mcp_fail += 1

    sep = "=" * 70
    print(f"\n{sep}")
    print(f"AUDITORIA DE AGENTES: {agents_dir}")
    print(sep)
    print(f"Total agentes: {total}")
    print(f"Core OK (IDENTITY + .py): {core_ok}")
    print(f"Core FAIL: {core_fail}")
    print(f"MCP OK (agent.json + entry): {mcp_ok}")
    print(f"MCP FAIL: {mcp_fail}")
    print(sep)

    # === CORE issues ===
    core_issue_types: dict[str, int] = {}
    for r in all_results:
        for issue in r["core_issues"]:
            core_issue_types[issue] = core_issue_types.get(issue, 0) + 1

    if core_issue_types:
        print("\nPROBLEMAS CORE (afectan funcionamiento):")
        for issue, count in sorted(core_issue_types.items(), key=lambda x: -x[1]):
            print(f"  [{count}x] {issue}")

    # === MCP issues ===
    mcp_issue_types: dict[str, int] = {}
    for r in all_results:
        for issue in r["mcp_issues"]:
            mcp_issue_types[issue] = mcp_issue_types.get(issue, 0) + 1

    if mcp_issue_types:
        print("\nPROBLEMAS MCP (afectan registro de tools):")
        for issue, count in sorted(mcp_issue_types.items(), key=lambda x: -x[1]):
            print(f"  [{count}x] {issue}")

    # === CORE fails detail ===
    core_fails = [r for r in all_results if not r["core_ok"]]
    if core_fails:
        print(f"\nAGENTES CON PROBLEMAS CORE ({len(core_fails)}):")
        for r in core_fails:
            print(f"\n  FAIL: {r['name']}")
            for issue in r["core_issues"]:
                print(f"    CORE: {issue}")

    # === MCP fails detail (only if --verbose) ===
    mcp_fails = [r for r in all_results if not r["mcp_ok"]]
    if mcp_fails:
        verbose = "--verbose" in sys.argv or "-v" in sys.argv
        if verbose:
            print(f"\nAGENTES CON PROBLEMAS MCP ({len(mcp_fails)}):")
            for r in mcp_fails:
                print(f"\n  MCP FAIL: {r['name']}")
                for issue in r["mcp_issues"]:
                    print(f"    MCP: {issue}")
        else:
            print(f"\n(i) {len(mcp_fails)} agentes sin agent.json o con entry_point faltante (use --verbose para detalle)")

    # === Summary ===
    no_logs = [r for r in all_results if "logs/" not in r["files"]]
    no_mem = [r for r in all_results if "memory/" not in r["files"]]
    if no_logs:
        print(f"\n(i) {len(no_logs)} agentes sin logs/: {', '.join(r['name'] for r in no_logs[:8])}{'...' if len(no_logs) > 8 else ''}")
    if no_mem:
        print(f"(i) {len(no_mem)} agentes sin memory/: {', '.join(r['name'] for r in no_mem[:8])}{'...' if len(no_mem) > 8 else ''}")

    print(f"\n{sep}")
    print("REPORTE COMPLETO:")
    for r in all_results:
        core = "OK" if r["core_ok"] else "FAIL"
        mcp = "MCP_OK" if r["mcp_ok"] else "MCP_FAIL"
        print(f"  [{core}] [{mcp}] {r['name']}")

    print(f"\n{sep}")
    sys.exit(0 if core_fail == 0 else 1)


if __name__ == "__main__":
    run_audit()
