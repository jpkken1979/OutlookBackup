"""Transactional SQLite state for provider routing.

Only metadata is stored here. API keys and OAuth tokens remain in the platform
credential store or process environment and are never accepted by this API.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9_./-]{0,79}$")
_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_ACCOUNT_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:@/-]{0,127}$")

DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "auto": {
        "required_capability": None,
        "weights": {
            "quality": 0.30,
            "health": 0.25,
            "quota": 0.15,
            "latency": 0.10,
            "cost": 0.10,
            "priority": 0.10,
        },
    },
    "auto/coding": {
        "required_capability": "coding",
        "weights": {
            "quality": 0.35,
            "health": 0.25,
            "quota": 0.10,
            "latency": 0.10,
            "cost": 0.05,
            "priority": 0.15,
        },
    },
    "auto/fast": {
        "required_capability": "fast",
        "weights": {
            "quality": 0.10,
            "health": 0.20,
            "quota": 0.10,
            "latency": 0.45,
            "cost": 0.05,
            "priority": 0.10,
        },
    },
    "auto/cheap": {
        "required_capability": "cheap",
        "weights": {
            "quality": 0.05,
            "health": 0.20,
            "quota": 0.15,
            "latency": 0.05,
            "cost": 0.50,
            "priority": 0.05,
        },
    },
    "auto/reliable": {
        "required_capability": "reliable",
        "weights": {
            "quality": 0.25,
            "health": 0.40,
            "quota": 0.10,
            "latency": 0.05,
            "cost": 0.00,
            "priority": 0.20,
        },
    },
}


def default_routing_db_path() -> Path:
    configured = os.environ.get("ANTIGRAVITY_ROUTING_DB", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".antigravity" / "state" / "routing.db"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat()


def _validate(value: str, pattern: re.Pattern[str], label: str) -> str:
    cleaned = value.strip()
    if not pattern.fullmatch(cleaned):
        raise ValueError(f"Invalid {label}")
    return cleaned


class RoutingStore:
    """Small connection-per-operation store, safe for gateway worker threads."""

    def __init__(self, path: Path | None = None, *, circuit_threshold: int = 3):
        self.path = path or default_routing_db_path()
        self.circuit_threshold = max(1, circuit_threshold)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()
        self._seed_profiles()
        if os.name != "nt":
            self.path.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if str(self.path) != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def _migrate(self) -> None:
        with self._transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                """
            )
            current = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()[0]
            if current < 1:
                connection.executescript(
                    """
                    CREATE TABLE routing_profiles (
                        profile_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE routing_settings (
                        setting_key TEXT PRIMARY KEY,
                        setting_value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE provider_accounts (
                        account_id TEXT PRIMARY KEY,
                        provider TEXT NOT NULL,
                        label TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'UNKNOWN',
                        quota_remaining REAL,
                        cooldown_until TEXT,
                        last_error_code INTEGER,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX idx_provider_accounts_provider
                        ON provider_accounts(provider, status);
                    CREATE TABLE provider_health (
                        provider TEXT PRIMARY KEY,
                        circuit_status TEXT NOT NULL DEFAULT 'CLOSED',
                        consecutive_failures INTEGER NOT NULL DEFAULT 0,
                        circuit_open_until TEXT,
                        latency_ms INTEGER,
                        last_status_code INTEGER,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE routing_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trace_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        provider TEXT,
                        account_id TEXT,
                        route TEXT,
                        detail_json TEXT NOT NULL CHECK(json_valid(detail_json)),
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX idx_routing_events_created
                        ON routing_events(created_at DESC);
                    CREATE INDEX idx_routing_events_trace
                        ON routing_events(trace_id);
                    CREATE TABLE routing_decisions (
                        trace_id TEXT PRIMARY KEY,
                        route TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        score REAL NOT NULL,
                        manual INTEGER NOT NULL CHECK(manual IN (0, 1)),
                        detail_json TEXT NOT NULL CHECK(json_valid(detail_json)),
                        created_at TEXT NOT NULL
                    );
                    """
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (1, "routing_authority_v1", _as_iso()),
                )

    def _seed_profiles(self) -> None:
        now = _as_iso()
        with self._transaction() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO routing_profiles(
                    profile_id, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (profile_id, json.dumps(payload, sort_keys=True), now, now)
                    for profile_id, payload in DEFAULT_PROFILES.items()
                ],
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO routing_settings(
                    setting_key, setting_value, updated_at
                ) VALUES (?, ?, ?)
                """,
                ("active_profile", "auto", now),
            )

    def put_profile(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = _validate(profile_id, _PROFILE_ID, "profile id")
        if not isinstance(payload, dict):
            raise ValueError("Profile payload must be an object")
        encoded = json.dumps(payload, sort_keys=True)
        now = _as_iso()
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO routing_profiles(profile_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (profile_id, encoded, now, now),
            )
        return {"profile_id": profile_id, **payload}

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        profile_id = _validate(profile_id, _PROFILE_ID, "profile id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM routing_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT profile_id, payload_json, updated_at FROM routing_profiles "
                "ORDER BY profile_id"
            ).fetchall()
        return [
            {
                "profile_id": row["profile_id"],
                **json.loads(row["payload_json"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def active_profile(self) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT setting_value FROM routing_settings WHERE setting_key = ?",
                ("active_profile",),
            ).fetchone()
        return str(row["setting_value"]) if row else "auto"

    def set_active_profile(self, profile_id: str) -> str:
        profile_id = _validate(profile_id, _PROFILE_ID, "profile id")
        if self.get_profile(profile_id) is None:
            raise ValueError("Unknown routing profile")
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO routing_settings(setting_key, setting_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    setting_value = excluded.setting_value,
                    updated_at = excluded.updated_at
                """,
                ("active_profile", profile_id, _as_iso()),
            )
        return profile_id

    def manual_override(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT setting_value FROM routing_settings WHERE setting_key = ?",
                ("manual_override",),
            ).fetchone()
        return str(row["setting_value"]) if row and row["setting_value"] else None

    def set_manual_override(self, provider: str, model: str) -> str:
        provider = _validate(provider, _PROVIDER_ID, "provider")
        model = model.strip()
        if not model or len(model) > 200 or any(char in model for char in "\r\n\0"):
            raise ValueError("Invalid model")
        route = f"{provider}/{model}"
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO routing_settings(setting_key, setting_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    setting_value = excluded.setting_value,
                    updated_at = excluded.updated_at
                """,
                ("manual_override", route, _as_iso()),
            )
        return route

    def clear_manual_override(self) -> None:
        with self._transaction() as connection:
            connection.execute(
                "DELETE FROM routing_settings WHERE setting_key = ?",
                ("manual_override",),
            )

    def _ensure_provider(
        self,
        connection: sqlite3.Connection,
        provider: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO provider_health(provider, updated_at)
            VALUES (?, ?)
            """,
            (provider, now),
        )

    def _ensure_account(
        self,
        connection: sqlite3.Connection,
        provider: str,
        account_id: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO provider_accounts(account_id, provider, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                provider = excluded.provider,
                updated_at = excluded.updated_at
            """,
            (account_id, provider, now),
        )

    def record_outcome(
        self,
        provider: str,
        *,
        account_id: str | None = None,
        status_code: int | None = None,
        error_kind: str | None = None,
        retry_after: int | None = None,
        latency_ms: int | None = None,
        quota_remaining: float | None = None,
        trace_id: str = "",
    ) -> None:
        provider = _validate(provider, _PROVIDER_ID, "provider")
        if account_id is not None:
            account_id = _validate(account_id, _ACCOUNT_ID, "account id")
        status_code = int(status_code) if status_code is not None else None
        now_dt = _utc_now()
        now = _as_iso(now_dt)
        event_type = "provider_success"
        detail: dict[str, Any] = {
            "status_code": status_code,
            "error_kind": error_kind,
            "retry_after": retry_after,
        }
        with self._transaction() as connection:
            self._ensure_provider(connection, provider, now)
            if account_id:
                self._ensure_account(connection, provider, account_id, now)

            if status_code in {401, 403} and account_id:
                event_type = "account_auth_error"
                connection.execute(
                    """
                    UPDATE provider_accounts
                    SET status = 'AUTH_ERROR', last_error_code = ?, cooldown_until = NULL,
                        updated_at = ?
                    WHERE account_id = ?
                    """,
                    (status_code, now, account_id),
                )
            elif status_code == 429 and account_id:
                event_type = "account_cooldown"
                cooldown = _as_iso(now_dt + timedelta(seconds=max(1, retry_after or 60)))
                connection.execute(
                    """
                    UPDATE provider_accounts
                    SET status = 'COOLDOWN', last_error_code = 429, cooldown_until = ?,
                        quota_remaining = COALESCE(?, quota_remaining), updated_at = ?
                    WHERE account_id = ?
                    """,
                    (cooldown, quota_remaining, now, account_id),
                )
            elif (status_code is not None and status_code >= 500) or error_kind in {
                "timeout",
                "transport",
            }:
                event_type = "provider_failure"
                row = connection.execute(
                    "SELECT consecutive_failures FROM provider_health WHERE provider = ?",
                    (provider,),
                ).fetchone()
                failures = int(row["consecutive_failures"]) + 1
                opened = failures >= self.circuit_threshold
                connection.execute(
                    """
                    UPDATE provider_health
                    SET consecutive_failures = ?, circuit_status = ?,
                        circuit_open_until = ?, last_status_code = ?,
                        latency_ms = COALESCE(?, latency_ms), updated_at = ?
                    WHERE provider = ?
                    """,
                    (
                        failures,
                        "OPEN" if opened else "CLOSED",
                        _as_iso(now_dt + timedelta(seconds=60)) if opened else None,
                        status_code,
                        latency_ms,
                        now,
                        provider,
                    ),
                )
            elif status_code is None or 200 <= status_code < 400:
                connection.execute(
                    """
                    UPDATE provider_health
                    SET consecutive_failures = 0, circuit_status = 'CLOSED',
                        circuit_open_until = NULL, last_status_code = ?,
                        latency_ms = COALESCE(?, latency_ms), updated_at = ?
                    WHERE provider = ?
                    """,
                    (status_code, latency_ms, now, provider),
                )
                if account_id:
                    connection.execute(
                        """
                        UPDATE provider_accounts
                        SET status = 'READY', cooldown_until = NULL, last_error_code = NULL,
                            quota_remaining = COALESCE(?, quota_remaining), updated_at = ?
                        WHERE account_id = ?
                        """,
                        (quota_remaining, now, account_id),
                    )
            else:
                event_type = "request_error"
                connection.execute(
                    """
                    UPDATE provider_health
                    SET last_status_code = ?, latency_ms = COALESCE(?, latency_ms),
                        updated_at = ?
                    WHERE provider = ?
                    """,
                    (status_code, latency_ms, now, provider),
                )

            connection.execute(
                """
                INSERT INTO routing_events(
                    trace_id, event_type, provider, account_id, route, detail_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id or f"evt-{now_dt.timestamp()}",
                    event_type,
                    provider,
                    account_id,
                    None,
                    json.dumps(detail, sort_keys=True),
                    now,
                ),
            )

    def record_decision(
        self,
        *,
        trace_id: str,
        route: str,
        provider: str,
        model: str,
        score: float,
        manual: bool,
        detail: dict[str, Any],
    ) -> None:
        now = _as_iso()
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO routing_decisions(
                    trace_id, route, provider, model, score, manual, detail_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    route,
                    provider,
                    model,
                    float(score),
                    int(manual),
                    json.dumps(detail, sort_keys=True),
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO routing_events(
                    trace_id, event_type, provider, account_id, route, detail_json, created_at
                ) VALUES (?, 'routing_decision', ?, NULL, ?, ?, ?)
                """,
                (trace_id, provider, route, json.dumps(detail, sort_keys=True), now),
            )

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, trace_id, event_type, provider, account_id, route,
                       detail_json, created_at
                FROM routing_events ORDER BY event_id DESC LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "trace_id": row["trace_id"],
                "event_type": row["event_type"],
                "provider": row["provider"],
                "account_id": row["account_id"],
                "route": row["route"],
                "detail": json.loads(row["detail_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def status(self) -> dict[str, Any]:
        with self._connect() as connection:
            providers = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM provider_health ORDER BY provider"
                ).fetchall()
            ]
            accounts = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM provider_accounts ORDER BY provider, account_id"
                ).fetchall()
            ]
        return {
            "active_profile": self.active_profile(),
            "manual_override": self.manual_override(),
            "profiles": self.list_profiles(),
            "providers": providers,
            "accounts": accounts,
        }
