#!/usr/bin/env python3
"""Process Doctor — diagnostico y housekeeping de procesos del ecosistema.

Inspecciona el arbol de procesos del runtime Antigravity en Windows: el gateway
local (:4747), su launcher de Nexus, y los MCP servers que cada cliente MCP
(Claude Code, Codex, Cursor, Nexus) spawnea. Detecta gateways zombie y MCP
servers huerfanos (de sesiones de cliente ya muertas), reporta el consumo de RAM
agrupado por cliente, y opcionalmente limpia los huerfanos con confirmacion.

Reglas de seguridad (aprendidas de la operacion real, NO inventadas):
    1. El proceso que responde ``GET :4747/v1/health`` es el gateway REAL y NUNCA
       se considera zombie, sin importar lo que reporte psutil sobre el socket.
    2. Un ``gateway_main`` sin LISTEN pero que es PADRE de uno que SI escucha es
       el *launcher* (lo arranca Nexus); se preserva.
    3. El arbol legitimo es ``antigravity-nexus.exe -> python launcher -> gateway``.
    4. Zombie real = ``gateway_main`` sin LISTEN, sin hijo que escuche, y fuera
       del arbol de Nexus.
    5. MCP server huerfano = su proceso cliente padre (claude.exe/codex.exe/...)
       ya no existe o fue reparentado al init de Windows.

Uso:
    python .agent/scripts/process_doctor.py status          # dashboard read-only
    python .agent/scripts/process_doctor.py status --json   # salida machine-readable
    python .agent/scripts/process_doctor.py clean           # limpieza asistida
    python .agent/scripts/process_doctor.py clean --yes     # sin confirmacion (CI)

Salida de codigo:
    0  OK (sin zombies, o limpieza exitosa)
    1  error de ejecucion (psutil ausente, etc.)
    2  hay zombies/huerfanos detectados (solo en ``status``)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
from dataclasses import asdict, dataclass, field
from urllib.error import URLError

# Windows usa cp932 por defecto en consolas JP; forzar UTF-8 para evitar
# UnicodeEncodeError al imprimir caracteres no-ASCII (em-dash, flechas, etc.).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("process-doctor")

GATEWAY_HEALTH_URL = "http://127.0.0.1:4747/v1/health"
GATEWAY_MARKER = "mcp.gateway_main"

# Nombres de proceso que actuan como clientes MCP (spawnean MCP servers).
CLIENT_NAMES = frozenset(
    {
        "claude.exe",
        "claude",
        "codex.exe",
        "codex",
        "cursor.exe",
        "antigravity-nexus.exe",
        "node.exe",
        "code.exe",
    }
)
# Procesos a los que Windows reparenta huerfanos cuando el padre muere.
REPARENT_NAMES = frozenset(
    {"services.exe", "wininit.exe", "svchost.exe", "explorer.exe", "userinit.exe"}
)

# Firmas para reconocer un proceso como MCP server del ecosistema.
_MCP_SIGNATURES = (
    ".agent/mcp/",
    "mcp-server/server.py",
    "21st-dev",
    "chrome-devtools-mcp",
    "context7",
    "server-github",
    "sequential-thinking",
    "playwright/mcp",
    "server-filesystem",
    "mcp-server-git",
    "mcp-server-time",
    "paddleocr_mcp",
    "jpkkenfull-server",
    "@modelcontextprotocol",
)


def _require_psutil():
    """Importa psutil o aborta con un mensaje claro.

    Returns:
        El modulo psutil.
    """
    try:
        import psutil  # noqa: PLC0415
    except ImportError:
        logger.error("psutil no esta instalado: pip install psutil")
        sys.exit(1)
    return psutil


def _gateway_health_ok() -> bool:
    """Consulta el health endpoint del gateway. Fuente de verdad de 'quien sirve'.

    Returns:
        True si el gateway responde ``status: healthy`` en :4747.
    """
    try:
        with urllib.request.urlopen(GATEWAY_HEALTH_URL, timeout=3) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return bool(data.get("data", {}).get("status") == "healthy")
    except (URLError, OSError, ValueError, json.JSONDecodeError):
        return False


def _normalize(cmd: str) -> str:
    """Normaliza separadores de path para matching cross-platform."""
    return cmd.replace("\\", "/")


def _is_mcp_server(cmd: str) -> bool:
    """True si el cmdline corresponde a un MCP server del ecosistema."""
    c = _normalize(cmd)
    return any(sig in c for sig in _MCP_SIGNATURES)


@dataclass
class GatewayInfo:
    """Estado de un proceso gateway_main."""

    pid: int
    ram_mb: float
    threads: int
    uptime_h: float
    listening: bool
    is_launcher: bool
    parent_name: str
    role: str  # "real" | "launcher" | "zombie"


@dataclass
class McpGroup:
    """Grupo de MCP servers agrupados por cliente padre."""

    client: str
    count: int = 0
    ram_mb: float = 0.0
    orphan_pids: list[int] = field(default_factory=list)


@dataclass
class Report:
    """Reporte completo del estado de procesos."""

    health_ok: bool
    gateways: list[GatewayInfo] = field(default_factory=list)
    mcp_total: int = 0
    mcp_ram_mb: float = 0.0
    groups: list[McpGroup] = field(default_factory=list)
    zombie_gateway_pids: list[int] = field(default_factory=list)
    orphan_mcp_pids: list[int] = field(default_factory=list)


def collect(psutil) -> Report:  # noqa: ANN001
    """Recorre el arbol de procesos y arma el reporte de estado.

    Args:
        psutil: El modulo psutil (inyectado para testabilidad).

    Returns:
        Un :class:`Report` con gateways, grupos MCP y candidatos a limpieza.
    """
    health_ok = _gateway_health_ok()
    procs = {
        p.pid: p for p in psutil.process_iter(["pid", "name", "ppid", "cmdline", "create_time"])
    }

    # --- Paso 1: ubicar gateways y quien escucha en :4747 -------------------
    gateway_pids: list[int] = []
    listening_pid: int | None = None
    for pid, p in procs.items():
        cmd = " ".join(p.info["cmdline"] or [])
        if GATEWAY_MARKER not in cmd or "python" not in (p.info["name"] or "").lower():
            continue
        gateway_pids.append(pid)
        try:
            if any(
                c.laddr.port == 4747 and c.status == "LISTEN"
                for c in psutil.Process(pid).connections(kind="inet")
            ):
                listening_pid = pid
        except Exception:  # noqa: BLE001
            pass

    # un gateway_main que es PADRE del que escucha = launcher (preservar)
    launcher_pids = (
        {
            procs[listening_pid].info["ppid"]
            for _ in (1,)
            if listening_pid is not None and procs[listening_pid].info["ppid"] in procs
        }
        if listening_pid
        else set()
    )

    report = Report(health_ok=health_ok)
    for pid in gateway_pids:
        p = procs[pid]
        try:
            proc = psutil.Process(pid)
            ram = proc.memory_info().rss / 1024 / 1024
            thr = proc.num_threads()
            up = (psutil.time.time() - p.info["create_time"]) / 3600
        except Exception:  # noqa: BLE001
            continue
        listening = pid == listening_pid
        is_launcher = pid in launcher_pids
        parent = procs.get(p.info["ppid"])
        pname = parent.info["name"] if parent else "<dead>"
        if listening:
            role = "real"
        elif is_launcher or "nexus" in pname.lower():
            role = "launcher"
        else:
            role = "zombie"
            report.zombie_gateway_pids.append(pid)
        report.gateways.append(
            GatewayInfo(pid, round(ram, 1), thr, round(up, 2), listening, is_launcher, pname, role)
        )

    # --- Paso 2: agrupar MCP servers por cliente y detectar huerfanos -------
    groups: dict[str, McpGroup] = {}
    for pid, p in procs.items():
        cmd = " ".join(p.info["cmdline"] or [])
        if not cmd or not _is_mcp_server(cmd):
            continue
        ppid = p.info["ppid"]
        parent = procs.get(ppid)
        if parent is None or ppid <= 4:
            client, orphan = "<dead-session>", True
        else:
            pname = (parent.info["name"] or "").lower()
            orphan = pname in REPARENT_NAMES
            client = "<reparented>" if orphan else parent.info["name"]
        try:
            ram = psutil.Process(pid).memory_info().rss / 1024 / 1024
        except Exception:  # noqa: BLE001
            ram = 0.0
        g = groups.setdefault(client, McpGroup(client=client))
        g.count += 1
        g.ram_mb = round(g.ram_mb + ram, 1)
        report.mcp_total += 1
        report.mcp_ram_mb = round(report.mcp_ram_mb + ram, 1)
        if orphan:
            g.orphan_pids.append(pid)
            report.orphan_mcp_pids.append(pid)

    report.groups = sorted(groups.values(), key=lambda x: -x.ram_mb)
    return report


def render_status(report: Report) -> None:
    """Imprime el dashboard read-only en formato humano."""
    print("=" * 64)
    print("  PROCESS DOCTOR — estado del ecosistema Antigravity")
    print("=" * 64)
    hp = "OK (healthy)" if report.health_ok else "NO RESPONDE"
    print(f"\nGateway :4747 health  -> {hp}")

    print("\n--- Gateways (gateway_main) ---")
    for g in report.gateways:
        tag = {"real": "REAL  ", "launcher": "LAUNCH", "zombie": "ZOMBIE"}[g.role]
        print(
            f"  [{tag}] PID={g.pid:6} RAM={g.ram_mb:6.0f}MB thr={g.threads:3} "
            f"up={g.uptime_h:.2f}h parent={g.parent_name}"
        )

    print(f"\n--- MCP servers: {report.mcp_total} procesos, {report.mcp_ram_mb:.0f}MB ---")
    for grp in report.groups:
        orph = f"  ({len(grp.orphan_pids)} HUERFANOS)" if grp.orphan_pids else ""
        print(f"  {grp.client:24} x{grp.count:<3} {grp.ram_mb:7.0f}MB{orph}")

    print("\n--- Resumen de limpieza ---")
    print(
        f"  Gateways zombie:     {len(report.zombie_gateway_pids)} "
        f"{report.zombie_gateway_pids or ''}"
    )
    print(f"  MCP huerfanos:       {len(report.orphan_mcp_pids)}")
    total_kill = len(report.zombie_gateway_pids) + len(report.orphan_mcp_pids)
    if total_kill:
        print(f"\n  -> {total_kill} procesos limpiables. Corre 'process_doctor.py clean'.")
    else:
        print("\n  -> Sin procesos para limpiar. Ecosistema sano.")


def _kill(psutil, pid: int) -> bool:  # noqa: ANN001
    """Termina un proceso (SIGTERM, luego SIGKILL como fallback).

    Args:
        psutil: El modulo psutil.
        pid: PID a terminar.

    Returns:
        True si el proceso fue terminado o ya no existia.
    """
    try:
        p = psutil.Process(pid)
        p.terminate()
        try:
            p.wait(timeout=5)
        except psutil.TimeoutExpired:
            p.kill()
        return True
    except psutil.NoSuchProcess:
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("no se pudo terminar PID %s: %s", pid, exc)
        return False


def run_clean(psutil, assume_yes: bool) -> int:  # noqa: ANN001
    """Limpieza asistida: lista zombies/huerfanos y los termina con confirmacion.

    Args:
        psutil: El modulo psutil.
        assume_yes: Si True, no pide confirmacion interactiva.

    Returns:
        Codigo de salida (0 = OK).
    """
    report = collect(psutil)
    targets = list(report.zombie_gateway_pids) + list(report.orphan_mcp_pids)
    if not targets:
        logger.info("No hay zombies ni huerfanos para limpiar. Ecosistema sano.")
        return 0

    # Guarda de seguridad: nunca tocar el gateway que responde health.
    if report.health_ok:
        real = [g.pid for g in report.gateways if g.role in ("real", "launcher")]
        targets = [t for t in targets if t not in real]

    print(f"\nSe terminaran {len(targets)} procesos:")
    print(f"  Gateways zombie: {report.zombie_gateway_pids}")
    print(f"  MCP huerfanos:   {report.orphan_mcp_pids}")

    if not assume_yes:
        try:
            ans = input("\nConfirmar limpieza? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans not in ("y", "yes", "s", "si"):
            logger.info("Cancelado por el usuario.")
            return 0

    killed = sum(1 for pid in targets if _kill(psutil, pid))
    logger.info("Terminados %d/%d procesos.", killed, len(targets))
    # Verificar que el gateway sigue sano tras la limpieza.
    if _gateway_health_ok():
        logger.info("Gateway :4747 sigue healthy tras la limpieza.")
    else:
        logger.warning("El gateway no responde tras la limpieza. Revisar Nexus/gateway.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point CLI.

    Args:
        argv: Argumentos (None usa sys.argv).

    Returns:
        Codigo de salida.
    """
    parser = argparse.ArgumentParser(
        description="Diagnostico y housekeeping de procesos del ecosistema Antigravity.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Dashboard read-only del estado de procesos.")
    p_status.add_argument("--json", action="store_true", help="Salida machine-readable.")

    p_clean = sub.add_parser("clean", help="Limpieza asistida de zombies y huerfanos.")
    p_clean.add_argument("--yes", action="store_true", help="No pedir confirmacion.")

    args = parser.parse_args(argv)
    psutil = _require_psutil()

    if args.command == "status":
        report = collect(psutil)
        if args.json:
            print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
        else:
            render_status(report)
        has_garbage = bool(report.zombie_gateway_pids or report.orphan_mcp_pids)
        return 2 if has_garbage else 0

    if args.command == "clean":
        return run_clean(psutil, assume_yes=args.yes)

    return 0


if __name__ == "__main__":
    sys.exit(main())
