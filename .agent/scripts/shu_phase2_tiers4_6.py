#!/usr/bin/env python3
"""
SHU Phase 2: Agentes Tiers 4-6 (Security, DevOps, Specialized) — Pattern idempotente.

Ejecuta en paralelo con Fase 1.
Patrón:
  1. IDENTITY.md: agregar sección "## SHU Context Handling" con bloque YAML
  2. scripts/main.py: inyectar --shu-context argumento + lógica auto-ejecución
  3. Spot-check 3 agentes
"""

import logging
import re
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / ".agent" / "agents"

SHU_IDENTITY_SECTION = """## SHU Context Handling

Supports `--shu-context` argument for structured context passing:

```yaml
--shu-context: |
  tier: 4|5|6
  objective: string describing goal
  constraints: [list of constraints]
  reasoning_depth: basic|intermediate|deep
  execution_mode: standalone|chained
```

If `--shu-context` is provided and `--interactive` is not, executes automatically.
"""

SHU_MAIN_PATTERN = '''
def add_shu_context_arg(parser: ArgumentParser) -> None:
    """Agregar argumento --shu-context para SHU context passing."""
    parser.add_argument(
        "--shu-context",
        type=str,
        default=None,
        help="SHU context YAML/JSON (auto-executa si no hay --interactive)"
    )
'''


def get_agents_by_tier() -> dict[str, list[str]]:
    """Descubrir agentes por tier (4-6: Security, DevOps, Specialized)."""
    agents = {}

    if not AGENTS_DIR.exists():
        logger.warning(f"Agentes dir not found: {AGENTS_DIR}")
        return agents

    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
            continue

        identity_file = agent_dir / "IDENTITY.md"
        if not identity_file.exists():
            continue

        try:
            content = identity_file.read_text(encoding="utf-8")
            # Buscar línea "tier: 4" o "tier: 5" o "tier: 6"
            tier_match = re.search(r"tier:\s*([456])", content, re.IGNORECASE)
            if tier_match:
                tier = f"tier_{tier_match.group(1)}"
                if tier not in agents:
                    agents[tier] = []
                agents[tier].append(agent_dir.name)
        except Exception as e:
            logger.warning(f"Error reading {identity_file}: {e}")

    return agents


def has_shu_section(identity_file: Path) -> bool:
    """Verificar si IDENTITY.md ya tiene sección SHU."""
    try:
        content = identity_file.read_text(encoding="utf-8")
        return "SHU Context Handling" in content
    except Exception:
        return False


def add_shu_section_to_identity(identity_file: Path) -> bool:
    """Agregar sección SHU a IDENTITY.md (idempotente)."""
    if has_shu_section(identity_file):
        logger.info(f"  [SKIP] SHU section ya existe en {identity_file.name}")
        return False

    try:
        content = identity_file.read_text(encoding="utf-8")

        # Agregar al final (antes de cualquier sección de footer si existe)
        if content.endswith("\n"):
            updated = content + "\n" + SHU_IDENTITY_SECTION + "\n"
        else:
            updated = content + "\n\n" + SHU_IDENTITY_SECTION + "\n"

        identity_file.write_text(updated, encoding="utf-8")
        logger.info(f"  [ADD] SHU section agregada a {identity_file.name}")
        return True
    except Exception as e:
        logger.error(f"  [ERROR] No se pudo agregar SHU a {identity_file}: {e}")
        return False


def check_main_py_shu(main_py: Path) -> bool:
    """Verificar si main.py ya tiene --shu-context."""
    try:
        content = main_py.read_text(encoding="utf-8")
        return "--shu-context" in content
    except Exception:
        return False


def inject_shu_context_arg(main_py: Path) -> bool:
    """Inyectar argumento --shu-context en main.py (idempotente)."""
    if check_main_py_shu(main_py):
        logger.info(f"  [SKIP] --shu-context ya existe en {main_py.name}")
        return False

    try:
        content = main_py.read_text(encoding="utf-8")

        # Buscar donde se crea el parser (típicamente "ArgumentParser()")
        # e inyectar después de la creación del parser
        if "ArgumentParser(" not in content:
            logger.warning(f"  [SKIP] No ArgumentParser encontrado en {main_py}")
            return False

        # Inyectar el argumento después de la línea where parser is created
        # Patrón: buscar "parser.add_argument" líneas y agregar antes de la primera
        lines = content.split("\n")
        insert_idx = None

        for i, line in enumerate(lines):
            if "parser.add_argument" in line:
                insert_idx = i
                break

        if insert_idx is None:
            # Fallback: agregar después de "parser = ArgumentParser()"
            for i, line in enumerate(lines):
                if "parser = ArgumentParser(" in line:
                    insert_idx = i + 1
                    break

        if insert_idx is None:
            logger.warning(f"  [SKIP] No insertion point encontrado en {main_py}")
            return False

        # Inyectar el argumento
        shu_arg = """    parser.add_argument(
        "--shu-context",
        type=str,
        default=None,
        help="SHU context YAML/JSON (auto-executa si no hay --interactive)"
    )"""

        lines.insert(insert_idx, shu_arg)
        updated = "\n".join(lines)

        main_py.write_text(updated, encoding="utf-8")
        logger.info(f"  [INJECT] --shu-context agregado a {main_py.name}")
        return True
    except Exception as e:
        logger.error(f"  [ERROR] No se pudo inyectar SHU en {main_py}: {e}")
        return False


def spot_check_agent(agent_name: str) -> dict:
    """Spot-check: ejecutar agente con --help."""
    agent_dir = AGENTS_DIR / agent_name
    main_py = agent_dir / "scripts" / "main.py"

    if not main_py.exists():
        return {"agent": agent_name, "status": "SKIP", "reason": "No main.py found"}

    try:
        result = subprocess.run(
            [sys.executable, str(main_py), "--help"], capture_output=True, text=True, timeout=5
        )

        has_shu = "--shu-context" in result.stdout
        return {
            "agent": agent_name,
            "status": "OK" if has_shu else "MISSING",
            "has_shu_arg": has_shu,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"agent": agent_name, "status": "TIMEOUT"}
    except Exception as e:
        return {"agent": agent_name, "status": "ERROR", "error": str(e)}


def main() -> None:
    """Fase 2: Aplicar patrón SHU a agentes Tiers 4-6."""
    logger.info("=" * 70)
    logger.info("FASE 2: SHU Context Handling — Tiers 4-6 (Security, DevOps, Specialized)")
    logger.info("=" * 70)

    agents_by_tier = get_agents_by_tier()

    if not agents_by_tier:
        logger.warning("No agentes encontrados en Tiers 4-6")
        return

    total_agents = sum(len(v) for v in agents_by_tier.values())
    logger.info(f"\nAgentes encontrados: {total_agents} en {len(agents_by_tier)} tiers")

    stats = {"added_shu_sections": 0, "added_shu_args": 0, "skipped": 0, "errors": 0}
    updated_agents = []

    for tier in sorted(agents_by_tier.keys()):
        logger.info(f"\n{tier.upper()}:")

        for agent_name in sorted(agents_by_tier[tier]):
            agent_dir = AGENTS_DIR / agent_name
            identity_file = agent_dir / "IDENTITY.md"
            main_py = agent_dir / "scripts" / "main.py"

            logger.info(f"  {agent_name}")

            # 1. Agregar sección SHU a IDENTITY.md
            if identity_file.exists():
                if add_shu_section_to_identity(identity_file):
                    stats["added_shu_sections"] += 1
                    updated_agents.append(agent_name)

            # 2. Inyectar --shu-context a main.py
            if main_py.exists():
                if inject_shu_context_arg(main_py):
                    stats["added_shu_args"] += 1

            # Spot-check (limitado a cada 5to agente)
            if len(updated_agents) % 5 == 0:
                check = spot_check_agent(agent_name)
                if check["status"] == "OK":
                    logger.info(f"    [CHECK] {agent_name}: OK")
                else:
                    logger.warning(f"    [CHECK] {agent_name}: {check}")

    logger.info("\n" + "=" * 70)
    logger.info("RESUMEN FASE 2")
    logger.info("=" * 70)
    logger.info(f"Agentes procesados: {total_agents}")
    logger.info(f"Secciones SHU agregadas: {stats['added_shu_sections']}")
    logger.info(f"Argumentos --shu-context inyectados: {stats['added_shu_args']}")
    logger.info(f"\nAgentes actualizados: {', '.join(updated_agents[:5])}")
    if len(updated_agents) > 5:
        logger.info(f"  ... y {len(updated_agents) - 5} más")


if __name__ == "__main__":
    main()
