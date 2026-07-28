#!/usr/bin/env python3
"""
Observation Pipeline - Captura estructurada de acciones para el ecosistema.

Este modulo captura CADA accion de herramienta
como una observacion estructurada y alimenta:
- IntelligenceHub (ranking, performance tracking)
- LearningLoop (patrones de exito/error)
- ProjectMemory (hotspots, decisiones)
- SharedMemory (vector search)
- SessionSummarizer (resumenes AI)

El pipeline es el ESLABON PERDIDO que conecta la infraestructura de
inteligencia existente con datos reales de cada sesion.

Almacenamiento DUAL (siguiendo patron de ProjectMemory):
- Primario: ~/.antigravity/projects/<hash>/observations/
- Secundario: <proyecto>/.antigravity/observations/

Usage:
    from .observation_pipeline import get_observation_pipeline, ObservationPipeline

    pipeline = get_observation_pipeline()

    # Capturar una observacion
    obs = pipeline.capture(
        tool_name="Edit",
        tool_input={"file_path": "src/main.py", "old_string": "...", "new_string": "..."},
        tool_output="File edited successfully",
        session_id="session_20260222_143000"
    )

    # Obtener observaciones de la sesion
    observations = pipeline.get_session_observations(session_id)

    # Obtener resumen para context injection
    context = pipeline.get_context_for_injection(max_observations=10)

v1.0.0 - 2026-02-22
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .memory_backend import MemoryBackend, get_backend_from_config

logger = logging.getLogger("antigravity.observation_pipeline")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class ObservationType(str, Enum):
    """Tipos de observacion capturada."""

    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    CODE_SEARCH = "code_search"
    BASH_COMMAND = "bash_command"
    GIT_OPERATION = "git_operation"
    TEST_EXECUTION = "test_execution"
    BUILD_OPERATION = "build_operation"
    WEB_FETCH = "web_fetch"
    AGENT_INVOCATION = "agent_invocation"
    DECISION = "decision"
    ERROR = "error"
    OTHER = "other"


class ObservationPriority(str, Enum):
    """Prioridad de la observacion para context injection."""

    CRITICAL = "critical"  # Siempre incluir (errores, decisiones)
    HIGH = "high"  # Incluir si hay espacio (ediciones, tests)
    MEDIUM = "medium"  # Incluir si es relevante (lecturas, busquedas)
    LOW = "low"  # Solo para historial (comandos triviales)


# Mapeo de tool_name a tipo y prioridad
TOOL_TYPE_MAP: dict[str, tuple[ObservationType, ObservationPriority]] = {
    "Read": (ObservationType.FILE_READ, ObservationPriority.MEDIUM),
    "Write": (ObservationType.FILE_WRITE, ObservationPriority.HIGH),
    "Edit": (ObservationType.FILE_EDIT, ObservationPriority.HIGH),
    "Glob": (ObservationType.CODE_SEARCH, ObservationPriority.LOW),
    "Grep": (ObservationType.CODE_SEARCH, ObservationPriority.MEDIUM),
    "Bash": (ObservationType.BASH_COMMAND, ObservationPriority.MEDIUM),
    "WebFetch": (ObservationType.WEB_FETCH, ObservationPriority.MEDIUM),
    "WebSearch": (ObservationType.WEB_FETCH, ObservationPriority.MEDIUM),
    "Task": (ObservationType.AGENT_INVOCATION, ObservationPriority.HIGH),
    "NotebookEdit": (ObservationType.FILE_EDIT, ObservationPriority.HIGH),
}


@dataclass
class Observation:
    """Observacion estructurada de una accion."""

    id: str
    session_id: str
    timestamp: str
    tool_name: str
    observation_type: str
    priority: str
    tool_input_summary: str
    tool_output_summary: str
    files_affected: list[str] = field(default_factory=list)
    success: bool = True
    error_message: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_context_string(self) -> str:
        """Genera representacion legible para context injection."""
        parts = [f"[{self.tool_name}]"]
        if self.files_affected:
            parts.append(f"files: {', '.join(self.files_affected[:3])}")
        parts.append(self.tool_input_summary[:200])
        if not self.success:
            parts.append(f"ERROR: {self.error_message or 'unknown'}")
        return " | ".join(parts)


@dataclass
class SessionObservationSummary:
    """Resumen de observaciones de una sesion."""

    session_id: str
    start_time: str
    end_time: str
    total_observations: int
    files_modified: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    tools_used: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    success_rate: float = 1.0


# ---------------------------------------------------------------------------
# SQLite Storage
# ---------------------------------------------------------------------------


class ObservationStore:
    """Almacenamiento SQLite para observaciones con busqueda eficiente."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        observation_type TEXT NOT NULL,
        priority TEXT NOT NULL,
        tool_input_summary TEXT,
        tool_output_summary TEXT,
        files_affected TEXT,
        success INTEGER DEFAULT 1,
        error_message TEXT,
        duration_ms REAL DEFAULT 0,
        metadata TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_obs_session ON observations(session_id);
    CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON observations(timestamp);
    CREATE INDEX IF NOT EXISTS idx_obs_type ON observations(observation_type);
    CREATE INDEX IF NOT EXISTS idx_obs_priority ON observations(priority);
    CREATE INDEX IF NOT EXISTS idx_obs_tool ON observations(tool_name);

    CREATE TABLE IF NOT EXISTS session_summaries (
        session_id TEXT PRIMARY KEY,
        start_time TEXT,
        end_time TEXT,
        total_observations INTEGER DEFAULT 0,
        files_modified TEXT,
        files_read TEXT,
        tools_used TEXT,
        errors TEXT,
        decisions TEXT,
        success_rate REAL DEFAULT 1.0,
        ai_summary TEXT
    );
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Cierra la conexion."""
        self._conn.close()

    def store_observation(self, obs: Observation) -> None:
        """Almacena una observacion."""
        self._conn.execute(
            """INSERT OR REPLACE INTO observations
               (id, session_id, timestamp, tool_name, observation_type, priority,
                tool_input_summary, tool_output_summary, files_affected,
                success, error_message, duration_ms, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                obs.id,
                obs.session_id,
                obs.timestamp,
                obs.tool_name,
                obs.observation_type,
                obs.priority,
                obs.tool_input_summary,
                obs.tool_output_summary,
                json.dumps(obs.files_affected),
                1 if obs.success else 0,
                obs.error_message,
                obs.duration_ms,
                json.dumps(obs.metadata),
            ),
        )
        self._conn.commit()

    def get_session_observations(self, session_id: str, limit: int = 500) -> list[Observation]:
        """Obtiene observaciones de una sesion."""
        rows = self._conn.execute(
            """SELECT * FROM observations
               WHERE session_id = ?
               ORDER BY timestamp ASC
               LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [self._row_to_observation(r) for r in rows]

    def get_recent_observations(
        self,
        limit: int = 50,
        min_priority: str | None = None,
        observation_type: str | None = None,
    ) -> list[Observation]:
        """Obtiene observaciones recientes con filtros opcionales."""
        query = "SELECT * FROM observations WHERE 1=1"
        params: list[Any] = []

        if min_priority:
            priorities = _priority_list_from(min_priority)
            placeholders = ",".join("?" for _ in priorities)
            query += f" AND priority IN ({placeholders})"
            params.extend(priorities)

        if observation_type:
            query += " AND observation_type = ?"
            params.append(observation_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_observation(r) for r in rows]

    def get_observations_by_file(self, file_path: str, limit: int = 20) -> list[Observation]:
        """Obtiene observaciones que afectan un archivo especifico."""
        rows = self._conn.execute(
            """SELECT * FROM observations
               WHERE files_affected LIKE ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (f"%{file_path}%", limit),
        ).fetchall()
        return [self._row_to_observation(r) for r in rows]

    def search_observations(self, query: str, limit: int = 20) -> list[Observation]:
        """Busca observaciones por texto en input/output summary."""
        rows = self._conn.execute(
            """SELECT * FROM observations
               WHERE tool_input_summary LIKE ? OR tool_output_summary LIKE ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [self._row_to_observation(r) for r in rows]

    def store_session_summary(
        self, summary: SessionObservationSummary, ai_summary: str | None = None
    ) -> None:
        """Almacena resumen de sesion."""
        self._conn.execute(
            """INSERT OR REPLACE INTO session_summaries
               (session_id, start_time, end_time, total_observations,
                files_modified, files_read, tools_used, errors, decisions,
                success_rate, ai_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                summary.session_id,
                summary.start_time,
                summary.end_time,
                summary.total_observations,
                json.dumps(summary.files_modified),
                json.dumps(summary.files_read),
                json.dumps(summary.tools_used),
                json.dumps(summary.errors),
                json.dumps(summary.decisions),
                summary.success_rate,
                ai_summary,
            ),
        )
        self._conn.commit()

    def get_recent_session_summaries(self, limit: int = 10) -> list[dict]:
        """Obtiene resumenes de sesiones recientes."""
        rows = self._conn.execute(
            """SELECT * FROM session_summaries
               ORDER BY end_time DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        results = []
        for r in rows:
            results.append(
                {
                    "session_id": r["session_id"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "total_observations": r["total_observations"],
                    "files_modified": json.loads(r["files_modified"] or "[]"),
                    "files_read": json.loads(r["files_read"] or "[]"),
                    "tools_used": json.loads(r["tools_used"] or "{}"),
                    "errors": json.loads(r["errors"] or "[]"),
                    "success_rate": r["success_rate"],
                    "ai_summary": r["ai_summary"],
                }
            )
        return results

    def get_stats(self) -> dict:
        """Obtiene estadisticas del store."""
        total = self._conn.execute("SELECT COUNT(*) as c FROM observations").fetchone()["c"]
        sessions = self._conn.execute(
            "SELECT COUNT(DISTINCT session_id) as c FROM observations"
        ).fetchone()["c"]
        by_type = {}
        for row in self._conn.execute(
            "SELECT observation_type, COUNT(*) as c FROM observations GROUP BY observation_type"
        ).fetchall():
            by_type[row["observation_type"]] = row["c"]
        return {
            "total_observations": total,
            "total_sessions": sessions,
            "by_type": by_type,
        }

    def _row_to_observation(self, row: sqlite3.Row) -> Observation:
        """Convierte fila SQLite a Observation."""
        return Observation(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            tool_name=row["tool_name"],
            observation_type=row["observation_type"],
            priority=row["priority"],
            tool_input_summary=row["tool_input_summary"] or "",
            tool_output_summary=row["tool_output_summary"] or "",
            files_affected=json.loads(row["files_affected"] or "[]"),
            success=bool(row["success"]),
            error_message=row["error_message"],
            duration_ms=row["duration_ms"] or 0.0,
            metadata=json.loads(row["metadata"] or "{}"),
        )


def _priority_list_from(min_priority: str) -> list[str]:
    """Devuelve lista de prioridades >= min_priority."""
    order = ["critical", "high", "medium", "low"]
    try:
        idx = order.index(min_priority)
        return order[: idx + 1]
    except ValueError:
        return order


# ---------------------------------------------------------------------------
# Observation Pipeline
# ---------------------------------------------------------------------------


class ObservationPipeline:
    """Pipeline central de captura de observaciones.

    Responsabilidades:
    1. Recibir datos crudos de tool use
    2. Clasificar tipo y prioridad
    3. Extraer archivos afectados
    4. Resumir input/output
    5. Almacenar en SQLite
    6. Alimentar IntelligenceHub, LearningLoop, ProjectMemory
    7. Proveer contexto para injection en futuras sesiones
    """

    MAX_INPUT_SUMMARY = 500
    MAX_OUTPUT_SUMMARY = 300

    def __init__(self, project_root: str | None = None, backend: MemoryBackend | None = None):
        self._backend = backend or get_backend_from_config()
        self._root = Path(project_root).resolve() if project_root else Path(".").resolve()
        project_hash = hashlib.sha256(str(self._root).encode()).hexdigest()[:16]

        # Dual storage
        self._home_dir = Path.home() / ".antigravity" / "projects" / project_hash / "observations"
        self._project_dir = self._root / ".antigravity" / "observations"
        self._home_dir.mkdir(parents=True, exist_ok=True)
        self._project_dir.mkdir(parents=True, exist_ok=True)

        # SQLite store (primario en home, secundario en proyecto)
        self._store = ObservationStore(self._home_dir / "observations.db")

        # Crear copia en proyecto si no existe
        project_db = self._project_dir / "observations.db"
        if not project_db.exists():
            self._project_store = ObservationStore(project_db)
        else:
            self._project_store = ObservationStore(project_db)

        # Subsistemas (lazy loading)
        self._intelligence_hub: Any = None
        self._learning_loop: Any = None
        self._project_memory: Any = None

        # Session tracking
        self._current_session_id: str | None = None
        self._session_start_time: str | None = None

        logger.info(
            "ObservationPipeline inicializado para %s (hash: %s)",
            self._root.name,
            project_hash,
        )

    # -----------------------------------------------------------------------
    # Lazy loading de subsistemas
    # -----------------------------------------------------------------------

    def _get_intelligence_hub(self) -> Any:
        if self._intelligence_hub is None:
            try:
                from .intelligence_hub import get_intelligence_hub

                self._intelligence_hub = get_intelligence_hub(str(self._root))
            except ImportError:
                logger.debug("IntelligenceHub no disponible")
        return self._intelligence_hub

    def _get_learning_loop(self) -> Any:
        if self._learning_loop is None:
            try:
                from .learning_loop import get_learning_loop

                self._learning_loop = get_learning_loop(str(self._root))
            except ImportError:
                logger.debug("LearningLoop no disponible")
        return self._learning_loop

    def _get_project_memory(self) -> Any:
        if self._project_memory is None:
            try:
                from .project_memory import get_project_memory

                self._project_memory = get_project_memory(str(self._root))
            except ImportError:
                logger.debug("ProjectMemory no disponible")
        return self._project_memory

    # -----------------------------------------------------------------------
    # Session Management
    # -----------------------------------------------------------------------

    def start_session(self, session_id: str | None = None) -> str:
        """Inicia una nueva sesion de observacion."""
        self._current_session_id = (
            session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self._session_start_time = datetime.now().isoformat()
        logger.info("Sesion de observacion iniciada: %s", self._current_session_id)
        return self._current_session_id

    def end_session(self) -> SessionObservationSummary | None:
        """Finaliza la sesion actual y genera resumen."""
        if not self._current_session_id:
            return None

        summary = self.generate_session_summary(self._current_session_id)

        # Almacenar resumen
        self._store.store_session_summary(summary)
        self._project_store.store_session_summary(summary)

        # Alimentar ProjectMemory con el resumen de sesion
        pm = self._get_project_memory()
        if pm:
            try:
                pm.record_session(
                    session_id=summary.session_id,
                    task_description=f"Sesion con {summary.total_observations} acciones",
                    files_created=[],
                    files_modified=summary.files_modified,
                    decisions_made=summary.decisions,
                    commits=[],
                )
            except Exception as e:
                logger.debug("Error alimentando ProjectMemory: %s", e)

        session_id = self._current_session_id
        self._current_session_id = None
        self._session_start_time = None

        logger.info(
            "Sesion %s finalizada: %d observaciones, %.0f%% exito",
            session_id,
            summary.total_observations,
            summary.success_rate * 100,
        )
        return summary

    # -----------------------------------------------------------------------
    # Core: Capture
    # -----------------------------------------------------------------------

    def capture(
        self,
        tool_name: str,
        tool_input: dict[str, Any] | str,
        tool_output: str,
        session_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
        duration_ms: float = 0.0,
    ) -> Observation:
        """Captura una observacion de tool use.

        Args:
            tool_name: Nombre de la herramienta (Read, Write, Edit, Bash, etc.)
            tool_input: Input de la herramienta (dict o string)
            tool_output: Output de la herramienta
            session_id: ID de sesion (usa la actual si no se especifica)
            success: Si la operacion fue exitosa
            error_message: Mensaje de error si aplica
            duration_ms: Duracion en milisegundos

        Returns:
            Observation capturada
        """
        sid = session_id or self._current_session_id or "unknown"

        # Clasificar tipo y prioridad
        obs_type, priority = TOOL_TYPE_MAP.get(
            tool_name, (ObservationType.OTHER, ObservationPriority.LOW)
        )

        # Detectar git operations en Bash
        if tool_name == "Bash" and isinstance(tool_input, dict):
            cmd = tool_input.get("command", "")
            if cmd.startswith("git "):
                obs_type = ObservationType.GIT_OPERATION
                priority = ObservationPriority.HIGH
            elif "pytest" in cmd or "npm test" in cmd:
                obs_type = ObservationType.TEST_EXECUTION
                priority = ObservationPriority.HIGH
            elif "npm run build" in cmd or "pip install" in cmd:
                obs_type = ObservationType.BUILD_OPERATION
                priority = ObservationPriority.MEDIUM

        # Elevar prioridad en errores
        if not success:
            obs_type = ObservationType.ERROR
            priority = ObservationPriority.CRITICAL

        # Extraer archivos afectados
        files = self._extract_files(tool_name, tool_input)

        # Resumir input/output
        input_summary = self._summarize_input(tool_name, tool_input)
        output_summary = self._summarize_output(tool_output)

        # Crear observacion
        obs = Observation(
            id=str(uuid.uuid4())[:12],
            session_id=sid,
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            observation_type=obs_type.value,
            priority=priority.value,
            tool_input_summary=input_summary,
            tool_output_summary=output_summary,
            files_affected=files,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata={},
        )

        # Almacenar en ambos stores
        self._store.store_observation(obs)
        try:
            self._project_store.store_observation(obs)
        except Exception:
            pass  # Proyecto secundario, no bloquear

        # Alimentar subsistemas (fire-and-forget)
        self._feed_subsystems(obs)

        return obs

    # -----------------------------------------------------------------------
    # Feed Subsystems
    # -----------------------------------------------------------------------

    def _feed_subsystems(self, obs: Observation) -> None:
        """Alimenta subsistemas de inteligencia con la observacion."""
        self._feed_intelligence_hub(obs)
        self._feed_learning_loop(obs)
        self._feed_project_memory(obs)

    def _feed_intelligence_hub(self, obs: Observation) -> None:
        """Registra el outcome en IntelligenceHub (solo prioridad critical/high)."""
        if obs.priority not in ("critical", "high"):
            return
        hub = self._get_intelligence_hub()
        if not hub:
            return
        try:
            hub.record_outcome(
                task=obs.tool_input_summary[:100],
                agent_name="claude",
                success=obs.success,
                quality_score=1.0 if obs.success else 0.0,
                duration_ms=int(obs.duration_ms),
                skills_used=[obs.tool_name],
                error_type=obs.error_message if not obs.success else None,
            )
        except Exception as e:
            logger.debug("Error alimentando IntelligenceHub: %s", e)

    def _feed_learning_loop(self, obs: Observation) -> None:
        """Registra la accion en LearningLoop (prioridad critical/high/medium)."""
        if obs.priority not in ("critical", "high", "medium"):
            return
        ll = self._get_learning_loop()
        if not ll:
            return
        try:
            event_id = ll.record_action(
                obs.tool_input_summary[:100],
                {"tool": obs.tool_name, "type": obs.observation_type},
            )
            if not obs.success:
                from .learning_loop import OutcomeType

                ll.record_outcome(event_id, OutcomeType.FAILED)
        except Exception as e:
            logger.debug("Error alimentando LearningLoop: %s", e)

    def _feed_project_memory(self, obs: Observation) -> None:
        """Registra hotspots de archivos modificados en ProjectMemory."""
        pm = self._get_project_memory()
        if not (pm and obs.files_affected):
            return
        try:
            for f in obs.files_affected:
                if obs.observation_type in ("file_write", "file_edit"):
                    pm.record_file_modification(f)
        except Exception as e:
            logger.debug("Error alimentando ProjectMemory: %s", e)

    # -----------------------------------------------------------------------
    # Extraction Helpers
    # -----------------------------------------------------------------------

    def _extract_files(self, tool_name: str, tool_input: dict | str) -> list[str]:
        """Extrae archivos afectados del input de la herramienta."""
        files: list[str] = []
        if isinstance(tool_input, str):
            return files

        # Herramientas con file_path directo
        if "file_path" in tool_input:
            fp = tool_input["file_path"]
            if isinstance(fp, str):
                files.append(self._normalize_path(fp))

        # Herramientas con path
        if "path" in tool_input and tool_name in ("Glob", "Grep"):
            p = tool_input["path"]
            if isinstance(p, str):
                files.append(self._normalize_path(p))

        # Bash - extraer del comando
        if tool_name == "Bash" and "command" in tool_input:
            cmd = tool_input["command"]
            # Buscar patrones de archivos en el comando
            for part in cmd.split():
                if "/" in part and not part.startswith("-"):
                    clean = part.strip("\"'")
                    if "." in clean.split("/")[-1]:
                        files.append(self._normalize_path(clean))

        return files[:10]  # Limitar a 10 archivos

    def _normalize_path(self, path: str) -> str:
        """Normaliza path relativo al proyecto."""
        try:
            p = Path(path)
            if p.is_absolute():
                try:
                    return str(p.relative_to(self._root))
                except ValueError:
                    return str(p)
            return str(p)
        except Exception:
            return path

    def _summarize_input(self, tool_name: str, tool_input: dict | str) -> str:
        """Genera resumen legible del input."""
        if isinstance(tool_input, str):
            return tool_input[: self.MAX_INPUT_SUMMARY]

        if tool_name == "Read":
            fp = tool_input.get("file_path", "")
            return f"Leer {self._normalize_path(fp)}"

        if tool_name in ("Write", "Edit"):
            fp = tool_input.get("file_path", "")
            return f"{'Escribir' if tool_name == 'Write' else 'Editar'} {self._normalize_path(fp)}"

        if tool_name == "Bash":
            cmd = tool_input.get("command", "")
            desc = tool_input.get("description", "")
            return desc or cmd[: self.MAX_INPUT_SUMMARY]

        if tool_name in ("Glob", "Grep"):
            pattern = tool_input.get("pattern", "")
            path = tool_input.get("path", ".")
            return f"{tool_name}: '{pattern}' en {path}"

        if tool_name == "Task":
            desc = tool_input.get("description", "")
            agent = tool_input.get("subagent_type", "")
            return f"Agente {agent}: {desc}"

        # Generico
        return json.dumps(tool_input, ensure_ascii=False)[: self.MAX_INPUT_SUMMARY]

    def _summarize_output(self, output: str) -> str:
        """Genera resumen del output."""
        if not output:
            return ""
        # Truncar output largo
        if len(output) > self.MAX_OUTPUT_SUMMARY:
            return output[: self.MAX_OUTPUT_SUMMARY] + "..."
        return output

    # -----------------------------------------------------------------------
    # Query & Context Injection
    # -----------------------------------------------------------------------

    def get_session_observations(self, session_id: str, limit: int = 500) -> list[Observation]:
        """Obtiene todas las observaciones de una sesion."""
        return self._store.get_session_observations(session_id, limit)

    def get_recent_observations(
        self,
        limit: int = 50,
        min_priority: str | None = None,
    ) -> list[Observation]:
        """Obtiene observaciones recientes."""
        return self._store.get_recent_observations(limit, min_priority)

    def get_context_for_injection(self, max_observations: int = 15, max_tokens: int = 3000) -> str:
        """Genera bloque de contexto para inyectar en nuevas sesiones.

        Selecciona las observaciones mas relevantes de sesiones recientes
        y las formatea como contexto legible.

        Args:
            max_observations: Maximo de observaciones a incluir
            max_tokens: Maximo aproximado de tokens (4 chars = 1 token)

        Returns:
            String formateado para context injection
        """
        # Obtener observaciones recientes de alta prioridad
        observations = self._store.get_recent_observations(
            limit=max_observations * 2,
            min_priority="high",
        )

        if not observations:
            return ""

        # Filtrar y formatear
        lines: list[str] = [
            "## Contexto de Sesiones Anteriores",
            "",
        ]

        current_chars = sum(len(l) for l in lines)
        max_chars = max_tokens * 4
        included = 0

        # Agrupar por sesion
        by_session: dict[str, list[Observation]] = {}
        for obs in observations:
            by_session.setdefault(obs.session_id, []).append(obs)

        for sid, session_obs in list(by_session.items())[:5]:
            session_header = f"### Sesion: {sid}"
            if current_chars + len(session_header) > max_chars:
                break

            lines.append(session_header)
            current_chars += len(session_header)

            for obs in session_obs:
                line = f"- {obs.to_context_string()}"
                if current_chars + len(line) > max_chars:
                    break
                lines.append(line)
                current_chars += len(line)
                included += 1

                if included >= max_observations:
                    break

            lines.append("")
            if included >= max_observations:
                break

        return "\n".join(lines)

    def generate_session_summary(self, session_id: str) -> SessionObservationSummary:
        """Genera resumen estructurado de una sesion."""
        observations = self._store.get_session_observations(session_id)

        if not observations:
            return SessionObservationSummary(
                session_id=session_id,
                start_time=datetime.now().isoformat(),
                end_time=datetime.now().isoformat(),
                total_observations=0,
            )

        files_modified: set[str] = set()
        files_read: set[str] = set()
        tools_used: dict[str, int] = {}
        errors: list[str] = []
        decisions: list[str] = []
        successes = 0

        for obs in observations:
            tools_used[obs.tool_name] = tools_used.get(obs.tool_name, 0) + 1

            if obs.success:
                successes += 1
            elif obs.error_message:
                errors.append(f"{obs.tool_name}: {obs.error_message[:100]}")

            for f in obs.files_affected:
                if obs.observation_type in ("file_write", "file_edit"):
                    files_modified.add(f)
                elif obs.observation_type == "file_read":
                    files_read.add(f)

            if obs.observation_type == "decision":
                decisions.append(obs.tool_input_summary[:100])

        return SessionObservationSummary(
            session_id=session_id,
            start_time=observations[0].timestamp,
            end_time=observations[-1].timestamp,
            total_observations=len(observations),
            files_modified=sorted(files_modified),
            files_read=sorted(files_read),
            tools_used=tools_used,
            errors=errors[:20],
            decisions=decisions[:10],
            success_rate=successes / len(observations) if observations else 1.0,
        )

    def get_stats(self) -> dict:
        """Obtiene estadisticas del pipeline."""
        return self._store.get_stats()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_pipeline_instances: dict[str, ObservationPipeline] = {}


def get_observation_pipeline(project_root: str | None = None) -> ObservationPipeline:
    """Obtiene instancia singleton del pipeline para un proyecto."""
    root = Path(project_root).resolve() if project_root else Path(".").resolve()
    key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    if key not in _pipeline_instances:
        _pipeline_instances[key] = ObservationPipeline(str(root))
    return _pipeline_instances[key]
