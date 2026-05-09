"""
Monitor unificado de conexiones MCP — local y remoto.

Verifica el estado de todos los servidores MCP configurados en .mcp.json
y proporciona reportes de salud, diagnósticos y reconexión automática.

Uso::

    from core.mcp_connection_monitor import MCPConnectionMonitor

    monitor = MCPConnectionMonitor()
    report = await monitor.check_all()
    print(report)

    # Diagnosticar un servidor específico
    diag = await monitor.diagnose("antigravity-remote")

    # Reconectar servidores caídos
    fixed = await monitor.heal_unhealthy()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.mcp_monitor")

# Timeouts para verificación de salud
HEALTH_CHECK_TIMEOUT = 10  # segundos
STDIO_CHECK_TIMEOUT = 5  # segundos


@dataclass
class ServerHealthResult:
    """Resultado de verificación de salud de un servidor MCP."""

    name: str
    transport: str
    status: str  # "healthy" | "degraded" | "unreachable" | "not_configured"
    latency_ms: float = 0.0
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "transport": self.transport,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 1),
            "error": self.error,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class MonitorReport:
    """Reporte completo del monitor de conexiones."""

    total_servers: int = 0
    healthy: int = 0
    degraded: int = 0
    unreachable: int = 0
    servers: list[ServerHealthResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    check_duration_ms: float = 0.0

    @property
    def overall_status(self) -> str:
        if self.total_servers == 0:
            return "unhealthy"
        if self.healthy == self.total_servers:
            return "healthy"
        if self.healthy > 0:
            return "degraded"
        return "unhealthy"

    @property
    def health_pct(self) -> float:
        if self.total_servers == 0:
            return 0.0
        return round(self.healthy / self.total_servers * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.overall_status,
            "health_pct": self.health_pct,
            "total_servers": self.total_servers,
            "healthy": self.healthy,
            "degraded": self.degraded,
            "unreachable": self.unreachable,
            "servers": [s.to_dict() for s in self.servers],
            "check_duration_ms": round(self.check_duration_ms, 1),
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        """Formato legible para humanos."""
        icon = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}
        lines = [
            f"# Estado de Conexiones MCP {icon.get(self.overall_status, '?')}",
            "",
            f"**Estado global:** {self.overall_status} ({self.health_pct}%)",
            f"**Servidores:** {self.healthy}/{self.total_servers} saludables",
            f"**Verificación:** {self.check_duration_ms:.0f}ms",
            "",
            "| Servidor | Transporte | Estado | Latencia | Error |",
            "|----------|-----------|--------|----------|-------|",
        ]
        status_icon = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unreachable": "❌",
            "not_configured": "⬜",
        }
        for s in self.servers:
            lines.append(
                f"| {s.name} | {s.transport} | "
                f"{status_icon.get(s.status, '?')} {s.status} | "
                f"{s.latency_ms:.0f}ms | {s.error or '-'} |"
            )
        return "\n".join(lines)


class MCPConnectionMonitor:
    """Monitor de salud para todas las conexiones MCP del ecosistema."""

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path or self._find_config()
        self._servers: dict[str, dict[str, Any]] = {}
        self._loaded = False

    @staticmethod
    def _find_config() -> Path | None:
        """Busca .mcp.json en ubicaciones conocidas."""
        candidates = [
            Path.cwd() / ".mcp.json",
            Path(__file__).parent.parent.parent / ".mcp.json",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def _load_config(self) -> None:
        """Carga la configuración de servidores MCP."""
        if self._loaded:
            return
        if not self._config_path or not self._config_path.exists():
            logger.warning("No .mcp.json found")
            self._loaded = True
            return

        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            self._servers = data.get("mcpServers", {})
            self._loaded = True
            logger.info("Loaded %d MCP servers from config", len(self._servers))
        except Exception as e:
            logger.error("Error loading MCP config: %s", e)
            self._loaded = True

    async def check_all(self) -> MonitorReport:
        """Verifica la salud de todos los servidores MCP configurados."""
        self._load_config()
        start = time.monotonic()
        report = MonitorReport(total_servers=len(self._servers))

        # Verificar en paralelo
        tasks = []
        for name, config in self._servers.items():
            tasks.append(self._check_server(name, config))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    report.servers.append(
                        ServerHealthResult(
                            name="unknown",
                            transport="unknown",
                            status="unreachable",
                            error=str(result),
                        )
                    )
                    report.unreachable += 1
                else:
                    report.servers.append(result)
                    if result.status == "healthy":
                        report.healthy += 1
                    elif result.status == "degraded":
                        report.degraded += 1
                    else:
                        report.unreachable += 1

        report.check_duration_ms = (time.perf_counter() - start) * 1000
        return report

    async def _check_server(self, name: str, config: dict[str, Any]) -> ServerHealthResult:
        """Verifica un servidor individual."""
        transport = config.get("type", "stdio")
        url = config.get("url", "")

        if transport in ("http", "url") and url:
            return await self._check_http_server(name, url, config.get("headers", {}))
        elif config.get("command"):
            return self._check_stdio_server(name, config)
        else:
            return ServerHealthResult(
                name=name,
                transport=transport,
                status="not_configured",
                error="No command or URL configured",
            )

    async def _check_http_server(
        self, name: str, url: str, headers: dict[str, str]
    ) -> ServerHealthResult:
        """Verifica un servidor HTTP remoto."""
        # Construir URL de health check
        health_url = url.replace("/mcp", "/health")
        start = time.monotonic()

        # Expandir variables de entorno en headers
        import re

        expanded = {}
        for key, value in headers.items():
            if isinstance(value, str) and "${" in value:
                expanded[key] = re.sub(
                    r"\$\{(\w+)\}",
                    lambda m: os.environ.get(m.group(1), ""),
                    value,
                )
            else:
                expanded[key] = value

        try:
            # Intentar con proxy del sistema, luego sin proxy
            from core.mcp_client import _build_url_opener

            opener = _build_url_opener()

            req = urllib.request.Request(health_url, method="GET")
            for key, value in expanded.items():
                req.add_header(key, value)

            response = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: opener.open(req, timeout=HEALTH_CHECK_TIMEOUT),
            )
            latency = (time.monotonic() - start) * 1000
            body = json.loads(response.read().decode("utf-8"))

            return ServerHealthResult(
                name=name,
                transport="http",
                status="healthy",
                latency_ms=latency,
                details=body,
            )

        except urllib.error.HTTPError as e:
            latency = (time.monotonic() - start) * 1000
            return ServerHealthResult(
                name=name,
                transport="http",
                status="degraded" if e.code < 500 else "unreachable",
                latency_ms=latency,
                error=f"HTTP {e.code}: {e.reason}",
            )
        except urllib.error.URLError as e:
            latency = (time.monotonic() - start) * 1000
            reason = str(e.reason)
            # Detectar problemas específicos
            if "host_not_allowed" in reason or "403" in reason:
                error_msg = f"Blocked by proxy: {reason}"
            elif "timed out" in reason:
                error_msg = f"Connection timeout ({HEALTH_CHECK_TIMEOUT}s)"
            elif "refused" in reason:
                error_msg = "Connection refused (server down?)"
            elif "Name or service not known" in reason:
                error_msg = "DNS resolution failed"
            else:
                error_msg = f"Connection error: {reason}"

            return ServerHealthResult(
                name=name,
                transport="http",
                status="unreachable",
                latency_ms=latency,
                error=error_msg,
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            return ServerHealthResult(
                name=name,
                transport="http",
                status="unreachable",
                latency_ms=latency,
                error=str(e),
            )

    def _check_stdio_server(self, name: str, config: dict[str, Any]) -> ServerHealthResult:
        """Verifica que un servidor stdio sea ejecutable."""
        import shutil

        command = config.get("command", "")
        args = config.get("args", [])

        # Verificar que el comando existe
        if command in ("python", "python3"):
            # Verificar que el script existe
            if args:
                script = Path(args[0])
                if not script.is_absolute():
                    # Relativo al proyecto
                    base = self._config_path.parent if self._config_path else Path.cwd()
                    script = base / args[0]
                if script.exists():
                    return ServerHealthResult(
                        name=name,
                        transport="stdio",
                        status="healthy",
                        details={"script": str(script), "exists": True},
                    )
                return ServerHealthResult(
                    name=name,
                    transport="stdio",
                    status="unreachable",
                    error=f"Script not found: {args[0]}",
                )
        elif command in ("npx", "uvx"):
            if shutil.which(command):
                return ServerHealthResult(
                    name=name,
                    transport="stdio",
                    status="healthy",
                    details={"command": command, "available": True},
                )
            return ServerHealthResult(
                name=name,
                transport="stdio",
                status="unreachable",
                error=f"Command not found: {command}",
            )

        # Comando genérico
        if shutil.which(command):
            return ServerHealthResult(
                name=name,
                transport="stdio",
                status="healthy",
                details={"command": command},
            )
        return ServerHealthResult(
            name=name,
            transport="stdio",
            status="unreachable",
            error=f"Command not found: {command}",
        )

    async def diagnose(self, server_name: str) -> dict[str, Any]:
        """Diagnóstico detallado de un servidor específico."""
        self._load_config()
        config = self._servers.get(server_name)
        if not config:
            return {"error": f"Server '{server_name}' not found in config"}

        transport = config.get("type", "stdio")
        url = config.get("url", "")

        diag: dict[str, Any] = {
            "server": server_name,
            "transport": transport,
            "config": {k: v for k, v in config.items() if k != "headers"},
            "checks": [],
        }

        if transport in ("http", "url") and url:
            # 1. DNS resolution
            from urllib.parse import urlparse

            parsed = urlparse(url)
            hostname = parsed.hostname or ""

            try:
                import socket

                ip = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: socket.gethostbyname(hostname)
                )
                diag["checks"].append({"dns": "ok", "hostname": hostname, "ip": ip})
            except Exception as e:
                diag["checks"].append({"dns": "failed", "hostname": hostname, "error": str(e)})
                diag["diagnosis"] = "DNS resolution failed. Check network or hostname."
                return diag

            # 2. TCP connectivity
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            try:
                import socket

                sock = socket.create_connection((hostname, port), timeout=5)
                sock.close()
                diag["checks"].append({"tcp": "ok", "host": hostname, "port": port})
            except Exception as e:
                diag["checks"].append(
                    {"tcp": "failed", "host": hostname, "port": port, "error": str(e)}
                )
                diag["diagnosis"] = (
                    f"Cannot reach {hostname}:{port}. Server may be down or blocked by firewall/proxy."
                )
                return diag

            # 3. HTTP health check
            health_result = await self._check_http_server(
                server_name, url, config.get("headers", {})
            )
            diag["checks"].append({"health": health_result.to_dict()})

            # 4. Auth check
            headers = config.get("headers", {})
            has_auth = any("auth" in k.lower() for k in headers)
            auth_value = headers.get("Authorization", "")
            has_env_ref = "${" in auth_value
            diag["checks"].append(
                {
                    "auth": "configured" if has_auth else "none",
                    "uses_env_var": has_env_ref,
                    "token_set": bool(os.environ.get("ANTIGRAVITY_API_TOKEN", ""))
                    if has_env_ref
                    else None,
                }
            )

            if health_result.status == "healthy":
                diag["diagnosis"] = "Server is healthy and reachable."
            elif "proxy" in health_result.error.lower():
                diag["diagnosis"] = (
                    "Connection blocked by proxy. This environment restricts outbound connections. "
                    "The remote server works fine from other environments (local machine, other apps)."
                )
            elif "timeout" in health_result.error.lower():
                diag["diagnosis"] = (
                    "Connection timed out. Server may be slow or network is congested."
                )
            else:
                diag["diagnosis"] = f"Issue detected: {health_result.error}"

        else:
            # stdio server diagnosis
            result = self._check_stdio_server(server_name, config)
            diag["checks"].append({"stdio": result.to_dict()})
            diag["diagnosis"] = (
                "Server is available." if result.status == "healthy" else f"Issue: {result.error}"
            )

        return diag

    async def heal_unhealthy(self) -> list[str]:
        """Intenta reconectar servidores caídos usando MCPClientManager."""
        try:
            from core.mcp_client import get_mcp_manager

            manager = await get_mcp_manager()
            return await manager.reconnect_unhealthy()
        except Exception as e:
            logger.error("Error healing unhealthy servers: %s", e)
            return []


async def main() -> None:
    """CLI para verificar salud de conexiones MCP."""
    import sys

    monitor = MCPConnectionMonitor()

    if len(sys.argv) > 1 and sys.argv[1] == "--diagnose":
        server = sys.argv[2] if len(sys.argv) > 2 else "antigravity-remote"
        diag = await monitor.diagnose(server)
        print(json.dumps(diag, indent=2, ensure_ascii=False))
    else:
        report = await monitor.check_all()
        if "--json" in sys.argv:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
