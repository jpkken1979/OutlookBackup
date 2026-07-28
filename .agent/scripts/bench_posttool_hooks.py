#!/usr/bin/env python3
"""
Benchmark de la cascada PostToolUse (MED #3 del audit 2026-07-12).

Cronometra cada hook PostToolUse configurado en .claude/settings.json
alimentandolo con un payload representativo (Edit sobre un .py real),
para validar el analisis estatico (~200-500ms happy path) y cuantificar
el beneficio de las 2 recomendaciones de consolidacion:
  (a) fusionar lint-on-edit + complexity-check en un solo ruff check
  (b) filtrar observation_hook a Edit|Write|MultiEdit

No requiere el clasificador de Bash de Claude Code: corre desde la
terminal del usuario (``python .agent/scripts/bench_posttool_hooks.py``)
y deja el reporte en ``docs/audits/`` + scratchpad.

Usage:
    python .agent/scripts/bench_posttool_hooks.py
    python .agent/scripts/bench_posttool_hooks.py --runs 10
    python .agent/scripts/bench_posttool_hooks.py --json
    python .agent/scripts/bench_posttool_hooks.py --file src/foo.py

Exit codes:
    0 = bench completo
    1 = error de configuracion (settings.json ausente / hook roto)
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Forzar UTF-8 en stdout (Windows japones -> cp932 default)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = AGENT_DIR.parent
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"
AUDIT_DIR = PROJECT_ROOT / "docs" / "audits"

# Payload representativo: Edit sobre un .py real del repo.
# Los hooks leen ``tool_input.file_path`` (lint/complexity) o
# ``tool_response.filePath`` (fallback). Usamos un .py que exista.
DEFAULT_TARGET = AGENT_DIR / "scripts" / "healthcheck.py"


@dataclass
class HookRun:
    name: str
    command: str
    times_ms: list[float] = field(default_factory=list)
    exit_codes: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class BenchReport:
    timestamp: str
    target_file: str
    runs: int
    hooks: list[HookRun]
    cascade_ms_p50: float
    cascade_ms_p95: float
    cascade_ms_sum_avg: float
    notes: list[str] = field(default_factory=list)


def load_posttool_hooks() -> list[tuple[str, str]]:
    """Extrae (nombre, command) de cada hook PostToolUse de settings.json.

    Respeta el orden de la cascada (el que vive Claude Code cuando se
    dispara PostToolUse). Devuelve una lista plana: los hooks del matcher
    ``Edit|Write|MultiEdit`` primero, luego los del matcher ```` (catch-all).
    """
    if not SETTINGS_PATH.exists():
        print(f"ERROR: {SETTINGS_PATH} no encontrado", file=sys.stderr)
        sys.exit(1)

    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    matchers = settings.get("hooks", {}).get("PostToolUse", [])

    hooks: list[tuple[str, str]] = []
    for block in matchers:
        matcher = block.get("matcher", "")
        for h in block.get("hooks", []):
            cmd = h.get("command", "")
            # Nombre legible: derivado del command (script path o modulo).
            label = _derive_label(cmd, matcher)
            hooks.append((label, cmd))
    return hooks


def _derive_label(cmd: str, matcher: str) -> str:
    """Deriva un nombre corto desde el command del hook."""
    # Prioridad: nombre de script .sh / .py al final del command.
    if ".sh" in cmd:
        tail = cmd.split("/")[-1].split("\\")[-1].strip('"').strip("'")
        return f"{tail} [{matcher or 'all'}]"
    if ".py" in cmd:
        # hook_runner.py observation_hook.py -> observation_hook
        parts = cmd.split()
        for p in parts:
            if p.endswith(".py") and "hook_runner" not in p:
                return f"{Path(p).stem} [{matcher or 'all'}]"
        # fallback: el propio hook_runner
        for p in parts:
            if p.endswith(".py"):
                return f"{Path(p).stem} [{matcher or 'all'}]"
    return f"{cmd[:40]}... [{matcher or 'all'}]"


def build_payload(target_file: Path) -> str:
    """Construye el JSON de stdin que Claude Code enviaria a un PostToolUse."""
    payload = {
        "session_id": "bench-session",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(target_file)},
        "tool_response": {"filePath": str(target_file)},
    }
    return json.dumps(payload)


def run_hook_once(command: str, payload: str) -> tuple[float, int, str]:
    """Ejecuta un hook una vez con el payload por stdin. Devuelve (ms, exit, stderr)."""
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(PROJECT_ROOT),
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms, proc.returncode, proc.stderr.strip()
    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms, -1, "TIMEOUT (>30s)"
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms, -1, str(exc)


def bench(hooks: list[tuple[str, str]], payload: str, runs: int) -> list[HookRun]:
    """Cronometra cada hook ``runs`` veces."""
    results: list[HookRun] = []
    for name, cmd in hooks:
        hr = HookRun(name=name, command=cmd)
        # Warmup descartado: 1 run no contado (cold start de python/ruff).
        run_hook_once(cmd, payload)
        for _ in range(runs):
            ms, exit_code, err = run_hook_once(cmd, payload)
            hr.times_ms.append(round(ms, 2))
            hr.exit_codes.append(exit_code)
            if err and exit_code != 0:
                hr.errors.append(err)
        results.append(hr)
    return results


def percentile(data: list[float], p: float) -> float:
    """Percentil ingenuo (suficiente para N pequeno)."""
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def summarize(hook_runs: list[HookRun]) -> tuple[float, float, float]:
    """Devuelve (p50 cascada, p95 cascada, suma de medias por hook)."""
    # Suma de medias (modelo: hooks corren secuencial, sin overlap).
    sum_avg = sum(statistics.mean(h.times_ms) for h in hook_runs if h.times_ms)
    # Cascada por-run: para cada run i, sumar el tiempo i de cada hook.
    runs_count = min(len(h.times_ms) for h in hook_runs) if hook_runs else 0
    cascade_per_run: list[float] = []
    for i in range(runs_count):
        total = sum(h.times_ms[i] for h in hook_runs)
        cascade_per_run.append(total)
    p50 = percentile(cascade_per_run, 50)
    p95 = percentile(cascade_per_run, 95)
    return p50, p95, sum_avg


def render_text(report: BenchReport) -> str:
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append("  BENCH PostToolUse — MED #3 (audit 2026-07-12)")
    lines.append("=" * 64)
    lines.append(f"  Timestamp:   {report.timestamp}")
    lines.append(f"  Target file: {report.target_file}")
    lines.append(f"  Runs/hook:   {report.runs} (+1 warmup descartado)")
    lines.append("-" * 64)
    lines.append(f"  {'Hook':<42} {'p50 (ms)':>9} {'p95 (ms)':>9} {'exit':>5}")
    for h in report.hooks:
        p50 = percentile(h.times_ms, 50)
        p95 = percentile(h.times_ms, 95)
        last_exit = h.exit_codes[-1] if h.exit_codes else "?"
        lines.append(f"  {h.name:<42} {p50:>9.1f} {p95:>9.1f} {last_exit:>5}")
        if h.errors:
            lines.append(f"    ⚠ {h.errors[0][:80]}")
    lines.append("-" * 64)
    lines.append(f"  Cascada p50 (suma por run):  {report.cascade_ms_p50:.1f} ms")
    lines.append(f"  Cascada p95 (suma por run):  {report.cascade_ms_p95:.1f} ms")
    lines.append(f"  Suma de medias por hook:     {report.cascade_ms_sum_avg:.1f} ms")
    lines.append("-" * 64)
    lines.append("  Interpretacion vs analisis estatico (~200-500ms happy path):")
    if report.cascade_ms_p50 < 200:
        lines.append("    → p50 POR DEBAJO del estimado — cascada mas rapida de lo esperado.")
    elif report.cascade_ms_p50 <= 500:
        lines.append("    → p50 DENTRO del rango estimado (200-500ms).")
    else:
        lines.append(
            "    → p50 POR ENCIMA del rango — consolidacion (recomendaciones a/b)"
            " tendria mas impacto del previsto."
        )
    if report.notes:
        lines.append("  Notas:")
        for note in report.notes:
            lines.append(f"    - {note}")
    lines.append("=" * 64)
    return "\n".join(lines)


def write_artifacts(report: BenchReport) -> tuple[Path, Path]:
    """Escribe JSON y MD en docs/audits/. Devuelve (json, md)."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    json_path = AUDIT_DIR / f"{stamp}-posttool-bench.json"
    md_path = AUDIT_DIR / f"{stamp}-posttool-bench.md"

    json_path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        f"# PostToolUse Hook Benchmark — {stamp}",
        "",
        f"**Target file:** `{report.target_file}`  ",
        f"**Runs/hook:** {report.runs} (+1 warmup descartado)  ",
        f"**Cascada p50:** {report.cascade_ms_p50:.1f} ms | **p95:** {report.cascade_ms_p95:.1f} ms",
        "",
        "## Por hook",
        "",
        "| Hook | p50 (ms) | p95 (ms) | exit |",
        "|------|---------:|---------:|-----:|",
    ]
    for h in report.hooks:
        p50 = percentile(h.times_ms, 50)
        p95 = percentile(h.times_ms, 95)
        last_exit = h.exit_codes[-1] if h.exit_codes else "?"
        md_lines.append(f"| `{h.name}` | {p50:.1f} | {p95:.1f} | {last_exit} |")
    if report.notes:
        md_lines += ["", "## Notas", ""]
        md_lines += [f"- {n}" for n in report.notes]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de la cascada PostToolUse (MED #3).")
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Cuantas veces cronometrar cada hook (default 5).",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=str(DEFAULT_TARGET),
        help=f"Archivo .py target del Edit simulado (default {DEFAULT_TARGET.name}).",
    )
    parser.add_argument("--json", action="store_true", help="Output solo JSON.")
    parser.add_argument(
        "--no-write", action="store_true", help="No escribir artefactos en docs/audits/."
    )
    args = parser.parse_args()

    target = Path(args.file)
    if not target.is_absolute():
        target = (PROJECT_ROOT / target).resolve()
    if not target.exists():
        print(f"ERROR: target file no existe: {target}", file=sys.stderr)
        return 1

    hooks = load_posttool_hooks()
    if not hooks:
        print("ERROR: no se encontraron hooks PostToolUse en settings.json", file=sys.stderr)
        return 1

    payload = build_payload(target)
    runs = bench(hooks, payload, args.runs)
    p50, p95, sum_avg = summarize(runs)

    report = BenchReport(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        target_file=str(target.relative_to(PROJECT_ROOT)),
        runs=args.runs,
        hooks=runs,
        cascade_ms_p50=round(p50, 1),
        cascade_ms_p95=round(p95, 1),
        cascade_ms_sum_avg=round(sum_avg, 1),
        notes=[
            "Suma de medias != cascada p50: la primera incluye warmup ya descartado "
            "pero los hooks tienen varianza independiente.",
            "Recomendacion (a): fusionar lint-on-edit + complexity-check en un solo "
            "`ruff check` reduciria 2 procesos -> 1.",
            "Recomendacion (b): filtrar observation_hook.py al matcher "
            "Edit|Write|MultiEdit evitaria dispararlo en cada tool (Read, Bash, ...).",
        ],
    )

    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print(render_text(report))

    if not args.no_write:
        try:
            json_path, md_path = write_artifacts(report)
            if not args.json:
                print(f"\nArtefactos: {md_path.name} + {json_path.name} en docs/audits/")
        except Exception as exc:
            print(f"(no se pudieron escribir artefactos: {exc})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
