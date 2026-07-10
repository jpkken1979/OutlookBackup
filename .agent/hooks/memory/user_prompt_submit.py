#!/usr/bin/env python3
"""Antigravity Memory Hook -- UserPromptSubmit.

Two responsibilities:
1. Captures user intent context at prompt time (sanitized) -> mem0 queue.
2. **Auto-recall proactivo**: hace brain + mem0 lookup con el prompt como query
   y lo emite a stdout como additional context para que Claude Code lo inyecte
   al turno actual, sin requerir /recall explicito del usuario.

El auto-recall se puede desactivar con `"auto_recall_user_prompt": false` en
`.claude/settings.json` -> `env` o via env var `ANTIGRAVITY_AUTO_RECALL=0`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import (
    get_hook_config,
    recall_recent_context,
    sanitize_private_content,
    store_memory_event,
)

MAX_PROMPT_CHARS = 500
MAX_BRAIN_HITS = 4
MAX_MEM0_HITS = 3
MIN_PROMPT_LEN_FOR_RECALL = 6


def _extract_prompt(data: dict[str, object]) -> str:
    candidates = ["prompt", "message", "input", "user_message", "text"]
    for key in candidates:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _auto_recall_enabled(hook_config: dict[str, Any]) -> bool:
    env_flag = os.environ.get("ANTIGRAVITY_AUTO_RECALL", "").strip().lower()
    if env_flag in {"0", "false", "no", "off"}:
        return False
    value = hook_config.get("auto_recall_user_prompt", True)
    return bool(value)


def _notebooklm_auto_recall_enabled(hook_config: dict[str, Any]) -> bool:
    env_flag = os.environ.get("ANTIGRAVITY_NOTEBOOKLM_AUTO_RECALL", "").strip().lower()
    if env_flag in {"0", "false", "no", "off"}:
        return False
    return bool(hook_config.get("notebooklm_auto_recall", True))


def _brain_query(prompt: str, limit: int = MAX_BRAIN_HITS) -> list[dict[str, Any]]:
    """Busca en el Brain Network local por el prompt.

    No depende del gateway: importa el Brain directo desde .agent/core.
    Fallback seguro: si algo explota, devuelve [].
    """
    try:
        # Locate .agent/ relative to this file -> ../../
        agent_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(agent_root))
        from core.brain import Brain  # type: ignore[import-not-found]

        brain_dir = agent_root / "brain"
        if not brain_dir.exists():
            return []

        brain = Brain(brain_dir, app_id="nexus-mother")
        results = brain.query(prompt, limit=limit)
        out: list[dict[str, Any]] = []
        for node in results:
            title = getattr(node, "title", "") or getattr(node, "slug", "")
            slug = getattr(node, "slug", "")
            tags = list(getattr(node, "tags", []) or [])[:4]
            node_type = getattr(node, "type", "")
            out.append(
                {
                    "title": str(title)[:160],
                    "slug": str(slug)[:120],
                    "type": str(node_type)[:20],
                    "tags": [str(t)[:40] for t in tags],
                }
            )
        return out
    except Exception:  # noqa: BLE001
        return []


def _emit_auto_recall(
    prompt: str,
    brain_hits: list[dict[str, Any]],
    mem0_hits: list[dict[str, Any]],
) -> None:
    """Imprime un bloque legible a stdout para que Claude Code lo vea."""
    if not brain_hits and not mem0_hits:
        return

    lines = [
        "[Antigravity Auto-Recall]",
        f"Prompt: {prompt[:120]}",
    ]
    if brain_hits:
        lines.append("")
        lines.append(f"Brain Network ({len(brain_hits)} nodos):")
        for hit in brain_hits:
            tags = ", ".join(hit.get("tags", []))
            tags_suffix = f" [{tags}]" if tags else ""
            lines.append(f"  - [{hit.get('type', '?')}] {hit.get('title', '?')}{tags_suffix}")
            lines.append(f"    slug: {hit.get('slug', '')}")
    if mem0_hits:
        lines.append("")
        lines.append(f"Mem0 ({len(mem0_hits)} memorias):")
        for hit in mem0_hits[:MAX_MEM0_HITS]:
            memory = str(hit.get("memory") or hit.get("content") or "")[:200]
            lines.append(f"  - {memory}")
    lines.append("")
    lines.append(
        "(Auto-inyectado por user_prompt_submit hook. Desactivar con ANTIGRAVITY_AUTO_RECALL=0.)"
    )

    print("\n".join(lines))


def _emit_notebooklm_auto_recall(raw_hook_payload: str, hook_config: dict[str, Any]) -> None:
    """Runs the selective NotebookLM recall helper without blocking forever."""
    if not _notebooklm_auto_recall_enabled(hook_config):
        return

    script = Path(__file__).resolve().parents[2] / "scripts" / "notebooklm_auto_recall.py"
    if not script.exists():
        return

    timeout = int(hook_config.get("notebooklm_auto_recall_timeout", 25))
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--timeout",
                str(timeout),
            ],
            input=raw_hook_payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout + 3,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("[NotebookLM Auto-Recall] timeout local; continua sin contexto NotebookLM.")
        return
    except Exception:  # noqa: BLE001
        return

    output = (result.stdout or "").strip()
    if output:
        print(output)


def main() -> None:
    try:
        hook_config = get_hook_config()
        if not bool(hook_config.get("capture_user_prompt_submit", True)):
            return

        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            return

        prompt = sanitize_private_content(_extract_prompt(data))
        if not prompt:
            return

        session_id = str(data.get("session_id", ""))[:16]
        cwd = str(data.get("cwd", ""))[:300]
        compact_prompt = prompt[:MAX_PROMPT_CHARS]

        # 1) Store user intent (behavior historico)
        store_memory_event(
            content=f"User intent: {compact_prompt}",
            metadata={
                "type": "user_prompt",
                "session_id": session_id,
                "cwd": cwd,
            },
            event_key=f"user_prompt|{session_id}|{compact_prompt[:120]}",
        )

        # 2) Auto-recall proactivo (nuevo)
        if _auto_recall_enabled(hook_config) and len(compact_prompt) >= MIN_PROMPT_LEN_FOR_RECALL:
            brain_hits = _brain_query(compact_prompt)
            mem0_hits = recall_recent_context(compact_prompt, limit=MAX_MEM0_HITS)
            _emit_auto_recall(compact_prompt, brain_hits, mem0_hits)
            _emit_notebooklm_auto_recall(raw, hook_config)

    except Exception:  # noqa: BLE001
        # Hook es best-effort: nunca bloquear el turno del user.
        pass


if __name__ == "__main__":
    main()
