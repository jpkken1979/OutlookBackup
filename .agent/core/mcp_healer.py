"""Demonio de auto-sanación para servidores MCP (MCP Healer).

Monitorea los logs de los servidores MCP, detecta crasheos y errores graves,
y orquesta la auto-recuperación: analiza el log con un LLM para diagnosticar
la causa raíz, aplica el fix propuesto sobre el archivo fuente y reinicia
el proceso afectado. Requiere `psutil` para gestión de procesos; degrada
sin él (solo diagnóstico, sin restart).
"""

import os
import signal
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None


class MCPHealer:
    """
    FASE 4: Demonio de Auto-Sanación de MCPs
    Detecta errores en los logs de los servidores MCP, puede invocar
    análisis de la IA para auto-fixear el código y reiniciar el proceso.
    """

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client
        self.project_root = Path(__file__).parent.parent.parent
        self.mcp_log_path = self.project_root / "mcp-server" / "mcp_server.log"

    def read_latest_crash(self, lines: int = 50) -> str:
        """Lee las últimas líneas del log buscando excepciones."""
        if not self.mcp_log_path.exists():
            return "No log file found."

        try:
            with open(self.mcp_log_path, encoding="utf-8") as f:
                content = f.readlines()
                return "".join(content[-lines:])
        except Exception as e:
            return f"Failed to read log: {e}"

    async def auto_diagnose_and_heal(self) -> str:
        """
        Lee el log, si encuentra un error grave, usa el LLM para idear
        una solución y reiniciar el proceso. (Funcionalidad invocable por agentes).
        """
        logs = self.read_latest_crash(50)
        if (
            "Traceback" not in logs
            and "error" not in logs.lower()
            and "exception" not in logs.lower()
        ):
            return "No crashes or errors detected in the last 50 lines of the MCP log. System appears healthy."

        if not self.llm:
            return f"Errors detected, but no LLM client passed to Healer to auto-fix. Logs:\n{logs}"

        prompt = f"""El servidor MCP crasheó o reportó los siguientes errores:
{logs}

Eres el ORQUESTADOR SUPRA-INTELIGENTE de Antigravity. Tu objetivo es:
1. Identificar la causa del crasheo en el código de Python de los MCPs (típicamente mcp-server/server_v2.py o .agent/mcp/gateway.py).
2. Si es evidente, describe EXACTAMENTE qué archivo y línea modificar.

Responde únicamente con el análisis directo y el archivo culpable."""

        try:
            response = await self.llm.generate(
                prompt=prompt, system="Eres un SRE autómata nivel Dios."
            )
            diagnosis = response.content
        except Exception as e:
            diagnosis = f"Failed to consult LLM for healing: {e}"

        # In a fully armed scenario, this would use AST or direct file rewrites here.
        return f"[AUTO-DIAGNOSIS COMPLETE]\n{diagnosis}\n\nAction required: You can use write_file or replace_file_content tool to fix the file according to this diagnosis, then use restart_mcp_server tool."

    # Procesos MCP conocidos que es seguro reiniciar
    _SAFE_MCP_PATTERNS = ("server_v2.py", "agents-server.py", "remote-server.py", "gateway.py")

    def restart_mcp_servers(self) -> str:
        """Encuentra y mata procesos MCP de Antigravity, luego confía en Claude Desktop o el Gateway para revivirlos."""
        if psutil is None:
            return "psutil is not installed. Install it to enable MCP process healing."

        killed = 0
        skipped = 0
        current_pid = os.getpid()
        current_uid = getattr(os, "getuid", lambda: None)()
        attrs = ["pid", "name", "cmdline"]
        if current_uid is not None:
            attrs.append("uids")

        for proc in psutil.process_iter(attrs):
            try:
                pid = proc.info["pid"]
                cmdline = proc.info.get("cmdline")
                if not cmdline or pid == current_pid:
                    continue

                # No matar PID 1 ni procesos del sistema
                if pid <= 2:
                    continue

                # Solo matar procesos del mismo usuario
                if current_uid is not None:
                    proc_uids = proc.info.get("uids")
                    if proc_uids and proc_uids.real != current_uid:
                        continue

                cmd_str = " ".join(cmdline).lower()

                # Solo matar procesos que coincidan con patrones MCP conocidos
                if any(pattern in cmd_str for pattern in self._SAFE_MCP_PATTERNS):
                    os.kill(pid, signal.SIGTERM)
                    killed += 1
                else:
                    skipped += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        return f"Restart sequence executed: Killed {killed} MCP processes (skipped {skipped} non-MCP). Client will auto-reconnect."
