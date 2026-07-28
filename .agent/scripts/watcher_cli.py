#!/usr/bin/env python3
"""Watcher CLI — cliente read-only sobre el SQLite del ProcessWatcher.

Pensado para ser llamado por Nexus (Tauri) o cualquier otro cliente que
necesite inspeccionar el estado persistido sin mantener un engine en memoria.

Operaciones soportadas:
    list                    -> lista watches (activos y finalizados recientes)
    status <watch_id>       -> estado + patterns de un watch
    matches <watch_id> [N]  -> ultimos N matches
    stats                   -> metricas globales
    kill <watch_id>         -> manda SIGTERM al pid persistido

Nota: spawn requiere un engine vivo (matching threads) y por lo tanto NO
se expone aqui. Usa el MCP `antigravity-watcher` (Claude Code) o el bot
de Telegram para spawnear.

Salida: siempre JSON a stdout, exit code 0 si success, 1 si error.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import sys
from pathlib import Path


def _resolve_state_path() -> Path:
    override = os.environ.get("ANTIGRAVITY_WATCHER_STATE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".antigravity" / "watcher" / "state.db"


def _conn() -> sqlite3.Connection:
    path = _resolve_state_path()
    if not path.exists():
        raise SystemExit(json.dumps({"success": False, "error": f"store no existe en {path}"}))
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_list(args: argparse.Namespace) -> dict:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT watch_id, label, cmd, cwd, pid, state, exit_code, "
            "started_at, ended_at, match_count "
            "FROM watches ORDER BY started_at DESC LIMIT ?",
            (args.limit,),
        ).fetchall()
    return {
        "success": True,
        "watches": [dict(r) for r in rows],
    }


def cmd_status(args: argparse.Namespace) -> dict:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM watches WHERE watch_id = ?", (args.watch_id,)).fetchone()
    if row is None:
        return {"success": False, "error": f"watch_id desconocido: {args.watch_id}"}
    data = dict(row)
    try:
        data["patterns"] = json.loads(data.pop("patterns_json") or "[]")
    except json.JSONDecodeError:
        data["patterns"] = []
    return {"success": True, **data}


def cmd_matches(args: argparse.Namespace) -> dict:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT pattern_label, importance, line_text, line_number, stream, matched_at "
            "FROM matches WHERE watch_id = ? ORDER BY matched_at DESC LIMIT ?",
            (args.watch_id, args.limit),
        ).fetchall()
    return {
        "success": True,
        "watch_id": args.watch_id,
        "matches": [dict(r) for r in rows],
    }


def cmd_stats(args: argparse.Namespace) -> dict:
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM watches").fetchone()["n"]
        by_state = {
            r["state"]: r["n"]
            for r in conn.execute("SELECT state, COUNT(*) AS n FROM watches GROUP BY state")
        }
        total_matches = conn.execute("SELECT COUNT(*) AS n FROM matches").fetchone()["n"]
        active = by_state.get("running", 0)
    return {
        "success": True,
        "total_watches": total,
        "by_state": by_state,
        "total_matches": total_matches,
        "active_running": active,
    }


def cmd_kill(args: argparse.Namespace) -> dict:
    """Manda SIGTERM al pid del watch si sigue vivo.

    El engine que creo el watch (MCP server, bot Telegram) detectara la
    muerte del proceso y actualizara el state a 'killed' o 'exited' al
    proximo wait(). Si el engine no esta vivo, el state en DB no se actualiza
    pero el proceso ya esta muerto — el usuario puede usar watch_cleanup
    para purgar eventualmente.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT pid, state FROM watches WHERE watch_id = ?", (args.watch_id,)
        ).fetchone()
    if row is None:
        return {"success": False, "error": f"watch_id desconocido: {args.watch_id}"}
    if row["state"] != "running":
        return {"success": False, "error": f"watch no esta running: {row['state']}"}
    pid = row["pid"]
    if not pid:
        return {"success": False, "error": "no pid registrado"}
    try:
        os.kill(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        return {"success": False, "error": f"proceso {pid} ya no existe"}
    except PermissionError as exc:
        return {"success": False, "error": f"sin permiso para kill pid {pid}: {exc}"}
    return {"success": True, "watch_id": args.watch_id, "pid": pid, "signal": "SIGTERM"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Watcher CLI read-only")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(fn=cmd_list)

    p_status = sub.add_parser("status")
    p_status.add_argument("watch_id")
    p_status.set_defaults(fn=cmd_status)

    p_matches = sub.add_parser("matches")
    p_matches.add_argument("watch_id")
    p_matches.add_argument("--limit", type=int, default=50)
    p_matches.set_defaults(fn=cmd_matches)

    p_stats = sub.add_parser("stats")
    p_stats.set_defaults(fn=cmd_stats)

    p_kill = sub.add_parser("kill")
    p_kill.add_argument("watch_id")
    p_kill.set_defaults(fn=cmd_kill)

    args = parser.parse_args()
    try:
        result = args.fn(args)
    except Exception as exc:  # noqa: BLE001
        result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
