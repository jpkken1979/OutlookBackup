#!/usr/bin/env python3
"""
LLM Fallback Manager — Apple Intelligence-style Local/Cloud toggle
===================================================================

Orquestador de providers LLM con fallback automático:
- Si Ollama está corriendo y disponible, usarlo primero
- Si falla o no hay modelo, fallback a Claude con notificación
- El estado se persiste en ~/.antigravity/config.json

Inspirado en Apple Intelligence: el usuario define preferencia,
el sistema ejecuta la mejor opción disponible sin fricción.

Uso:
    from .llm_fallback import LLMFallbackManager, get_fallback_manager

    mgr = get_fallback_manager()
    result = await mgr.chat("Hola")
    # Intenta Ollama primero, luego Claude si falla
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger("antigravity.llm_fallback")

# =============================================================================
# CONSTANTS
# =============================================================================

CONFIG_PATH = Path.home() / ".antigravity" / "config.json"
LOG_DIR = Path.home() / ".antigravity" / "logs"
LOG_FILE = LOG_DIR / "llm_fallback.log"

LOCAL_PROVIDERS = ["ollama", "lmstudio", "llama.cpp"]
CLOUD_PROVIDERS = ["claude", "openai", "minimax", "zai", "gemini", "openrouter", "groq", "nvidia"]

OLLAMA_DEFAULT_PORT = 11434
LMSTUDIO_DEFAULT_PORT = 1234


class LLMFallbackMode(str, Enum):
    """Modo de selección de provider."""

    LOCAL = "local"  # Solo providers locales (Ollama, LM Studio)
    CLOUD = "cloud"  # Solo cloud (Claude, etc.)
    AUTO = "auto"  # Intentá local primero, fallback a cloud


# =============================================================================
# PROBE UTILITIES
# =============================================================================


def probe_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Verifica si un host:puerto está abierto."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except OSError:
        return False


def probe_ollama() -> tuple[bool, list[str]]:
    """Verifica si Ollama está corriendo y lista modelos disponibles."""
    if not probe_port("localhost", OLLAMA_DEFAULT_PORT):
        return False, []

    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            return True, models
    except Exception:
        return False, []


def probe_lmstudio() -> tuple[bool, list[str]]:
    """Verifica si LM Studio está corriendo."""
    if not probe_port("localhost", LMSTUDIO_DEFAULT_PORT):
        return False, []

    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:1234/v1/models",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            return True, models
    except Exception:
        return False, []


# =============================================================================
# LOGGING
# =============================================================================


def _log_event(level: str, message: str, extra: dict[str, Any] | None = None) -> None:
    """Escribe un evento al log de fallback."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat()
    entry = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        **(extra or {}),
    }
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    logger.info(f"[llm_fallback] {level}: {message}")


# =============================================================================
# LLM CHAT PROTOCOL
# =============================================================================


class LLMChatProtocol(Protocol):
    """Protocolo que debe implementar un cliente LLM.

    Coincide con ``LLMClient.generate`` definido en ``llm.py``.
    """

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: object,
    ) -> object:
        """Genera una respuesta del LLM."""
        ...


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class FallbackResult:
    """Resultado de una llamada con fallback."""

    content: str
    provider_used: str
    mode: LLMFallbackMode
    fallback_triggered: str | None  # None = sin fallback
    latency_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "provider_used": self.provider_used,
            "mode": self.mode.value,
            "fallback_triggered": self.fallback_triggered,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


@dataclass
class LLMStatus:
    """Estado actual del sistema LLM."""

    local_available: bool
    cloud_available: bool
    ollama_running: bool
    lmstudio_running: bool
    installed_ollama_models: list[str] = field(default_factory=list)
    installed_lmstudio_models: list[str] = field(default_factory=list)
    current_mode: LLMFallbackMode = LLMFallbackMode.AUTO
    last_fallback: datetime | None = None
    last_fallback_reason: str | None = None
    last_provider_used: str | None = None
    preference: LLMFallbackMode = LLMFallbackMode.AUTO

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_available": self.local_available,
            "cloud_available": self.cloud_available,
            "ollama_running": self.ollama_running,
            "lmstudio_running": self.lmstudio_running,
            "installed_ollama_models": self.installed_ollama_models,
            "installed_lmstudio_models": self.installed_lmstudio_models,
            "current_mode": self.current_mode.value,
            "last_fallback": self.last_fallback.isoformat() if self.last_fallback else None,
            "last_fallback_reason": self.last_fallback_reason,
            "last_provider_used": self.last_provider_used,
            "preference": self.preference.value,
        }


# =============================================================================
# CONFIG STORAGE
# =============================================================================


def _load_config() -> dict[str, Any]:
    """Carga config de ~/.antigravity/config.json."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(data: dict[str, Any]) -> None:
    """Guarda config en ~/.antigravity/config.json."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_config()
    existing.update(data)
    CONFIG_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")


# =============================================================================
# MAIN CLASS
# =============================================================================


class LLMFallbackManager:
    """Gestor de fallback LLM con persistencia de preferencia.

    El flujo es similar a Apple Intelligence:
    1. El usuario setea "prefer local" / "prefer cloud" / "auto"
    2. En cada chat, el manager verifica disponibilidad en tiempo real
    3. Si el provider preferido falla, hace fallback automático al otro
    4. Notifica al usuario cuando ocurre fallback (toast + log)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Clientes lazy-imported (`from .llm import LLMClient`). Se tipan via Protocol
        # estructural — mypy no infiere subtyping con Protocol por re-import.
        self._ollama_client: Any | None = None
        self._claude_client: Any | None = None
        self._last_status_check: datetime | None = None
        self._cached_status: LLMStatus | None = None

        # Cargar preferencia persistida
        config = _load_config()
        self._preference: LLMFallbackMode = LLMFallbackMode(config.get("llm_fallback_mode", "auto"))

        # Inicializar clientes
        self._init_clients()

    def _init_clients(self) -> None:
        """Inicializa clientes LLM lazily."""
        try:
            from .llm import LLMClient, LLMConfig, LLMProvider

            # Ollama client (OpenAI-compatible, dummy key)
            try:
                ollama_cfg = LLMConfig(
                    provider=LLMProvider.OLLAMA,
                    model="llama3.2:3b",
                    base_url="http://localhost:11434/v1",
                    api_key="ollama",
                )
                self._ollama_client = LLMClient(ollama_cfg)
            except Exception as e:
                logger.debug(f"Ollama client init failed: {e}")

            # Claude client (Anthropic)
            try:
                claude_cfg = LLMConfig(provider=LLMProvider.ANTHROPIC)
                self._claude_client = LLMClient(claude_cfg)
            except Exception as e:
                logger.debug(f"Claude client init failed: {e}")

        except ImportError:
            logger.warning("llm module not available — fallback solo probe de red")

    # -------------------------------------------------------------------------
    # Availability checks
    # -------------------------------------------------------------------------

    def is_local_available(self) -> bool:
        """Check si algún provider local está corriendo."""
        ollama_ok, _ = probe_ollama()
        lmstudio_ok, _ = probe_lmstudio()
        return ollama_ok or lmstudio_ok

    def is_cloud_available(self) -> bool:
        """Check si la API de Claude está alcanzable."""
        return probe_port("api.anthropic.com", 443, timeout=3.0)

    def get_status(self, force_refresh: bool = False) -> LLMStatus:
        """Obtiene el estado actual del sistema LLM (cacheado 30s)."""
        now = datetime.now()
        if (
            not force_refresh
            and self._cached_status
            and self._last_status_check
            and (now - self._last_status_check).total_seconds() < 30
        ):
            return self._cached_status

        ollama_running, ollama_models = probe_ollama()
        lmstudio_running, lmstudio_models = probe_lmstudio()
        cloud_available = self.is_cloud_available()

        status = LLMStatus(
            local_available=ollama_running or lmstudio_running,
            cloud_available=cloud_available,
            ollama_running=ollama_running,
            lmstudio_running=lmstudio_running,
            installed_ollama_models=ollama_models,
            installed_lmstudio_models=lmstudio_models,
            preference=self._preference,
        )
        self._cached_status = status
        self._last_status_check = now
        return status

    # -------------------------------------------------------------------------
    # Preference
    # -------------------------------------------------------------------------

    def get_preference(self) -> LLMFallbackMode:
        """Obtiene la preferencia del usuario."""
        return self._preference

    def set_preference(self, mode: LLMFallbackMode) -> None:
        """Setea y persiste la preferencia del usuario."""
        if mode not in LLMFallbackMode:
            raise ValueError(f"Modo inválido: {mode}")
        self._preference = mode
        _save_config({"llm_fallback_mode": mode.value})
        _log_event("INFO", f"Preferencia cambiada a {mode.value}", {"mode": mode.value})

    # -------------------------------------------------------------------------
    # Core chat with fallback
    # -------------------------------------------------------------------------

    async def chat(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
    ) -> FallbackResult:
        """Ejecuta un chat con fallback automático.

        Estrategia según modo:
        - local: solo providers locales
        - cloud: solo cloud
        - auto: local primero, fallback a cloud
        """
        start = datetime.now()
        mode = self._preference

        # Determinar order de providers según modo
        if mode == LLMFallbackMode.LOCAL:
            order = ["ollama", "lmstudio"]
        elif mode == LLMFallbackMode.CLOUD:
            order = ["claude"]
        else:  # AUTO
            order = ["ollama", "claude"]

        last_error: str | None = None
        for provider in order:
            try:
                result = await self._try_provider(provider, prompt, system, model)
                latency = (datetime.now() - start).total_seconds() * 1000

                _log_event(
                    "INFO",
                    f"Chat exitoso via {provider}",
                    {"provider": provider, "latency_ms": latency},
                )

                # Actualizar status con último provider
                status = self.get_status()
                status.last_provider_used = provider

                return FallbackResult(
                    content=result,
                    provider_used=provider,
                    mode=mode,
                    fallback_triggered=None,
                    latency_ms=latency,
                )
            except Exception as e:
                last_error = str(e)
                _log_event(
                    "WARNING",
                    f"Fallback de {provider}: {e}",
                    {"provider": provider, "error": str(e)},
                )
                continue

        # Todos fallaron
        latency = (datetime.now() - start).total_seconds() * 1000
        fallback_reason = last_error or "Sin providers disponibles"
        _log_event("ERROR", f"Todos los providers fallaron: {fallback_reason}", {})

        return FallbackResult(
            content="",
            provider_used="none",
            mode=mode,
            fallback_triggered=fallback_reason,
            latency_ms=latency,
            error=fallback_reason,
        )

    async def _try_provider(
        self,
        provider: str,
        prompt: str,
        system: str | None,
        model: str | None,
    ) -> str:
        """Intenta un provider específico."""
        if provider == "ollama":
            return await self._chat_ollama(prompt, system, model)
        elif provider == "lmstudio":
            return await self._chat_lmstudio(prompt, system, model)
        elif provider == "claude":
            return await self._chat_claude(prompt, system, model)
        else:
            raise ValueError(f"Provider desconocido: {provider}")

    async def _chat_ollama(self, prompt: str, system: str | None, model: str | None) -> str:
        """Chat via Ollama. Verifica disponibilidad + modelo primero."""
        running, models = probe_ollama()
        if not running:
            raise RuntimeError("Ollama no está corriendo")
        if not models:
            raise RuntimeError("Ollama sin modelos instalados")

        if self._ollama_client is None:
            raise RuntimeError("Cliente Ollama no inicializado")

        resp = await self._ollama_client.generate(
            prompt=prompt,
            system=system,
        )
        return resp.content if hasattr(resp, "content") else str(resp)

    async def _chat_lmstudio(self, prompt: str, system: str | None, model: str | None) -> str:
        """Chat via LM Studio."""
        running, models = probe_lmstudio()
        if not running:
            raise RuntimeError("LM Studio no está corriendo")

        # Usar call_openai_compatible_chat desde Rust si está disponible
        # Por ahora delegamos a Claude como fallback
        raise RuntimeError("LM Studio — delegando a fallback")

    async def _chat_claude(self, prompt: str, system: str | None, model: str | None) -> str:
        """Chat via Claude API."""
        if not self.is_cloud_available():
            raise RuntimeError("Claude API no disponible")

        if self._claude_client is None:
            raise RuntimeError("Cliente Claude no inicializado")

        resp = await self._claude_client.generate(
            prompt=prompt,
            system=system,
        )
        return resp.content if hasattr(resp, "content") else str(resp)

    # -------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------

    def notify_fallback(self, from_provider: str, to_provider: str, reason: str) -> None:
        """Callback cuando ocurre fallback. Se puede hookear desde Nexus."""
        _log_event(
            "INFO",
            f"Fallback: {from_provider} → {to_provider} | {reason}",
            {"from": from_provider, "to": to_provider, "reason": reason},
        )
        # Actualizar cached status
        if self._cached_status:
            self._cached_status.last_fallback = datetime.now()
            self._cached_status.last_fallback_reason = reason

    def get_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Lee las últimas entradas del log de fallback."""
        if not LOG_FILE.exists():
            return []
        try:
            lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
            entries = [json.loads(l) for l in lines[-limit:] if l.strip()]
            return entries
        except Exception:
            return []


# =============================================================================
# SINGLETON
# =============================================================================

_manager: LLMFallbackManager | None = None
_manager_lock = threading.Lock()


def get_fallback_manager() -> LLMFallbackManager:
    """Obtiene la instancia singleton del manager."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = LLMFallbackManager()
    return _manager


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="LLM Fallback Manager")
    parser.add_argument("command", choices=["status", "probe", "set-mode", "log", "chat"])
    parser.add_argument("--mode", choices=["local", "cloud", "auto"], default=None)
    parser.add_argument("--prompt", default="¿Qué hora es?")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    mgr = get_fallback_manager()

    if args.command == "status":
        status = mgr.get_status()
        if args.json:
            print(json.dumps(status.to_dict(), indent=2))
        else:
            local_icon = "🟢" if status.local_available else "🔴"
            cloud_icon = "🔵" if status.cloud_available else "🔴"
            print(
                f"Local:   {local_icon} Ollama={status.ollama_running} ({len(status.installed_ollama_models)} models)"
            )
            print(f"Cloud:   {cloud_icon} Claude={status.cloud_available}")
            print(f"Modo:    {status.preference.value}")
            print(f"Prefer:  {status.preference.value}")
            print(f"Last FB: {status.last_fallback_reason or 'nunca'}")

    elif args.command == "probe":
        ollama_ok, ollama_models = probe_ollama()
        lmstudio_ok, lmstudio_models = probe_lmstudio()
        cloud_ok = mgr.is_cloud_available()
        if args.json:
            print(
                json.dumps(
                    {
                        "ollama": {"running": ollama_ok, "models": ollama_models},
                        "lmstudio": {"running": lmstudio_ok, "models": lmstudio_models},
                        "cloud": cloud_ok,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Ollama:    {'🟢' if ollama_ok else '🔴'} ({len(ollama_models)} modelos)")
            print(f"LM Studio: {'🟢' if lmstudio_ok else '🔴'} ({len(lmstudio_models)} modelos)")
            print(f"Cloud:     {'🔵' if cloud_ok else '🔴'}")

    elif args.command == "set-mode":
        if not args.mode:
            print("--mode requerido: local, cloud, auto")
        else:
            mgr.set_preference(LLMFallbackMode(args.mode))
            print(f"Modo seteado a: {args.mode}")

    elif args.command == "log":
        for entry in mgr.get_log(limit=20):
            ts = entry.get("timestamp", "")[:19]
            print(f"[{ts}] {entry.get('level', '?')}: {entry.get('message', '')}")

    elif args.command == "chat":

        async def run() -> None:
            result = await mgr.chat(args.prompt)
            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
            else:
                print(f"Provider: {result.provider_used}")
                print(f"Modo: {result.mode.value}")
                print(f"Fallback: {result.fallback_triggered or 'no'}")
                print(f"Latencia: {result.latency_ms:.0f}ms")
                if result.error:
                    print(f"Error: {result.error}")
                else:
                    print(f"Respuesta: {result.content[:200]}")

        asyncio.run(run())
