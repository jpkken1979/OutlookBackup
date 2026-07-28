"""Registry de Context Engines — carga builtins + plugins y selecciona el activo.

Selección del engine activo:
    1. Argumento explicito pasado a `get_engine(name)`.
    2. Env var `ANTIGRAVITY_CONTEXT_ENGINE`.
    3. Campo `context_engine` en `.antigravity/config.json`.
    4. Fallback: `"default"`.

Los engines built-in se cargan lazy para evitar ciclos de import (varios
engines importan `context_injection`, que a su vez expone `get_engine`).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .base import ContextEngine, ContextEngineMetadata

logger = logging.getLogger(__name__)

_BUILTIN_NAMES = (
    "default",
    "brain_aware",
    "delta_aware",
    "summarizing",
    "domain_uns",
    "composite",
)

_registry: dict[str, ContextEngine] = {}
_loaded = False


def _load_builtin(name: str) -> ContextEngine | None:
    """Import lazy de un engine built-in por slug."""
    try:
        if name == "default":
            from .builtin.default import DefaultContextEngine

            return DefaultContextEngine()
        if name == "brain_aware":
            from .builtin.brain_aware import BrainAwareContextEngine

            return BrainAwareContextEngine()
        if name == "delta_aware":
            from .builtin.delta_aware import DeltaAwareContextEngine

            return DeltaAwareContextEngine()
        if name == "summarizing":
            from .builtin.summarizing import SummarizingContextEngine

            return SummarizingContextEngine()
        if name == "domain_uns":
            from .builtin.domain_uns import DomainUnsContextEngine

            return DomainUnsContextEngine()
        if name == "composite":
            from .builtin.composite import CompositeContextEngine

            return CompositeContextEngine()
    except Exception as exc:  # noqa: BLE001
        logger.warning("No pude cargar engine %r: %s", name, exc)
    return None


def _ensure_loaded() -> None:
    """Carga los builtins una sola vez (idempotente)."""
    global _loaded
    if _loaded:
        return
    for name in _BUILTIN_NAMES:
        engine = _load_builtin(name)
        if engine is not None:
            _registry[name] = engine
    _loaded = True


def register_engine(name: str, engine: ContextEngine) -> None:
    """Registra un engine externo (plugins, tests, customizaciones)."""
    _ensure_loaded()
    _registry[name] = engine
    logger.info("Engine %r registrado", name)


def list_engines() -> list[ContextEngineMetadata]:
    """Lista engines disponibles con metadata."""
    _ensure_loaded()
    return [e.metadata for e in _registry.values()]


def resolve_engine_name(explicit: str | None = None) -> str:
    """Determina el nombre del engine activo segun las 4 fuentes."""
    if explicit:
        return explicit.strip()
    env = os.environ.get("ANTIGRAVITY_CONTEXT_ENGINE", "").strip()
    if env:
        return env
    cfg_name = _read_config_engine()
    if cfg_name:
        return cfg_name
    return "default"


def _read_config_engine() -> str | None:
    """Lee `.antigravity/config.json` si existe en CWD o en ANTIGRAVITY_ROOT."""
    candidates: list[Path] = []
    root_env = os.environ.get("ANTIGRAVITY_ROOT", "").strip()
    if root_env:
        candidates.append(Path(root_env) / ".antigravity" / "config.json")
    candidates.append(Path.cwd() / ".antigravity" / "config.json")
    for path in candidates:
        try:
            if path.is_file():
                raw = json.loads(path.read_text(encoding="utf-8"))
                val = raw.get("context_engine")
                if isinstance(val, str) and val.strip():
                    return val.strip()
        except (OSError, json.JSONDecodeError):
            continue
    return None


def get_engine(name: str | None = None) -> ContextEngine:
    """Retorna el engine activo.

    Si `name` es None, resuelve via env/config. Si el nombre no existe,
    log de warning y fallback a `default`.
    """
    _ensure_loaded()
    resolved = resolve_engine_name(name)
    engine = _registry.get(resolved)
    if engine is not None:
        return engine
    logger.warning(
        "Engine %r no encontrado; disponibles=%s; fallback a default",
        resolved,
        sorted(_registry.keys()),
    )
    fallback = _registry.get("default")
    if fallback is None:
        # ultimo recurso — no deberia pasar si el modulo default esta bien
        from .builtin.default import DefaultContextEngine

        fallback = DefaultContextEngine()
        _registry["default"] = fallback
    return fallback


def reset_for_tests() -> None:
    """Utilidad para tests — re-inicializa el registry."""
    global _loaded
    _registry.clear()
    _loaded = False


def engine_names() -> list[str]:
    _ensure_loaded()
    return sorted(_registry.keys())


def config_snapshot() -> dict[str, Any]:
    """Diagnostico: fuentes de seleccion y engine resuelto."""
    return {
        "resolved": resolve_engine_name(),
        "env": os.environ.get("ANTIGRAVITY_CONTEXT_ENGINE", ""),
        "config_file": _read_config_engine(),
        "available": engine_names(),
    }
