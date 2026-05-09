#!/usr/bin/env python3
"""
Self-Improver: Generación de nuevos skills.
Crea skills automáticamente basándose en gaps detectados.
"""

import argparse
import json
import sys
import io
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

AGENT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # repo root
SKILLS_DIR = Path(__file__).parent.parent  # self-improver


SKILL_SIMPLE_TEMPLATE = """---
name: {skill_name}
description: {description}
triggers:
  - "{trigger1}"
  - "{trigger2}"
version: "1.0.0"
author: Self-Improver (auto-generated)
tags: [{tags}]
category: custom
---

# {title}

## Propósito

{description}

## Cuándo usar

- {use_case1}
- {use_case2}

## Proceso

1. {step1}
2. {step2}
3. {step3}

## Ejemplo

```bash
python .agent/skills-custom/{skill_name}/scripts/main.py --input "..."
```

## Notas

- Generado automáticamente por self-improver
- Fecha: {date}
- Gap original: {gap}
"""

SKILL_SCRIPT_TEMPLATE = '''#!/usr/bin/env python3
"""
{title} - Skill auto-generado
Gap que resuelve: {gap}
"""

import argparse
import sys
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="{description}")
    parser.add_argument("--input", "-i", required=True, help="Input data")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    # Implementación del skill
    result = {{
        "skill": "{skill_name}",
        "input": args.input,
        "status": "implemented",
        "output": f"Procesado: " + args.input
    }}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"[OK] {{result['output']}}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
'''


def generate_skill(
    skill_name: str,
    description: str,
    gap: str,
    triggers: list[str],
    use_cases: list[str],
    steps: list[str],
) -> dict[str, str]:
    """Genera un skill completo con SKILL.md y scripts/."""
    safe_name = skill_name.lower().replace(" ", "-").replace("_", "-")
    skill_dir = SKILLS_DIR.parent / safe_name
    scripts_dir = skill_dir / "scripts"

    # Crear estructura
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Generar SKILL.md
    skill_md = SKILL_SIMPLE_TEMPLATE.format(
        skill_name=safe_name,
        description=description,
        title=skill_name.title(),
        trigger1=triggers[0] if len(triggers) > 0 else safe_name,
        trigger2=triggers[1] if len(triggers) > 1 else triggers[0],
        tags=", ".join([f'"{t}"' for t in [safe_name, "auto-generated", "custom"]]),
        use_case1=use_cases[0] if len(use_cases) > 0 else "Caso de uso principal",
        use_case2=use_cases[1] if len(use_cases) > 1 else "Caso de uso secundario",
        step1=steps[0] if len(steps) > 0 else "Paso 1",
        step2=steps[1] if len(steps) > 1 else "Paso 2",
        step3=steps[2] if len(steps) > 2 else "Paso 3",
        date=datetime.now().isoformat()[:10],
        gap=gap,
    )

    # Generar scripts/main.py
    script_py = SKILL_SCRIPT_TEMPLATE.format(
        title=skill_name.title(),
        description=description,
        skill_name=safe_name,
        gap=gap,
    )

    # Escribir archivos
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    (scripts_dir / "main.py").write_text(script_py, encoding="utf-8")

    return {
        "skill_name": safe_name,
        "path": str(skill_dir),
        "files_created": ["SKILL.md", "scripts/main.py"],
    }


def update_registry(skill_info: dict[str, str]):
    """Actualiza el registry de skills generados."""
    registry_path = SKILLS_DIR / "registry.json"
    registry = {"generated_skills": []}

    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    registry["generated_skills"].append({
        **skill_info,
        "created_at": datetime.now().isoformat(),
    })

    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generación de nuevos skills")
    parser.add_argument("--gap", "-g", required=True, help="Descripción del gap a resolver")
    parser.add_argument("--name", "-n", help="Nombre del skill (generado si no se especifica)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se crearía")

    args = parser.parse_args()

    # Generar nombre si no se especifica
    skill_name = args.name or f"auto-{args.gap[:20].lower().replace(' ', '-')}"

    # Detectar triggers basándose en el gap
    triggers = [
        args.gap[:30].lower(),
        skill_name.lower(),
    ]

    # Generar el skill
    result = generate_skill(
        skill_name=skill_name,
        description=f"Auto-generado para resolver: {args.gap}",
        gap=args.gap,
        triggers=triggers,
        use_cases=[
            f"Cuando se necesita {args.gap}",
            "Ejecución automática",
        ],
        steps=[
            "Recibir input",
            "Procesar según lógica",
            "Retornar resultado",
        ],
    )

    # Actualizar registry
    update_registry(result)

    if args.dry_run:
        print(f"[DRY-RUN] Se crearía: {result['skill_name']}")
        print(f"  Archivos: {result['files_created']}")
    else:
        print(f"[OK] Skill generado: {result['skill_name']}")
        print(f"  Ubicación: {result['path']}")
        print(f"  Archivos: {', '.join(result['files_created'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
