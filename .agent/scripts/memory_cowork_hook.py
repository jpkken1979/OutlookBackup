#!/usr/bin/env python3
"""
Memory Cowork Hook — Stop hook que persiste memoria de sesión en .claude/rules/AI_MEMORY.md

Este archivo es auto-inyectado en cada sesión (Cowork + Claude Code) vía:
  context.autoInject: [".claude/rules/*.md"]

El hook se activa en cada Stop de sesión y:
1. Lee el stdin del hook (puede contener info de herramientas usadas)
2. Extrae señales de la sesión (archivos modificados, decisiones)
3. Actualiza la sección "Últimas sesiones" de AI_MEMORY.md
4. Mantiene el archivo bajo ~4000 palabras (para no saturar el contexto)

Uso (desde .claude/settings.json Stop hooks):
    python -X utf8 "$CC_PROJECT_DIR/.agent/scripts/hook_runner.py" memory_cowork_hook.py

v1.0.0 - 2026-03-19
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

MAX_SESSIONS_TO_KEEP = 8
MAX_MEMORY_LINES = 200


def get_project_root() -> Path:
    cwd = (
        os.environ.get("CC_PROJECT_DIR")
        or os.environ.get("CC_CWD")
        or os.environ.get("PWD")
        or str(Path.cwd())
    )
    return Path(cwd).resolve()


def read_stdin_safe() -> dict:
    """Lee stdin del hook si hay datos disponibles."""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read(8192)
            if raw.strip():
                return json.loads(raw)
    except Exception:
        pass
    return {}


def extract_session_signals(hook_data: dict) -> dict[str, list[str]]:
    """Extrae señales útiles del payload del hook."""
    signals: dict[str, list[str]] = {"files_modified": [], "tools_used": [], "topics": []}
    try:
        tool_input = hook_data.get("tool_input") or {}
        file_path = tool_input.get("file_path") or tool_input.get("path")
        if file_path:
            signals["files_modified"].append(str(file_path))

        tool_name = hook_data.get("tool_name") or ""
        if tool_name:
            signals["tools_used"].append(tool_name)
    except Exception:
        pass
    return signals


def read_memory_file(memory_path: Path) -> str:
    if not memory_path.exists():
        return ""
    try:
        return memory_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_session_entry(signals: dict[str, list[str]]) -> str:
    """Construye la entrada de sesión para el log."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    client = os.environ.get("CLAUDE_CLIENT", "Cowork/Claude Code")
    lines = [f"### Sesión {now} ({client})"]

    files = signals.get("files_modified") or []
    if files:
        unique_files = list(dict.fromkeys(files))[:6]
        lines.append("Archivos: " + ", ".join(f"`{f}`" for f in unique_files))

    tools = signals.get("tools_used") or []
    if tools:
        unique_tools = list(dict.fromkeys(tools))[:5]
        lines.append("Tools: " + ", ".join(unique_tools))

    topics = signals.get("topics") or []
    if topics:
        lines.append("Temas: " + "; ".join(topics[:3]))

    return "\n".join(lines)


def inject_session_into_memory(memory_content: str, new_entry: str) -> str:
    """Inserta la nueva sesión justo debajo del marcador ## Últimas sesiones."""
    marker = "## Últimas sesiones"
    if marker not in memory_content:
        return memory_content + f"\n\n{marker}\n\n{new_entry}\n"

    idx = memory_content.index(marker) + len(marker)
    before = memory_content[:idx]
    after = memory_content[idx:]
    return before + "\n\n" + new_entry + after


def trim_old_sessions(content: str) -> str:
    """Mantiene solo las últimas MAX_SESSIONS_TO_KEEP sesiones en el log."""
    marker = "## Últimas sesiones"
    if marker not in content:
        return content

    header_end = content.index(marker) + len(marker)
    header = content[:header_end]
    sessions_block = content[header_end:]

    # Dividir por bloques ### Sesión
    parts = re.split(r"(?=### Sesión)", sessions_block)
    non_session_prefix = parts[0] if not parts[0].strip().startswith("### Sesión") else ""
    session_parts = [p for p in parts if p.strip().startswith("### Sesión")]

    # Limitar sesiones
    if len(session_parts) > MAX_SESSIONS_TO_KEEP:
        session_parts = session_parts[:MAX_SESSIONS_TO_KEEP]

    rebuilt_block = non_session_prefix + "".join(session_parts)
    return header + rebuilt_block


def trim_total_lines(content: str) -> str:
    """Si el archivo supera MAX_MEMORY_LINES, recorta el final."""
    lines = content.splitlines()
    if len(lines) <= MAX_MEMORY_LINES:
        return content
    # Mantener siempre el header fijo (primeras 60 líneas) + sesiones recientes
    header = lines[:60]
    tail = lines[-(MAX_MEMORY_LINES - 60) :]
    return "\n".join(
        header + ["", "*(entradas antiguas truncadas para conservar contexto)*", ""] + tail
    )


def main() -> None:
    hook_data = read_stdin_safe()
    signals = extract_session_signals(hook_data)

    root = get_project_root()
    memory_path = root / ".claude" / "rules" / "AI_MEMORY.md"

    memory_content = read_memory_file(memory_path)
    if not memory_content:
        # Si el archivo no existe aún, no escribir entrada vacía
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    new_entry = build_session_entry(signals)
    updated = inject_session_into_memory(memory_content, new_entry)
    updated = trim_old_sessions(updated)
    updated = trim_total_lines(updated)

    try:
        memory_path.write_text(updated, encoding="utf-8")
    except Exception:
        pass  # Nunca bloquear la sesión por un error del hook

    print(json.dumps({"continue": True, "suppressOutput": True}))


if __name__ == "__main__":
    main()
