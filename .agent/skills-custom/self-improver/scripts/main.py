#!/usr/bin/env python3
"""
Self-Improver: Auto-mejora continua de Claude Code.
Detecta gaps, genera skills y optimiza existentes.
"""
import io
import sys

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import subprocess
import os
from pathlib import Path

AGENT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # repo root
SELF_DIR = Path(__file__).parent  # self-improver/scripts


def run_script(script_name: str, args: list[str]) -> dict:
    """Ejecuta un script y retorna el resultado JSON."""
    cmd = [sys.executable, str(SELF_DIR / script_name)] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(AGENT_ROOT),
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"raw": result.stdout}
        else:
            return {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def auto_improve(verbose: bool = True):
    """Ejecuta el ciclo completo de auto-mejora."""
    if verbose:
        print("=== SELF-IMPROVER: CICLO DE AUTO-MEJORA ===\n")

    # 1. Analizar gaps con el nuevo formato
    if verbose:
        print("[1/3] Analizando gaps...")
    analysis = run_script("analyze.py", ["--json"])
    coverage = analysis.get("coverage", {})
    gaps = coverage.get("gaps", [])
    gaps_detected = analysis.get("gaps_detected", len(gaps))  # Backwards compat
    if verbose:
        print(f"      Skills cargados: {coverage.get('total_skills', 0)}")
        print(f"      Gaps detectados: {len(gaps)}")

    # 2. Filtrar gaps prioritarios (MISSING primero)
    if verbose:
        print("[2/3] Filtrando gaps prioritarios...")
    priority_gaps = [g for g in gaps if g.get("status") in ["MISSING", "WEAK"]]
    if verbose:
        print(f"      Gaps de alta prioridad: {len(priority_gaps)}")

    # 3. Generar skills para gaps críticos
    if verbose:
        print("[3/3] Generando skills...")
    generated = []
    for gap in priority_gaps[:3]:
        result = run_script("generate.py", ["-g", gap.get("suggestion", gap.get("area", "unknown"))])
        if "error" not in result:
            generated.append(gap.get("area", "unknown"))
            if verbose:
                print(f"      [OK] auto-{gap.get('area', 'unknown')}")
        else:
            if verbose:
                print(f"      [SKIP] {gap.get('area', 'unknown')}: {result.get('error', 'unknown')[:50]}...")

    if verbose:
        print("\n=== RESUMEN ===")
        print(f"Gaps detectados: {gaps_detected}")
        print(f"Gaps analizados: {len(gaps)}")
        print(f"Skills generados: {len(generated)}")
        print(f"Coverage score: {coverage.get('coverage_score', 0)}%")

    return {
        "gaps_detected": gaps_detected,
        "gaps_analyzed": len(gaps),
        "skills_generated": len(generated),
        "coverage_score": coverage.get("coverage_score", 0),
        "skills": generated,
    }


def main():
    parser = argparse.ArgumentParser(description="Self-Improver: Auto-mejora de Claude Code")
    parser.add_argument("--auto", action="store_true", help="Ejecutar ciclo completo")
    parser.add_argument("--analyze", action="store_true", help="Solo analizar gaps")
    parser.add_argument("--generate", "-g", metavar="GAP", help="Generar skill para gap")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Modo detallado")
    parser.add_argument("--brain", action="store_true", help="Ingestar al Brain")

    args = parser.parse_args()

    if args.analyze:
        result = run_script("analyze.py", ["--json"] if args.json else ["-v"] if args.verbose else [])
    elif args.generate:
        result = run_script("generate.py", ["-g", args.generate])
    elif args.auto:
        result = auto_improve(verbose=not args.json)
    else:
        print("Self-Improver - Auto-mejora de Claude Code")
        print("\nModos de uso:")
        print("  --analyze     Analizar gaps de capacidad")
        print("  --generate    Generar skill para un gap específico")
        print("  --auto        Ciclo completo de auto-mejora")
        print("  -v            Modo detallado")
        return 0

    if args.json or (not sys.stdout.isatty()):
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
