#!/usr/bin/env python3
"""Dead-code budget gate using vulture (Python) and ts-prune (TypeScript)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VULTURE_ALLOWLIST = PROJECT_ROOT / "governance" / "dead-code" / "vulture-allowlist.txt"
DEFAULT_TS_ALLOWLIST = PROJECT_ROOT / "governance" / "dead-code" / "ts-prune-allowlist.txt"


def _run(cmd: list[str]) -> list[str]:
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    return [line.strip() for line in output.splitlines() if line.strip()]


def _normalize(lines: list[str]) -> list[str]:
    return [line.replace("\\", "/") for line in lines]


def _load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip().replace("\\", "/")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def _filter_ts_prune(lines: list[str]) -> list[str]:
    return [line for line in lines if "(used in module)" not in line]


def _write_baseline(path: Path, findings: list[str], tool: str) -> None:
    """Escribe los findings actuales como allowlist/baseline ordenado.

    El gate es de tipo budget: se registran los findings conocidos para que el
    job pase, y SOLO los findings nuevos (no baseline-ados) lo hacen fallar.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Baseline de dead-code ({tool}) — findings conocidos/aceptados.\n"
        f"# Regenerar con: python .agent/scripts/dead_code_budget.py --update-baseline\n"
        f"# Findings NUEVOS fuera de esta lista hacen fallar el gate.\n"
    )
    body = "\n".join(sorted(findings))
    path.write_text(header + body + ("\n" if body else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dead-code budget gate")
    parser.add_argument(
        "--vulture-allowlist",
        type=Path,
        default=DEFAULT_VULTURE_ALLOWLIST,
    )
    parser.add_argument(
        "--ts-allowlist",
        type=Path,
        default=DEFAULT_TS_ALLOWLIST,
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "governance" / "dead-code" / "latest-report.json",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Escribe los findings actuales a los allowlists (re-baseline) y sale 0.",
    )
    args = parser.parse_args()

    vulture_raw = _run(
        ["python", "-m", "vulture", ".agent/core", ".agent/scripts", "--min-confidence", "80"]
    )
    npx_bin = shutil.which("npx") or shutil.which("npx.cmd")
    npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
    if npx_bin:
        ts_cmd = [npx_bin, "--yes", "ts-prune", "-p", "tsconfig.json"]
    elif npm_bin:
        ts_cmd = [npm_bin, "exec", "--yes", "ts-prune", "--", "-p", "tsconfig.json"]
    else:
        print("ts-prune skipped: npx/npm not found")
        ts_cmd = []

    ts_raw = _run(ts_cmd) if ts_cmd else []

    vulture_findings = _normalize(vulture_raw)
    ts_findings = _normalize(_filter_ts_prune(ts_raw))

    if args.update_baseline:
        _write_baseline(args.vulture_allowlist, vulture_findings, "vulture")
        _write_baseline(args.ts_allowlist, ts_findings, "ts-prune")
        print(f"baseline actualizado: vulture={len(vulture_findings)} ts-prune={len(ts_findings)}")
        return 0

    vulture_allow = _load_allowlist(args.vulture_allowlist)
    ts_allow = _load_allowlist(args.ts_allowlist)

    new_vulture = [line for line in vulture_findings if line not in vulture_allow]
    new_ts = [line for line in ts_findings if line not in ts_allow]

    resolved_vulture = [line for line in vulture_allow if line not in vulture_findings]
    resolved_ts = [line for line in ts_allow if line not in ts_findings]

    report = {
        "vulture": {
            "total": len(vulture_findings),
            "allowlisted": len(vulture_allow),
            "new": new_vulture,
            "resolved": resolved_vulture,
        },
        "ts_prune": {
            "total": len(ts_findings),
            "allowlisted": len(ts_allow),
            "new": new_ts,
            "resolved": resolved_ts,
        },
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"vulture findings: total={len(vulture_findings)} new={len(new_vulture)} resolved={len(resolved_vulture)}"
    )
    print(
        f"ts-prune findings: total={len(ts_findings)} new={len(new_ts)} resolved={len(resolved_ts)}"
    )
    print(f"report: {args.report}")

    if new_vulture:
        print("\nNew vulture findings:")
        for line in new_vulture:
            print(f"- {line}")

    if new_ts:
        print("\nNew ts-prune findings:")
        for line in new_ts:
            print(f"- {line}")

    return 1 if (new_vulture or new_ts) else 0


if __name__ == "__main__":
    sys.exit(main())
