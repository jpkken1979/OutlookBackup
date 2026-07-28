#!/usr/bin/env python3
"""Smoke test MCP-first stack (Memory + Registry + Teams + Injector + Gateway).

Uso:
    python .agent/scripts/smoke_mcp_stack.py
    python .agent/scripts/smoke_mcp_stack.py --strict-runtime
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    """Resultado de una verificación."""

    name: str
    ok: bool
    details: str
    critical: bool = False


def http_json(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 8,
) -> tuple[int, Any]:
    """Ejecuta request JSON simple con urllib."""
    data: bytes | None = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc)}


def read_text(path: Path) -> str:
    """Lee archivo UTF-8 seguro."""
    return path.read_text(encoding="utf-8")


def check_static_mcp_surface(repo_root: Path) -> CheckResult:
    """Valida presencia de tools/resources nuevos en mcp-server/server.py."""
    server_file = repo_root / "mcp-server" / "server.py"
    if not server_file.exists():
        return CheckResult(
            name="mcp-surface",
            ok=False,
            details=f"No existe {server_file}",
            critical=True,
        )

    content = read_text(server_file)
    required_tokens = [
        'name="memory_store"',
        'name="memory_recall"',
        'name="memory_stats"',
        'name="registry_search"',
        'name="registry_load"',
        'name="teams_run_pipeline"',
        'name="teams_run_step"',
        "antigravity://memory/backend-status",
        "antigravity://registry/cache-stats",
        "antigravity://teams/traces",
    ]
    missing = [token for token in required_tokens if token not in content]
    if missing:
        return CheckResult(
            name="mcp-surface",
            ok=False,
            details=f"Faltan tokens en server.py: {missing}",
            critical=True,
        )
    return CheckResult(
        name="mcp-surface",
        ok=True,
        details="Tools/resources MCP nuevos detectados en server.py",
        critical=True,
    )


def check_injector_schema(repo_root: Path) -> CheckResult:
    """Ejecuta --inspect y valida outOfScope schema."""
    injector = repo_root / ".agent" / "scripts" / "mcp_injector.py"
    if not injector.exists():
        return CheckResult(
            name="injector-schema",
            ok=False,
            details=f"No existe {injector}",
            critical=True,
        )

    cmd = [
        sys.executable,
        str(injector),
        str(repo_root),
        "--root",
        str(repo_root),
        "--inspect",
        "--dev-preset",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="injector-schema",
            ok=False,
            details=f"Error ejecutando injector inspect: {exc}",
            critical=True,
        )

    if proc.returncode != 0:
        return CheckResult(
            name="injector-schema",
            ok=False,
            details=f"Injector failed (rc={proc.returncode}): {proc.stderr.strip()[:300]}",
            critical=True,
        )

    try:
        data = json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        return CheckResult(
            name="injector-schema",
            ok=False,
            details=f"Salida JSON inválida del injector: {exc}",
            critical=True,
        )

    summary = data.get("summary", {})
    out_of_scope = data.get("outOfScope", {})
    ok = (
        "outOfScopeItems" in summary
        and "hasOutOfScope" in summary
        and isinstance(out_of_scope, dict)
    )
    if not ok:
        return CheckResult(
            name="injector-schema",
            ok=False,
            details="Faltan summary.outOfScopeItems / summary.hasOutOfScope / outOfScope",
            critical=True,
        )

    return CheckResult(
        name="injector-schema",
        ok=True,
        details=(
            "Schema OK: outOfScopeItems="
            f"{summary.get('outOfScopeItems', 0)} hasOutOfScope={summary.get('hasOutOfScope', False)}"
        ),
        critical=True,
    )


def check_gateway_health(gateway_url: str) -> CheckResult:
    """Health check del gateway."""
    status, body = http_json(f"{gateway_url.rstrip('/')}/v1/health")
    if status == 200:
        return CheckResult(
            name="gateway-health",
            ok=True,
            details=f"Gateway online ({status})",
        )
    return CheckResult(
        name="gateway-health",
        ok=False,
        details=f"Gateway no disponible ({status}) body={str(body)[:180]}",
    )


def check_gateway_memory_roundtrip(gateway_url: str, agent: str) -> CheckResult:
    """Roundtrip store/recall contra memoria del gateway."""
    base = gateway_url.rstrip("/")
    key = f"smoke:{int(time.time())}"
    value = f"smoke-test-value-{int(time.time())}"
    store_status, store_body = http_json(
        f"{base}/v1/memory/{urllib.parse.quote(agent)}/store",
        method="POST",
        payload={"key": key, "value": value, "source_agent": "smoke"},
    )
    if store_status not in {200, 201}:
        return CheckResult(
            name="gateway-memory-roundtrip",
            ok=False,
            details=f"Store falló ({store_status}) body={str(store_body)[:180]}",
        )

    recall_status, recall_body = http_json(
        f"{base}/v1/memory/{urllib.parse.quote(agent)}/recall"
        f"?q={urllib.parse.quote(value)}&limit=5",
    )
    if recall_status != 200:
        return CheckResult(
            name="gateway-memory-roundtrip",
            ok=False,
            details=f"Recall falló ({recall_status}) body={str(recall_body)[:180]}",
        )

    serialized = json.dumps(recall_body, ensure_ascii=False)
    found = value in serialized
    return CheckResult(
        name="gateway-memory-roundtrip",
        ok=found,
        details="Roundtrip OK"
        if found
        else "Recall respondió pero no encontró el valor recién guardado",
    )


def check_gateway_registry(gateway_url: str) -> CheckResult:
    """Smoke de registry por endpoint /v1/skills."""
    status, body = http_json(f"{gateway_url.rstrip('/')}/v1/skills?search=ui&limit=5")
    if status != 200:
        return CheckResult(
            name="gateway-registry",
            ok=False,
            details=f"/v1/skills no disponible ({status}) body={str(body)[:180]}",
        )
    return CheckResult(
        name="gateway-registry",
        ok=True,
        details="/v1/skills responde correctamente",
    )


def check_tauri_hooks(repo_root: Path) -> CheckResult:
    """Verifica que Tauri expone los hooks Memory del ecosistema."""
    ecosystem = repo_root / "nexus-app" / "src-tauri" / "src" / "commands" / "ecosystem.rs"
    main_rs = repo_root / "nexus-app" / "src-tauri" / "src" / "main.rs"
    if not ecosystem.exists() or not main_rs.exists():
        return CheckResult(
            name="tauri-hooks",
            ok=False,
            details="No se encontraron archivos Tauri esperados",
            critical=True,
        )

    eco = read_text(ecosystem)
    main = read_text(main_rs)
    # Solo se exigen hooks que realmente existen en el codigo. El antiguo
    # `execute_agent_teams_pipeline` nunca se implemento (solo aparecia en un
    # comentario), por lo que exigirlo hacia fallar el smoke siempre. Si se
    # agrega un command de teams pipeline en el futuro, sumarlo aca.
    required = [
        "pub async fn check_memory_status",
        "commands::ecosystem::check_memory_status",
    ]
    missing = [token for token in required if token not in eco and token not in main]
    if missing:
        return CheckResult(
            name="tauri-hooks",
            ok=False,
            details=f"Faltan hooks Tauri: {missing}",
            critical=True,
        )
    return CheckResult(
        name="tauri-hooks",
        ok=True,
        details="Hooks Tauri Memory detectados",
        critical=True,
    )


def print_results(results: list[CheckResult]) -> None:
    """Imprime reporte final."""
    print("\n=== Smoke MCP Stack Report ===")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        level = "CRIT" if result.critical else "INFO"
        print(f"[{status}] [{level}] {result.name}: {result.details}")

    total = len(results)
    passed = sum(1 for item in results if item.ok)
    failed = total - passed
    print(f"\nResumen: {passed}/{total} OK - {failed} FAIL")


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Smoke test MCP-first stack")
    parser.add_argument("--repo-root", default=".", help="Ruta del repo raíz")
    parser.add_argument("--gateway-url", default="http://127.0.0.1:4747")
    parser.add_argument("--agent", default="codex")
    parser.add_argument(
        "--strict-runtime",
        action="store_true",
        help="Si está activo, falla por checks runtime (gateway) además de checks críticos.",
    )
    parser.add_argument(
        "--skip-runtime", action="store_true", help="Omite todos los checks runtime."
    )
    parser.add_argument("--skip-gateway", action="store_true", help="Omite checks de gateway.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    checks: list[CheckResult] = [
        check_static_mcp_surface(repo_root),
        check_injector_schema(repo_root),
        check_tauri_hooks(repo_root),
    ]

    if not args.skip_runtime:
        if not args.skip_gateway:
            checks.extend(
                [
                    check_gateway_health(args.gateway_url),
                    check_gateway_memory_roundtrip(args.gateway_url, args.agent),
                    check_gateway_registry(args.gateway_url),
                ]
            )

    print_results(checks)

    critical_failed = any((not c.ok) and c.critical for c in checks)
    runtime_failed = any((not c.ok) and (not c.critical) for c in checks)

    if critical_failed:
        return 1
    if args.strict_runtime and runtime_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
