#!/usr/bin/env python3
"""Render the current CodexBar quota snapshot for slash commands.

The default mode is intentionally read-only: it reads ~/.codexbar/snapshots.json,
which is the same cache the tray UI persists after refreshes. Use --refresh only
when a live CodexBar CLI refresh is desired, because that may rewrite the cache.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROVIDER_NAMES: dict[str, str] = {
    "claude": "Claude",
    "codex": "OpenAI Codex",
    "copilot": "GitHub Copilot",
    "minimax": "MiniMax",
    "zai": "z.ai",
    "antigravity": "Antigravity",
    "openrouter": "OpenRouter",
    "opencode": "OpenCode",
    "opencode-go": "OpenCode Go",
}

DEFAULT_ORDER = [
    "claude",
    "codex",
    "copilot",
    "minimax",
    "zai",
    "antigravity",
    "openrouter",
    "opencode",
    "opencode-go",
]


def home_path(*parts: str) -> Path:
    return Path(os.path.expanduser("~")).joinpath(*parts)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def enabled_order(config: dict[str, Any] | None) -> list[str]:
    if not config:
        return DEFAULT_ORDER

    providers = config.get("providers")
    if not isinstance(providers, list):
        return DEFAULT_ORDER

    order = [
        str(provider.get("id"))
        for provider in providers
        if isinstance(provider, dict)
        and provider.get("enabled", True) is not False
        and provider.get("id")
    ]
    return order or DEFAULT_ORDER


def filter_enabled_snapshots(
    snapshots: dict[str, Any], config: dict[str, Any] | None
) -> dict[str, Any]:
    if not config or not isinstance(config.get("providers"), list):
        return snapshots

    enabled = set(enabled_order(config))
    return {
        provider_id: snapshot
        for provider_id, snapshot in snapshots.items()
        if provider_id in enabled
    }


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def format_duration(target: Any, now: datetime | None = None) -> str:
    parsed = parse_dt(target)
    if not parsed:
        return ""
    base = now or datetime.now(UTC)
    seconds = math.floor((parsed.astimezone(UTC) - base).total_seconds())
    if seconds <= 0:
        return "vencido"

    days, rem = divmod(seconds, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes = rem // 60

    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_percent(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "sin dato"
    if not math.isfinite(number):
        return "sin dato"
    if abs(number - round(number)) < 0.05:
        return f"{int(round(number))}%"
    return f"{number:.1f}%"


def provider_label(provider_id: str) -> str:
    return PROVIDER_NAMES.get(provider_id, provider_id)


def window_text(window: dict[str, Any] | None, now: datetime) -> str:
    if not isinstance(window, dict):
        return "sin dato"
    pct = format_percent(window.get("usedPercent"))
    reset = format_duration(window.get("resetsAt"), now)
    return f"{pct} ({reset})" if reset else pct


def top_line(provider_id: str, snapshot: dict[str, Any], now: datetime) -> str:
    name = provider_label(provider_id)
    if snapshot.get("error"):
        return f"{name} - error: {snapshot['error']}"
    return f"{name} - {window_text(snapshot.get('primary'), now)}"


def quota_windows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for key in ("primary", "secondary", "tertiary"):
        value = snapshot.get(key)
        if isinstance(value, dict):
            windows.append(value)
    extras = snapshot.get("extraQuotas")
    if isinstance(extras, list):
        windows.extend(extra for extra in extras if isinstance(extra, dict))
    return windows


def detail_lines(provider_id: str, snapshot: dict[str, Any], now: datetime) -> list[str]:
    name = provider_label(provider_id)
    if snapshot.get("error"):
        return [f"{name}:", f"  ERROR - {snapshot['error']}"]

    windows = quota_windows(snapshot)
    if len(windows) <= 1 and not snapshot.get("credits"):
        return []

    lines = [f"{name}:"]
    for window in windows:
        label = str(window.get("label") or "Quota").upper()
        lines.append(f"  {label} - {window_text(window, now)}")

    credits = snapshot.get("credits")
    if isinstance(credits, dict):
        used = credits.get("used")
        limit = credits.get("limit")
        currency = credits.get("currencyCode") or "USD"
        try:
            used_text = f"{float(used):.2f}"
            limit_text = f"{float(limit):.2f}"
            lines.append(f"  CREDITS - ${used_text} / ${limit_text} {currency}")
        except (TypeError, ValueError):
            pass
    return lines


def ordered_snapshots(
    snapshots: dict[str, Any], order: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    seen: set[str] = set()
    ordered: list[tuple[str, dict[str, Any]]] = []
    for provider_id in order:
        snapshot = snapshots.get(provider_id)
        if isinstance(snapshot, dict):
            ordered.append((provider_id, snapshot))
            seen.add(provider_id)
    for provider_id, snapshot in snapshots.items():
        if provider_id not in seen and isinstance(snapshot, dict):
            ordered.append((provider_id, snapshot))
    return ordered


def render_text(
    snapshots: dict[str, Any],
    order: list[str],
    *,
    snapshot_path: Path,
    now: datetime | None = None,
) -> str:
    base = now or datetime.now(UTC)
    entries = ordered_snapshots(snapshots, order)
    if not entries:
        return "CodexBar: no hay snapshots disponibles."

    try:
        stamp = datetime.fromtimestamp(snapshot_path.stat().st_mtime).strftime("%H:%M:%S")
    except OSError:
        stamp = "desconocida"

    lines = [f"CodexBar - snapshot local ({stamp})", "", "Panel superior:"]
    lines.extend(f"- {top_line(provider_id, snapshot, base)}" for provider_id, snapshot in entries)

    detail: list[str] = []
    for provider_id, snapshot in entries:
        provider_detail = detail_lines(provider_id, snapshot, base)
        if provider_detail:
            if detail:
                detail.append("")
            detail.extend(provider_detail)

    if detail:
        lines.extend(["", "Panel detallado:", *detail])

    lines.extend(
        [
            "",
            f"Fuente: {snapshot_path}",
            "Nota: usa --refresh si queres forzar un fetch live de CodexBar.",
        ]
    )
    return "\n".join(lines)


def run_refresh(codexbar_root: Path) -> str:
    cli = codexbar_root / "dist-electron" / "electron" / "cli" / "cli-entry.js"
    if not cli.exists():
        raise FileNotFoundError(f"No encontre el CLI de CodexBar en {cli}")
    completed = subprocess.run(
        ["node", str(cli), "usage", "--format", "json"],
        cwd=str(codexbar_root),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mostrar cuotas guardadas por CodexBar.")
    parser.add_argument("--json", action="store_true", help="Imprime el snapshot crudo.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresca via CLI de CodexBar antes de leer el cache.",
    )
    parser.add_argument(
        "--snapshot-path",
        default=str(home_path(".codexbar", "snapshots.json")),
        help="Ruta al snapshots.json de CodexBar.",
    )
    parser.add_argument(
        "--config-path",
        default=str(home_path(".codexbar", "config.json")),
        help="Ruta al config.json de CodexBar.",
    )
    parser.add_argument(
        "--codexbar-root",
        default=str(home_path("Github", "Jpkken1979", "CodexBar-mainJp26.3.30", "win-codexbar")),
        help="Checkout de win-codexbar para --refresh.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot_path = Path(args.snapshot_path)
    config_path = Path(args.config_path)

    try:
        if args.refresh:
            run_refresh(Path(args.codexbar_root))

        if not snapshot_path.exists():
            print(
                f"CodexBar: no existe {snapshot_path}. Abri CodexBar o ejecuta con --refresh.",
                file=sys.stderr,
            )
            return 1

        snapshots = load_json(snapshot_path)
        if not isinstance(snapshots, dict):
            raise ValueError("snapshots.json no tiene forma de objeto")

        config = load_json(config_path) if config_path.exists() else None
        snapshots = filter_enabled_snapshots(snapshots, config)
        if args.json:
            print(json.dumps(snapshots, ensure_ascii=False, indent=2))
        else:
            print(render_text(snapshots, enabled_order(config), snapshot_path=snapshot_path))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"CodexBar: error leyendo cuotas: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
