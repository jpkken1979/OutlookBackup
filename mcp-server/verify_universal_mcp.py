#!/usr/bin/env python3
"""Verificador universal MCP para Antigravity.

Valida dos servidores:
1) mcp-server/server.py
2) .agent/mcp/agents-server.py

Checks:
- existencia de archivos
- compilacion Python
- carga de modulo
- listado de tools por API interna

Uso:
  python mcp-server/verify_universal_mcp.py
  python mcp-server/verify_universal_mcp.py --json
  python mcp-server/verify_universal_mcp.py --strict
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import py_compile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ProbeResult:
    name: str
    path: str
    exists: bool
    compiles: bool
    loads: bool
    tools_count: int
    ok: bool
    error: str | None = None


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo crear spec para {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def probe_universal_server(root: Path) -> ProbeResult:
    path = root / "mcp-server" / "server.py"
    name = "antigravity"

    if not path.exists():
        return ProbeResult(name, str(path), False, False, False, 0, False, "Archivo no existe")

    try:
        py_compile.compile(str(path), doraise=True)
        compiles = True
    except Exception as exc:
        return ProbeResult(name, str(path), True, False, False, 0, False, f"py_compile: {exc}")

    try:
        mod = _load_module(path, "antigravity_universal_server")
        server = mod.AntigravityMCPServer()
        tools = asyncio.run(server._list_tools())
        tools_count = len(tools)
        ok = tools_count > 0
        return ProbeResult(name, str(path), True, compiles, True, tools_count, ok, None if ok else "tools vacias")
    except Exception as exc:
        return ProbeResult(name, str(path), True, compiles, False, 0, False, f"load/probe: {exc}")


def probe_agents_server(root: Path) -> ProbeResult:
    path = root / ".agent" / "mcp" / "agents-server.py"
    name = "antigravity-agents"

    if not path.exists():
        return ProbeResult(name, str(path), False, False, False, 0, False, "Archivo no existe")

    try:
        py_compile.compile(str(path), doraise=True)
        compiles = True
    except Exception as exc:
        return ProbeResult(name, str(path), True, False, False, 0, False, f"py_compile: {exc}")

    try:
        mod = _load_module(path, "antigravity_agents_server")
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        _ = mod.handle_request(init_req)
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        resp: dict[str, Any] = mod.handle_request(tools_req)
        tools = resp.get("result", {}).get("tools", [])
        tools_count = len(tools)
        ok = tools_count > 0
        return ProbeResult(name, str(path), True, compiles, True, tools_count, ok, None if ok else "tools vacias")
    except Exception as exc:
        return ProbeResult(name, str(path), True, compiles, False, 0, False, f"load/probe: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica integracion MCP universal de Antigravity")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Salida JSON")
    parser.add_argument("--strict", action="store_true", help="Retorna exit code 1 si hay fallas")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent

    results = [
        probe_universal_server(root),
        probe_agents_server(root),
    ]

    all_ok = all(r.ok for r in results)

    if args.json_output:
        payload = {
            "ok": all_ok,
            "results": [asdict(r) for r in results],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("=== Antigravity MCP Universal Verification ===")
        print(f"Root: {root}")
        print()
        for r in results:
            status = "OK" if r.ok else "FAIL"
            print(f"[{status}] {r.name}")
            print(f"  path: {r.path}")
            print(f"  exists: {r.exists}")
            print(f"  compiles: {r.compiles}")
            print(f"  loads: {r.loads}")
            print(f"  tools_count: {r.tools_count}")
            if r.error:
                print(f"  error: {r.error}")
            print()

        print("Resultado global:", "OK" if all_ok else "FAIL")

    if args.strict and not all_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
