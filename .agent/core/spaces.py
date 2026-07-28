"""Antigravity Research Spaces — Contenedores de investigación por proyecto/tema.

Un "Space" agrupa sesiones, agentes, contexto y timeline de actividad.
Similar a Claude Projects + Perplexity Spaces.

v1.0.0 — 2026-05-09
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SPACES_ROOT = Path(__file__).resolve().parents[1] / "spaces"
SPACES_ROOT.mkdir(exist_ok=True)

VALID_NODE_TYPES = {"session", "agent", "concept"}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class ResearchSpace:
    """Un space de investigación — contenedor de contexto compartido.

    Agrupa sesiones relacionadas, agentes asignados, y contexto propio.
    """

    id: str
    name: str
    description: str
    created_at: str  # ISO 8601
    updated_at: str  # ISO 8601
    agents: list[str] = field(default_factory=list)
    sessions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "active"

    @classmethod
    def create(
        cls,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchSpace:
        """Factory: crea un nuevo space con directorio y config."""
        space_id = cls._slugify(name)
        now = datetime.now(UTC).isoformat()
        space = cls(
            id=space_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            agents=[],
            sessions=[],
            tags=tags or [],
            metadata=metadata or {},
            status="active",
        )
        space._create_structure()
        space.save()
        logger.info("Created research space: %s (%s)", name, space_id)
        return space

    @classmethod
    def _slugify(cls, name: str) -> str:
        """Genera un slug único a partir del nombre."""
        import re

        slug = re.sub(r"[^\w\s-]", "", name.lower())
        slug = re.sub(r"[\s_]+", "-", slug).strip("-")
        suffix = str(uuid.uuid4())[:6]
        return f"{slug}-{suffix}"

    @property
    def space_dir(self) -> Path:
        """Directorio base del space."""
        return SPACES_ROOT / self.id

    @property
    def config_path(self) -> Path:
        """Path al archivo de configuración JSON."""
        return self.space_dir / "space.json"

    @property
    def sessions_dir(self) -> Path:
        """Path al directorio de sesiones vinculadas."""
        return self.space_dir / "sessions"

    @property
    def agents_dir(self) -> Path:
        """Path al directorio de agentes vinculados."""
        return self.space_dir / "agents"

    @property
    def index_path(self) -> Path:
        """Path al índice del space."""
        return self.space_dir / "index.md"

    def _create_structure(self) -> None:
        """Crea la estructura de directorios del space."""
        dirs = [self.space_dir, self.sessions_dir, self.agents_dir]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Persiste la configuración del space a JSON."""
        data = asdict(self)
        self.config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        self._update_index()

    def _update_index(self) -> None:
        """Genera/actualiza el index.md del space."""
        lines = [
            f"# {self.name}",
            "",
            f"> {self.description}" if self.description else "",
            "",
            f"**ID**: `{self.id}`",
            f"**Status**: `{self.status}`",
            f"**Creado**: {self.created_at}",
            f"**Última actualización**: {self.updated_at}",
            "",
            "## Etiquetas",
            "",
        ]
        if self.tags:
            for tag in self.tags:
                lines.append(f"- `{tag}`")
        else:
            lines.append("_Ninguna_")

        lines.extend(
            [
                "",
                "## Sesiones vinculadas",
                "",
            ]
        )
        if self.sessions:
            for sid in self.sessions:
                lines.append(f"- `{sid}`")
        else:
            lines.append("_Ninguna sesión vinculada_")

        lines.extend(
            [
                "",
                "## Agentes asignados",
                "",
            ]
        )
        if self.agents:
            for aid in self.agents:
                lines.append(f"- `{aid}`")
        else:
            lines.append("_Ningún agente asignado_")

        if self.metadata:
            lines.extend(["", "## Metadata", ""])
            for k, v in self.metadata.items():
                lines.append(f"- **{k}**: `{v}`")

        self.index_path.write_text("\n".join(lines), encoding="utf-8")

    # -------------------------------------------------------------------------
    # Space management
    # -------------------------------------------------------------------------

    @classmethod
    def load(cls, space_id: str) -> ResearchSpace | None:
        """Carga un space desde su archivo de configuración."""
        candidate = SPACES_ROOT / space_id / "space.json"
        if not candidate.exists():
            return None
        data = json.loads(candidate.read_text(encoding="utf-8"))
        return cls(**data)

    def attach_session(self, session_path: str | Path) -> None:
        """Vincula una sesión/memoria al space.

        Args:
            session_path: Path absoluto o relativo a la memoria/sesión.
        """
        sp = str(session_path)
        if sp not in self.sessions:
            self.sessions.append(sp)
            self.updated_at = datetime.now(UTC).isoformat()
            self.save()
            logger.info("Attached session %s to space %s", sp, self.id)

    def detach_session(self, session_path: str) -> None:
        """Desvincula una sesión del space."""
        if session_path in self.sessions:
            self.sessions.remove(session_path)
            self.updated_at = datetime.now(UTC).isoformat()
            self.save()
            logger.info("Detached session %s from space %s", session_path, self.id)

    def attach_agent(self, agent_id: str) -> None:
        """Vincula un agente al space.

        Args:
            agent_id: ID del agente (nombre del directorio en .agent/agents/).
        """
        if agent_id not in self.agents:
            self.agents.append(agent_id)
            self.updated_at = datetime.now(UTC).isoformat()
            self.save()
            logger.info("Attached agent %s to space %s", agent_id, self.id)

    def detach_agent(self, agent_id: str) -> None:
        """Desvincula un agente del space."""
        if agent_id in self.agents:
            self.agents.remove(agent_id)
            self.updated_at = datetime.now(UTC).isoformat()
            self.save()
            logger.info("Detached agent %s from space %s", agent_id, self.id)

    def get_context(self) -> dict[str, Any]:
        """Recupera todo el contexto del space: config + sesiones + agentes.

        Returns:
            Diccionario con toda la información del space.
        """
        sessions_content = []
        for sp in self.sessions:
            p = Path(sp)
            if p.exists():
                text = p.read_text(encoding="utf-8", errors="replace")[:2000]
                sessions_content.append({"path": sp, "preview": text})
            else:
                sessions_content.append({"path": sp, "error": "not found"})

        agents_content = []
        repo_root = SPACES_ROOT.parents[1]
        for aid in self.agents:
            agent_dir = repo_root / "agents" / aid
            identity = agent_dir / "IDENTITY.md"
            if identity.exists():
                text = identity.read_text(encoding="utf-8", errors="replace")[:500]
                agents_content.append({"id": aid, "identity": text[:200]})
            else:
                agents_content.append({"id": aid, "error": "IDENTITY.md not found"})

        index_content = ""
        if self.index_path.exists():
            index_content = self.index_path.read_text(encoding="utf-8")

        return {
            "space": asdict(self),
            "sessions": sessions_content,
            "agents": agents_content,
            "index": index_content,
        }

    def delete(self) -> None:
        """Elimina el space y toda su estructura de archivos."""
        import shutil

        if self.space_dir.exists():
            shutil.rmtree(self.space_dir)
            logger.info("Deleted research space: %s", self.id)

    def to_summary(self) -> dict[str, Any]:
        """Resumen compacto del space para listados."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sessions_count": len(self.sessions),
            "agents_count": len(self.agents),
            "tags": self.tags,
        }

    # -------------------------------------------------------------------------
    # Static helpers
    # -------------------------------------------------------------------------

    @classmethod
    def list_spaces(cls) -> list[ResearchSpace]:
        """Lista todos los spaces existentes ordenados por update descendente."""
        spaces: list[ResearchSpace] = []
        if not SPACES_ROOT.exists():
            return spaces
        for d in SPACES_ROOT.iterdir():
            if d.is_dir():
                space = cls.load(d.name)
                if space is not None:
                    spaces.append(space)
        spaces.sort(key=lambda s: s.updated_at, reverse=True)
        return spaces

    @classmethod
    def find_by_tag(cls, tag: str) -> list[ResearchSpace]:
        """Busca todos los spaces que tienen una etiqueta."""
        return [s for s in cls.list_spaces() if tag in s.tags]

    @classmethod
    def space_stats(cls) -> dict[str, Any]:
        """Estadísticas globales del sistema de spaces."""
        spaces = cls.list_spaces()
        total_sessions = sum(len(s.sessions) for s in spaces)
        total_agents = sum(len(s.agents) for s in spaces)
        all_tags: dict[str, int] = {}
        for s in spaces:
            for t in s.tags:
                all_tags[t] = all_tags.get(t, 0) + 1
        return {
            "total_spaces": len(spaces),
            "total_sessions_linked": total_sessions,
            "total_agents_linked": total_agents,
            "top_tags": dict(sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:10]),
            "spaces": [s.to_summary() for s in spaces],
        }
