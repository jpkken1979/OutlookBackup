"""Agent Bulletin Board — tablón de anuncios entre agentes.

Permite a los agentes publicar resultados de sus ejecuciones
para que otros agentes puedan reaccionar proactivamente.
"""

from __future__ import annotations

import json
import logging
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
class BulletinEntry:
    """Entrada en el tablón de anuncios."""

    agent: str
    action: str  # "created" | "modified" | "deleted" | "analyzed" | "fixed" | "detected"
    summary: str
    files_affected: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    entry_id: str = ""

    def __post_init__(self) -> None:
        """Inicializa campos automáticos."""
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()
        if not self.entry_id:
            import hashlib

            raw = f"{self.agent}-{self.timestamp}-{self.summary[:50]}"
            self.entry_id = hashlib.sha256(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return asdict(self)


@dataclass
class BulletinQuery:
    """Criterios para buscar en el tablón."""

    agent: str = ""
    action: str = ""
    tags: list[str] = field(default_factory=list)
    since_minutes: int = 60
    limit: int = 20


class AgentBulletinBoard:
    """Tablón de anuncios centralizado para comunicación entre agentes.

    Los agentes publican resultados de sus ejecuciones. Otros agentes
    o watchers pueden suscribirse y reaccionar a estos anuncios.

    Uso:
        board = get_bulletin_board()
        board.post(BulletinEntry(
            agent="frontend-specialist",
            action="created",
            summary="Creé formulario de login en Login.tsx",
            files_affected=["src/components/Login.tsx"],
            tags=["auth", "form", "security-review-needed"],
        ))

        # Otro agente busca entradas relevantes
        entries = board.query(BulletinQuery(tags=["security-review-needed"]))
    """

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        """Inicializa el tablón.

        Args:
            storage_dir: Directorio para persistencia (auto-detecta si None).
        """
        if storage_dir is None:
            self._storage = Path.home() / ".antigravity" / "bulletin"
        else:
            self._storage = Path(storage_dir)
        self._storage.mkdir(parents=True, exist_ok=True)
        self._entries: list[BulletinEntry] = []
        self._max_entries = 500
        self._load()

    def _load(self) -> None:
        """Carga entradas desde disco."""
        bulletin_file = self._storage / "bulletin.jsonl"
        if not bulletin_file.exists():
            return
        try:
            lines = bulletin_file.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-self._max_entries :]:
                try:
                    data = json.loads(line)
                    self._entries.append(BulletinEntry(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
        except OSError as e:
            logger.warning("Error cargando bulletin: %s", e)

    def _save(self) -> None:
        """Persiste entradas a disco."""
        bulletin_file = self._storage / "bulletin.jsonl"
        try:
            lines = [
                json.dumps(e.to_dict(), ensure_ascii=False)
                for e in self._entries[-self._max_entries :]
            ]
            bulletin_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            logger.warning("Error guardando bulletin: %s", e)

    def post(self, entry: BulletinEntry) -> str:
        """Publica una entrada en el tablón.

        Args:
            entry: Entrada a publicar.

        Returns:
            ID de la entrada.
        """
        self._entries.append(entry)

        # Trim old entries
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

        self._save()

        logger.info(
            "[Bulletin] %s: %s — %s",
            entry.agent,
            entry.action,
            entry.summary[:80],
        )
        return entry.entry_id

    def query(self, criteria: BulletinQuery) -> list[BulletinEntry]:
        """Busca entradas que cumplan los criterios.

        Args:
            criteria: Criterios de búsqueda.

        Returns:
            Entradas que coinciden.
        """
        results: list[BulletinEntry] = []
        cutoff = ""
        if criteria.since_minutes > 0:
            from datetime import timedelta

            cutoff_dt = datetime.now(UTC) - timedelta(minutes=criteria.since_minutes)
            cutoff = cutoff_dt.isoformat()

        for entry in reversed(self._entries):
            if len(results) >= criteria.limit:
                break

            # Time filter
            if cutoff and entry.timestamp < cutoff:
                continue

            # Agent filter
            if criteria.agent and criteria.agent != entry.agent:
                continue

            # Action filter
            if criteria.action and criteria.action != entry.action:
                continue

            # Tags filter (any match)
            if criteria.tags:
                if not any(tag in entry.tags for tag in criteria.tags):
                    continue

            results.append(entry)

        return results

    def get_recent(self, limit: int = 10) -> list[BulletinEntry]:
        """Obtiene las entradas más recientes.

        Args:
            limit: Máximo de entradas.

        Returns:
            Entradas más recientes.
        """
        return list(reversed(self._entries[-limit:]))

    def get_for_agent(self, agent_name: str, limit: int = 10) -> list[BulletinEntry]:
        """Obtiene entradas publicadas por un agente específico.

        Args:
            agent_name: Nombre del agente.
            limit: Máximo de entradas.

        Returns:
            Entradas del agente.
        """
        return self.query(BulletinQuery(agent=agent_name, limit=limit))

    def get_actionable(self, for_agent: str) -> list[BulletinEntry]:
        """Obtiene entradas que requieren acción de un agente.

        Busca entradas con tags que indiquen revisión pendiente
        en el dominio del agente.

        Args:
            for_agent: Nombre del agente que consulta.

        Returns:
            Entradas accionables.
        """
        # Map agent types to tags they should watch
        agent_interests: dict[str, list[str]] = {
            "security-auditor": ["security-review-needed", "auth", "secrets", "vulnerability"],
            "test-engineer": ["needs-tests", "untested", "test-update-needed"],
            "documentation-specialist": ["needs-docs", "undocumented", "api-change"],
            "performance-optimizer": ["performance-issue", "slow", "optimization-needed"],
            "devops-engineer": ["ci-fix-needed", "deploy-issue", "infra-change"],
            "code-reviewer": ["needs-review", "complex-change", "architecture-change"],
        }

        # Find matching interests
        tags_to_watch: list[str] = []
        for agent_key, tags in agent_interests.items():
            if agent_key in for_agent or for_agent in agent_key:
                tags_to_watch.extend(tags)

        if not tags_to_watch:
            return []

        return self.query(
            BulletinQuery(
                tags=tags_to_watch,
                since_minutes=1440,  # Last 24 hours
                limit=20,
            )
        )

    def stats(self) -> dict[str, Any]:
        """Estadísticas del tablón."""
        agents: dict[str, int] = {}
        actions: dict[str, int] = {}
        for entry in self._entries:
            agents[entry.agent] = agents.get(entry.agent, 0) + 1
            actions[entry.action] = actions.get(entry.action, 0) + 1

        return {
            "total_entries": len(self._entries),
            "by_agent": agents,
            "by_action": actions,
            "storage_path": str(self._storage),
        }


# Singleton
_board: AgentBulletinBoard | None = None


def get_bulletin_board(storage_dir: str | Path | None = None) -> AgentBulletinBoard:
    """Obtiene la instancia singleton del tablón.

    Args:
        storage_dir: Directorio de almacenamiento.

    Returns:
        Instancia de AgentBulletinBoard.
    """
    global _board
    if _board is None:
        _board = AgentBulletinBoard(storage_dir=storage_dir)
    return _board
