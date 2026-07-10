#!/bin/bash
# SessionStart hook — Carga contexto relevante del Brain al iniciar Claude Code.
#
# Instalar: agregar a ~/.claude/settings.json o .claude/settings.json
#   {
#     "hooks": {
#       "SessionStart": [
#         { "command": "bash .agent/hooks/session-start-brain.sh" }
#       ]
#     }
#   }

set -e

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
BRAIN_DIR="$REPO_ROOT/.agent/brain"

# Solo activar si existe el brain
if [ ! -d "$BRAIN_DIR" ]; then
    exit 0
fi

# Resumen conciso para inyectar en contexto
python3 << PYEOF 2>/dev/null
import sys
sys.path.insert(0, "$REPO_ROOT/.agent")
try:
    from core.brain import Brain
    from pathlib import Path
    from datetime import datetime, timezone, timedelta

    brain = Brain(Path("$BRAIN_DIR"), app_id="nexus-mother")
    stats = brain.stats()

    # Nodos criticos
    critical = [
        n for n in brain.list_nodes(status="active")
        if n.importance == "critical"
    ][:5]

    # Sesiones ultima semana
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    recent = [
        n for n in brain.list_nodes(node_type="session", status="active")
        if n.date >= week_ago
    ][:5]

    # Bugfixes reciente
    bugfixes = [
        n for n in brain.list_nodes(node_type="pattern", status="active")
        if "bugfix" in n.tags and n.date >= week_ago
    ][:3]

    print("=== Brain Network: contexto de sesion ===")
    print(f"{stats['total_nodes']} nodos | {stats['total_connections']} conexiones")

    if critical:
        print("\nConocimiento critico disponible:")
        for n in critical:
            print(f"  - {n.title}")

    if recent:
        print("\nSesiones recientes:")
        for n in recent:
            print(f"  [{n.date}] {n.title}")

    if bugfixes:
        print("\nBugfixes recientes:")
        for n in bugfixes:
            print(f"  [{n.date}] {n.title}")

    print("\nUsa /recall <tema> para traer contexto especifico.")
    print("Usa /brain query <pregunta> para busqueda semantica completa.")
except Exception as e:
    print(f"[brain-hook] error: {e}", file=sys.stderr)
PYEOF
