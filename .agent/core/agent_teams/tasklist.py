"""Task List Teams: tareas compartidas con file locking.

Sistema de tareas compartidas inspirado en la arquitectura de equipos de Claude
Code. Extraido del monolito ``agent_teams.py`` (refactor 2026-05-31). Sin cambios
de comportamiento.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from core.log_rotation import rotate_jsonl_if_needed

logger = logging.getLogger("antigravity.agent_teams")


TEAMS_ROOT = Path.home() / ".antigravity" / "teams"


class TaskStatus(str, Enum):
    """Estado de una tarea en el equipo."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class TeamTask:
    """Una tarea dentro del equipo con tracking de estado."""

    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assignee: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str | None = None
    completed_at: str | None = None
    priority: int = 0  # 0=low, 1=medium, 2=high

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assignee": self.assignee,
            "blocked_by": self.blocked_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TeamTask:
        status_val = data.get("status", "pending")
        status = TaskStatus(status_val) if isinstance(status_val, str) else status_val
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=status,
            assignee=data.get("assignee"),
            blocked_by=data.get("blocked_by", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at"),
            completed_at=data.get("completed_at"),
            priority=data.get("priority", 0),
        )


@dataclass
class TeamFileLock:
    """Representa un lock sobre un archivo."""

    file_path: str
    agent_id: str
    task_id: str
    acquired_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TeamEvent:
    """Un evento en el log del equipo."""

    timestamp: str
    event_type: str
    agent_id: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "payload": self.payload,
        }


class TaskListTeam:
    """Equipo basado en task list compartida con file locking.

    Extiende AgentTeam con:
    - Task list compartida (pending/in-progress/completed/blocked)
    - File locking para prevenir race conditions
    - Self-claim cuando un teammate termina una tarea
    - El lead solo orquesta, no ejecuta

    Usage:
        from antigravity.sdk.client import Client
        client = Client()

        team = TaskListTeam(name="auth-team", lead="architect")
        team.add_member("coder")
        team.add_member("reviewer")

        task = team.add_task(
            title="Implementar endpoint /login",
            description="POST /api/auth/login con JWT",
            blocked_by=[],
            priority=2,
        )

        team.claim_task(task.id, "coder")
        team.acquire_lock(".env", "coder", task.id)

        team.complete_task(task.id)  # auto-claims next pending task
    """

    def __init__(
        self,
        name: str,
        lead: str,
        members: list[str] | None = None,
        storage_dir: Path | None = None,
    ) -> None:
        self.name = name
        self.lead = lead
        self.members: list[str] = members or []
        self.tasks: list[TeamTask] = []
        self.file_locks: dict[str, TeamFileLock] = {}
        self._created_at = datetime.now().isoformat()

        if storage_dir is None:
            storage_dir = TEAMS_ROOT / self.name
        self._storage_dir = storage_dir
        self._state_file = storage_dir / "state.json"
        self._log_file = storage_dir / "log.jsonl"
        storage_dir.mkdir(parents=True, exist_ok=True)

        self._load()

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _load(self) -> None:
        """Carga estado desde state.json."""
        if not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            self.members = data.get("members", [])
            self.tasks = [TeamTask.from_dict(t) for t in data.get("tasks", [])]
            locks_raw = data.get("file_locks", {})
            self.file_locks = {
                path: TeamFileLock(**lock_data) for path, lock_data in locks_raw.items()
            }
            self._created_at = data.get("created_at", self._created_at)
        except Exception as e:
            logger.warning("Failed to load task team state: %s", e)

    def save(self) -> None:
        """Guarda estado en state.json."""
        data = {
            "name": self.name,
            "lead": self.lead,
            "created_at": self._created_at,
            "members": self.members,
            "tasks": [t.to_dict() for t in self.tasks],
            "file_locks": {path: asdict(lock) for path, lock in self.file_locks.items()},
        }
        self._state_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _log(self, event_type: str, agent_id: str, payload: dict) -> None:
        """Escribe un evento en log.jsonl."""
        event = TeamEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            agent_id=agent_id,
            payload=payload,
        )
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        rotate_jsonl_if_needed(self._log_file, max_lines=2000)

    # -------------------------------------------------------------------------
    # Member management
    # -------------------------------------------------------------------------

    def add_member(self, agent_id: str) -> bool:
        """Agrega un miembro al equipo."""
        if agent_id in self.members or agent_id == self.lead:
            return False
        self.members.append(agent_id)
        self._log("member_added", "system", {"agent_id": agent_id})
        self.save()
        return True

    def remove_member(self, agent_id: str) -> bool:
        """Remueve un miembro y libera sus locks."""
        if agent_id not in self.members:
            return False
        self.members.remove(agent_id)
        for path, lock in list(self.file_locks.items()):
            if lock.agent_id == agent_id:
                self.file_locks.pop(path)
        self._log("member_removed", "system", {"agent_id": agent_id})
        self.save()
        return True

    # -------------------------------------------------------------------------
    # Task management
    # -------------------------------------------------------------------------

    def add_task(
        self,
        title: str,
        description: str = "",
        blocked_by: list[str] | None = None,
        priority: int = 0,
    ) -> TeamTask:
        """Agrega una tarea al backlog del equipo."""
        task_id = str(uuid.uuid4())[:8]
        task = TeamTask(
            id=task_id,
            title=title,
            description=description,
            blocked_by=blocked_by or [],
            priority=priority,
        )
        self.tasks.append(task)
        self._log("task_added", self.lead, {"task_id": task_id, "title": title})
        self.save()
        return task

    def claim_task(self, task_id: str, agent_id: str) -> bool:
        """Reclama una tarea. Devuelve True si fue asignada."""
        task = self._find_task(task_id)
        if task is None:
            return False
        # Only reject if another agent already owns this task
        if task.assignee is not None and task.assignee != agent_id:
            return False
        # Pre-assign blocked tasks (unblock when blocker completes)
        task.assignee = agent_id
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now().isoformat()
        self._log(
            "task_claimed",
            agent_id,
            {"task_id": task_id, "title": task.title},
        )
        self.save()
        return True

    def complete_task(self, task_id: str) -> bool:
        """Marca tarea como completada y libera locks."""
        task = self._find_task(task_id)
        if task is None:
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now().isoformat()
        task.updated_at = task.completed_at

        # Release locks held for this task
        for path, lock in list(self.file_locks.items()):
            if lock.task_id == task_id:
                self.file_locks.pop(path)

        self._log(
            "task_completed",
            task.assignee or "unknown",
            {"task_id": task_id, "title": task.title},
        )
        self.save()

        # Self-claim: auto-buscar proxima tarea
        self._auto_claim_next(task.assignee or "unknown")
        return True

    def block_task(self, task_id: str, reason: str = "") -> bool:
        """Bloquea una tarea."""
        task = self._find_task(task_id)
        if task is None:
            return False
        task.status = TaskStatus.BLOCKED
        task.updated_at = datetime.now().isoformat()
        self._log(
            "task_blocked",
            task.assignee or "unknown",
            {"task_id": task_id, "reason": reason},
        )
        self.save()
        return True

    def unblock_task(self, task_id: str) -> bool:
        """Desbloquea una tarea."""
        task = self._find_task(task_id)
        if task is None:
            return False
        task.status = TaskStatus.PENDING
        task.assignee = None
        task.updated_at = datetime.now().isoformat()
        self._log("task_unblocked", "system", {"task_id": task_id})
        self.save()
        return True

    # -------------------------------------------------------------------------
    # File locking
    # -------------------------------------------------------------------------

    def acquire_lock(
        self,
        file_path: str,
        agent_id: str,
        task_id: str,
    ) -> tuple[bool, str]:
        """Pide lock sobre un archivo. Devuelve (success, message)."""
        if file_path in self.file_locks:
            existing = self.file_locks[file_path]
            if existing.agent_id == agent_id:
                return True, "already_held"
            return False, f"held_by:{existing.agent_id}"

        self.file_locks[file_path] = TeamFileLock(
            file_path=file_path,
            agent_id=agent_id,
            task_id=task_id,
        )
        self._log(
            "lock_acquired",
            agent_id,
            {"file_path": file_path, "task_id": task_id},
        )
        self.save()
        return True, "acquired"

    def release_lock(self, file_path: str) -> bool:
        """Libera un lock de archivo."""
        if file_path not in self.file_locks:
            return False
        lock = self.file_locks.pop(file_path)
        self._log(
            "lock_released",
            "system",
            {"file_path": file_path, "was_held_by": lock.agent_id},
        )
        self.save()
        return True

    def get_lock_holder(self, file_path: str) -> str | None:
        """Devuelve el agent_id que tiene lock, o None."""
        lock = self.file_locks.get(file_path)
        return lock.agent_id if lock else None

    # -------------------------------------------------------------------------
    # Self-claim
    # -------------------------------------------------------------------------

    def _auto_claim_next(self, agent_id: str) -> bool:
        """Auto-claim la proxima tarea libre para el mismo agente.

        Solo reclama tareas que ya estaban pending para este agente
        (que no fueron bloqueadas por una dependencia).
        Las tareas desbloqueadas por completitud de otra tarea
        se quedan en pending para que el lead las reasigne.
        """
        if agent_id not in self.members:
            return False
        # Only auto-claim tasks that were already assigned to this agent
        # (i.e. previously claimed, became available)
        owned = [
            t
            for t in self.tasks
            if t.assignee == agent_id and t.status == TaskStatus.PENDING and not self._is_blocked(t)
        ]
        if owned:
            owned.sort(key=lambda t: (-t.priority, t.created_at))
            return self.claim_task(owned[0].id, agent_id)
        return False

    # -------------------------------------------------------------------------
    # Status / reporting
    # -------------------------------------------------------------------------

    def status(self) -> dict:
        """Estado completo del equipo para display."""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        progress = (completed / total * 100) if total > 0 else 0.0

        return {
            "name": self.name,
            "lead": self.lead,
            "members": self.members,
            "stats": {
                "total": total,
                "completed": completed,
                "in_progress": sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS),
                "pending": sum(1 for t in self.tasks if t.status == TaskStatus.PENDING),
                "blocked": sum(1 for t in self.tasks if t.status == TaskStatus.BLOCKED),
                "progress_pct": round(progress, 1),
            },
            "tasks_by_status": {
                s.value: [t.to_dict() for t in self.tasks if t.status == s] for s in TaskStatus
            },
            "file_locks": {path: asdict(lock) for path, lock in self.file_locks.items()},
        }

    def tasks_for_agent(self, agent_id: str) -> list[TeamTask]:
        """Tareas asignadas a un agente especifico."""
        return [t for t in self.tasks if t.assignee == agent_id]

    def next_pending(self) -> TeamTask | None:
        """Proxima tarea disponible para reclamar."""
        available = [
            t for t in self.tasks if t.status == TaskStatus.PENDING and not self._is_blocked(t)
        ]
        if not available:
            return None
        available.sort(key=lambda t: (-t.priority, t.created_at))
        return available[0]

    def _find_task(self, task_id: str) -> TeamTask | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def _is_blocked(self, task: TeamTask) -> bool:
        for blocked_id in task.blocked_by:
            blocker = self._find_task(blocked_id)
            if blocker and blocker.status != TaskStatus.COMPLETED:
                return True
        return False


class TaskListManager:
    """Gestor global de TaskListTeam. Factory y registry."""

    def __init__(self, teams_root: Path | None = None) -> None:
        self._teams_root = teams_root or TEAMS_ROOT
        self._teams_root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, TaskListTeam] = {}

    def create_team(self, name: str, lead: str) -> TaskListTeam:
        """Crea un nuevo equipo o devuelve el existente."""
        if name in self._cache:
            return self._cache[name]
        team = TaskListTeam(
            name=name,
            lead=lead,
            storage_dir=self._teams_root / name,
        )
        self._cache[name] = team
        return team

    def get_team(self, name: str) -> TaskListTeam | None:
        """Carga un equipo existente."""
        if name in self._cache:
            return self._cache[name]
        team_dir = self._teams_root / name
        if not team_dir.exists() or not (team_dir / "state.json").exists():
            return None
        team = TaskListTeam(name=name, lead="unknown", storage_dir=team_dir)
        self._cache[name] = team
        return team

    def list_teams(self) -> list[str]:
        """Lista todos los equipos en storage."""
        if not self._teams_root.exists():
            return []
        return [
            d.name for d in self._teams_root.iterdir() if d.is_dir() and (d / "state.json").exists()
        ]

    def delete_team(self, name: str) -> bool:
        """Elimina un equipo (borra archivos de storage)."""
        if name in self._cache:
            del self._cache[name]
        import shutil

        team_dir = self._teams_root / name
        if not team_dir.exists():
            return False
        shutil.rmtree(team_dir)
        return True
