"""Process Watcher — lanza procesos en background y matchea patrones regex en su output.

Pensado para reemplazar el flujo `bash run_in_background + polling` con
notificaciones en tiempo real cuando el stdout/stderr del proceso matchea
uno o mas patrones definidos por el usuario.

Casos tipicos:
    - `npm run tauri:dev` -> alert cuando aparezca "Compiled successfully"
      o cualquier "error[E".
    - `python start_gateway.py` -> alert en "Uvicorn running on" o
      "Address already in use".
    - `make test` -> alert al primer "FAILED" o al "passed" final.

Arquitectura:
    - subprocess.Popen + 2 threads (stdout/stderr) para streaming linea a linea.
    - SQLite WAL como store persistente de watches y matches (metadata, no output).
    - Output buffer circular en memoria (deque) por watch para servir `tail`.
    - Config por env var (max_watches, max_tail_lines, TTL).
    - Windows-friendly: usa TerminateProcess via Popen.terminate() en vez de killpg.

Este engine NO depende de Claude Code ni MCP; es agnostico del transporte.
El server MCP vive en .agent/mcp/watcher-server.py.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / schema
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
Importance = Literal["low", "high", "critical"]
WatchState = Literal["running", "exited", "killed", "error"]

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS watches (
    watch_id      TEXT PRIMARY KEY,
    cmd           TEXT NOT NULL,
    cwd           TEXT,
    pid           INTEGER,
    state         TEXT NOT NULL,
    exit_code     INTEGER,
    started_at    INTEGER NOT NULL,
    ended_at      INTEGER,
    patterns_json TEXT NOT NULL,
    match_count   INTEGER NOT NULL DEFAULT 0,
    label         TEXT
);

CREATE INDEX IF NOT EXISTS idx_watch_state ON watches(state);
CREATE INDEX IF NOT EXISTS idx_watch_started ON watches(started_at);

CREATE TABLE IF NOT EXISTS matches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_id      TEXT NOT NULL,
    pattern_label TEXT NOT NULL,
    importance    TEXT NOT NULL,
    line_text     TEXT NOT NULL,
    line_number   INTEGER NOT NULL,
    stream        TEXT NOT NULL,
    matched_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_match_watch ON matches(watch_id);
CREATE INDEX IF NOT EXISTS idx_match_time ON matches(matched_at);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Config y tipos publicos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WatcherConfig:
    """Configuracion del engine.

    Args:
        max_watches: limite de watches activos concurrentes.
        max_tail_lines: lineas de stdout/stderr a retener en memoria por watch.
        ttl_seconds: edad maxima de watches finalizados antes de ser purgados.
        allowed_cwds: si no vacio, cwd del proceso debe caer dentro de alguno.
        enable_gateway_notify: si true, POST a gateway :4747 en matches importantes.
        gateway_url: URL base del gateway local (override via env).
        enable_brain_ingest: si true, matches criticos van al Brain como pattern.
    """

    max_watches: int = 16
    max_tail_lines: int = 500
    ttl_seconds: int = 7 * 24 * 3600
    allowed_cwds: tuple[str, ...] = ()
    enable_gateway_notify: bool = True
    gateway_url: str = "http://127.0.0.1:4747"
    enable_brain_ingest: bool = False


@dataclass(frozen=True)
class Pattern:
    """Patron a matchear contra el output del proceso.

    Args:
        regex: expresion regular (compilada con re.search).
        label: nombre legible para el match (aparece en notificaciones).
        importance: low|high|critical — solo high y critical notifican al gateway.
        auto_brain_ingest: si true y es critical, ingesta al Brain.
    """

    regex: str
    label: str
    importance: Importance = "low"
    auto_brain_ingest: bool = False


@dataclass
class MatchEvent:
    """Un match concreto: linea que disparo el pattern."""

    watch_id: str
    pattern_label: str
    importance: Importance
    line_text: str
    line_number: int
    stream: Literal["stdout", "stderr"]
    matched_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "watch_id": self.watch_id,
            "pattern_label": self.pattern_label,
            "importance": self.importance,
            "line_text": self.line_text,
            "line_number": self.line_number,
            "stream": self.stream,
            "matched_at": self.matched_at,
        }


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


class WatcherError(RuntimeError):
    """Error generico del engine."""


class CwdNotAllowedError(WatcherError):
    """cwd esta fuera de allowed_cwds."""


class TooManyWatchesError(WatcherError):
    """Limite de watches activos alcanzado."""


class UnknownWatchError(WatcherError):
    """watch_id no existe."""


# ---------------------------------------------------------------------------
# Estado en memoria de un watch activo
# ---------------------------------------------------------------------------


@dataclass
class _ActiveWatch:
    """Handle en memoria de un proceso corriendo."""

    watch_id: str
    cmd: str
    cwd: str | None
    patterns: list[Pattern]
    compiled: list[re.Pattern[str]]
    label: str | None
    proc: subprocess.Popen[str]
    started_at: int
    threads: list[threading.Thread] = field(default_factory=list)
    tail_stdout: deque[tuple[int, str]] = field(default_factory=deque)
    tail_stderr: deque[tuple[int, str]] = field(default_factory=deque)
    line_counter_out: int = 0
    line_counter_err: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    state: WatchState = "running"
    exit_code: int | None = None
    ended_at: int | None = None
    match_count: int = 0
    finished_streaming: threading.Event = field(default_factory=threading.Event)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ProcessWatcher:
    """Engine de watch de procesos con matching de patrones regex.

    Uso:
        >>> w = ProcessWatcher(Path("~/.antigravity/watcher/state.db"))
        >>> wid = w.spawn("ls -la", patterns=[Pattern(r"\\.py$", "python files")])
        >>> status = w.status(wid)
        >>> w.kill(wid)
    """

    def __init__(
        self,
        state_path: Path,
        config: WatcherConfig | None = None,
    ) -> None:
        self.state_path = Path(state_path).expanduser().resolve()
        self.config = config or WatcherConfig()
        self._active: dict[str, _ActiveWatch] = {}
        self._active_lock = threading.Lock()
        self._init_store()

    # -- Storage bootstrap --------------------------------------------------

    def _init_store(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA_SQL)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            conn.commit()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(
            str(self.state_path),
            isolation_level=None,
            timeout=10.0,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # -- Helpers ------------------------------------------------------------

    def _validate_cwd(self, cwd: str | None) -> None:
        if not cwd or not self.config.allowed_cwds:
            return
        resolved = str(Path(cwd).expanduser().resolve())
        for root in self.config.allowed_cwds:
            root_resolved = str(Path(root).expanduser().resolve())
            if resolved == root_resolved or resolved.startswith(root_resolved + os.sep):
                return
        raise CwdNotAllowedError(
            f"cwd {resolved!r} fuera de allowed_cwds={self.config.allowed_cwds}"
        )

    def _count_running(self) -> int:
        with self._active_lock:
            return sum(1 for w in self._active.values() if w.state == "running")

    _MAX_REGEX_LEN = 512
    _REDOS_SUSPECTS = (
        re.compile(r"\([^)]*[+*]\s*\)\s*[+*]"),
        re.compile(r"\([^)]*\|[^)]*\)\s*[+*]"),
        re.compile(r"(?:\.\*){2,}"),
        re.compile(r"(?:\.\+){2,}"),
    )

    def _validate_regex_safety(self, regex: str, label: str) -> None:
        if len(regex) > self._MAX_REGEX_LEN:
            raise WatcherError(
                f"regex en pattern {label!r} excede {self._MAX_REGEX_LEN} chars"
            )
        for suspect in self._REDOS_SUSPECTS:
            if suspect.search(regex):
                raise WatcherError(
                    f"regex en pattern {label!r} contiene patron potencialmente "
                    f"catastrofico (nested quantifier o repeticion .*/.+ excesiva)"
                )

    def _parse_patterns(self, raw: list[Any]) -> tuple[list[Pattern], list[re.Pattern[str]]]:
        patterns: list[Pattern] = []
        compiled: list[re.Pattern[str]] = []
        for item in raw or []:
            if isinstance(item, Pattern):
                p = item
            elif isinstance(item, dict):
                p = Pattern(
                    regex=str(item.get("regex", "")).strip(),
                    label=str(item.get("label", "")).strip() or "unnamed",
                    importance=item.get("importance", "low"),  # type: ignore[arg-type]
                    auto_brain_ingest=bool(item.get("auto_brain_ingest", False)),
                )
            else:
                continue
            if not p.regex:
                continue
            self._validate_regex_safety(p.regex, p.label)
            try:
                compiled.append(re.compile(p.regex))
            except re.error as exc:
                raise WatcherError(f"regex invalida en pattern {p.label!r}: {exc}") from exc
            patterns.append(p)
        return patterns, compiled

    # -- API publica: spawn / status / kill / list / tail -------------------

    def spawn(
        self,
        cmd: str,
        patterns: list[Any] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        label: str | None = None,
    ) -> str:
        """Lanza un proceso en background y empieza a matchear patterns.

        Args:
            cmd: comando a ejecutar (se parsea con shlex.split, shell=False).
            patterns: lista de Pattern o dicts con {regex, label, importance}.
            cwd: directorio de trabajo (validado contra allowed_cwds si hay).
            env: variables de entorno adicionales.
            label: alias humano del watch.

        Returns:
            watch_id (UUID-ish).
        """
        cmd = (cmd or "").strip()
        if not cmd:
            raise WatcherError("cmd es requerido")

        self._validate_cwd(cwd)

        if self._count_running() >= self.config.max_watches:
            raise TooManyWatchesError(
                f"max_watches={self.config.max_watches} alcanzado; "
                "termina alguno con watch_kill antes de lanzar otro"
            )

        parsed_patterns, compiled = self._parse_patterns(patterns or [])

        try:
            argv = shlex.split(cmd, posix=(os.name != "nt"))
        except ValueError as exc:
            raise WatcherError(f"no se pudo parsear cmd: {exc}") from exc

        spawn_env = None
        if env:
            spawn_env = {**os.environ, **env}

        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                cwd=cwd or None,
                env=spawn_env,
                text=True,
                bufsize=1,
                errors="replace",
                shell=False,
            )
        except FileNotFoundError as exc:
            raise WatcherError(f"comando no encontrado: {argv[0]!r}") from exc
        except OSError as exc:
            raise WatcherError(f"no se pudo spawnear: {exc}") from exc

        watch_id = f"w-{uuid.uuid4().hex[:12]}"
        started_at = int(time.time())

        active = _ActiveWatch(
            watch_id=watch_id,
            cmd=cmd,
            cwd=cwd,
            patterns=parsed_patterns,
            compiled=compiled,
            label=label,
            proc=proc,
            started_at=started_at,
            tail_stdout=deque(maxlen=self.config.max_tail_lines),
            tail_stderr=deque(maxlen=self.config.max_tail_lines),
        )

        with self._active_lock:
            self._active[watch_id] = active

        self._persist_new_watch(active)

        t_out = threading.Thread(
            target=self._stream_reader,
            args=(active, "stdout"),
            daemon=True,
            name=f"watcher-{watch_id}-stdout",
        )
        t_err = threading.Thread(
            target=self._stream_reader,
            args=(active, "stderr"),
            daemon=True,
            name=f"watcher-{watch_id}-stderr",
        )
        t_wait = threading.Thread(
            target=self._wait_exit,
            args=(active,),
            daemon=True,
            name=f"watcher-{watch_id}-wait",
        )
        active.threads = [t_out, t_err, t_wait]
        for t in active.threads:
            t.start()

        logger.info(
            "watch %s iniciado: pid=%s cmd=%r patterns=%d",
            watch_id,
            proc.pid,
            cmd,
            len(parsed_patterns),
        )
        return watch_id

    def status(self, watch_id: str) -> dict[str, Any]:
        active = self._get_active(watch_id)
        if active is not None:
            with active.lock:
                return self._active_to_dict(active, include_tail=False)
        row = self._load_persisted(watch_id)
        if row is None:
            raise UnknownWatchError(f"watch_id desconocido: {watch_id!r}")
        return self._row_to_status(row)

    def tail(self, watch_id: str, lines: int = 50, stream: str = "both") -> dict[str, Any]:
        active = self._get_active(watch_id)
        lines = max(1, min(lines, self.config.max_tail_lines))
        stdout_tail: list[dict[str, Any]] = []
        stderr_tail: list[dict[str, Any]] = []
        if active is not None:
            # Wait for streams to finish so tail returns complete output.
            active.finished_streaming.wait(timeout=2.0)
            with active.lock:
                if stream in ("stdout", "both"):
                    stdout_tail = [
                        {"line": n, "text": t} for n, t in list(active.tail_stdout)[-lines:]
                    ]
                if stream in ("stderr", "both"):
                    stderr_tail = [
                        {"line": n, "text": t} for n, t in list(active.tail_stderr)[-lines:]
                    ]
            return {
                "watch_id": watch_id,
                "state": active.state,
                "stdout": stdout_tail,
                "stderr": stderr_tail,
            }
        # si ya termino, el tail vive en memoria solo mientras este activo.
        # No persistimos output lines a disco por costo — decision de diseno.
        row = self._load_persisted(watch_id)
        if row is None:
            raise UnknownWatchError(f"watch_id desconocido: {watch_id!r}")
        return {
            "watch_id": watch_id,
            "state": row["state"],
            "stdout": [],
            "stderr": [],
            "note": "output tail no disponible despues de fin de proceso",
        }

    def kill(self, watch_id: str, signal_term_only: bool = False) -> bool:
        active = self._get_active(watch_id)
        if active is None:
            row = self._load_persisted(watch_id)
            if row is None:
                raise UnknownWatchError(f"watch_id desconocido: {watch_id!r}")
            return False
        with active.lock:
            if active.state != "running":
                return False
            # Marcamos "killed" antes de terminar para ganar la carrera con _wait_exit.
            active.state = "killed"
        try:
            active.proc.terminate()
            try:
                active.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                if not signal_term_only:
                    active.proc.kill()
                    active.proc.wait(timeout=2.0)
        except Exception as exc:
            logger.warning("kill %s fallo: %s", watch_id, exc)
            return False
        with active.lock:
            active.exit_code = active.proc.returncode
            active.ended_at = int(time.time())
        self._persist_final_state(active)
        return True

    def list_watches(self, include_finished: bool = True) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        with self._active_lock:
            for active in self._active.values():
                with active.lock:
                    out.append(self._active_to_dict(active, include_tail=False))
        if include_finished:
            with self._conn() as conn:
                for row in conn.execute(
                    "SELECT * FROM watches WHERE state != 'running' "
                    "ORDER BY started_at DESC LIMIT 50"
                ):
                    if row["watch_id"] not in self._active:
                        out.append(self._row_to_status(row))
        return out

    def matches(self, watch_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self._get_active(watch_id) is None and self._load_persisted(watch_id) is None:
            raise UnknownWatchError(f"watch_id desconocido: {watch_id!r}")
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM matches WHERE watch_id = ? "
                "ORDER BY matched_at DESC LIMIT ?",
                (watch_id, max(1, min(limit, 500))),
            ).fetchall()
        return [
            {
                "pattern_label": r["pattern_label"],
                "importance": r["importance"],
                "line_text": r["line_text"],
                "line_number": r["line_number"],
                "stream": r["stream"],
                "matched_at": r["matched_at"],
            }
            for r in rows
        ]

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM watches").fetchone()["n"]
            by_state = {
                r["state"]: r["n"]
                for r in conn.execute(
                    "SELECT state, COUNT(*) AS n FROM watches GROUP BY state"
                )
            }
            total_matches = conn.execute("SELECT COUNT(*) AS n FROM matches").fetchone()["n"]
        return {
            "total_watches": total,
            "by_state": by_state,
            "total_matches": total_matches,
            "active_in_memory": self._count_running(),
        }

    def cleanup_expired(self) -> int:
        cutoff = int(time.time()) - self.config.ttl_seconds
        with self._conn() as conn:
            expired_ids = [
                row["watch_id"]
                for row in conn.execute(
                    "SELECT watch_id FROM watches "
                    "WHERE ended_at IS NOT NULL AND ended_at < ?",
                    (cutoff,),
                )
            ]
            cur = conn.execute(
                "DELETE FROM matches WHERE watch_id IN ("
                "  SELECT watch_id FROM watches WHERE ended_at IS NOT NULL AND ended_at < ?"
                ")",
                (cutoff,),
            )
            removed_matches = cur.rowcount
            cur = conn.execute(
                "DELETE FROM watches WHERE ended_at IS NOT NULL AND ended_at < ?",
                (cutoff,),
            )
            conn.commit()
            removed_watches = cur.rowcount
        # Tambien limpiamos el cache en memoria para mantener coherencia.
        with self._active_lock:
            for wid in expired_ids:
                if wid in self._active and self._active[wid].state != "running":
                    del self._active[wid]
        return removed_matches + removed_watches

    # -- Streaming internals ------------------------------------------------

    def _stream_reader(self, active: _ActiveWatch, stream_name: str) -> None:
        """Thread: lee linea a linea uno de los streams y matchea patterns."""
        stream = active.proc.stdout if stream_name == "stdout" else active.proc.stderr
        if stream is None:
            return
        try:
            for raw_line in iter(stream.readline, ""):
                if raw_line == "":
                    break
                text = raw_line.rstrip("\r\n")
                with active.lock:
                    if stream_name == "stdout":
                        active.line_counter_out += 1
                        line_number = active.line_counter_out
                        active.tail_stdout.append((line_number, text))
                    else:
                        active.line_counter_err += 1
                        line_number = active.line_counter_err
                        active.tail_stderr.append((line_number, text))
                self._check_patterns(active, text, line_number, stream_name)
        except Exception as exc:
            logger.warning("stream_reader %s/%s fallo: %s", active.watch_id, stream_name, exc)
        finally:
            try:
                stream.close()
            except Exception:
                pass
            active.finished_streaming.set()

    def _wait_exit(self, active: _ActiveWatch) -> None:
        """Thread: espera la terminacion y persiste el estado final."""
        try:
            exit_code = active.proc.wait()
        except Exception as exc:
            logger.warning("wait %s fallo: %s", active.watch_id, exc)
            exit_code = -1
        with active.lock:
            if active.state == "running":
                # Termino solo — exito si exit_code==0, sino exited con codigo != 0.
                active.state = "exited" if exit_code is not None else "error"
                active.exit_code = exit_code
                active.ended_at = int(time.time())
            elif active.state == "killed" and active.ended_at is None:
                # kill() todavia no termino de setear metadata; ayudamos acá.
                active.exit_code = exit_code
                active.ended_at = int(time.time())
        self._persist_final_state(active)
        logger.info(
            "watch %s termino: state=%s exit_code=%s matches=%d",
            active.watch_id,
            active.state,
            active.exit_code,
            active.match_count,
        )

    _MAX_LINE_FOR_REGEX = 4096

    def _check_patterns(
        self,
        active: _ActiveWatch,
        line: str,
        line_number: int,
        stream_name: str,
    ) -> None:
        # Limitar el input al regex engine: aunque el patron pase la validacion
        # heuristica, lineas muy largas amplifican cualquier backtracking residual.
        scan_text = line if len(line) <= self._MAX_LINE_FOR_REGEX else line[: self._MAX_LINE_FOR_REGEX]
        for pattern, compiled in zip(active.patterns, active.compiled, strict=True):
            if compiled.search(scan_text):
                event = MatchEvent(
                    watch_id=active.watch_id,
                    pattern_label=pattern.label,
                    importance=pattern.importance,
                    line_text=line[:500],
                    line_number=line_number,
                    stream=stream_name,  # type: ignore[arg-type]
                    matched_at=int(time.time()),
                )
                with active.lock:
                    active.match_count += 1
                self._persist_match(event)
                if pattern.importance in ("high", "critical"):
                    self._notify_gateway(active, event, pattern)
                if pattern.importance == "critical" and pattern.auto_brain_ingest:
                    self._ingest_brain(active, event, pattern)

    # -- Persistence helpers -----------------------------------------------

    def _persist_new_watch(self, active: _ActiveWatch) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO watches "
                "(watch_id, cmd, cwd, pid, state, started_at, patterns_json, label) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    active.watch_id,
                    active.cmd,
                    active.cwd,
                    active.proc.pid,
                    active.state,
                    active.started_at,
                    json.dumps(
                        [
                            {
                                "regex": p.regex,
                                "label": p.label,
                                "importance": p.importance,
                                "auto_brain_ingest": p.auto_brain_ingest,
                            }
                            for p in active.patterns
                        ]
                    ),
                    active.label,
                ),
            )
            conn.commit()

    def _persist_final_state(self, active: _ActiveWatch) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE watches SET state = ?, exit_code = ?, ended_at = ?, "
                "match_count = ? WHERE watch_id = ?",
                (
                    active.state,
                    active.exit_code,
                    active.ended_at,
                    active.match_count,
                    active.watch_id,
                ),
            )
            conn.commit()

    def _persist_match(self, event: MatchEvent) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO matches "
                "(watch_id, pattern_label, importance, line_text, line_number, stream, matched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.watch_id,
                    event.pattern_label,
                    event.importance,
                    event.line_text,
                    event.line_number,
                    event.stream,
                    event.matched_at,
                ),
            )
            conn.commit()

    def _load_persisted(self, watch_id: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM watches WHERE watch_id = ?", (watch_id,)
            ).fetchone()

    # -- Notificaciones best-effort ---------------------------------------

    def _notify_gateway(
        self,
        active: _ActiveWatch,
        event: MatchEvent,
        pattern: Pattern,
    ) -> None:
        if not self.config.enable_gateway_notify:
            return
        try:
            import urllib.error
            import urllib.request

            payload = json.dumps(
                {
                    "type": "watcher.match",
                    "watch_id": event.watch_id,
                    "label": active.label or active.cmd[:60],
                    "pattern_label": pattern.label,
                    "importance": pattern.importance,
                    "line_text": event.line_text,
                    "line_number": event.line_number,
                    "stream": event.stream,
                    "matched_at": event.matched_at,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.config.gateway_url.rstrip('/')}/v1/watcher/events",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.5)
        except Exception as exc:
            logger.debug("gateway notify skip: %s", exc)

    def _ingest_brain(
        self,
        active: _ActiveWatch,
        event: MatchEvent,
        pattern: Pattern,
    ) -> None:
        if not self.config.enable_brain_ingest:
            return
        try:
            agent_dir = Path(__file__).parent.parent
            if str(agent_dir) not in sys.path:
                sys.path.insert(0, str(agent_dir))
            from core.brain import Brain  # type: ignore[import-not-found]

            brain_dir = agent_dir / "brain"
            if not brain_dir.exists():
                return
            brain = Brain(brain_dir, app_id="nexus-mother")
            brain.ingest(
                title=f"watcher-match: {pattern.label}",
                context=(
                    f"Proceso: `{active.cmd}`\n\n"
                    f"Match critico en linea {event.line_number} ({event.stream}):\n\n"
                    f"```\n{event.line_text}\n```"
                ),
                area="ops",
                tags=["watcher", pattern.label, pattern.importance],
                node_type="pattern",
                importance="high",
            )
        except Exception as exc:
            logger.debug("brain ingest skip: %s", exc)

    # -- Internals ---------------------------------------------------------

    def _get_active(self, watch_id: str) -> _ActiveWatch | None:
        with self._active_lock:
            return self._active.get(watch_id)

    def _active_to_dict(
        self,
        active: _ActiveWatch,
        include_tail: bool = False,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "watch_id": active.watch_id,
            "cmd": active.cmd,
            "cwd": active.cwd,
            "label": active.label,
            "pid": active.proc.pid,
            "state": active.state,
            "exit_code": active.exit_code,
            "started_at": active.started_at,
            "ended_at": active.ended_at,
            "match_count": active.match_count,
            "patterns": [
                {
                    "regex": p.regex,
                    "label": p.label,
                    "importance": p.importance,
                }
                for p in active.patterns
            ],
        }
        if include_tail:
            out["stdout_tail"] = [
                {"line": n, "text": t} for n, t in list(active.tail_stdout)[-20:]
            ]
            out["stderr_tail"] = [
                {"line": n, "text": t} for n, t in list(active.tail_stderr)[-20:]
            ]
        return out

    def _row_to_status(self, row: sqlite3.Row) -> dict[str, Any]:
        patterns = []
        try:
            patterns = json.loads(row["patterns_json"] or "[]")
        except json.JSONDecodeError:
            pass
        return {
            "watch_id": row["watch_id"],
            "cmd": row["cmd"],
            "cwd": row["cwd"],
            "label": row["label"],
            "pid": row["pid"],
            "state": row["state"],
            "exit_code": row["exit_code"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "match_count": row["match_count"],
            "patterns": patterns,
        }


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def default_state_path() -> Path:
    """Ruta por defecto del store SQLite.

    Override via env ANTIGRAVITY_WATCHER_STATE.
    """
    override = os.environ.get("ANTIGRAVITY_WATCHER_STATE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".antigravity" / "watcher" / "state.db"
