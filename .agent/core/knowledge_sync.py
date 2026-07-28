"""Knowledge Sync — sincronización bidireccional entre fuentes de conocimiento.

Motor que sincroniza:
- ProjectMemory → Obsidian (decisiones, sesiones → ADRs y notas)
- Obsidian → mem0 (notas del vault → embeddings semánticos)

Diseñado para ejecutarse on-demand o como tarea periódica del gateway.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .unified_knowledge_bridge import (
        Mem0Adapter,
        ObsidianAdapter,
        ProjectMemoryAdapter,
        SyncResult,
    )

logger = logging.getLogger(__name__)

# Ruta donde se guarda el estado de sync para evitar duplicados
_SYNC_STATE_DIR = Path(os.getenv("ANTIGRAVITY_HOME", Path.home() / ".antigravity")) / "sync"


def _load_sync_state(source: str) -> dict[str, Any]:
    """Carga el estado de sincronización para evitar re-syncs."""
    state_file = _SYNC_STATE_DIR / f"sync_{source}.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_sync_state(source: str, state: dict[str, Any]) -> None:
    """Guarda el estado de sincronización."""
    _SYNC_STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = _SYNC_STATE_DIR / f"sync_{source}.json"
    state["last_sync"] = datetime.now().isoformat()
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _content_hash(content: str) -> str:
    """Hash corto del contenido para detectar duplicados."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


async def sync_project_to_obsidian(
    project: ProjectMemoryAdapter,
    obsidian: ObsidianAdapter,
) -> SyncResult:
    """Sincroniza decisiones y sesiones de ProjectMemory → Obsidian.

    Solo sincroniza entradas que no se hayan sincronizado previamente
    (tracking via sync state file).

    Args:
        project: Adapter de ProjectMemory.
        obsidian: Adapter de Obsidian.

    Returns:
        SyncResult con contadores de lo sincronizado.
    """
    from .unified_knowledge_bridge import SyncResult

    result = SyncResult()
    state = _load_sync_state("project_to_obsidian")
    synced_ids: set[str] = set(state.get("synced_decision_ids", []))
    synced_session_ids: set[str] = set(state.get("synced_session_ids", []))

    # --- Sincronizar decisiones ---
    decisions = project.get_decisions(limit=50)
    for dec in decisions:
        dec_id = dec.id
        if dec_id in synced_ids:
            continue  # Ya sincronizada

        meta = dec.metadata
        try:
            path = await obsidian.write_decision(
                title=meta.get("description", dec.content[:80]),
                context=meta.get("reasoning", "Decisión registrada en ProjectMemory"),
                decision=meta.get("chosen", dec.content),
                consequences=meta.get("outcome", "Pendiente de evaluación"),
            )
            if path:
                synced_ids.add(dec_id)
                result.synced_to_obsidian += 1
                logger.info("Synced decision → Obsidian: %s", dec_id)
        except Exception as exc:
            result.errors.append(f"Decision {dec_id}: {exc}")

    # --- Sincronizar sesiones ---
    sessions = project.get_sessions(limit=20)
    for sess in sessions:
        sess_id = sess.id
        if sess_id in synced_session_ids:
            continue

        meta = sess.metadata
        try:
            path = await obsidian.write_session(
                summary=meta.get("task_description", sess.content[:200]),
                files_changed=meta.get("files_modified", []) + meta.get("files_created", []),
                decisions=meta.get("decisions_made", []),
            )
            if path:
                synced_session_ids.add(sess_id)
                result.synced_to_obsidian += 1
                logger.info("Synced session → Obsidian: %s", sess_id)
        except Exception as exc:
            result.errors.append(f"Session {sess_id}: {exc}")

    # Guardar estado
    state["synced_decision_ids"] = list(synced_ids)
    state["synced_session_ids"] = list(synced_session_ids)
    _save_sync_state("project_to_obsidian", state)

    return result


async def sync_obsidian_to_mem0(
    obsidian: ObsidianAdapter,
    mem0: Mem0Adapter,
) -> SyncResult:
    """Sincroniza notas de Obsidian → mem0 para búsqueda semántica.

    Toma decisiones y sesiones de Obsidian y las indexa como
    memorias en mem0, permitiendo búsqueda semántica cross-source.

    Args:
        obsidian: Adapter de Obsidian.
        mem0: Adapter de mem0.

    Returns:
        SyncResult con contadores.
    """
    from .unified_knowledge_bridge import SyncResult

    result = SyncResult()
    state = _load_sync_state("obsidian_to_mem0")
    synced_hashes: set[str] = set(state.get("synced_hashes", []))

    # --- Indexar decisiones de Obsidian ---
    decisions = await obsidian.list_decisions(limit=30)
    for note in decisions:
        content_h = _content_hash(note.content)
        if content_h in synced_hashes:
            continue

        stored = await mem0.store(
            content=f"[Obsidian ADR] {note.content[:1500]}",
            metadata={
                "source": "obsidian",
                "category": "decision",
                "obsidian_path": note.metadata.get("path", ""),
                "synced_at": datetime.now().isoformat(),
            },
        )
        if stored:
            synced_hashes.add(content_h)
            result.synced_to_mem0 += 1
            result.synced_from_obsidian += 1

    # --- Indexar sesiones de Obsidian ---
    sessions = await obsidian.list_sessions(limit=15)
    for note in sessions:
        content_h = _content_hash(note.content)
        if content_h in synced_hashes:
            continue

        stored = await mem0.store(
            content=f"[Obsidian Session] {note.content[:1500]}",
            metadata={
                "source": "obsidian",
                "category": "session",
                "obsidian_path": note.metadata.get("path", ""),
                "synced_at": datetime.now().isoformat(),
            },
        )
        if stored:
            synced_hashes.add(content_h)
            result.synced_to_mem0 += 1
            result.synced_from_obsidian += 1

    # Guardar estado
    state["synced_hashes"] = list(synced_hashes)[-500:]  # Mantener últimos 500
    _save_sync_state("obsidian_to_mem0", state)

    return result
