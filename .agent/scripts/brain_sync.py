#!/usr/bin/env python3
"""
Brain Sync — Sincronizacion bidireccional del Brain Network entre local y cloud.

Flujo:
  1. LOCK: crear lock file (evitar concurrent sync)
  2. PULL: bajar nodos nuevos/modificados desde el cloud
  3. MERGE: resolver conflictos (timestamp mas nuevo gana)
  4. PUSH: subir nodos locales nuevos/modificados al cloud
  5. UNLOCK: remover lock file

Uso:
  python brain_sync.py --target ssh://user@mcp.uns-kikaku.cloud:/opt/antigravity
  python brain_sync.py --daemon     # modo daemon (cada 5min)
  python brain_sync.py --status     # ver estado de sync sin ejecutar

Variables de entorno:
  BRAIN_SYNC_TARGET      ssh://user@host:/path (VPS destino)
  BRAIN_SYNC_INTERVAL    intervalo en segundos (default: 300 = 5min)
  BRAIN_SYNC_SSH_KEY     path a la clave SSH (default: ~/.ssh/id_rsa)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AGENT_ROOT = Path(__file__).resolve().parent.parent  # .agent/
BRAIN_DIR = AGENT_ROOT / "brain"
LOCK_FILE = BRAIN_DIR / ".sync.lock"
STATE_FILE = BRAIN_DIR / ".sync.state.json"
LOG_FILE = BRAIN_DIR / ".sync.log"

DEFAULT_INTERVAL = 300  # 5 min
LOCK_TIMEOUT = 600  # 10 min stale lock threshold


@dataclass
class SyncTarget:
    """Destino de sincronizacion (VPS remoto)."""

    user: str
    host: str
    path: str
    ssh_key: str = ""

    @classmethod
    def parse(cls, url: str) -> SyncTarget:
        """Parsea ssh://user@host:/path -> SyncTarget."""
        if not url.startswith("ssh://"):
            raise ValueError(f"Target debe empezar con ssh:// — got {url!r}")
        rest = url[6:]
        user_host, _, path = rest.partition(":")
        user, _, host = user_host.partition("@")
        if not user or not host or not path:
            raise ValueError(f"Formato invalido: {url!r}")
        return cls(user=user, host=host, path=path)

    @property
    def rsync_dest(self) -> str:
        return f"{self.user}@{self.host}:{self.path}/.agent/brain/"

    @property
    def ssh_host(self) -> str:
        return f"{self.user}@{self.host}"


# ---------------------------------------------------------------------------
# Lock management
# ---------------------------------------------------------------------------


def acquire_lock() -> bool:
    """Adquiere lock exclusivo para sync. Returns False si ya hay lock activo."""
    if LOCK_FILE.exists():
        try:
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < LOCK_TIMEOUT:
                logger.warning(
                    "Lock activo hace %.0fs (%s). Saltando sync.",
                    age,
                    LOCK_FILE,
                )
                return False
            logger.warning("Lock stale (%.0fs). Tomandolo.", age)
        except OSError:
            pass

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "acquired_at": datetime.now(UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return True


def release_lock() -> None:
    """Libera el lock."""
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_sync": None, "history": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def log_sync_event(event: str, details: dict) -> None:
    """Append a sync event to state history."""
    state = load_state()
    state["history"] = state.get("history", [])[-49:]  # mantener ultimos 50
    state["history"].append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "details": details,
        }
    )
    state["last_sync"] = datetime.now(UTC).isoformat()
    save_state(state)


# ---------------------------------------------------------------------------
# Rsync operations
# ---------------------------------------------------------------------------


def run_rsync(
    source: str,
    dest: str,
    ssh_key: str = "",
    extra_args: list[str] | None = None,
) -> dict:
    """Ejecuta rsync y parsea el output."""
    ssh_cmd = "ssh -o StrictHostKeyChecking=accept-new"
    if ssh_key:
        ssh_cmd += f" -i {ssh_key}"

    cmd = [
        "rsync",
        "-avz",
        "--itemize-changes",
        "--stats",
        "--exclude=.sync.lock",
        "-e",
        ssh_cmd,
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend([source, dest])

    logger.info("rsync %s -> %s", source, dest)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "rsync timeout (600s)"}

    # Parsear stats
    stats = {}
    for line in result.stdout.split("\n"):
        if "files transferred:" in line.lower():
            stats["transferred"] = line.split(":")[-1].strip()
        elif "total bytes sent:" in line.lower():
            stats["bytes_sent"] = line.split(":")[-1].strip()

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout[-2000:] if result.stdout else "",
        "stderr": result.stderr[-1000:] if result.stderr else "",
        "stats": stats,
    }


def pull_from_cloud(target: SyncTarget) -> dict:
    """PULL: bajar cambios del VPS al local (solo archivos mas nuevos)."""
    return run_rsync(
        source=target.rsync_dest,
        dest=f"{BRAIN_DIR}/",
        ssh_key=target.ssh_key,
        extra_args=["--update"],  # solo si remote es mas nuevo
    )


def push_to_cloud(target: SyncTarget) -> dict:
    """PUSH: subir cambios locales al VPS."""
    return run_rsync(
        source=f"{BRAIN_DIR}/",
        dest=target.rsync_dest,
        ssh_key=target.ssh_key,
        extra_args=["--update"],  # solo si local es mas nuevo
    )


def rebuild_remote_index(target: SyncTarget) -> dict:
    """Despues del sync, reconstruir el index.md remoto."""
    ssh_cmd = "ssh"
    if target.ssh_key:
        ssh_cmd += f" -i {target.ssh_key}"

    script = (
        f"cd {target.path} && "
        "python -c \"import sys; sys.path.insert(0, '.agent'); "
        "from core.brain import Brain; from pathlib import Path; "
        "b = Brain(Path('.agent/brain'), app_id='nexus-mother'); "
        "print(f'Rebuilt: {b.rebuild_index()} nodes')\""
    )

    try:
        result = subprocess.run(
            [*ssh_cmd.split(), target.ssh_host, script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip() or result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout"}
    except FileNotFoundError:
        return {"success": False, "error": "ssh no disponible"}


# ---------------------------------------------------------------------------
# Sync principal
# ---------------------------------------------------------------------------


def sync_once(target: SyncTarget) -> bool:
    """Ejecuta una sincronizacion completa bidireccional."""
    if not acquire_lock():
        return False

    try:
        logger.info("=== Brain Sync: %s <-> %s ===", BRAIN_DIR, target.host)

        # 1. PULL
        pull_result = pull_from_cloud(target)
        log_sync_event("pull", pull_result)
        if not pull_result["success"]:
            logger.error("PULL fallo: %s", pull_result.get("stderr", ""))

        # 2. PUSH
        push_result = push_to_cloud(target)
        log_sync_event("push", push_result)
        if not push_result["success"]:
            logger.error("PUSH fallo: %s", push_result.get("stderr", ""))

        # 3. Reconstruir index remoto
        rebuild_result = rebuild_remote_index(target)
        log_sync_event("rebuild_index", rebuild_result)

        # 4. Reconstruir index local
        try:
            sys.path.insert(0, str(AGENT_ROOT))
            from core.brain import Brain  # noqa: PLC0415

            brain = Brain(BRAIN_DIR, app_id="nexus-mother")
            local_count = brain.rebuild_index()
            logger.info("Local index: %d nodos", local_count)
        except Exception as e:
            logger.warning("No se pudo rebuild local index: %s", e)

        return pull_result["success"] and push_result["success"]

    finally:
        release_lock()


def daemon_mode(target: SyncTarget, interval: int) -> None:
    """Modo daemon: sync cada N segundos."""
    logger.info("=== Brain Sync Daemon: cada %ds ===", interval)
    while True:
        try:
            sync_once(target)
        except KeyboardInterrupt:
            logger.info("Daemon detenido por usuario")
            break
        except Exception as e:
            logger.error("Error en sync: %s", e)

        logger.info("Proximo sync en %ds", interval)
        time.sleep(interval)


def show_status() -> None:
    """Muestra estado del sync sin ejecutar."""
    state = load_state()
    print(f"Brain: {BRAIN_DIR}")
    print(f"Ultima sync: {state.get('last_sync') or 'nunca'}")
    print(f"Lock activo: {'SI' if LOCK_FILE.exists() else 'no'}")
    print(f"Eventos en historial: {len(state.get('history', []))}")
    if state.get("history"):
        print("\nUltimos 5 eventos:")
        for ev in state["history"][-5:]:
            print(f"  [{ev['timestamp']}] {ev['event']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain Network sync bidireccional")
    parser.add_argument(
        "--target",
        default=os.environ.get("BRAIN_SYNC_TARGET", ""),
        help="ssh://user@host:/path",
    )
    parser.add_argument(
        "--ssh-key",
        default=os.environ.get("BRAIN_SYNC_SSH_KEY", ""),
        help="Path a clave SSH",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("BRAIN_SYNC_INTERVAL", DEFAULT_INTERVAL)),
        help="Intervalo en segundos (daemon mode)",
    )
    parser.add_argument("--daemon", action="store_true", help="Modo daemon")
    parser.add_argument("--status", action="store_true", help="Solo mostrar estado")
    parser.add_argument("--pull-only", action="store_true", help="Solo bajar del VPS")
    parser.add_argument("--push-only", action="store_true", help="Solo subir al VPS")
    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    if not args.target:
        logger.error("No hay target. Define BRAIN_SYNC_TARGET o usa --target ssh://...")
        return 1

    try:
        target = SyncTarget.parse(args.target)
        target.ssh_key = args.ssh_key
    except ValueError as e:
        logger.error("%s", e)
        return 1

    if args.pull_only:
        return 0 if pull_from_cloud(target)["success"] else 1
    if args.push_only:
        return 0 if push_to_cloud(target)["success"] else 1

    if args.daemon:
        daemon_mode(target, args.interval)
        return 0

    return 0 if sync_once(target) else 1


if __name__ == "__main__":
    sys.exit(main())
