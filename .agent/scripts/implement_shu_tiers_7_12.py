#!/usr/bin/env python3
"""Implementar SHU Context Handling idempotentemente en Tiers 7-12."""

import sys
from pathlib import Path
import re
import json

# Agregar .agent al path
sys.path.insert(0, str(Path(__file__).parent.parent))

AGENTS_DIR = Path(__file__).parent.parent / "agents"
TIER_RANGE = (7, 12)

# Formato de SHU Context Handling a inyectar
SHU_CONTEXT_SECTION = """## SHU Context Handling

This agent accepts an optional `shu_context` parameter:
- If `shu_context` is empty or not provided: automatically execute `/shu` to gather ecosystem context
- If `shu_context` is populated: use the provided context directly
- Integration point: pass `shu_context` to any subprocess calls via environment variable `SHU_CONTEXT`
"""

# Argumento para inyectar en main.py
SHU_CONTEXT_ARG = """    parser.add_argument(
        "--shu-context",
        type=str,
        default="",
        help="SHU (Structured Habitat Understanding) context JSON. If empty, will auto-execute /shu."
    )"""


def get_agents_by_tier() -> dict:
    """Retorna dict {agent_name: tier} para todos los agentes en TIER_RANGE."""
    result = {}
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith(("_", "__")):
            continue

        identity_file = agent_dir / "IDENTITY.md"
        if not identity_file.exists():
            continue

        content = identity_file.read_text(encoding="utf-8")
        match = re.search(r"^tier:\s*(\d+)", content, re.MULTILINE)
        if match:
            tier = int(match.group(1))
            if TIER_RANGE[0] <= tier <= TIER_RANGE[1]:
                result[agent_dir.name] = tier

    return result


def has_shu_context_handling(identity_content: str) -> bool:
    """Verifica si ya tiene 'SHU Context Handling'."""
    return "## SHU Context Handling" in identity_content


def has_shu_context_arg(main_py_content: str) -> bool:
    """Verifica si ya tiene '--shu-context' argumento."""
    return "--shu-context" in main_py_content


def get_insertion_point_identity(content: str) -> int | None:
    """Retorna línea después de '## Capabilities' para insertar SHU Context Handling.
    Si no existe Capabilities, retorna -1 (no insertar).
    """
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## Capabilities"):
            # Buscar la próxima sección (## ...) o EOF
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("##"):
                    return j  # Insertar antes de la siguiente sección
            return len(lines)  # Insertar al final
    return None


def add_shu_context_to_identity(agent_name: str, identity_path: Path) -> bool:
    """Inyecta SHU Context Handling en IDENTITY.md. Retorna True si se cambió."""
    content = identity_path.read_text(encoding="utf-8")

    if has_shu_context_handling(content):
        return False  # Ya existe

    insertion_point = get_insertion_point_identity(content)
    if insertion_point is None:
        return False  # No encontró dónde insertar

    lines = content.split("\n")
    # Insertar con línea en blanco antes
    lines.insert(insertion_point, "")
    lines.insert(insertion_point + 1, SHU_CONTEXT_SECTION)

    new_content = "\n".join(lines)
    identity_path.write_text(new_content, encoding="utf-8")
    return True


def add_shu_context_to_main_py(agent_name: str, main_py_path: Path) -> bool:
    """Inyecta --shu-context al argparser. Retorna True si se cambió."""
    if not main_py_path.exists():
        return False  # No existe main.py

    content = main_py_path.read_text(encoding="utf-8")

    if has_shu_context_arg(content):
        return False  # Ya existe

    # Buscar "if __name__" para asegurar que uses main_wrapper
    if "main_wrapper" not in content:
        return False  # No usa main_wrapper, skip

    # Buscar argparser.add_argument o parser.add_argument
    # Buscar la última línea antes de "if __name__"
    lines = content.split("\n")

    # Buscar la estructura: típicamente def execute(...), luego if __name__
    # Vamos a insertar antes de if __name__
    insert_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if "if __name__" in lines[i]:
            insert_idx = i
            break

    if insert_idx is None:
        return False

    # Insertar el argumento antes de if __name__
    lines.insert(insert_idx, SHU_CONTEXT_ARG)
    lines.insert(insert_idx, "")

    new_content = "\n".join(lines)
    main_py_path.write_text(new_content, encoding="utf-8")
    return True


def main() -> None:
    """Ejecutar implementación SHU Context para Tiers 7-12."""
    agents = get_agents_by_tier()

    print(f"Encontrados {len(agents)} agentes en Tiers 7-12")
    print()

    results = {"identity_updated": [], "main_py_updated": [], "skipped": [], "errors": []}

    # Agrupar por tier
    by_tier = {}
    for agent, tier in agents.items():
        if tier not in by_tier:
            by_tier[tier] = []
        by_tier[tier].append(agent)

    # Procesar cada agente
    for agent in sorted(agents.keys()):
        tier = agents[agent]
        agent_dir = AGENTS_DIR / agent
        identity_path = agent_dir / "IDENTITY.md"
        main_py_path = agent_dir / "scripts" / "main.py"

        try:
            # Inyectar SHU Context en IDENTITY.md
            if add_shu_context_to_identity(agent, identity_path):
                results["identity_updated"].append((agent, tier))
                print(f"✓ {agent} (Tier {tier}): IDENTITY.md actualizado")
            else:
                print(
                    f"- {agent} (Tier {tier}): IDENTITY.md ya tiene SHU Context o no se pudo insertar"
                )
                results["skipped"].append((agent, tier, "identity"))

            # Inyectar --shu-context en main.py
            if add_shu_context_to_main_py(agent, main_py_path):
                results["main_py_updated"].append((agent, tier))
                print(f"✓ {agent} (Tier {tier}): scripts/main.py actualizado")
            else:
                print(
                    f"- {agent} (Tier {tier}): scripts/main.py ya tiene --shu-context o no se pudo modificar"
                )
                results["skipped"].append((agent, tier, "main.py"))

        except Exception as e:
            results["errors"].append((agent, tier, str(e)))
            print(f"✗ {agent} (Tier {tier}): ERROR - {e}")

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)

    print(f"\nAgentes con IDENTITY.md actualizado: {len(results['identity_updated'])}")
    print(f"Agentes con scripts/main.py actualizado: {len(results['main_py_updated'])}")
    print(f"Agentes skipeados: {len(results['skipped'])}")
    print(f"Errores: {len(results['errors'])}")

    print("\nConteos por tier:")
    for tier in sorted(by_tier.keys()):
        tier_names = {
            7: "UNS Enterprise",
            8: "Intelligence",
            9: "System",
            10: "Data & ML",
            11: "Desktop",
            12: "Content",
        }
        print(f"  Tier {tier} ({tier_names[tier]}): {len(by_tier[tier])} agentes")

    # Guardar resultados en JSON
    output_file = Path(__file__).parent / "shu_implementation_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": {
                    "total_agents": len(agents),
                    "identity_updated": len(results["identity_updated"]),
                    "main_py_updated": len(results["main_py_updated"]),
                    "skipped": len(results["skipped"]),
                    "errors": len(results["errors"]),
                },
                "identity_updated": results["identity_updated"],
                "main_py_updated": results["main_py_updated"],
                "skipped": results["skipped"],
                "errors": results["errors"],
            },
            f,
            indent=2,
        )

    print(f"\nResultados guardados en: {output_file}")


if __name__ == "__main__":
    main()
