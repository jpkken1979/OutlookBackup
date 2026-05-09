"""Delta Reader — re-read deduplication engine for Claude Code sessions.

Cuando un archivo se lee mas de una vez en la misma sesion, el engine
devuelve solo el diff unificado respecto de la lectura anterior en vez
del contenido completo. Esto reduce drasticamente el consumo de tokens
en sesiones largas donde los mismos archivos se leen/editan varias veces.

Arquitectura:
    - Pure stdlib: zero external dependencies (difflib, hashlib, sqlite3).
    - SQLite como store persistente (WAL mode, single-writer friendly).
    - Estado keyed por (session_id, resolved_path).
    - Politica configurable: min_lines, max_bytes, delta_ratio_threshold.

Decisiones clave:
    - Se detecta edicion externa via (mtime, size) — si cambian fuera
      de nuestro flujo, la snapshot se invalida y se devuelve full.
    - Binarios se rechazan (null byte en primeros 8192 bytes).
    - Diffs > 40% del tamano original devuelven full (no vale la pena).
    - Archivos < 50 lineas devuelven full siempre (overhead no justificado).

Este engine NO depende de Claude Code ni MCP; es agnostico del transporte.
El server MCP vive en .agent/mcp/delta-reader-server.py.

Referencia: inspirado en el Delta Mode de alexgreensh/token-optimizer,
reimplementado desde cero bajo licencia del proyecto.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants and schema
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
_MAX_READ_BYTES = 50_000_000
"""Hard-limit absoluto de I/O. Archivos mas grandes se rechazan antes de leer."""


class FileTooLargeError(OSError):
    """Archivo excede el hard-limit de I/O para el engine."""


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    session_id   TEXT NOT NULL,
    resolved_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content      TEXT NOT NULL,
    mtime_ns     INTEGER NOT NULL,
    size_bytes   INTEGER NOT NULL,
    turn_count   INTEGER NOT NULL DEFAULT 0,
    first_read_at INTEGER NOT NULL,
    last_read_at  INTEGER NOT NULL,
    PRIMARY KEY (session_id, resolved_path)
);

CREATE INDEX IF NOT EXISTS idx_session ON snapshots(session_id);
CREATE INDEX IF NOT EXISTS idx_last_read ON snapshots(last_read_at);

CREATE TABLE IF NOT EXISTS stats (
    session_id    TEXT PRIMARY KEY,
    reads_total   INTEGER NOT NULL DEFAULT 0,
    reads_full    INTEGER NOT NULL DEFAULT 0,
    reads_delta   INTEGER NOT NULL DEFAULT 0,
    reads_unchanged INTEGER NOT NULL DEFAULT 0,
    reads_external_edit INTEGER NOT NULL DEFAULT 0,
    bytes_full    INTEGER NOT NULL DEFAULT 0,
    bytes_served  INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Config and result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeltaReaderConfig:
    """Configuracion del engine.

    Todos los thresholds son ajustables sin tocar codigo. Valores default
    fueron elegidos por el tradeoff observado en codebases Python/TS/Rust.
    """

    min_lines_for_delta: int = 50
    """Archivos con menos lineas siempre devuelven full."""

    max_file_bytes: int = 2_000_000
    """Archivos mas grandes devuelven full (diff overhead alto)."""

    delta_ratio_threshold: float = 0.4
    """Si diff/full > threshold, devolver full."""

    session_ttl_seconds: int = 7 * 24 * 3600
    """TTL de snapshots; mas viejas se limpian."""

    unified_diff_context: int = 3
    """Lineas de contexto en diffs unificados."""

    allowed_roots: tuple[str, ...] = ()
    """Si no es vacio, paths deben estar dentro de alguno de estos roots."""

    def __post_init__(self) -> None:
        if self.min_lines_for_delta < 1:
            raise ValueError("min_lines_for_delta debe ser >= 1")
        if self.max_file_bytes < 1024:
            raise ValueError("max_file_bytes debe ser >= 1024")
        if not 0 < self.delta_ratio_threshold <= 1.0:
            raise ValueError("delta_ratio_threshold debe estar en (0, 1]")


ReadMode = Literal["full", "delta", "unchanged", "external_edit", "error"]


@dataclass
class ReadResult:
    """Resultado de una lectura delta-aware."""

    mode: ReadMode
    path: str
    session_id: str
    content: str = ""
    """Contenido completo (mode=full) o marker (mode=unchanged)."""

    diff: str = ""
    """Diff unificado (solo mode=delta)."""

    prior_turn: int | None = None
    """Numero de turn de la snapshot anterior."""

    stats: dict[str, Any] = field(default_factory=dict)
    """Metricas: bytes_full, bytes_served, savings_ratio, lines, etc."""

    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializa para respuesta JSON-RPC."""
        d: dict[str, Any] = {
            "mode": self.mode,
            "path": self.path,
            "session_id": self.session_id,
            "stats": self.stats,
        }
        if self.mode == "full":
            d["content"] = self.content
        elif self.mode == "delta":
            d["diff"] = self.diff
            d["prior_turn"] = self.prior_turn
        elif self.mode in ("unchanged", "external_edit"):
            d["content"] = self.content
            d["prior_turn"] = self.prior_turn
        elif self.mode == "error":
            d["error"] = self.error
        return d


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DeltaReader:
    """Motor de lectura con deduplicacion por diff.

    Thread-safety: SQLite con isolation_level=None y manejo explicito de
    transacciones por call. Un solo proceso writer (el MCP server) se
    asume, pero WAL mode tolera readers concurrentes si se expone por HTTP.

    Uso:
        reader = DeltaReader(Path("/tmp/state.db"))
        result = reader.read("/ruta/archivo.py", session_id="s1")
        if result.mode == "full":
            enviar result.content al modelo
        elif result.mode == "delta":
            enviar result.diff al modelo
    """

    def __init__(
        self,
        state_path: Path,
        config: DeltaReaderConfig | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.config = config or DeltaReaderConfig()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # -- schema / connection -------------------------------------------------

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            str(self.state_path),
            timeout=10.0,
            isolation_level=None,  # autocommit; manage txns manually
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # -- public API ----------------------------------------------------------

    def read(
        self,
        path: str | Path,
        session_id: str,
        force_full: bool = False,
    ) -> ReadResult:
        """Leer un archivo con deduplicacion por diff.

        Args:
            path: ruta al archivo (relativa o absoluta).
            session_id: id logico de la sesion del caller.
            force_full: si True, ignora snapshots y devuelve full.

        Returns:
            ReadResult con mode, content/diff y stats.
        """
        if not session_id:
            return ReadResult(
                mode="error",
                path=str(path),
                session_id=session_id,
                error="session_id es requerido",
            )

        try:
            resolved = self._resolve_path(path)
        except ValueError as exc:
            return ReadResult(
                mode="error",
                path=str(path),
                session_id=session_id,
                error=str(exc),
            )

        try:
            content, mtime_ns, size = self._read_file(resolved)
        except FileNotFoundError:
            return ReadResult(
                mode="error",
                path=str(resolved),
                session_id=session_id,
                error=f"Archivo no existe: {resolved}",
            )
        except IsADirectoryError:
            return ReadResult(
                mode="error",
                path=str(resolved),
                session_id=session_id,
                error=f"Es un directorio: {resolved}",
            )
        except FileTooLargeError as exc:
            return ReadResult(
                mode="error",
                path=str(resolved),
                session_id=session_id,
                error=str(exc),
            )
        except UnicodeDecodeError:
            return ReadResult(
                mode="error",
                path=str(resolved),
                session_id=session_id,
                error="Archivo binario (no UTF-8)",
            )

        if self._is_binary(content):
            return ReadResult(
                mode="error",
                path=str(resolved),
                session_id=session_id,
                error="Archivo binario detectado (null byte)",
            )

        content_hash = self._hash(content)
        line_count = content.count("\n") + 1
        resolved_str = str(resolved)

        prior = None if force_full else self._load_snapshot(session_id, resolved_str)
        result = self._decide_mode(
            session_id=session_id,
            resolved=resolved_str,
            content=content,
            content_hash=content_hash,
            mtime_ns=mtime_ns,
            size=size,
            line_count=line_count,
            prior=prior,
        )
        self._persist_and_track(
            session_id=session_id,
            resolved=resolved_str,
            content=content,
            content_hash=content_hash,
            mtime_ns=mtime_ns,
            size=size,
            prior=prior,
            result=result,
        )
        return result

    def reset_session(self, session_id: str) -> int:
        """Elimina todas las snapshots de una sesion. Devuelve cuantas borro."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM snapshots WHERE session_id = ?",
                (session_id,),
            )
            conn.execute(
                "DELETE FROM stats WHERE session_id = ?",
                (session_id,),
            )
            return cur.rowcount

    def session_stats(self, session_id: str) -> dict[str, Any]:
        """Metricas acumuladas de una sesion."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM stats WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            snap_count = conn.execute(
                "SELECT COUNT(*) AS n FROM snapshots WHERE session_id = ?",
                (session_id,),
            ).fetchone()["n"]

        if row is None:
            return {
                "session_id": session_id,
                "reads_total": 0,
                "snapshots": 0,
                "savings_ratio": 0.0,
            }

        bytes_full = row["bytes_full"] or 0
        bytes_served = row["bytes_served"] or 0
        savings = 0.0
        if bytes_full > 0:
            savings = max(0.0, 1.0 - (bytes_served / bytes_full))

        return {
            "session_id": session_id,
            "reads_total": row["reads_total"],
            "reads_full": row["reads_full"],
            "reads_delta": row["reads_delta"],
            "reads_unchanged": row["reads_unchanged"],
            "reads_external_edit": row["reads_external_edit"],
            "bytes_full": bytes_full,
            "bytes_served": bytes_served,
            "savings_ratio": round(savings, 4),
            "snapshots": snap_count,
            "created_at": row["created_at"],
        }

    def cleanup_expired(self) -> int:
        """Elimina snapshots mas viejas que session_ttl_seconds. Devuelve borradas."""
        cutoff = int(time.time()) - self.config.session_ttl_seconds
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM snapshots WHERE last_read_at < ?",
                (cutoff,),
            )
            return cur.rowcount

    # -- core logic ----------------------------------------------------------

    def _decide_mode(
        self,
        session_id: str,
        resolved: str,
        content: str,
        content_hash: str,
        mtime_ns: int,
        size: int,
        line_count: int,
        prior: sqlite3.Row | None,
    ) -> ReadResult:
        """Politica pura: dado el archivo y prior, decide mode."""
        base_stats = {
            "bytes_full": size,
            "lines": line_count,
            "hash": content_hash[:12],
        }

        # Primera vez en la sesion, archivo chico, o muy grande → full.
        if prior is None:
            return ReadResult(
                mode="full",
                path=resolved,
                session_id=session_id,
                content=content,
                stats={
                    **base_stats,
                    "bytes_served": size,
                    "reason": "first_read",
                },
            )

        if line_count < self.config.min_lines_for_delta:
            return ReadResult(
                mode="full",
                path=resolved,
                session_id=session_id,
                content=content,
                stats={
                    **base_stats,
                    "bytes_served": size,
                    "reason": "file_too_small",
                },
            )

        if size > self.config.max_file_bytes:
            return ReadResult(
                mode="full",
                path=resolved,
                session_id=session_id,
                content=content,
                stats={
                    **base_stats,
                    "bytes_served": size,
                    "reason": "file_too_large",
                },
            )

        prior_hash = prior["content_hash"]
        prior_mtime = prior["mtime_ns"]
        prior_size = prior["size_bytes"]
        prior_turn = prior["turn_count"]

        # Hash identico → unchanged marker (casi cero tokens).
        if prior_hash == content_hash:
            marker = f"[sin cambios desde turn {prior_turn}; hash={content_hash[:12]}]"
            return ReadResult(
                mode="unchanged",
                path=resolved,
                session_id=session_id,
                content=marker,
                prior_turn=prior_turn,
                stats={
                    **base_stats,
                    "bytes_served": len(marker.encode("utf-8")),
                    "reason": "hash_match",
                },
            )

        # Edicion externa sospechosa: mtime cambio muy fuera de rango esperado.
        # No es un fallo, solo devolvemos full para que el modelo vea todo.
        external_edit = prior_mtime != mtime_ns and abs(size - prior_size) > max(
            1024, prior_size // 2
        )
        if external_edit:
            return ReadResult(
                mode="external_edit",
                path=resolved,
                session_id=session_id,
                content=content,
                prior_turn=prior_turn,
                stats={
                    **base_stats,
                    "bytes_served": size,
                    "reason": "external_edit_detected",
                    "prior_size": prior_size,
                    "size_delta": size - prior_size,
                },
            )

        # Caso principal: diff.
        diff = self._compute_diff(prior["content"], content, resolved)
        diff_bytes = len(diff.encode("utf-8"))

        if size == 0:
            ratio = 1.0
        else:
            ratio = diff_bytes / size

        if ratio > self.config.delta_ratio_threshold:
            return ReadResult(
                mode="full",
                path=resolved,
                session_id=session_id,
                content=content,
                stats={
                    **base_stats,
                    "bytes_served": size,
                    "reason": "diff_too_large",
                    "diff_ratio": round(ratio, 3),
                },
            )

        return ReadResult(
            mode="delta",
            path=resolved,
            session_id=session_id,
            diff=diff,
            prior_turn=prior_turn,
            stats={
                **base_stats,
                "bytes_served": diff_bytes,
                "reason": "delta_compressed",
                "diff_ratio": round(ratio, 3),
                "savings_ratio": round(1.0 - ratio, 3) if size else 0.0,
            },
        )

    def _compute_diff(self, old: str, new: str, label: str) -> str:
        """Diff unificado entre old y new con label en los headers."""
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        # difflib requiere que cada linea termine en \n para output estable.
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        diff_iter = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
            n=self.config.unified_diff_context,
        )
        return "".join(diff_iter)

    # -- persistence ---------------------------------------------------------

    def _load_snapshot(
        self,
        session_id: str,
        resolved: str,
    ) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM snapshots WHERE session_id = ? AND resolved_path = ?",
                (session_id, resolved),
            ).fetchone()

    def _persist_and_track(
        self,
        session_id: str,
        resolved: str,
        content: str,
        content_hash: str,
        mtime_ns: int,
        size: int,
        prior: sqlite3.Row | None,
        result: ReadResult,
    ) -> None:
        """Upsert snapshot + update stats en una unica transaccion."""
        now = int(time.time())
        new_turn = (prior["turn_count"] + 1) if prior is not None else 1

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            try:
                conn.execute(
                    """
                    INSERT INTO snapshots(
                        session_id, resolved_path, content_hash, content,
                        mtime_ns, size_bytes, turn_count,
                        first_read_at, last_read_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, resolved_path) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        content      = excluded.content,
                        mtime_ns     = excluded.mtime_ns,
                        size_bytes   = excluded.size_bytes,
                        turn_count   = excluded.turn_count,
                        last_read_at = excluded.last_read_at
                    """,
                    (
                        session_id,
                        resolved,
                        content_hash,
                        content,
                        mtime_ns,
                        size,
                        new_turn,
                        prior["first_read_at"] if prior else now,
                        now,
                    ),
                )

                bytes_served = result.stats.get("bytes_served", size)
                mode_col = {
                    "full": "reads_full",
                    "delta": "reads_delta",
                    "unchanged": "reads_unchanged",
                    "external_edit": "reads_external_edit",
                }.get(result.mode)

                if mode_col is not None:
                    conn.execute(
                        f"""
                        INSERT INTO stats(
                            session_id, reads_total, {mode_col},
                            bytes_full, bytes_served, created_at
                        ) VALUES (?, 1, 1, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            reads_total = reads_total + 1,
                            {mode_col}  = {mode_col} + 1,
                            bytes_full  = bytes_full + excluded.bytes_full,
                            bytes_served = bytes_served + excluded.bytes_served
                        """,
                        (session_id, size, bytes_served, now),
                    )
                conn.execute("COMMIT;")
            except Exception:
                conn.execute("ROLLBACK;")
                raise

    # -- helpers -------------------------------------------------------------

    def _resolve_path(self, path: str | Path) -> Path:
        """Resuelve y valida path contra allowed_roots.

        Fail-closed: si allowed_roots esta vacio, rechaza por seguridad.
        Sin esta defensa el reader podria abrir cualquier path del filesystem
        (~/.ssh, /etc/passwd, .env con tokens) si por error la config llega vacia.
        """
        p = Path(path).expanduser().resolve()
        if not self.config.allowed_roots:
            raise ValueError(
                f"DeltaReader sin allowed_roots configurados; rechazando lectura de {p}",
            )
        allowed = [Path(r).expanduser().resolve() for r in self.config.allowed_roots]
        if not any(_is_within(p, root) for root in allowed):
            raise ValueError(
                f"Path fuera de roots permitidos: {p}",
            )
        return p

    @staticmethod
    def _read_file(path: Path) -> tuple[str, int, int]:
        """Lee archivo como UTF-8 y devuelve (content, mtime_ns, size).

        Raises:
            FileNotFoundError: si el path no existe.
            IsADirectoryError: si el path es un directorio.
            FileTooLargeError: si el archivo supera _MAX_READ_BYTES.
            UnicodeDecodeError: si no es texto UTF-8 valido.
        """
        if path.is_dir():
            raise IsADirectoryError(str(path))
        stat = path.stat()  # raises FileNotFoundError si no existe
        if stat.st_size > _MAX_READ_BYTES:
            raise FileTooLargeError(
                f"Archivo supera el limite de {_MAX_READ_BYTES} bytes "
                f"(size={stat.st_size}). Usa Read nativo para archivos enormes.",
            )
        content = path.read_text(encoding="utf-8")
        return content, stat.st_mtime_ns, stat.st_size

    @staticmethod
    def _is_binary(content: str) -> bool:
        """Heuristica: null byte en los primeros 8192 chars."""
        return "\x00" in content[:8192]

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    """True si path esta dentro de root (o es root)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------


def default_state_path() -> Path:
    """Ubicacion estandar del SQLite del delta reader.

    Honra ANTIGRAVITY_DELTA_STATE si esta seteada, sino usa
    ~/.antigravity/delta-reader/state.db.
    """
    override = os.environ.get("ANTIGRAVITY_DELTA_STATE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".antigravity" / "delta-reader" / "state.db"
