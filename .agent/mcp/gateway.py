#!/usr/bin/env python3
"""
Antigravity MCP HTTP Gateway — entrypoint.

Este archivo es el punto de entrada ejecutable (python .agent/mcp/gateway.py).
La implementacion completa vive en gateway_main.py; este modulo simplemente
re-exporta todo para compatibilidad de importacion y llama a main() cuando
se ejecuta directamente.

Uso:
    python .agent/mcp/gateway.py [--port 4747] [--host 0.0.0.0] [--no-auth]
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

# SIEMPRE configurar el path para que pueda encontrar los módulos del ecosistema.
# Esto necesita estar ANTES de cualquier import relativo.
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Re-exportar todo desde gateway_main para compatibilidad de importacion.
# Los consumidores que hagan `from mcp.gateway import AntigravityGateway`
# o `from mcp.gateway import _make_response` seguiran funcionando.
try:
    # Intentar import relativo (cuando se importa como módulo: from mcp.gateway import ...)
    from .gateway_main import (
        # Infraestructura
        GatewayConfig,
        RateLimiter,
        TTLCache,
        Metrics,
        EventManager,
        # Helpers
        _validate_name,
        _sanitize_error,
        _make_response,
        _normalize_plugin_stats,
        _build_openapi_schema,
        # Clase principal
        AntigravityGateway,
        # CLI
        main,
        # Constantes
        VERSION,
        DEFAULT_PORT,
        DEFAULT_HOST,
        MAX_ITERATIONS_CAP,
        MAX_TIMEOUT_SECONDS,
        MAX_TASK_LENGTH,
        MAX_TEAMS,
        TEAM_TTL_SECONDS,
        SSE_QUEUE_MAXSIZE,
        MAX_SSE_SUBSCRIBERS,
        CACHE_TTL_SECONDS,
        SAFE_NAME_PATTERN,
        # Paths
        BASE_DIR,
        AGENTS_DIR,
        SKILLS_DIR,
        SKILLS_CUSTOM_DIR,
        CORE_DIR,
        # Flags
        EXECUTOR_AVAILABLE,
        AIOHTTP_AVAILABLE,
        AgentExecutor,
    )
except ImportError:
    # Fallback a absolute import (cuando se ejecuta como script directo: python gateway.py)
    # En este caso, ejecutamos desde .agent/mcp/, así que gateway_main está aquí mismo
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mcp.gateway_main", Path(__file__).parent / "gateway_main.py"
    )
    if spec and spec.loader:
        gateway_main = importlib.util.module_from_spec(spec)
        # Configurar __package__ para que los relative imports en gateway_main.py funcionen
        gateway_main.__package__ = "mcp"
        sys.modules["mcp.gateway_main"] = gateway_main
        sys.modules["gateway_main"] = gateway_main  # Para compatibilidad
        spec.loader.exec_module(gateway_main)
        GatewayConfig = gateway_main.GatewayConfig
        RateLimiter = gateway_main.RateLimiter
        TTLCache = gateway_main.TTLCache
        Metrics = gateway_main.Metrics
        EventManager = gateway_main.EventManager
        _validate_name = gateway_main._validate_name
        _sanitize_error = gateway_main._sanitize_error
        _make_response = gateway_main._make_response
        _normalize_plugin_stats = gateway_main._normalize_plugin_stats
        _build_openapi_schema = gateway_main._build_openapi_schema
        AntigravityGateway = gateway_main.AntigravityGateway
        main = gateway_main.main
        VERSION = gateway_main.VERSION
        DEFAULT_PORT = gateway_main.DEFAULT_PORT
        DEFAULT_HOST = gateway_main.DEFAULT_HOST
        MAX_ITERATIONS_CAP = gateway_main.MAX_ITERATIONS_CAP
        MAX_TIMEOUT_SECONDS = gateway_main.MAX_TIMEOUT_SECONDS
        MAX_TASK_LENGTH = gateway_main.MAX_TASK_LENGTH
        MAX_TEAMS = gateway_main.MAX_TEAMS
        TEAM_TTL_SECONDS = gateway_main.TEAM_TTL_SECONDS
        SSE_QUEUE_MAXSIZE = gateway_main.SSE_QUEUE_MAXSIZE
        MAX_SSE_SUBSCRIBERS = gateway_main.MAX_SSE_SUBSCRIBERS
        CACHE_TTL_SECONDS = gateway_main.CACHE_TTL_SECONDS
        SAFE_NAME_PATTERN = gateway_main.SAFE_NAME_PATTERN
        BASE_DIR = gateway_main.BASE_DIR
        AGENTS_DIR = gateway_main.AGENTS_DIR
        SKILLS_DIR = gateway_main.SKILLS_DIR
        SKILLS_CUSTOM_DIR = gateway_main.SKILLS_CUSTOM_DIR
        CORE_DIR = gateway_main.CORE_DIR
        EXECUTOR_AVAILABLE = gateway_main.EXECUTOR_AVAILABLE
        AIOHTTP_AVAILABLE = gateway_main.AIOHTTP_AVAILABLE
        AgentExecutor = gateway_main.AgentExecutor
    else:
        raise ImportError("No se pudo cargar gateway_main.py")

__all__ = [
    "GatewayConfig",
    "RateLimiter",
    "TTLCache",
    "Metrics",
    "EventManager",
    "_validate_name",
    "_sanitize_error",
    "_make_response",
    "_normalize_plugin_stats",
    "_build_openapi_schema",
    "AntigravityGateway",
    "main",
    "VERSION",
    "DEFAULT_PORT",
    "DEFAULT_HOST",
    "MAX_ITERATIONS_CAP",
    "MAX_TIMEOUT_SECONDS",
    "MAX_TASK_LENGTH",
    "MAX_TEAMS",
    "TEAM_TTL_SECONDS",
    "SSE_QUEUE_MAXSIZE",
    "MAX_SSE_SUBSCRIBERS",
    "CACHE_TTL_SECONDS",
    "SAFE_NAME_PATTERN",
    "BASE_DIR",
    "AGENTS_DIR",
    "SKILLS_DIR",
    "SKILLS_CUSTOM_DIR",
    "CORE_DIR",
    "EXECUTOR_AVAILABLE",
    "AIOHTTP_AVAILABLE",
    "AgentExecutor",
]

if __name__ == "__main__":
    main()
