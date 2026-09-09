#!/usr/bin/env python3
"""Run OpenCodex with an exact, crash-recoverable Codex config backup.

OpenCodex already performs reversible injection.  This wrapper adds a separate
OpenAntigravity safety layer: immutable timestamped backups, an active recovery
marker, hash verification, and an atomic byte-for-byte restore.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

OCX_PORT = 10100
OCX_NPM_PACKAGE = "@bitkyc08/opencodex"
BACKUP_DIR_NAME = ".antigravity-ocx-backups"
ACTIVE_MARKER = "active.json"
BACKUP_RETENTION = 10
INJECTION_MARKERS = (
    "127.0.0.1:10100",
    "localhost:10100",
    'model_provider = "opencodex"',
    "managed by opencodex",
)


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()


def config_path(codex_home: Path) -> Path:
    return codex_home / "config.toml"


def backup_dir(codex_home: Path) -> Path:
    return codex_home / BACKUP_DIR_NAME


def active_marker_path(codex_home: Path) -> Path:
    return backup_dir(codex_home) / ACTIVE_MARKER


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def is_injected(content: bytes) -> bool:
    text = content.decode("utf-8", errors="replace").lower()
    return any(marker in text for marker in INJECTION_MARKERS)


def port_open(host: str = "127.0.0.1", port: int = OCX_PORT, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def atomic_write(path: Path, content: bytes) -> None:
    """Replace *path* atomically with flushed content in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _load_marker(codex_home: Path) -> dict[str, str] | None:
    marker = active_marker_path(codex_home)
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid recovery marker: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("invalid recovery marker payload")
    backup_name = data.get("backup")
    expected_hash = data.get("sha256")
    if not isinstance(backup_name, str) or not isinstance(expected_hash, str):
        raise RuntimeError("incomplete recovery marker")
    return {"backup": backup_name, "sha256": expected_hash}


def active_backup_path(codex_home: Path) -> Path | None:
    data = _load_marker(codex_home)
    if data is None:
        return None
    directory = backup_dir(codex_home).resolve()
    candidate = (directory / data["backup"]).resolve()
    if candidate.parent != directory or candidate.suffix != ".toml":
        raise RuntimeError("recovery marker points outside the backup directory")
    if not candidate.is_file():
        raise RuntimeError(f"active backup is missing: {candidate}")
    content = candidate.read_bytes()
    if sha256_bytes(content) != data["sha256"]:
        raise RuntimeError("active backup hash mismatch")
    return candidate


def _prune_backups(codex_home: Path) -> None:
    directory = backup_dir(codex_home)
    if not directory.is_dir():
        return
    active = active_backup_path(codex_home)
    candidates = sorted(
        directory.glob("config-*.toml"),
        key=lambda item: item.stat().st_mtime_ns,
        reverse=True,
    )
    retained = 0
    for candidate in candidates:
        if active is not None and candidate.resolve() == active.resolve():
            continue
        retained += 1
        if retained > BACKUP_RETENTION:
            candidate.unlink(missing_ok=True)


def create_backup(codex_home: Path) -> Path:
    """Create an immutable backup and its active recovery marker."""
    config = config_path(codex_home)
    if active_marker_path(codex_home).exists():
        raise RuntimeError("an active OpenCodex recovery session already exists")
    if not config.is_file():
        raise RuntimeError(f"Codex config does not exist: {config}")
    content = config.read_bytes()
    if is_injected(content):
        raise RuntimeError(
            "Codex config already looks injected; refusing to create a poisoned backup"
        )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = backup_dir(codex_home) / f"config-{stamp}-{uuid.uuid4().hex[:8]}.toml"
    atomic_write(destination, content)
    marker = {
        "backup": destination.name,
        "sha256": sha256_bytes(content),
        "created_at": datetime.now(UTC).isoformat(),
    }
    atomic_write(
        active_marker_path(codex_home),
        (json.dumps(marker, indent=2) + "\n").encode("utf-8"),
    )
    _prune_backups(codex_home)
    return destination


def restore_backup(codex_home: Path, selected: Path | None = None) -> Path:
    """Atomically restore a verified backup and clear the active marker."""
    backup = selected.resolve() if selected else active_backup_path(codex_home)
    if backup is None:
        raise RuntimeError("no active OpenCodex backup to restore")

    directory = backup_dir(codex_home).resolve()
    if backup.parent != directory or backup.suffix != ".toml" or not backup.is_file():
        raise RuntimeError("backup path is invalid")
    content = backup.read_bytes()
    marker_data = _load_marker(codex_home)
    if marker_data and backup.name == marker_data["backup"]:
        if sha256_bytes(content) != marker_data["sha256"]:
            raise RuntimeError("backup hash mismatch; refusing to restore")

    atomic_write(config_path(codex_home), content)
    restored = config_path(codex_home).read_bytes()
    if restored != content:
        raise RuntimeError("post-restore byte verification failed")
    active_marker_path(codex_home).unlink(missing_ok=True)
    return backup


def recover_stale_session(codex_home: Path) -> Path | None:
    """Recover a previous interrupted session when no OpenCodex proxy is alive."""
    active = active_backup_path(codex_home)
    if active is None:
        return None
    if port_open():
        raise RuntimeError("OpenCodex is still running; use the stop command first")
    return restore_backup(codex_home, active)


def resolve_ocx() -> Path:
    names = ("ocx.cmd", "ocx") if os.name == "nt" else ("ocx",)
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidate = Path(appdata) / "npm" / "ocx.cmd"
            if candidate.is_file():
                return candidate.resolve()
    raise RuntimeError(
        f"OpenCodex is not installed; install the official {OCX_NPM_PACKAGE} package"
    )


def is_ocx_installed() -> bool:
    try:
        resolve_ocx()
        return True
    except RuntimeError:
        return False


def installed_ocx_version() -> str | None:
    """Best-effort `ocx --version`; None if not installed or the call fails."""
    try:
        executable = resolve_ocx()
    except RuntimeError:
        return None
    try:
        completed = subprocess.run(
            ocx_command(executable, "--version"),
            text=True,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (completed.stdout or completed.stderr or "").strip()
    return output or None


def latest_ocx_version(timeout: float = 3.0) -> str | None:
    """Latest published version on the public npm registry, or None if unreachable."""
    url = f"https://registry.npmjs.org/{OCX_NPM_PACKAGE}/latest"
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None
    version = payload.get("version") if isinstance(payload, dict) else None
    return str(version) if version else None


def ocx_command(executable: Path, *arguments: str) -> list[str]:
    if os.name == "nt" and executable.suffix.lower() in {".cmd", ".bat"}:
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        command_line = subprocess.list2cmdline([str(executable), *arguments])
        return [comspec, "/d", "/s", "/c", command_line]
    return [str(executable), *arguments]


def run_ocx(
    *arguments: str,
    check: bool = False,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ocx_command(resolve_ocx(), *arguments),
        text=True,
        check=check,
        capture_output=capture_output,
    )


def wait_for_port(expected_open: bool, timeout: float = 12.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_open() is expected_open:
            return True
        time.sleep(0.2)
    return port_open() is expected_open


def probe_opencodex(timeout: float = 1.5) -> dict[str, object]:
    """Verify identity and catalog without sending an inference request."""
    if not port_open(timeout=min(timeout, 0.5)):
        return {"identity_ok": False, "health_ok": False, "catalog_count": 0}

    def read_json(path: str) -> dict[str, object]:
        request = urllib.request.Request(
            f"http://127.0.0.1:{OCX_PORT}{path}",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    health: dict[str, object] | None = None
    for attempt in range(3):
        try:
            health = read_json("/healthz")
            break
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            if attempt < 2:
                time.sleep(0.15)
    if health is None:
        return {"identity_ok": False, "health_ok": False, "catalog_count": 0}

    identity_ok = health.get("service") == "opencodex"
    health_ok = identity_ok and health.get("status") == "ok"
    catalog_count = 0
    if health_ok:
        for attempt in range(2):
            try:
                models = read_json("/v1/models")
                rows = models.get("data", [])
                catalog_count = len(rows) if isinstance(rows, list) else 0
                break
            except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
                if attempt == 0:
                    time.sleep(0.15)
    return {
        "identity_ok": identity_ok,
        "health_ok": health_ok,
        "catalog_count": catalog_count,
        "version": str(health.get("version", "")),
    }


def managed_status(codex_home: Path) -> dict[str, object]:
    active = active_backup_path(codex_home)
    config = config_path(codex_home)
    config_injected = config.is_file() and is_injected(config.read_bytes())
    port_running = port_open()
    probe = (
        probe_opencodex()
        if port_running
        else {
            "identity_ok": False,
            "health_ok": False,
            "catalog_count": 0,
        }
    )
    identity_ok = bool(probe.get("identity_ok"))
    health_ok = bool(probe.get("health_ok"))
    catalog_count = int(probe.get("catalog_count", 0) or 0)
    # Solo shutil.which(), sin red — barato, apto para el poll de status habitual.
    installed = is_ocx_installed()
    if not installed and not port_running:
        state = "not_installed"
    elif active is not None and not port_running:
        state = "recovery_required"
    elif port_running and not identity_ok:
        state = "foreign_service"
    elif health_ok and catalog_count > 0:
        state = "healthy" if active is not None else "unmanaged_healthy"
    elif identity_ok:
        state = "degraded"
    else:
        state = "stopped"
    return {
        "state": state,
        "managed": active is not None,
        "proxy_running": port_running,
        "port": OCX_PORT,
        "identity_ok": identity_ok,
        "health_ok": health_ok,
        "catalog_count": catalog_count,
        "version": str(probe.get("version", "")),
        "config_exists": config.is_file(),
        "config_injected": config_injected,
        "recovery_pending": active is not None,
        "recovery_backup": active.name if active else None,
        "installed": installed,
    }


def managed_install(codex_home: Path) -> dict[str, object]:
    """Install (or update) the official OpenCodex npm package globally."""
    if port_open():
        raise RuntimeError("OpenCodex is running; stop it before installing/updating")
    npm_executable = "npm.cmd" if os.name == "nt" else "npm"
    try:
        completed = subprocess.run(
            [npm_executable, "install", "-g", OCX_NPM_PACKAGE],
            text=True,
            capture_output=True,
            timeout=180,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("npm was not found on PATH; install Node.js 18+ first") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("npm install timed out after 180s") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        raise RuntimeError(f"npm install -g {OCX_NPM_PACKAGE} failed: {detail[:600]}")
    return managed_status(codex_home)


def check_ocx_update() -> dict[str, object]:
    """On-demand version check against the public npm registry (real network call —
    never invoked from the regular status poll, only when the user asks explicitly)."""
    installed = is_ocx_installed()
    installed_version = installed_ocx_version() if installed else None
    latest_version = latest_ocx_version()
    update_available = bool(
        installed_version and latest_version and installed_version != latest_version
    )
    return {
        "installed": installed,
        "installed_version": installed_version,
        "latest_version": latest_version,
        "update_available": update_available,
    }


def _rollback_managed_start(codex_home: Path, backup: Path) -> None:
    try:
        run_ocx("stop", capture_output=True)
    except OSError:
        pass
    if wait_for_port(False, timeout=8.0):
        restore_backup(codex_home, backup)


def managed_start(codex_home: Path) -> dict[str, object]:
    """Start the background service while retaining ownership for exact restore."""
    active = active_backup_path(codex_home)
    if port_open():
        status_payload = managed_status(codex_home)
        if status_payload["state"] == "healthy":
            return status_payload
        if status_payload["state"] == "unmanaged_healthy":
            raise RuntimeError(
                "OpenCodex is already running outside the managed lifecycle; stop it first"
            )
        raise RuntimeError("port 10100 is occupied by a service that is not healthy OpenCodex")

    if active is not None:
        restore_backup(codex_home, active)

    backup = create_backup(codex_home)
    try:
        completed = run_ocx("start", capture_output=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            raise RuntimeError(f"ocx start failed ({completed.returncode}): {detail[:600]}")
        if not wait_for_port(True):
            raise RuntimeError("OpenCodex did not become reachable on port 10100")
        status_payload = managed_status(codex_home)
        if status_payload["state"] != "healthy":
            raise RuntimeError(
                "OpenCodex failed identity, health, or catalog verification after start"
            )
        return status_payload
    except Exception:
        _rollback_managed_start(codex_home, backup)
        raise


def managed_stop(codex_home: Path) -> dict[str, object]:
    """Stop only a service owned by this wrapper and restore exact config bytes."""
    active = active_backup_path(codex_home)
    if active is None:
        if port_open():
            raise RuntimeError("refusing to stop an unmanaged OpenCodex service")
        return managed_status(codex_home)

    completed = run_ocx("stop", capture_output=True)
    if not wait_for_port(False):
        raise RuntimeError("OpenCodex is still running; recovery marker was preserved")
    restore_backup(codex_home, active)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        raise RuntimeError(
            f"ocx stop failed ({completed.returncode}) after restore: {detail[:600]}"
        )
    return managed_status(codex_home)


def managed_restart(codex_home: Path) -> dict[str, object]:
    if active_backup_path(codex_home) is None:
        raise RuntimeError("refusing to restart an unmanaged OpenCodex service")
    managed_stop(codex_home)
    return managed_start(codex_home)


def managed_restore(codex_home: Path) -> dict[str, object]:
    if port_open():
        raise RuntimeError("OpenCodex is still running; stop it before restore")
    active = active_backup_path(codex_home)
    if active is not None:
        restore_backup(codex_home, active)
    return managed_status(codex_home)


def start(codex_home: Path, *, dry_run: bool = False) -> int:
    """Start OpenCodex and guarantee exact restoration on every normal exit."""
    stale = active_backup_path(codex_home)
    if stale is not None:
        if port_open():
            raise RuntimeError("an OpenCodex session is already active")
        if dry_run:
            print(f"Would recover stale backup: {stale}")
        else:
            recovered = restore_backup(codex_home, stale)
            print(f"Recovered interrupted session from {recovered.name}")

    if dry_run:
        config = config_path(codex_home)
        if not config.is_file():
            raise RuntimeError(f"Codex config does not exist: {config}")
        if is_injected(config.read_bytes()):
            raise RuntimeError("Codex config already looks injected")
        print(f"Would back up {config} and run OpenCodex on port {OCX_PORT}")
        return 0

    backup = create_backup(codex_home)
    print(f"Safety backup created: {backup.name}")
    process: subprocess.Popen[str] | None = None
    exit_code = 1
    try:
        process = subprocess.Popen(ocx_command(resolve_ocx(), "start"), text=True)
        if not wait_for_port(True):
            exit_code = process.poll() if process.poll() is not None else 1
            raise RuntimeError("OpenCodex did not become healthy on port 10100")
        print("OpenCodex proxy is ready on http://127.0.0.1:10100")
        exit_code = process.wait()
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        try:
            run_ocx("stop")
        except OSError:
            pass
        if not wait_for_port(False):
            raise RuntimeError("OpenCodex proxy is still running; recovery marker was preserved")
        restored_from = restore_backup(codex_home, backup)
        print(f"Codex config restored exactly from {restored_from.name}")
    return exit_code


def stop(codex_home: Path) -> int:
    completed = run_ocx("stop")
    if not wait_for_port(False):
        raise RuntimeError("OpenCodex proxy is still running; config was not restored")
    active = active_backup_path(codex_home)
    if active is not None:
        restored = restore_backup(codex_home, active)
        print(f"Codex config restored exactly from {restored.name}")
    return completed.returncode


def status(codex_home: Path, *, as_json: bool = False) -> int:
    payload = managed_status(codex_home)
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 2 if payload["state"] == "recovery_required" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=default_codex_home())
    subparsers = parser.add_subparsers(dest="command", required=True)
    start_parser = subparsers.add_parser("start", help="start with exact config restoration")
    start_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("stop", help="stop OpenCodex and restore any active backup")
    subparsers.add_parser("restore", help="restore an interrupted session")
    subparsers.add_parser(
        "managed-start", help="start background OpenCodex and retain restore ownership"
    )
    subparsers.add_parser("managed-stop", help="stop an owned background service and restore")
    subparsers.add_parser("managed-restart", help="restart an owned background service")
    subparsers.add_parser("managed-restore", help="restore a stale owned session")
    subparsers.add_parser("install", help="npm install -g the official OpenCodex package")
    subparsers.add_parser("check-update", help="compare installed vs latest npm version")
    status_parser = subparsers.add_parser("status", help="show proxy and recovery state")
    status_parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    codex_home = args.codex_home.resolve()
    try:
        if args.command == "start":
            return start(codex_home, dry_run=args.dry_run)
        if args.command == "stop":
            return stop(codex_home)
        if args.command == "restore":
            restored = recover_stale_session(codex_home)
            print(f"Restored {restored.name}" if restored else "No recovery was pending")
            return 0
        if args.command == "managed-start":
            print(json.dumps(managed_start(codex_home), indent=2))
            return 0
        if args.command == "managed-stop":
            print(json.dumps(managed_stop(codex_home), indent=2))
            return 0
        if args.command == "managed-restart":
            print(json.dumps(managed_restart(codex_home), indent=2))
            return 0
        if args.command == "managed-restore":
            print(json.dumps(managed_restore(codex_home), indent=2))
            return 0
        if args.command == "install":
            print(json.dumps(managed_install(codex_home), indent=2))
            return 0
        if args.command == "check-update":
            print(json.dumps(check_ocx_update(), indent=2))
            return 0
        return status(codex_home, as_json=args.as_json)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
