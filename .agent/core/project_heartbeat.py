"""Project Heartbeat — sincronización bidireccional proyecto↔Nexus.

Genera un reporte post-sesión que se envía al gateway para que
Nexus tenga visibilidad sobre lo que pasa en cada proyecto inyectado.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field

try:
    from datetime import datetime, UTC
except ImportError:  # Python < 3.11
    from datetime import datetime, timezone

    UTC = UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionHeartbeat:
    """Latido de una sesión de trabajo en un proyecto."""

    project_name: str
    project_dir: str
    session_id: str = ""
    timestamp: str = ""
    files_modified: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    errors_encountered: list[str] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)
    skills_used: list[str] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)
    duration_minutes: float = 0.0
    success: bool = True
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return asdict(self)


def collect_heartbeat(
    project_dir: str | Path,
    *,
    session_id: str = "",
) -> SessionHeartbeat:
    """Recopila información de la sesión actual para generar un heartbeat.

    Args:
        project_dir: Directorio del proyecto.
        session_id: ID de la sesión (opcional).

    Returns:
        SessionHeartbeat con datos de la sesión.
    """
    proj = Path(project_dir).resolve()
    heartbeat = SessionHeartbeat(
        project_name=proj.name,
        project_dir=str(proj),
        session_id=session_id or _generate_session_id(),
        timestamp=datetime.now(UTC).isoformat(),
    )

    # Collect from observations if available
    try:
        from .memory_router import get_memory_router

        router = get_memory_router(str(proj))
        obs_store = router._get_observation_store()
        if obs_store:
            recent = obs_store.get_recent(limit=50)
            for obs in recent:
                obs_str = str(obs)
                if "FILE_EDIT" in obs_str or "FILE_WRITE" in obs_str:
                    # Extract file path if available
                    heartbeat.files_modified.append(obs_str[:200])
                elif "ERROR" in obs_str:
                    heartbeat.errors_encountered.append(obs_str[:200])
                elif "AGENT" in obs_str:
                    heartbeat.agents_used.append(obs_str[:100])
    except Exception as e:
        logger.debug("No se pudieron recopilar observaciones: %s", e)

    # Collect from project memory
    try:
        from .project_memory import get_project_memory

        pm = get_project_memory(str(proj))
        sessions = pm.get_recent_sessions(last_n=1)
        if sessions:
            last = sessions[0]
            if isinstance(last, dict):
                heartbeat.summary = last.get("summary", "")
                heartbeat.duration_minutes = last.get("duration_minutes", 0.0)
    except Exception as e:
        logger.debug("No se pudo acceder a project memory: %s", e)

    # Deduplicate
    heartbeat.files_modified = list(dict.fromkeys(heartbeat.files_modified))
    heartbeat.errors_encountered = list(dict.fromkeys(heartbeat.errors_encountered))
    heartbeat.agents_used = list(dict.fromkeys(heartbeat.agents_used))

    return heartbeat


async def send_heartbeat(
    heartbeat: SessionHeartbeat,
    *,
    gateway_url: str = "http://127.0.0.1:4747",
) -> bool:
    """Envía el heartbeat al gateway de Nexus.

    Args:
        heartbeat: Datos de la sesión.
        gateway_url: URL del gateway.

    Returns:
        True si se envió correctamente.
    """
    try:
        import aiohttp

        payload = heartbeat.to_dict()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{gateway_url}/v1/heartbeat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                success = resp.status in (200, 201, 202)
                if success:
                    logger.info("Heartbeat enviado para %s", heartbeat.project_name)
                else:
                    logger.warning("Heartbeat rechazado: HTTP %d", resp.status)
                return success
    except Exception as e:
        logger.debug("No se pudo enviar heartbeat: %s", e)
        return False


def save_heartbeat_local(
    heartbeat: SessionHeartbeat,
    *,
    history_dir: str | Path | None = None,
) -> Path:
    """Guarda el heartbeat localmente como fallback.

    Args:
        heartbeat: Datos de la sesión.
        history_dir: Directorio para historial (auto-detecta si None).

    Returns:
        Path al archivo guardado.
    """
    if history_dir is None:
        base = Path.home() / ".antigravity" / "heartbeats"
    else:
        base = Path(history_dir)

    base.mkdir(parents=True, exist_ok=True)

    filename = f"{heartbeat.project_name}_{heartbeat.timestamp[:10]}.jsonl"
    filepath = base / filename

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(heartbeat.to_dict(), ensure_ascii=False) + "\n")

    logger.info("Heartbeat guardado localmente: %s", filepath)
    return filepath


def _generate_session_id() -> str:
    """Genera un ID de sesión único."""
    import hashlib
    import time

    raw = f"{time.time()}-{os.getpid()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


async def heartbeat_sync(
    project_dir: str | Path,
    *,
    session_id: str = "",
    gateway_url: str = "http://127.0.0.1:4747",
) -> SessionHeartbeat:
    """Flujo completo: recopilar, enviar y guardar heartbeat.

    Args:
        project_dir: Directorio del proyecto.
        session_id: ID de sesión.
        gateway_url: URL del gateway.

    Returns:
        SessionHeartbeat generado.
    """
    heartbeat = collect_heartbeat(project_dir, session_id=session_id)

    # Try to send to gateway
    sent = await send_heartbeat(heartbeat, gateway_url=gateway_url)

    # Always save locally as backup
    save_heartbeat_local(heartbeat)

    if not sent:
        logger.info("Heartbeat guardado localmente (gateway no disponible)")

    return heartbeat
