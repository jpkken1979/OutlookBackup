#!/usr/bin/env python3
"""Skill de auto-mejora del bot OpenGravity.

Analiza fallos del bot y propone mejoras concretas.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def analyze_failure(failure_description: str) -> dict:
    """Analiza un fallo del bot y propone mejoras."""

    # Patrones de fallos conocidos y sus soluciones
    known_patterns = [
        {
            "pattern": "ZodError",
            "cause": "LLM devolvió JSON con campos faltantes",
            "fix": "Agregar .optional().default() al campo en el schema correspondiente",
            "file": "src/types/executor-schema.ts o critic-schema.ts",
        },
        {
            "pattern": "Tool.*not found",
            "cause": "El planner planeó usar una herramienta que no existe",
            "fix": "Crear la herramienta faltante en src/tools/pc_tools.ts o extended.ts",
            "file": "src/tools/",
        },
        {
            "pattern": "planificar",
            "cause": "Fallo en el Planner — probablemente JSON malformado del LLM",
            "fix": "Agregar fallback en validatePlanner() en validator.ts",
            "file": "src/utils/validator.ts",
        },
        {
            "pattern": "imagen|photo|foto",
            "cause": "Bot recibió imagen pero no tiene handler",
            "fix": "Agregar handler bot.on('message:photo') en src/index.ts",
            "file": "src/index.ts",
        },
        {
            "pattern": "url|link|http",
            "cause": "Usuario quiere leer una URL pero no hay herramienta",
            "fix": "Usar fetch_url tool (ya implementada en pc_tools.ts)",
            "file": "src/tools/pc_tools.ts",
        },
    ]

    matches = []
    failure_lower = failure_description.lower()

    import re

    for p in known_patterns:
        if re.search(p["pattern"].lower(), failure_lower):
            matches.append(p)

    if not matches:
        matches = [
            {
                "pattern": "desconocido",
                "cause": "Fallo no catalogado",
                "fix": "Revisar logs del bot, identificar el error exacto y agregar manejo específico",
                "file": "src/agent/supervisor.ts",
            }
        ]

    # Propuesta de nueva skill si el fallo es sistemático
    needs_new_skill = any(
        word in failure_lower for word in ["siempre", "repetidamente", "cada vez", "nunca puede"]
    )

    return {
        "failure": failure_description,
        "analysis": matches,
        "needs_new_skill": needs_new_skill,
        "recommendation": matches[0]["fix"] if matches else "Revisar logs detallados",
        "priority_file": matches[0]["file"] if matches else "src/agent/supervisor.ts",
        "next_steps": [
            "1. Identificar el error exacto en los logs",
            "2. Aplicar el fix recomendado",
            "3. Probar con el mismo input que falló",
            "4. Si el fallo persiste, crear una nueva skill específica",
        ],
    }


def scan_bot_logs() -> dict:
    """Escanea el codebase del bot buscando TODOs y áreas de mejora."""

    src_dir = REPO_ROOT / "src"
    improvements = []

    if not src_dir.exists():
        return {"improvements": [], "note": "src/ directory not found"}

    for ts_file in src_dir.rglob("*.ts"):
        try:
            content = ts_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if any(marker in line.upper() for marker in ["TODO", "FIXME", "HACK", "XXX"]):
                    improvements.append(
                        {
                            "file": str(ts_file.relative_to(REPO_ROOT)),
                            "line": i,
                            "content": line.strip(),
                        }
                    )
        except Exception:
            continue

    return {
        "total_improvements_found": len(improvements),
        "improvements": improvements[:20],  # max 20
    }


def main() -> int:
    """Entry point principal."""
    parser = argparse.ArgumentParser(description="Bot Self-Improvement Skill")
    parser.add_argument("--failure", type=str, help="Descripción del fallo a analizar")
    parser.add_argument("--scan", action="store_true", help="Escanear el codebase por mejoras")
    parser.add_argument("--json", action="store_true", help="Output en formato JSON")
    args = parser.parse_args()

    result: dict = {}

    if args.failure:
        result = analyze_failure(args.failure)
    elif args.scan:
        result = scan_bot_logs()
    else:
        result = {
            "usage": "python main.py --failure 'descripcion' | --scan",
            "capabilities": [
                "Analiza fallos específicos del bot",
                "Escanea el codebase buscando TODOs y mejoras",
                "Propone fixes concretos con archivos específicos",
            ],
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Análisis: {result.get('failure', 'scan')}")
        if "recommendation" in result:
            print(f"Recomendación: {result['recommendation']}")
            print(f"Archivo a modificar: {result['priority_file']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
