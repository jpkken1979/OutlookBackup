"""Evidence-based, reversible learning loop for the Hermes gateway.

The runtime adapter records bounded, redacted turn summaries here.  This
module deliberately keeps the learning state outside Brain/mem0: shared memory
remains owned by Nexus, while candidate prompt/skill changes live in a local,
auditable SQLite control plane until they prove useful.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TERMINAL_PROPOSAL_STATES = {"rejected", "rolled_back", "failed"}
ACTIVE_PROPOSAL_STATES = {"canary", "promoted"}


@dataclass(frozen=True)
class LearningPolicy:
    """Safety and evaluation thresholds for one Hermes profile."""

    enabled: bool = True
    retention_days: int = 90
    max_turns: int = 10_000
    failure_pattern_threshold: int = 3
    preference_pattern_threshold: int = 2
    canary_min_samples: int = 3
    canary_max_samples: int = 10
    promotion_min_delta: float = 0.05
    rollback_max_regression: float = 0.08
    auto_canary_low_risk: bool = True
    canary_traffic_percent: int = 50
    store_excerpts: bool = False
    max_excerpt_chars: int = 180
    max_overlay_chars: int = 2_000

    @classmethod
    def load(cls, path: Path | None) -> LearningPolicy:
        if path is None or not path.is_file():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Hermes learning policy must be a JSON object")
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"Unknown Hermes learning policy keys: {', '.join(unknown)}")
        policy = cls(**raw)
        policy.validate()
        return policy

    def validate(self) -> None:
        if not 1 <= self.retention_days <= 3650:
            raise ValueError("retention_days must be between 1 and 3650")
        if not 100 <= self.max_turns <= 1_000_000:
            raise ValueError("max_turns must be between 100 and 1000000")
        if self.failure_pattern_threshold < 2 or self.preference_pattern_threshold < 2:
            raise ValueError("pattern thresholds must be at least 2")
        if not 2 <= self.canary_min_samples <= self.canary_max_samples:
            raise ValueError("canary samples must satisfy 2 <= min <= max")
        if not 0.0 <= self.promotion_min_delta <= 1.0:
            raise ValueError("promotion_min_delta must be between 0 and 1")
        if not 0.0 <= self.rollback_max_regression <= 1.0:
            raise ValueError("rollback_max_regression must be between 0 and 1")
        if not 1 <= self.canary_traffic_percent <= 100:
            raise ValueError("canary_traffic_percent must be between 1 and 100")
        if not 80 <= self.max_excerpt_chars <= 1000:
            raise ValueError("max_excerpt_chars must be between 80 and 1000")
        if not 256 <= self.max_overlay_chars <= 8000:
            raise ValueError("max_overlay_chars must be between 256 and 8000")


@dataclass(frozen=True)
class FeedbackSignal:
    kind: str
    score: float
    category: str


PROMPT_TEMPLATES = {
    "tool_error": (
        "When a tool fails, inspect the exact error, change the next attempt, "
        "and use a verified fallback. Never repeat an unchanged failing call."
    ),
    "budget_exhausted": (
        "Before a multi-step task, define completion checks and reserve time for "
        "verification. Report an exact blocker instead of claiming completion."
    ),
    "persistence_error": (
        "Treat persistence failures as incomplete work. Verify durable state, "
        "preserve the user's data, and give a concrete recovery action."
    ),
    "provider_error": (
        "Distinguish provider/network failures from task failures. Retry only "
        "transient errors with a bound, then use a configured fallback or explain the blocker."
    ),
    "interrupted": (
        "When interrupted, preserve completed evidence and resume from the last "
        "verified checkpoint instead of restarting or inventing progress."
    ),
    "generic_failure": (
        "For repeated failures, identify the root cause, change strategy, and "
        "verify the result before responding. Never hide a failed check."
    ),
    "verbosity_more": (
        "This user consistently prefers additional explanation, concrete evidence, "
        "and explicit next steps. Provide them when relevant."
    ),
    "verbosity_less": (
        "This user consistently prefers concise answers. Lead with the result and "
        "omit background that is not needed to act."
    ),
    "language_spanish": (
        "This user prefers responses in Spanish unless they explicitly request another language."
    ),
    "verification": (
        "This user expects claims to be backed by checks. State what was verified "
        "and distinguish PASS, FAIL, and not-run results."
    ),
}


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_ -]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:sk|pk|ghp|github_pat)_[A-Za-z0-9_-]{16,}\b", re.IGNORECASE),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*"),
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _redact(text: str) -> str:
    redacted = str(text or "")
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return re.sub(r"\s+", " ", redacted).strip()


def redact_learning_text(text: str) -> str:
    """Public redaction boundary shared by learning artifacts and experiments."""

    return _redact(text)


def learning_text_contains_secret(text: str) -> bool:
    """Return True when a learning artifact contains a credential-shaped value."""

    return any(pattern.search(str(text or "")) for pattern in _SECRET_PATTERNS)


def _classify_task(text: str) -> str:
    normalized = text.casefold()
    categories = (
        ("code", ("código", "codigo", "code", "test", "bug", "git", "python", "typescript")),
        ("research", ("investiga", "research", "busca", "fuentes", "documentación")),
        ("system", ("windows", "sistema", "terminal", "powershell", "servicio", "gateway")),
        ("document", ("pdf", "excel", "documento", "docx", "informe")),
    )
    for category, terms in categories:
        if any(term in normalized for term in terms):
            return category
    return "general"


def _classify_failure(result: dict[str, Any]) -> str:
    reason = str(result.get("turn_exit_reason") or result.get("failure_reason") or "").casefold()
    if result.get("interrupted"):
        return "interrupted"
    if "max_iteration" in reason or "budget" in reason:
        return "budget_exhausted"
    if "persist" in reason or "storage" in reason:
        return "persistence_error"
    if "provider" in reason or "network" in reason or "rate" in reason:
        return "provider_error"
    if "tool" in reason or result.get("guardrail"):
        return "tool_error"
    return "generic_failure"


def _extract_tool_names(result: dict[str, Any]) -> list[str]:
    """Extract tool identifiers only; never persist arguments or tool output."""

    names: list[str] = []
    messages = result.get("messages")
    if not isinstance(messages, list):
        return names
    last_user_index = max(
        (
            index
            for index, message in enumerate(messages)
            if isinstance(message, dict) and message.get("role") == "user"
        ),
        default=-1,
    )
    for message in messages[last_user_index + 1 :]:
        if not isinstance(message, dict):
            continue
        calls = message.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            function = call.get("function")
            name = function.get("name") if isinstance(function, dict) else call.get("name")
            candidate = str(name or "").strip()
            if re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", candidate) and candidate not in names:
                names.append(candidate)
    return names[:20]


def classify_feedback(text: str, *, explicit_context: bool = False) -> FeedbackSignal | None:
    """Recognize bounded feedback without treating arbitrary conversation as labels."""

    cleaned = _redact(text)[:1000]
    normalized = cleaned.casefold().strip()
    explicit = explicit_context or normalized.startswith("/feedback")
    if normalized.startswith("/feedback"):
        normalized = normalized[len("/feedback") :].strip(" :-")

    preference_patterns = (
        ("verbosity_more", ("más detalle", "mas detalle", "explica más", "explain more")),
        ("verbosity_less", ("más corto", "mas corto", "muy largo", "too long", "be concise")),
        ("language_spanish", ("en español", "en espanol", "responde español", "answer in spanish")),
        ("verification", ("verifícalo", "verificalo", "compruébalo", "show the checks")),
    )
    for category, terms in preference_patterns:
        if any(term in normalized for term in terms):
            return FeedbackSignal("preference", 0.0, category)

    negative_terms = (
        "no funciona",
        "no funcionó",
        "no funciono",
        "está mal",
        "esta mal",
        "incorrecto",
        "falló",
        "fallo",
        "no era eso",
        "wrong",
        "didn't work",
        "does not work",
    )
    positive_terms = (
        "perfecto",
        "excelente",
        "funcionó",
        "funciono",
        "eso era",
        "muy bien",
        "works now",
        "exactly right",
        "great job",
    )
    short_feedback = len(normalized.split()) <= 8
    if (explicit or short_feedback) and any(term in normalized for term in negative_terms):
        return FeedbackSignal("negative", -1.0, "correction")
    if (explicit or short_feedback) and any(term in normalized for term in positive_terms):
        return FeedbackSignal("positive", 1.0, "success")
    if explicit and re.search(r"\b(gracias|thanks|good|bien)\b", normalized):
        return FeedbackSignal("positive", 0.75, "success")
    if explicit and re.search(r"\b(mal|no|error|bad)\b", normalized):
        return FeedbackSignal("negative", -0.75, "correction")
    return None


class HermesLearningEngine:
    """SQLite-backed learning control plane for one Hermes profile."""

    def __init__(
        self,
        profile_dir: Path,
        *,
        repo_root: Path | None = None,
        policy_path: Path | None = None,
    ) -> None:
        self.profile_dir = Path(profile_dir).resolve()
        self.repo_root = Path(repo_root).resolve() if repo_root else None
        self.state_dir = self.profile_dir / "learning"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        effective_policy_path = policy_path or self.state_dir / "policy.json"
        self.policy = LearningPolicy.load(effective_policy_path)
        self.db_path = self.state_dir / "hermes-learning.db"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    session_hash TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    task_category TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    prompt_excerpt TEXT NOT NULL,
                    response_hash TEXT NOT NULL,
                    response_excerpt TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    quality_score REAL NOT NULL,
                    feedback_score REAL,
                    duration_ms REAL NOT NULL,
                    api_calls INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    tools_json TEXT NOT NULL,
                    exit_reason TEXT NOT NULL,
                    failure_category TEXT,
                    active_proposals TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL REFERENCES turns(id),
                    kind TEXT NOT NULL,
                    score REAL NOT NULL,
                    category TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target TEXT NOT NULL,
                    title TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_signature TEXT NOT NULL UNIQUE,
                    baseline_score REAL NOT NULL,
                    baseline_samples INTEGER NOT NULL,
                    candidate_score REAL,
                    candidate_samples INTEGER NOT NULL DEFAULT 0,
                    control_score REAL,
                    control_samples INTEGER NOT NULL DEFAULT 0,
                    min_delta REAL NOT NULL,
                    min_samples INTEGER NOT NULL,
                    auto_eligible INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    activated_at TEXT,
                    decided_at TEXT,
                    snapshot_json TEXT NOT NULL DEFAULT '{}',
                    last_error TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_turns_created ON turns(created_at);
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_hash, created_at);
                CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status, created_at);
                """
            )
            turn_columns = {
                str(row["name"]) for row in conn.execute("PRAGMA table_info(turns)").fetchall()
            }
            if "tools_json" not in turn_columns:
                conn.execute("ALTER TABLE turns ADD COLUMN tools_json TEXT NOT NULL DEFAULT '[]'")
            proposal_columns = {
                str(row["name"]) for row in conn.execute("PRAGMA table_info(proposals)").fetchall()
            }
            if "control_score" not in proposal_columns:
                conn.execute("ALTER TABLE proposals ADD COLUMN control_score REAL")
            if "control_samples" not in proposal_columns:
                conn.execute(
                    "ALTER TABLE proposals ADD COLUMN control_samples INTEGER NOT NULL DEFAULT 0"
                )
            current = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if current and int(current["value"]) != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported Hermes learning schema {current['value']} (expected {SCHEMA_VERSION})"
                )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            if not conn.execute("SELECT 1 FROM meta WHERE key='hmac_secret'").fetchone():
                conn.execute(
                    "INSERT INTO meta(key, value) VALUES('hmac_secret', ?)",
                    (secrets.token_hex(32),),
                )

    def _secret(self, conn: sqlite3.Connection) -> bytes:
        row = conn.execute("SELECT value FROM meta WHERE key='hmac_secret'").fetchone()
        if row is None:
            raise RuntimeError("Hermes learning HMAC secret is missing")
        return str(row["value"]).encode("utf-8")

    def _digest(self, conn: sqlite3.Connection, value: str) -> str:
        return hmac.new(self._secret(conn), value.encode("utf-8"), hashlib.sha256).hexdigest()

    def _excerpt(self, text: str) -> str:
        if not self.policy.store_excerpts:
            return ""
        return _redact(text)[: self.policy.max_excerpt_chars]

    def record_turn(
        self,
        *,
        session_key: str,
        platform: str,
        prompt: str,
        response: str,
        result: dict[str, Any],
        duration_ms: float,
    ) -> str | None:
        if not self.policy.enabled:
            return None
        turn_id = "turn_" + secrets.token_hex(12)
        completed = bool(result.get("completed"))
        failed = bool(result.get("failed"))
        interrupted = bool(result.get("interrupted"))
        success = completed and not failed and not interrupted and bool(response.strip())
        quality = 0.15
        if success:
            quality = 0.82
            if int(result.get("api_calls") or 0) <= 4:
                quality += 0.05
            if response.strip():
                quality += 0.03
        elif response.strip():
            quality = 0.35
        failure_category = None if success else _classify_failure(result)
        active_ids = self.active_proposal_ids(session_key=session_key)
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO turns(
                    id, session_hash, platform, task_category, prompt_hash,
                    prompt_excerpt, response_hash, response_excerpt, success,
                    quality_score, feedback_score, duration_ms, api_calls,
                    total_tokens, estimated_cost_usd, model, provider,
                    tools_json, exit_reason, failure_category, active_proposals, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    self._digest(conn, session_key),
                    str(platform or "unknown")[:40],
                    _classify_task(prompt),
                    self._digest(conn, prompt),
                    self._excerpt(prompt),
                    self._digest(conn, response),
                    self._excerpt(response),
                    int(success),
                    _clamp(quality),
                    max(0.0, float(duration_ms)),
                    max(0, int(result.get("api_calls") or 0)),
                    max(0, int(result.get("total_tokens") or 0)),
                    max(0.0, float(result.get("estimated_cost_usd") or 0.0)),
                    str(result.get("model") or "")[:160],
                    str(result.get("provider") or "")[:80],
                    json.dumps(_extract_tool_names(result)),
                    str(result.get("turn_exit_reason") or result.get("failure_reason") or "")[:240],
                    failure_category,
                    json.dumps(active_ids),
                    now,
                ),
            )
        self.prune()
        self.evaluate_canaries()
        self.analyze()
        return turn_id

    def record_feedback(
        self,
        *,
        session_key: str,
        text: str,
        explicit_context: bool = False,
    ) -> FeedbackSignal | None:
        if not self.policy.enabled:
            return None
        signal = classify_feedback(text, explicit_context=explicit_context)
        if signal is None:
            return None
        with self._connect() as conn:
            session_hash = self._digest(conn, session_key)
            turn = conn.execute(
                "SELECT id, quality_score FROM turns WHERE session_hash=? "
                "ORDER BY created_at DESC LIMIT 1",
                (session_hash,),
            ).fetchone()
            if turn is None:
                return None
            feedback_id = "fb_" + secrets.token_hex(12)
            conn.execute(
                "INSERT INTO feedback(id, turn_id, kind, score, category, excerpt, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    feedback_id,
                    turn["id"],
                    signal.kind,
                    signal.score,
                    signal.category,
                    self._excerpt(text),
                    _utc_now(),
                ),
            )
            adjusted = float(turn["quality_score"])
            if signal.kind in {"positive", "negative"}:
                adjusted = _clamp(adjusted + signal.score * 0.22)
            conn.execute(
                "UPDATE turns SET feedback_score=?, quality_score=? WHERE id=?",
                (signal.score, adjusted, turn["id"]),
            )
            self._audit(conn, None, "feedback_recorded", asdict(signal))
        self.evaluate_canaries()
        return signal

    def _audit(
        self,
        conn: sqlite3.Connection,
        proposal_id: str | None,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            "INSERT INTO audit_events(proposal_id, action, details_json, created_at) "
            "VALUES(?, ?, ?, ?)",
            (proposal_id, action, json.dumps(details or {}, ensure_ascii=False), _utc_now()),
        )

    def _score_rows(self, rows: Iterable[sqlite3.Row]) -> tuple[float, int]:
        values = [float(row["quality_score"]) for row in rows]
        if not values:
            return 0.0, 0
        return sum(values) / len(values), len(values)

    def _existing_signature(self, conn: sqlite3.Connection, signature: str) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM proposals WHERE source_signature=? LIMIT 1", (signature,)
            ).fetchone()
            is not None
        )

    def _create_proposal(
        self,
        conn: sqlite3.Connection,
        *,
        kind: str,
        risk: str,
        target: str,
        title: str,
        rationale: str,
        instruction: str,
        artifact: dict[str, Any],
        source_signature: str,
        baseline_rows: list[sqlite3.Row],
        auto_eligible: bool,
    ) -> str:
        baseline_score, baseline_samples = self._score_rows(baseline_rows)
        proposal_id = (
            "hlp_" + datetime.now(UTC).strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(3)
        )
        content_hash = hashlib.sha256(
            json.dumps(
                {"instruction": instruction, "artifact": artifact},
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        conn.execute(
            """
            INSERT INTO proposals(
                id, version, kind, risk, status, target, title, rationale,
                instruction, artifact_json, content_hash, source_signature,
                baseline_score, baseline_samples, min_delta, min_samples,
                auto_eligible, created_at
            ) VALUES(?, 1, ?, ?, 'proposed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                kind,
                risk,
                target,
                title,
                rationale,
                instruction,
                json.dumps(artifact, ensure_ascii=False),
                content_hash,
                source_signature,
                baseline_score,
                baseline_samples,
                self.policy.promotion_min_delta,
                self.policy.canary_min_samples,
                int(auto_eligible),
                _utc_now(),
            ),
        )
        self._audit(
            conn,
            proposal_id,
            "proposal_created",
            {"kind": kind, "risk": risk, "baseline_samples": baseline_samples},
        )
        return proposal_id

    def analyze(self) -> list[str]:
        """Create deduplicated proposals from observed failure/feedback patterns."""

        if not self.policy.enabled:
            return []
        cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        created: list[str] = []
        auto_candidates: list[str] = []
        with self._connect() as conn:
            failures = conn.execute(
                """
                SELECT failure_category, COUNT(*) AS count
                FROM turns
                WHERE created_at >= ? AND success=0 AND failure_category IS NOT NULL
                GROUP BY failure_category
                HAVING COUNT(*) >= ?
                """,
                (cutoff, self.policy.failure_pattern_threshold),
            ).fetchall()
            for group in failures:
                category = str(group["failure_category"])
                category_row = conn.execute(
                    """
                    SELECT task_category, COUNT(*) AS count FROM turns
                    WHERE created_at>=? AND failure_category=?
                    GROUP BY task_category ORDER BY count DESC, task_category LIMIT 1
                    """,
                    (cutoff, category),
                ).fetchone()
                task_category = str(category_row["task_category"]) if category_row else "general"
                signature = f"failure:{category}:{task_category}:v1"
                if self._existing_signature(conn, signature):
                    continue
                rows = conn.execute(
                    "SELECT quality_score FROM turns WHERE created_at>=? AND task_category=? "
                    "ORDER BY created_at DESC LIMIT 100",
                    (cutoff, task_category),
                ).fetchall()
                instruction = PROMPT_TEMPLATES.get(category, PROMPT_TEMPLATES["generic_failure"])
                proposal_id = self._create_proposal(
                    conn,
                    kind="prompt",
                    risk="low",
                    target=f"hermes:{category}",
                    title=f"Guardrail for recurring {category.replace('_', ' ')}",
                    rationale=f"Hermes observed {int(group['count'])} failures in this category in 30 days.",
                    instruction=instruction,
                    artifact={
                        "category": category,
                        "task_category": task_category,
                        "source": "deterministic_template",
                    },
                    source_signature=signature,
                    baseline_rows=list(rows),
                    auto_eligible=True,
                )
                created.append(proposal_id)
                auto_candidates.append(proposal_id)

            preferences = conn.execute(
                """
                SELECT f.category, COUNT(*) AS count
                FROM feedback f
                WHERE f.created_at >= ? AND f.kind='preference'
                GROUP BY f.category
                HAVING COUNT(*) >= ?
                """,
                (cutoff, self.policy.preference_pattern_threshold),
            ).fetchall()
            for group in preferences:
                category = str(group["category"])
                if category not in PROMPT_TEMPLATES:
                    continue
                signature = f"preference:{category}:v1"
                if self._existing_signature(conn, signature):
                    continue
                rows = conn.execute(
                    "SELECT quality_score FROM turns WHERE created_at>=? "
                    "ORDER BY created_at DESC LIMIT 100",
                    (cutoff,),
                ).fetchall()
                proposal_id = self._create_proposal(
                    conn,
                    kind="prompt",
                    risk="low",
                    target="hermes:user-preference",
                    title=f"Learned user preference: {category.replace('_', ' ')}",
                    rationale=f"The same explicit preference was observed {int(group['count'])} times.",
                    instruction=PROMPT_TEMPLATES[category],
                    artifact={"category": category, "source": "bounded_feedback_classifier"},
                    source_signature=signature,
                    baseline_rows=list(rows),
                    auto_eligible=True,
                )
                created.append(proposal_id)
                auto_candidates.append(proposal_id)

            negative_categories = conn.execute(
                """
                SELECT t.task_category, COUNT(*) AS count
                FROM feedback f JOIN turns t ON t.id=f.turn_id
                WHERE f.created_at>=? AND f.kind='negative'
                GROUP BY t.task_category
                HAVING COUNT(*) >= ?
                """,
                (cutoff, self.policy.failure_pattern_threshold),
            ).fetchall()
            for group in negative_categories:
                task_category = str(group["task_category"])
                signature = f"skill:{task_category}:negative-feedback:v1"
                if self._existing_signature(conn, signature):
                    continue
                rows = conn.execute(
                    "SELECT quality_score FROM turns WHERE created_at>=? AND task_category=? "
                    "ORDER BY created_at DESC LIMIT 100",
                    (cutoff, task_category),
                ).fetchall()
                skill_slug = re.sub(r"[^a-z0-9-]+", "-", f"hermes-learned-{task_category}").strip(
                    "-"
                )
                skill_body = (
                    f"---\nname: {skill_slug}\n"
                    f'description: "Use when Hermes handles {task_category} tasks that need explicit verification."\n'
                    "---\n\n# Learned verification workflow\n\n"
                    "1. Restate the measurable outcome.\n"
                    "2. Inspect the exact evidence and error output.\n"
                    "3. Change strategy after a failed attempt.\n"
                    "4. Run the narrowest relevant verification.\n"
                    "5. Report PASS, FAIL, or BLOCKED without inventing success.\n"
                )
                proposal_id = self._create_proposal(
                    conn,
                    kind="skill",
                    risk="medium",
                    target=skill_slug,
                    title=f"Candidate verification skill for {task_category}",
                    rationale=f"Hermes received {int(group['count'])} negative feedback signals for this task category.",
                    instruction=(
                        f"For {task_category} tasks: restate the measurable outcome, inspect exact "
                        "evidence and errors, change strategy after failure, run the narrowest "
                        "relevant verification, and report PASS, FAIL, or BLOCKED honestly."
                    ),
                    artifact={"slug": skill_slug, "content": skill_body},
                    source_signature=signature,
                    baseline_rows=list(rows),
                    auto_eligible=False,
                )
                created.append(proposal_id)

            successful_tool_patterns = conn.execute(
                """
                SELECT task_category, tools_json, COUNT(*) AS count,
                       AVG(quality_score) AS quality
                FROM turns
                WHERE created_at>=? AND success=1 AND feedback_score>0
                  AND tools_json NOT IN ('[]', '')
                GROUP BY task_category, tools_json
                HAVING COUNT(*) >= ?
                """,
                (cutoff, self.policy.preference_pattern_threshold),
            ).fetchall()
            for group in successful_tool_patterns:
                task_category = str(group["task_category"])
                tools = json.loads(str(group["tools_json"]))
                signature = (
                    "tools:"
                    + hashlib.sha256(
                        f"{task_category}:{group['tools_json']}:v1".encode()
                    ).hexdigest()
                )
                if not tools or self._existing_signature(conn, signature):
                    continue
                rows = conn.execute(
                    "SELECT quality_score FROM turns WHERE created_at>=? AND task_category=? "
                    "ORDER BY created_at DESC LIMIT 100",
                    (cutoff, task_category),
                ).fetchall()
                tool_list = ", ".join(str(tool) for tool in tools)
                proposal_id = self._create_proposal(
                    conn,
                    kind="prompt",
                    risk="low",
                    target=f"hermes:tools:{task_category}",
                    title=f"Verified tool pattern for {task_category}",
                    rationale=(
                        f"The tool pattern [{tool_list}] received positive feedback "
                        f"{int(group['count'])} times with quality {float(group['quality']):.2f}."
                    ),
                    instruction=(
                        f"For {task_category} tasks, consider the verified tool pattern "
                        f"[{tool_list}] when applicable. Check tool availability, adapt to context, "
                        "and verify the result; never force it onto a different task."
                    ),
                    artifact={"task_category": task_category, "tools": tools},
                    source_signature=signature,
                    baseline_rows=list(rows),
                    auto_eligible=True,
                )
                created.append(proposal_id)
                auto_candidates.append(proposal_id)

            severe = conn.execute(
                """
                SELECT failure_category, COUNT(*) AS count FROM turns
                WHERE created_at>=? AND success=0
                  AND failure_category IN ('persistence_error', 'generic_failure')
                GROUP BY failure_category HAVING COUNT(*) >= ?
                """,
                (cutoff, self.policy.failure_pattern_threshold * 2),
            ).fetchall()
            for group in severe:
                category = str(group["failure_category"])
                signature = f"code-review:{category}:v1"
                if self._existing_signature(conn, signature):
                    continue
                rows = conn.execute(
                    "SELECT quality_score FROM turns WHERE created_at>=? "
                    "ORDER BY created_at DESC LIMIT 100",
                    (cutoff,),
                ).fetchall()
                proposal_id = self._create_proposal(
                    conn,
                    kind="code",
                    risk="high",
                    target="hermes-runtime",
                    title=f"Human code review required for recurring {category}",
                    rationale=f"The runtime observed {int(group['count'])} severe repeated failures.",
                    instruction="Do not auto-apply. Reproduce, patch in a worktree, run gates, and request review.",
                    artifact={"category": category, "action": "review_only"},
                    source_signature=signature,
                    baseline_rows=list(rows),
                    auto_eligible=False,
                )
                created.append(proposal_id)

        if self.policy.auto_canary_low_risk:
            self._activate_next_auto_canary()
        return created

    def _activate_next_auto_canary(self) -> str | None:
        """Serialize experiments so one proposal owns each observed delta."""

        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM proposals WHERE status='canary' LIMIT 1").fetchone():
                return None
            next_row = conn.execute(
                """
                SELECT id FROM proposals
                WHERE status='proposed' AND auto_eligible=1
                  AND risk='low' AND kind='prompt'
                ORDER BY created_at, id LIMIT 1
                """
            ).fetchone()
        if next_row is None:
            return None
        proposal_id = str(next_row["id"])
        self.approve(proposal_id, actor="policy:auto-low-risk")
        return proposal_id

    def _proposal(self, conn: sqlite3.Connection, proposal_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown Hermes learning proposal: {proposal_id}")
        return row

    def approve(self, proposal_id: str, *, actor: str = "owner") -> dict[str, Any]:
        """Start a reversible canary. High-risk/code proposals remain review-only."""

        with self._connect() as conn:
            row = self._proposal(conn, proposal_id)
            if row["status"] in ACTIVE_PROPOSAL_STATES:
                return dict(row)
            if row["status"] != "proposed":
                raise ValueError(f"Proposal {proposal_id} cannot be approved from {row['status']}")
            if row["risk"] == "high" or row["kind"] == "code":
                raise PermissionError(
                    "High-risk/code proposals are review-only and cannot be applied by Hermes"
                )
            active_canary = conn.execute(
                "SELECT id FROM proposals WHERE status='canary' AND id<>? LIMIT 1",
                (proposal_id,),
            ).fetchone()
            if active_canary is not None:
                raise ValueError(
                    f"Proposal {proposal_id} is queued behind active canary {active_canary['id']}"
                )
            snapshot: dict[str, Any] = {}
            if row["kind"] == "skill":
                artifact = json.loads(row["artifact_json"])
                snapshot = self._snapshot_skill(artifact)
            now = _utc_now()
            conn.execute(
                "UPDATE proposals SET status='canary', approved_at=?, activated_at=?, "
                "snapshot_json=?, last_error=NULL WHERE id=?",
                (now, now, json.dumps(snapshot), proposal_id),
            )
            self._audit(conn, proposal_id, "canary_started", {"actor": actor})
            return dict(self._proposal(conn, proposal_id))

    def _safe_skill_path(self, slug: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,49}", slug):
            raise ValueError("Unsafe learned skill identifier")
        skills_root = (self.profile_dir / "skills").resolve()
        skills_root.mkdir(parents=True, exist_ok=True)
        target = (skills_root / slug).resolve()
        if target.parent != skills_root:
            raise ValueError("Learned skill escaped the profile skills directory")
        return target

    def _snapshot_skill(self, artifact: dict[str, Any]) -> dict[str, Any]:
        slug = str(artifact.get("slug") or "")
        target = self._safe_skill_path(slug)
        snapshot: dict[str, Any] = {"path": str(target), "existed": target.exists()}
        if target.exists():
            prior = target / "SKILL.md"
            snapshot["prior_content"] = (
                prior.read_text(encoding="utf-8") if prior.is_file() else None
            )
        snapshot["materialized"] = False
        return snapshot

    def _materialize_skill(
        self, proposal_id: str, artifact: dict[str, Any], snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        slug = str(artifact.get("slug") or "")
        content = str(artifact.get("content") or "")
        if len(content) < 80 or len(content) > 12_000:
            raise ValueError("Learned skill content has an unsafe size")
        target = self._safe_skill_path(slug)
        target.mkdir(parents=True, exist_ok=True)
        skill_path = target / "SKILL.md"
        pending = target / ".SKILL.md.pending"
        pending.write_text(content, encoding="utf-8", newline="\n")
        pending.replace(skill_path)
        snapshot["proposal_id"] = proposal_id
        snapshot["materialized"] = True
        return snapshot

    def reject(self, proposal_id: str, *, actor: str = "owner") -> dict[str, Any]:
        with self._connect() as conn:
            row = self._proposal(conn, proposal_id)
            if row["status"] != "proposed":
                raise ValueError(f"Proposal {proposal_id} cannot be rejected from {row['status']}")
            conn.execute(
                "UPDATE proposals SET status='rejected', decided_at=? WHERE id=?",
                (_utc_now(), proposal_id),
            )
            self._audit(conn, proposal_id, "proposal_rejected", {"actor": actor})
            return dict(self._proposal(conn, proposal_id))

    def rollback(
        self,
        proposal_id: str,
        *,
        reason: str,
        actor: str = "evaluator",
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = self._proposal(conn, proposal_id)
            if row["status"] not in ACTIVE_PROPOSAL_STATES:
                raise ValueError(f"Proposal {proposal_id} cannot roll back from {row['status']}")
            if row["kind"] == "skill":
                self._rollback_skill(proposal_id, json.loads(row["snapshot_json"] or "{}"))
            conn.execute(
                "UPDATE proposals SET status='rolled_back', decided_at=?, last_error=? WHERE id=?",
                (_utc_now(), _redact(reason)[:500], proposal_id),
            )
            self._audit(
                conn, proposal_id, "proposal_rolled_back", {"actor": actor, "reason": reason}
            )
            return dict(self._proposal(conn, proposal_id))

    def _rollback_skill(self, proposal_id: str, snapshot: dict[str, Any]) -> None:
        target_raw = snapshot.get("path")
        if not target_raw or not snapshot.get("materialized"):
            return
        target = Path(str(target_raw)).resolve()
        skills_root = (self.profile_dir / "skills").resolve()
        if target.parent != skills_root or not target.exists():
            return
        if snapshot.get("existed"):
            prior = snapshot.get("prior_content")
            if prior is not None:
                (target / "SKILL.md").write_text(str(prior), encoding="utf-8", newline="\n")
            return
        archive_root = (self.state_dir / "rollback").resolve()
        archive_root.mkdir(parents=True, exist_ok=True)
        archive = archive_root / f"{proposal_id}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        shutil.move(str(target), str(archive))

    def active_proposal_ids(self, *, session_key: str | None = None) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, status FROM proposals WHERE status IN ('canary','promoted') "
                "ORDER BY created_at"
            ).fetchall()
            secret = self._secret(conn)
        active: list[str] = []
        for row in rows:
            proposal_id = str(row["id"])
            if row["status"] == "promoted":
                active.append(proposal_id)
                continue
            if not session_key:
                continue
            digest = hmac.new(
                secret,
                f"{proposal_id}:{session_key}".encode(),
                hashlib.sha256,
            ).digest()
            bucket = int.from_bytes(digest[:4], "big") % 100
            if bucket < self.policy.canary_traffic_percent:
                active.append(proposal_id)
        return active

    def active_revision(self, *, session_key: str | None = None) -> str:
        """Hash active overlay bytes so Hermes can invalidate its prompt pin."""

        overlay = self.render_active_overlays(session_key=session_key)
        return hashlib.sha256(overlay.encode()).hexdigest() if overlay else ""

    def render_active_overlays(self, *, session_key: str | None = None) -> str:
        """Render only internally generated, currently active instructions."""

        active_ids = set(self.active_proposal_ids(session_key=session_key))
        if not active_ids:
            return ""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, kind, status, title, instruction FROM proposals
                WHERE status IN ('canary','promoted') AND kind IN ('prompt','skill')
                ORDER BY CASE status WHEN 'promoted' THEN 0 ELSE 1 END, created_at
                """
            ).fetchall()
        rows = [row for row in rows if str(row["id"]) in active_ids]
        if not rows:
            return ""
        lines = ["<hermes_learning_policy>", "Apply these trusted, versioned local policies:"]
        for row in rows:
            label = "candidate" if row["status"] == "canary" else "promoted"
            instruction = _redact(str(row["instruction"]))
            lines.append(f"- [{label}:{row['id']}] {instruction}")
        lines.append("Do not claim a policy worked; normal verification still applies.")
        lines.append("</hermes_learning_policy>")
        return "\n".join(lines)[: self.policy.max_overlay_chars]

    def evaluate_canaries(self) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        with self._connect() as conn:
            canaries = conn.execute("SELECT * FROM proposals WHERE status='canary'").fetchall()
            for proposal in canaries:
                proposal_id = str(proposal["id"])
                artifact = json.loads(proposal["artifact_json"] or "{}")
                task_category = str(artifact.get("task_category") or "").strip()
                activated_at = str(proposal["activated_at"] or proposal["created_at"])
                if task_category:
                    matching = conn.execute(
                        "SELECT quality_score FROM turns WHERE active_proposals LIKE ? "
                        "AND task_category=? AND created_at>=? ORDER BY created_at",
                        (f'%"{proposal_id}"%', task_category, activated_at),
                    ).fetchall()
                    controls = conn.execute(
                        "SELECT quality_score FROM turns WHERE active_proposals NOT LIKE ? "
                        "AND task_category=? AND created_at>=? ORDER BY created_at",
                        (f'%"{proposal_id}"%', task_category, activated_at),
                    ).fetchall()
                else:
                    matching = conn.execute(
                        "SELECT quality_score FROM turns WHERE active_proposals LIKE ? "
                        "AND created_at>=? ORDER BY created_at",
                        (f'%"{proposal_id}"%', activated_at),
                    ).fetchall()
                    controls = conn.execute(
                        "SELECT quality_score FROM turns WHERE active_proposals NOT LIKE ? "
                        "AND created_at>=? ORDER BY created_at",
                        (f'%"{proposal_id}"%', activated_at),
                    ).fetchall()
                candidate_score, candidate_samples = self._score_rows(matching)
                control_score, control_samples = self._score_rows(controls)
                conn.execute(
                    "UPDATE proposals SET candidate_score=?, candidate_samples=?, "
                    "control_score=?, control_samples=? WHERE id=?",
                    (
                        candidate_score if candidate_samples else None,
                        candidate_samples,
                        control_score if control_samples else None,
                        control_samples,
                        proposal_id,
                    ),
                )
                if candidate_samples < int(proposal["min_samples"]) or control_samples < int(
                    proposal["min_samples"]
                ):
                    continue
                baseline = float(proposal["baseline_score"])
                comparison_score = max(baseline, control_score)
                delta = candidate_score - comparison_score
                if delta >= float(proposal["min_delta"]):
                    snapshot = json.loads(proposal["snapshot_json"] or "{}")
                    if proposal["kind"] == "skill":
                        try:
                            snapshot = self._materialize_skill(
                                proposal_id,
                                json.loads(proposal["artifact_json"]),
                                snapshot,
                            )
                        except Exception as exc:
                            conn.execute(
                                "UPDATE proposals SET status='failed', decided_at=?, last_error=? "
                                "WHERE id=?",
                                (_utc_now(), _redact(str(exc))[:500], proposal_id),
                            )
                            self._audit(
                                conn,
                                proposal_id,
                                "promotion_failed",
                                {"error": _redact(str(exc))[:500]},
                            )
                            decisions.append(
                                {"id": proposal_id, "decision": "failed", "delta": delta}
                            )
                            continue
                    conn.execute(
                        "UPDATE proposals SET status='promoted', decided_at=?, snapshot_json=? "
                        "WHERE id=?",
                        (_utc_now(), json.dumps(snapshot), proposal_id),
                    )
                    self._audit(
                        conn,
                        proposal_id,
                        "proposal_promoted",
                        {
                            "baseline": baseline,
                            "control": control_score,
                            "candidate": candidate_score,
                            "delta": delta,
                        },
                    )
                    decisions.append({"id": proposal_id, "decision": "promoted", "delta": delta})
                elif delta <= -self.policy.rollback_max_regression:
                    # Commit this transaction before the public rollback opens another one.
                    decisions.append({"id": proposal_id, "decision": "rollback", "delta": delta})
                elif candidate_samples >= self.policy.canary_max_samples:
                    decisions.append({"id": proposal_id, "decision": "rollback", "delta": delta})
        for decision in list(decisions):
            if decision["decision"] == "rollback":
                self.rollback(
                    decision["id"],
                    reason=f"Canary regressed by {abs(float(decision['delta'])):.3f}",
                )
        if decisions and self.policy.auto_canary_low_risk:
            self._activate_next_auto_canary()
        return decisions

    def prune(self) -> dict[str, int]:
        cutoff = (datetime.now(UTC) - timedelta(days=self.policy.retention_days)).isoformat()
        with self._connect() as conn:
            old_feedback = conn.execute(
                "DELETE FROM feedback WHERE turn_id IN (SELECT id FROM turns WHERE created_at < ?)",
                (cutoff,),
            ).rowcount
            old_turns = conn.execute("DELETE FROM turns WHERE created_at < ?", (cutoff,)).rowcount
            excess = conn.execute(
                "SELECT id FROM turns ORDER BY created_at DESC LIMIT -1 OFFSET ?",
                (self.policy.max_turns,),
            ).fetchall()
            excess_ids = [str(row["id"]) for row in excess]
            if excess_ids:
                placeholders = ",".join("?" for _ in excess_ids)
                conn.execute(f"DELETE FROM feedback WHERE turn_id IN ({placeholders})", excess_ids)
                conn.execute(f"DELETE FROM turns WHERE id IN ({placeholders})", excess_ids)
            return {
                "old_turns": old_turns,
                "old_feedback": old_feedback,
                "excess_turns": len(excess_ids),
            }

    def list_proposals(self, *, status: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM proposals WHERE status=? ORDER BY created_at DESC", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM proposals ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            return dict(self._proposal(conn, proposal_id))

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            turn_stats = conn.execute(
                "SELECT COUNT(*) AS count, COALESCE(AVG(quality_score),0) AS quality, "
                "COALESCE(SUM(success),0) AS successes FROM turns"
            ).fetchone()
            proposal_stats = conn.execute(
                "SELECT status, COUNT(*) AS count FROM proposals GROUP BY status"
            ).fetchall()
            feedback_count = conn.execute("SELECT COUNT(*) AS count FROM feedback").fetchone()
            active_rows = conn.execute(
                "SELECT id FROM proposals WHERE status IN ('canary','promoted') ORDER BY created_at"
            ).fetchall()
        count = int(turn_stats["count"])
        return {
            "enabled": self.policy.enabled,
            "schema_version": SCHEMA_VERSION,
            "database": str(self.db_path),
            "turns": count,
            "success_rate": (float(turn_stats["successes"]) / count) if count else 0.0,
            "average_quality": float(turn_stats["quality"]),
            "feedback": int(feedback_count["count"]),
            "proposals": {str(row["status"]): int(row["count"]) for row in proposal_stats},
            # Operational status must expose every live experiment. Cohort filtering
            # belongs only to prompt rendering for an individual session.
            "active_overlays": [str(row["id"]) for row in active_rows],
            "policy": asdict(self.policy),
        }

    def doctor(self) -> dict[str, Any]:
        checks: dict[str, bool] = {
            "profile_dir": self.profile_dir.is_dir(),
            "state_dir": self.state_dir.is_dir(),
            "database": self.db_path.is_file(),
            "policy": True,
            "schema": False,
            "integrity": False,
        }
        try:
            self.policy.validate()
            with self._connect() as conn:
                version = conn.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()
                checks["schema"] = bool(version and int(version["value"]) == SCHEMA_VERSION)
                checks["integrity"] = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        except Exception:
            checks["policy"] = False
        return {"ok": all(checks.values()), "checks": checks, "status": self.status()}


def resolve_learning_engine(
    *,
    repo_root: Path | None = None,
    profile_dir: Path | None = None,
) -> HermesLearningEngine:
    """Resolve the same profile-local store for CLI and gateway adapters."""

    effective_repo = Path(
        repo_root or os.environ.get("HERMES_PROJECT_ROOT") or Path.cwd()
    ).resolve()
    if profile_dir is None:
        local_app_data = os.environ.get("LOCALAPPDATA")
        hermes_home = Path(
            os.environ.get("HERMES_HOME")
            or os.environ.get("HERMES_INSTALL_ROOT")
            or (Path(local_app_data) / "hermes" if local_app_data else Path.home() / ".hermes")
        )
        profile = os.environ.get("HERMES_PROFILE", "antigravity").strip() or "antigravity"
        profile_dir = hermes_home / "profiles" / profile
    policy_path = Path(profile_dir) / "learning" / "policy.json"
    if not policy_path.is_file():
        fallback = effective_repo / "config" / "hermes-learning-policy.json"
        policy_path = fallback if fallback.is_file() else policy_path
    return HermesLearningEngine(
        Path(profile_dir), repo_root=effective_repo, policy_path=policy_path
    )


__all__ = [
    "FeedbackSignal",
    "HermesLearningEngine",
    "LearningPolicy",
    "classify_feedback",
    "learning_text_contains_secret",
    "redact_learning_text",
    "resolve_learning_engine",
]
