"""PKCE pairing, scoped access tokens and one-time approvals for mobile Nexus."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import sqlite3
import threading
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

PAIRING_TTL_SECONDS: Final = 300
ACCESS_TOKEN_TTL_SECONDS: Final = 900
APPROVAL_TTL_SECONDS: Final = 300
READ_SCOPES: Final = frozenset(
    {
        "status:read",
        "providers:read",
        "routing:read",
        "sessions:read",
        "activity:read",
    }
)
OPTIONAL_SCOPES: Final = frozenset({"actions:request"})
ALLOWED_SCOPES: Final = READ_SCOPES | OPTIONAL_SCOPES
DEFAULT_SCOPES: Final = tuple(sorted(READ_SCOPES))
_PKCE_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class PairingStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairing_id: str
    pairing_secret: str
    user_code: str
    device_name: str
    requested_scopes: list[str]
    expires_at: str


class PairingStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairing_id: str
    user_code: str
    device_name: str
    status: str
    requested_scopes: list[str]
    approved_scopes: list[str]
    expires_at: str


class AccessGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    expires_at: str
    scopes: list[str]
    device_name: str


class AccessIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_id: str
    device_name: str
    scopes: list[str]
    created_at: str
    expires_at: str
    last_seen_at: str | None


class ActionApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    token_id: str
    device_name: str
    action: str
    payload: dict[str, Any]
    payload_digest: str
    status: str
    created_at: str
    expires_at: str
    resolved_at: str | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _scopes(values: list[str] | tuple[str, ...] | None) -> list[str]:
    requested = values or list(DEFAULT_SCOPES)
    normalized = sorted({str(value).strip().lower() for value in requested})
    if not normalized or any(value not in ALLOWED_SCOPES for value in normalized):
        raise ValueError("Invalid remote control scopes")
    return normalized


def _device_name(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > 80 or any(ord(char) < 32 for char in normalized):
        raise ValueError("Invalid device name")
    return normalized


def _payload_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _hash(encoded)


def _approval_from_row(row: sqlite3.Row) -> ActionApproval:
    data = dict(row)
    payload_json = data.pop("payload_json", "{}")
    try:
        payload = json.loads(payload_json)
    except (json.JSONDecodeError, TypeError):
        payload = {}
    data["payload"] = payload if isinstance(payload, dict) else {}
    return ActionApproval(**data)


class RemotePairingStore:
    """SQLite-backed control-plane credentials with atomic one-time transitions."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS remote_pairings (
                    pairing_id TEXT PRIMARY KEY,
                    secret_hash TEXT NOT NULL,
                    user_code TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    code_challenge TEXT NOT NULL,
                    requested_scopes TEXT NOT NULL,
                    approved_scopes TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS remote_access_tokens (
                    token_id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    device_name TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS remote_action_approvals (
                    approval_id TEXT PRIMARY KEY,
                    token_id TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    payload_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY(token_id) REFERENCES remote_access_tokens(token_id)
                );
                CREATE INDEX IF NOT EXISTS idx_remote_pairings_status
                    ON remote_pairings(status, expires_at);
                CREATE INDEX IF NOT EXISTS idx_remote_tokens_hash
                    ON remote_access_tokens(token_hash, expires_at);
                CREATE INDEX IF NOT EXISTS idx_remote_approvals_status
                    ON remote_action_approvals(status, expires_at);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(remote_pairings)").fetchall()
            }
            if "user_code" not in columns:
                connection.execute(
                    "ALTER TABLE remote_pairings ADD COLUMN user_code TEXT NOT NULL DEFAULT ''"
                )
            approval_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(remote_action_approvals)"
                ).fetchall()
            }
            if "payload_json" not in approval_columns:
                connection.execute(
                    "ALTER TABLE remote_action_approvals "
                    "ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}'"
                )
                connection.execute(
                    """
                    UPDATE remote_action_approvals
                    SET status = 'expired', resolved_at = ?
                    WHERE status IN ('pending', 'approved')
                    """,
                    (_iso(_utc_now()),),
                )

    def start_pairing(
        self,
        *,
        device_name: str,
        code_challenge: str,
        requested_scopes: list[str] | None = None,
    ) -> PairingStart:
        device = _device_name(device_name)
        challenge = code_challenge.strip()
        if not _PKCE_CHALLENGE.fullmatch(challenge):
            raise ValueError("PKCE S256 challenge must be 43 base64url characters")
        scopes = _scopes(requested_scopes)
        now = _utc_now()
        expires = now + timedelta(seconds=PAIRING_TTL_SECONDS)
        pairing_id = f"pair_{secrets.token_urlsafe(18)}"
        pairing_secret = secrets.token_urlsafe(32)
        user_code = f"{secrets.randbelow(1_000_000):06d}"
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO remote_pairings(
                    pairing_id, secret_hash, user_code, device_name, code_challenge,
                    requested_scopes, status, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    pairing_id,
                    _hash(pairing_secret),
                    user_code,
                    device,
                    challenge,
                    json.dumps(scopes),
                    _iso(now),
                    _iso(expires),
                ),
            )
        return PairingStart(
            pairing_id=pairing_id,
            pairing_secret=pairing_secret,
            user_code=user_code,
            device_name=device,
            requested_scopes=scopes,
            expires_at=_iso(expires),
        )

    def pairing_status(self, pairing_id: str, pairing_secret: str) -> PairingStatus | None:
        if not _OPAQUE_ID.fullmatch(pairing_id):
            return None
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM remote_pairings WHERE pairing_id = ?",
                (pairing_id,),
            ).fetchone()
            if row is None or not secrets.compare_digest(row["secret_hash"], _hash(pairing_secret)):
                return None
            status = row["status"]
            if (
                status in {"pending", "approved"}
                and datetime.fromisoformat(row["expires_at"]) <= _utc_now()
            ):
                status = "expired"
                connection.execute(
                    "UPDATE remote_pairings SET status = 'expired' WHERE pairing_id = ?",
                    (pairing_id,),
                )
            return PairingStatus(
                pairing_id=pairing_id,
                user_code=row["user_code"],
                device_name=row["device_name"],
                status=status,
                requested_scopes=json.loads(row["requested_scopes"]),
                approved_scopes=json.loads(row["approved_scopes"]),
                expires_at=row["expires_at"],
            )

    def list_pairings(self, status: str = "pending", limit: int = 100) -> list[PairingStatus]:
        safe_status = (
            status if status in {"pending", "approved", "denied", "expired", "all"} else "pending"
        )
        query = "SELECT * FROM remote_pairings"
        parameters: list[Any] = []
        if safe_status != "all":
            query += " WHERE status = ?"
            parameters.append(safe_status)
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(min(max(limit, 1), 500))
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE remote_pairings SET status = 'expired'
                WHERE status IN ('pending', 'approved') AND expires_at <= ?
                """,
                (_iso(_utc_now()),),
            )
            rows = connection.execute(query, parameters).fetchall()
        return [
            PairingStatus(
                pairing_id=row["pairing_id"],
                user_code=row["user_code"],
                device_name=row["device_name"],
                status=row["status"],
                requested_scopes=json.loads(row["requested_scopes"]),
                approved_scopes=json.loads(row["approved_scopes"]),
                expires_at=row["expires_at"],
            )
            for row in rows
        ]

    def decide_pairing(
        self,
        pairing_id: str,
        *,
        approved: bool,
        scopes: list[str] | None = None,
    ) -> PairingStatus | None:
        if not _OPAQUE_ID.fullmatch(pairing_id):
            return None
        now = _utc_now()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM remote_pairings WHERE pairing_id = ? AND status = 'pending'",
                (pairing_id,),
            ).fetchone()
            if row is None or datetime.fromisoformat(row["expires_at"]) <= now:
                return None
            requested = set(json.loads(row["requested_scopes"]))
            approved_scopes = _scopes(scopes) if approved else []
            if not set(approved_scopes).issubset(requested):
                raise ValueError("Approved scopes must be a subset of requested scopes")
            status = "approved" if approved else "denied"
            connection.execute(
                """
                UPDATE remote_pairings
                SET status = ?, approved_scopes = ?, approved_at = ?
                WHERE pairing_id = ? AND status = 'pending'
                """,
                (status, json.dumps(approved_scopes), _iso(now), pairing_id),
            )
        return self.pairing_status_by_admin(pairing_id)

    def pairing_status_by_admin(self, pairing_id: str) -> PairingStatus | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM remote_pairings WHERE pairing_id = ?",
                (pairing_id,),
            ).fetchone()
        if row is None:
            return None
        return PairingStatus(
            pairing_id=row["pairing_id"],
            user_code=row["user_code"],
            device_name=row["device_name"],
            status=row["status"],
            requested_scopes=json.loads(row["requested_scopes"]),
            approved_scopes=json.loads(row["approved_scopes"]),
            expires_at=row["expires_at"],
        )

    def exchange(
        self,
        *,
        pairing_id: str,
        pairing_secret: str,
        code_verifier: str,
    ) -> AccessGrant | None:
        if not _OPAQUE_ID.fullmatch(pairing_id) or not 43 <= len(code_verifier) <= 128:
            return None
        now = _utc_now()
        expires = now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        raw_token = secrets.token_urlsafe(32)
        token_id = f"rctl_{secrets.token_urlsafe(18)}"
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM remote_pairings WHERE pairing_id = ?",
                (pairing_id,),
            ).fetchone()
            if (
                row is None
                or row["status"] != "approved"
                or datetime.fromisoformat(row["expires_at"]) <= now
                or not secrets.compare_digest(row["secret_hash"], _hash(pairing_secret))
                or not secrets.compare_digest(row["code_challenge"], _pkce_challenge(code_verifier))
            ):
                return None
            scopes = json.loads(row["approved_scopes"])
            updated = connection.execute(
                """
                UPDATE remote_pairings SET status = 'exchanged'
                WHERE pairing_id = ? AND status = 'approved'
                """,
                (pairing_id,),
            )
            if updated.rowcount != 1:
                return None
            connection.execute(
                """
                INSERT INTO remote_access_tokens(
                    token_id, token_hash, device_name, scopes, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    _hash(raw_token),
                    row["device_name"],
                    json.dumps(scopes),
                    _iso(now),
                    _iso(expires),
                ),
            )
        return AccessGrant(
            access_token=raw_token,
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            expires_at=_iso(expires),
            scopes=scopes,
            device_name=row["device_name"],
        )

    def authenticate(
        self,
        access_token: str,
        required_scope: str | None = None,
    ) -> AccessIdentity | None:
        if not access_token:
            return None
        now = _utc_now()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM remote_access_tokens
                WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?
                """,
                (_hash(access_token), _iso(now)),
            ).fetchone()
            if row is None:
                return None
            scopes = json.loads(row["scopes"])
            if required_scope is not None and required_scope not in scopes:
                return None
            connection.execute(
                "UPDATE remote_access_tokens SET last_seen_at = ? WHERE token_id = ?",
                (_iso(now), row["token_id"]),
            )
        return AccessIdentity(
            token_id=row["token_id"],
            device_name=row["device_name"],
            scopes=scopes,
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_seen_at=_iso(now),
        )

    def list_access_tokens(self, limit: int = 100) -> list[AccessIdentity]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM remote_access_tokens
                WHERE revoked_at IS NULL AND expires_at > ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (_iso(_utc_now()), min(max(limit, 1), 500)),
            ).fetchall()
        return [
            AccessIdentity(
                token_id=row["token_id"],
                device_name=row["device_name"],
                scopes=json.loads(row["scopes"]),
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                last_seen_at=row["last_seen_at"],
            )
            for row in rows
        ]

    def revoke_access_token(self, token_id: str) -> bool:
        if not _OPAQUE_ID.fullmatch(token_id):
            return False
        with self._lock, self._connect() as connection:
            result = connection.execute(
                """
                UPDATE remote_access_tokens SET revoked_at = ?
                WHERE token_id = ? AND revoked_at IS NULL
                """,
                (_iso(_utc_now()), token_id),
            )
        return result.rowcount == 1

    def request_action_approval(
        self,
        *,
        access_token: str,
        action: str,
        payload: Mapping[str, Any],
    ) -> ActionApproval | None:
        identity = self.authenticate(access_token, "actions:request")
        normalized_action = action.strip().lower()
        if identity is None or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,80}", normalized_action):
            return None
        now = _utc_now()
        expires = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
        approval = ActionApproval(
            approval_id=f"rapp_{secrets.token_urlsafe(18)}",
            token_id=identity.token_id,
            device_name=identity.device_name,
            action=normalized_action,
            payload=dict(payload),
            payload_digest=_payload_digest(payload),
            status="pending",
            created_at=_iso(now),
            expires_at=_iso(expires),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO remote_action_approvals(
                    approval_id, token_id, device_name, action, payload_json, payload_digest,
                    status, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.token_id,
                    approval.device_name,
                    approval.action,
                    json.dumps(
                        approval.payload,
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    approval.payload_digest,
                    approval.created_at,
                    approval.expires_at,
                ),
            )
        return approval

    def list_action_approvals(self, status: str = "pending") -> list[ActionApproval]:
        safe_status = (
            status
            if status in {"pending", "approved", "denied", "expired", "consumed", "all"}
            else "pending"
        )
        query = "SELECT * FROM remote_action_approvals"
        parameters: list[Any] = []
        if safe_status != "all":
            query += " WHERE status = ?"
            parameters.append(safe_status)
        query += " ORDER BY created_at DESC LIMIT 200"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_approval_from_row(row) for row in rows]

    def action_approval_status(
        self,
        *,
        access_token: str,
        approval_id: str,
    ) -> ActionApproval | None:
        identity = self.authenticate(access_token, "actions:request")
        if identity is None or not _OPAQUE_ID.fullmatch(approval_id):
            return None
        now = _iso(_utc_now())
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE remote_action_approvals
                SET status = 'expired', resolved_at = ?
                WHERE approval_id = ? AND token_id = ? AND status IN ('pending', 'approved')
                  AND expires_at <= ?
                """,
                (now, approval_id, identity.token_id, now),
            )
            row = connection.execute(
                """
                SELECT * FROM remote_action_approvals
                WHERE approval_id = ? AND token_id = ?
                """,
                (approval_id, identity.token_id),
            ).fetchone()
        return _approval_from_row(row) if row else None

    def decide_action_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
    ) -> ActionApproval | None:
        if not _OPAQUE_ID.fullmatch(approval_id):
            return None
        now = _utc_now()
        with self._lock, self._connect() as connection:
            result = connection.execute(
                """
                UPDATE remote_action_approvals
                SET status = ?, resolved_at = ?
                WHERE approval_id = ? AND status = 'pending' AND expires_at > ?
                """,
                (
                    "approved" if approved else "denied",
                    _iso(now),
                    approval_id,
                    _iso(now),
                ),
            )
            if result.rowcount != 1:
                return None
            row = connection.execute(
                "SELECT * FROM remote_action_approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        return _approval_from_row(row) if row else None

    def consume_action_approval(
        self,
        *,
        access_token: str,
        approval_id: str,
        action: str,
        payload: Mapping[str, Any],
    ) -> bool:
        identity = self.authenticate(access_token, "actions:request")
        if identity is None or not _OPAQUE_ID.fullmatch(approval_id):
            return False
        with self._lock, self._connect() as connection:
            result = connection.execute(
                """
                UPDATE remote_action_approvals
                SET status = 'consumed', resolved_at = ?
                WHERE approval_id = ? AND token_id = ? AND action = ?
                  AND payload_digest = ? AND status = 'approved' AND expires_at > ?
                """,
                (
                    _iso(_utc_now()),
                    approval_id,
                    identity.token_id,
                    action.strip().lower(),
                    _payload_digest(payload),
                    _iso(_utc_now()),
                ),
            )
        return result.rowcount == 1
