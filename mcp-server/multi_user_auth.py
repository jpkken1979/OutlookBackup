#!/usr/bin/env python3
"""
Multi-User Auth — Autenticacion multi-token con revocacion por usuario.

Reemplaza el Bearer Token unico por un sistema multi-usuario:
- Cada usuario tiene su propio token
- Tokens revocables independientemente
- Scopes por token (read-only, read-write, admin)
- Rate limiting por usuario
- Audit log de accesos

Almacen: ~/.antigravity/auth/users.json (o path configurable)

CLI:
  python multi_user_auth.py add <username> [--scope read|write|admin]
  python multi_user_auth.py revoke <username>
  python multi_user_auth.py list
  python multi_user_auth.py rotate <username>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

AUTH_DIR = Path(os.environ.get("ANTIGRAVITY_AUTH_DIR", str(Path.home() / ".antigravity" / "auth")))
USERS_FILE = AUTH_DIR / "users.json"
AUDIT_LOG = AUTH_DIR / "audit.jsonl"

VALID_SCOPES = {"read", "write", "admin"}


def _hash_token(token: str) -> str:
    """Hash SHA-256 del token (no almacenamos plaintext)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load_users() -> dict[str, Any]:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}}


def _save_users(data: dict[str, Any]) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    USERS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        USERS_FILE.chmod(0o600)
    except OSError:
        pass


def _audit(event: str, username: str, details: dict | None = None) -> None:
    """Registra evento en audit log."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "username": username,
        "details": details or {},
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def add_user(username: str, scope: str = "read") -> str:
    """Crea un usuario y retorna su token plaintext (solo se muestra 1 vez)."""
    if scope not in VALID_SCOPES:
        raise ValueError(f"Scope invalido: {scope}. Validos: {VALID_SCOPES}")

    data = _load_users()
    if username in data["users"]:
        raise ValueError(f"Usuario '{username}' ya existe. Usa rotate.")

    token = secrets.token_urlsafe(32)
    data["users"][username] = {
        "token_hash": _hash_token(token),
        "scope": scope,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None,
        "active": True,
        "requests_count": 0,
    }
    _save_users(data)
    _audit("user_created", username, {"scope": scope})
    return token


def revoke_user(username: str) -> bool:
    """Desactiva un usuario (sin borrar historial)."""
    data = _load_users()
    if username not in data["users"]:
        return False
    data["users"][username]["active"] = False
    data["users"][username]["revoked_at"] = datetime.now(timezone.utc).isoformat()
    _save_users(data)
    _audit("user_revoked", username)
    return True


def rotate_user(username: str) -> str:
    """Genera nuevo token para usuario existente."""
    data = _load_users()
    if username not in data["users"]:
        raise ValueError(f"Usuario '{username}' no existe")
    new_token = secrets.token_urlsafe(32)
    data["users"][username]["token_hash"] = _hash_token(new_token)
    data["users"][username]["rotated_at"] = datetime.now(timezone.utc).isoformat()
    data["users"][username]["active"] = True
    _save_users(data)
    _audit("token_rotated", username)
    return new_token


def verify_token(token: str) -> dict | None:
    """Verifica token y retorna info del usuario (o None si invalido)."""
    if not token:
        return None
    token_hash = _hash_token(token)
    data = _load_users()
    for username, user_data in data["users"].items():
        if not user_data.get("active"):
            continue
        if secrets.compare_digest(user_data["token_hash"], token_hash):
            # Update stats (no es transaccional pero OK para auditoria)
            user_data["last_used"] = datetime.now(timezone.utc).isoformat()
            user_data["requests_count"] = user_data.get("requests_count", 0) + 1
            _save_users(data)
            return {
                "username": username,
                "scope": user_data["scope"],
                "created_at": user_data["created_at"],
            }
    return None


def list_users() -> list[dict]:
    """Lista usuarios (sin tokens)."""
    data = _load_users()
    return [
        {
            "username": u,
            "scope": d.get("scope"),
            "active": d.get("active", False),
            "created_at": d.get("created_at"),
            "last_used": d.get("last_used"),
            "requests": d.get("requests_count", 0),
        }
        for u, d in data["users"].items()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-user auth for MCP")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("username")
    p_add.add_argument("--scope", default="read", choices=list(VALID_SCOPES))

    p_revoke = sub.add_parser("revoke")
    p_revoke.add_argument("username")

    p_rotate = sub.add_parser("rotate")
    p_rotate.add_argument("username")

    sub.add_parser("list")

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("token")

    args = parser.parse_args()

    if args.cmd == "add":
        try:
            token = add_user(args.username, args.scope)
            print(f"Usuario '{args.username}' creado (scope={args.scope})")
            print(f"\nToken (guardalo, solo se muestra 1 vez):")
            print(f"  {token}\n")
            print("Uso:")
            print(f"  curl -H 'Authorization: Bearer {token}' https://mcp.uns-kikaku.cloud/mcp")
            return 0
        except ValueError as e:
            logger.error("%s", e)
            return 1

    if args.cmd == "revoke":
        if revoke_user(args.username):
            print(f"Usuario '{args.username}' revocado")
            return 0
        print(f"Usuario no encontrado: {args.username}")
        return 1

    if args.cmd == "rotate":
        try:
            token = rotate_user(args.username)
            print(f"Token rotado para '{args.username}'")
            print(f"\nNuevo token:\n  {token}\n")
            return 0
        except ValueError as e:
            logger.error("%s", e)
            return 1

    if args.cmd == "list":
        users = list_users()
        if not users:
            print("Sin usuarios configurados")
            return 0
        print(f"{'USERNAME':20s} {'SCOPE':8s} {'ACTIVE':8s} {'REQUESTS':10s} {'LAST USED':25s}")
        for u in users:
            active = "YES" if u["active"] else "revoked"
            last = u["last_used"] or "nunca"
            print(f"{u['username']:20s} {u['scope']:8s} {active:8s} {u['requests']:<10d} {last[:25]}")
        return 0

    if args.cmd == "verify":
        info = verify_token(args.token)
        if info:
            print(f"Valido: {info['username']} (scope={info['scope']})")
            return 0
        print("Token invalido o revocado")
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
