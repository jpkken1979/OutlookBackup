#!/usr/bin/env python3
"""
Playwright Skill - Utility Script

Uso:
    python playwright_skill.py --analyze <input>
    python playwright_skill.py --help
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def analyze(input_path: Path) -> dict:
    """Analiza el input."""
    if not input_path.exists():
        return {"success": False, "error": "Archivo no encontrado"}

    content = input_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    return {
        "success": True,
        "file": str(input_path),
        "lines": len(lines),
        "words": len(content.split()),
        "characters": len(content),
    }


def main():
    parser = argparse.ArgumentParser(description="Playwright Skill")
    parser.add_argument("--analyze", "-a", type=Path, help="Archivo a analizar")
    parser.add_argument("--output", "-o", type=Path, help="Salida JSON")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.analyze:
        result = analyze(args.analyze)

        if args.output:
            args.output.write_text(json.dumps(result, indent=2))
            logger.info(f"Resultado: {args.output}")
        else:
            print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
