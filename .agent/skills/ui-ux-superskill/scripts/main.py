#!/usr/bin/env python3
"""UI/UX Superskill — Entry point."""

import sys
from pathlib import Path


def main() -> None:
    """Muestra info del skill y módulos disponibles."""
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8")
        # Extraer módulos
        modules = [line.strip() for line in content.splitlines() if line.startswith("## MÓDULO")]
        print("UI/UX Superskill — Sistema Definitivo de Diseño")
        print("=" * 50)
        print()
        for mod in modules:
            print(f"  {mod.replace('## ', '')}")
        print()
        print(f"Documentación completa: {skill_md}")
    else:
        print("ERROR: SKILL.md no encontrado", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
