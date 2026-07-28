#!/usr/bin/env python3
"""Unified Configuration Loader — Multi-source config con perfiles.

Unifica las fuentes de configuración del ecosistema:
  1. Defaults internos
  2. pyproject.toml [tool.antigravity]
  3. .env / variables de entorno
  4. intelligence_config.json
  5. Overrides de perfil (dev/staging/prod)

Inspirado en el ConfigManager de OpenClaw (JSON5 + Zod + env substitution
+ includes + migration + UI hints) adaptado al ecosistema Python.

Uso:
    from .unified_config import load_config, get_profile

    config = load_config()  # Carga automática
    config = load_config(profile="production")

    # Acceder a valores
    config["llm"]["model"]
    config["gateway"]["port"]
    config.get_nested("llm.model", default="claude-sonnet-4-20250514")

v1.0.0 - 2026-02-27
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.unified_config")

# =============================================================================
# CONSTANTS
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENT_DIR = PROJECT_ROOT / ".agent"
CONFIG_DIR = AGENT_DIR / "core" / "config"

PROFILES = {"development", "staging", "production", "testing"}

# =============================================================================
# DEFAULT CONFIG
# =============================================================================

_DEFAULTS: dict[str, Any] = {
    "version": "2.1.0",
    "profile": "development",
    "llm": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "temperature": 0.1,
        "fallback_model": "gpt-4o-mini",
    },
    "gateway": {
        "host": "127.0.0.1",
        "port": 4747,
        "protocol": "http",
        "auto_open_browser": True,
        "cors_origins": ["http://localhost:*"],
    },
    "memory": {
        "backend": "sqlite+chroma",
        "sqlite_weight": 0.4,
        "chroma_weight": 0.6,
        "mmr_enabled": True,
        "mmr_lambda": 0.7,
        "max_observations": 10000,
    },
    "agents": {
        "max_concurrent": 5,
        "default_timeout": 120,
        "fallback_strategy": "crewai->react->simulation",
        "auto_discover": True,
        "llm_enabled": True,
        "llm_mode": "auto",
    },
    "security": {
        "bandit_enabled": True,
        "skill_scanner_enabled": True,
        "boundary_check_enabled": True,
        "max_subprocess_timeout": 30,
    },
    "observability": {
        "log_level": "INFO",
        "telemetry_enabled": False,
        "metrics_port": 9090,
        "prometheus_enabled": False,
    },
    "paths": {
        "agent_dir": ".agent",
        "skills_dir": ".agent/skills",
        "plugins_dir": ".agent/plugins",
        "logs_dir": ".agent/logs",
        "data_dir": ".agent/data",
    },
}

# =============================================================================
# PROFILE OVERRIDES
# =============================================================================

_PROFILE_OVERRIDES: dict[str, dict[str, Any]] = {
    "development": {
        "observability": {
            "log_level": "DEBUG",
            "telemetry_enabled": False,
        },
        "security": {
            "boundary_check_enabled": True,
        },
    },
    "staging": {
        "observability": {
            "log_level": "INFO",
            "telemetry_enabled": True,
        },
        "agents": {
            "max_concurrent": 3,
        },
    },
    "production": {
        "llm": {
            "temperature": 0.0,
        },
        "observability": {
            "log_level": "WARNING",
            "telemetry_enabled": True,
            "prometheus_enabled": True,
        },
        "agents": {
            "max_concurrent": 10,
            "default_timeout": 300,
        },
        "security": {
            "bandit_enabled": True,
            "skill_scanner_enabled": True,
            "boundary_check_enabled": True,
        },
    },
    "testing": {
        "llm": {
            "provider": "mock",
            "model": "test-model",
        },
        "observability": {
            "log_level": "DEBUG",
            "telemetry_enabled": False,
        },
        "agents": {
            "max_concurrent": 1,
            "default_timeout": 10,
        },
    },
}


# =============================================================================
# UNIFIED CONFIG CLASS
# =============================================================================


class UnifiedConfig:
    """Configuración unificada con acceso por clave y merge profundo.

    Soporta:
    - Acceso por corchetes: config["llm"]["model"]
    - Acceso anidado: config.get_nested("llm.model")
    - Merge profundo de fuentes con prioridad
    - Serialización a dict/JSON
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = data or deepcopy(_DEFAULTS)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene valor por clave de primer nivel."""
        return self._data.get(key, default)

    def get_nested(self, dotted_key: str, default: Any = None) -> Any:
        """Obtiene valor por clave con notación punto.

        Args:
            dotted_key: Clave tipo "llm.model" o "gateway.port".
            default: Valor por defecto si no existe.

        Returns:
            Valor encontrado o default.
        """
        parts = dotted_key.split(".")
        current: Any = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set_nested(self, dotted_key: str, value: Any) -> None:
        """Establece valor por clave con notación punto.

        Args:
            dotted_key: Clave tipo "llm.model".
            value: Valor a establecer.
        """
        parts = dotted_key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def to_dict(self) -> dict[str, Any]:
        """Retorna copia del diccionario completo."""
        return deepcopy(self._data)

    def to_json(self, indent: int = 2) -> str:
        """Serializa a JSON."""
        return json.dumps(self._data, indent=indent, default=str)


# =============================================================================
# MERGE UTILITIES
# =============================================================================


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge profundo de dos diccionarios.

    Args:
        base: Diccionario base.
        override: Diccionario con valores que sobreescriben.

    Returns:
        Nuevo diccionario mergeado.
    """
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


# =============================================================================
# SOURCE LOADERS
# =============================================================================


def _load_from_pyproject(project_root: Path) -> dict[str, Any]:
    """Carga config desde [tool.antigravity] en pyproject.toml.

    Args:
        project_root: Raíz del proyecto.

    Returns:
        Diccionario con config de pyproject.toml.
    """
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.is_file():
        return {}

    try:
        # Python 3.11+ tiene tomllib
        import tomllib

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("tool", {}).get("antigravity", {})
    except ImportError:
        logger.debug("tomllib no disponible, saltando pyproject.toml")
        return {}
    except Exception as e:
        logger.debug("Error leyendo pyproject.toml: %s", e)
        return {}


def _load_from_env() -> dict[str, Any]:
    """Carga config desde variables de entorno con prefijo ANTIGRAVITY_.

    Variables reconocidas:
    - ANTIGRAVITY_PROFILE: perfil activo
    - ANTIGRAVITY_LLM_MODEL: modelo LLM
    - ANTIGRAVITY_LLM_PROVIDER: proveedor LLM
    - ANTIGRAVITY_GATEWAY_PORT: puerto del gateway
    - ANTIGRAVITY_LOG_LEVEL: nivel de log
    - ANTIGRAVITY_TELEMETRY: habilitar telemetría

    Returns:
        Diccionario con config extraída de env vars.
    """
    config: dict[str, Any] = {}

    env_mapping: dict[str, str] = {
        "ANTIGRAVITY_PROFILE": "profile",
        "ANTIGRAVITY_LLM_MODEL": "llm.model",
        "ANTIGRAVITY_LLM_PROVIDER": "llm.provider",
        "ANTIGRAVITY_LLM_TEMPERATURE": "llm.temperature",
        "ANTIGRAVITY_LLM_MAX_TOKENS": "llm.max_tokens",
        "ANTIGRAVITY_LLM_THINKING": "llm.thinking_level",
        "ANTIGRAVITY_PERSONA": "persona.mode",
        "ANTIGRAVITY_SESSION_PROFILE": "session.profile",
        "ANTIGRAVITY_GATEWAY_HOST": "gateway.host",
        "ANTIGRAVITY_GATEWAY_PORT": "gateway.port",
        "ANTIGRAVITY_LOG_LEVEL": "observability.log_level",
        "ANTIGRAVITY_TELEMETRY": "observability.telemetry_enabled",
        "ANTIGRAVITY_MAX_AGENTS": "agents.max_concurrent",
    }

    for env_key, config_path in env_mapping.items():
        value = os.environ.get(env_key)
        if value is None:
            continue

        # Conversión de tipos
        if config_path.endswith("_port") or "port" in config_path:
            try:
                value = int(value)  # type: ignore[assignment]  # str->int: env var validated upstream
            except ValueError:
                continue
        elif config_path.endswith("_enabled") or "enabled" in config_path:
            value = value.lower() in ("true", "1", "yes")  # type: ignore[assignment]  # str->bool: env var coercion
        elif "temperature" in config_path or "max_concurrent" in config_path:
            try:
                value = float(value)  # type: ignore[assignment]  # str->float: env var coercion
            except ValueError:
                continue

        # Convertir clave dotted a diccionario anidado
        parts = config_path.split(".")
        current = config
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value

    return config


def _load_from_dotenv(project_root: Path) -> None:
    """Carga .env si existe (sin dependencia python-dotenv).

    Args:
        project_root: Raíz del proyecto.
    """
    env_file = project_root / ".env"
    if not env_file.is_file():
        return

    try:
        content = env_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception as e:
        logger.debug("Error leyendo .env: %s", e)


def _load_intelligence_config(agent_dir: Path) -> dict[str, Any]:
    """Carga intelligence_config.json si existe.

    Args:
        agent_dir: Directorio .agent.

    Returns:
        Config del intelligence center mapeada a formato unificado.
    """
    config_files = [
        agent_dir / "core" / "config" / "intelligence_config.json",
        agent_dir / "config" / "intelligence_config.json",
    ]

    for config_file in config_files:
        if config_file.is_file():
            try:
                data = json.loads(config_file.read_text(encoding="utf-8"))
                # Mapear campos conocidos al formato unificado
                result: dict[str, Any] = {}
                if "model" in data:
                    result.setdefault("llm", {})["model"] = data["model"]
                if "provider" in data:
                    result.setdefault("llm", {})["provider"] = data["provider"]
                if "temperature" in data:
                    result.setdefault("llm", {})["temperature"] = data["temperature"]
                if "max_tokens" in data:
                    result.setdefault("llm", {})["max_tokens"] = data["max_tokens"]
                return result
            except Exception as e:
                logger.debug("Error leyendo intelligence_config.json: %s", e)

    return {}


# =============================================================================
# MAIN LOADER
# =============================================================================


def load_config(
    project_root: Path | None = None,
    profile: str | None = None,
) -> UnifiedConfig:
    """Carga configuración unificada desde todas las fuentes.

    Prioridad (mayor a menor):
    1. Variables de entorno (ANTIGRAVITY_*)
    2. intelligence_config.json
    3. pyproject.toml [tool.antigravity]
    4. Profile overrides
    5. Defaults

    Args:
        project_root: Raíz del proyecto, auto-detecta si None.
        profile: Perfil activo (dev/staging/prod/testing).

    Returns:
        UnifiedConfig con toda la configuración mergeada.
    """
    root = project_root or PROJECT_ROOT
    agent_dir = root / ".agent"

    # 1. Empezar con defaults
    config = deepcopy(_DEFAULTS)

    # 2. Cargar .env primero (para que env vars estén disponibles)
    _load_from_dotenv(root)

    # 3. Determinar perfil
    active_profile = (
        profile or os.environ.get("ANTIGRAVITY_PROFILE") or config.get("profile", "development")
    )

    if active_profile not in PROFILES:
        logger.warning("Perfil '%s' no reconocido, usando 'development'", active_profile)
        active_profile = "development"

    config["profile"] = active_profile

    # 4. Aplicar overrides del perfil
    profile_overrides = _PROFILE_OVERRIDES.get(active_profile, {})
    config = _deep_merge(config, profile_overrides)

    # 5. Merge pyproject.toml [tool.antigravity]
    pyproject_config = _load_from_pyproject(root)
    if pyproject_config:
        config = _deep_merge(config, pyproject_config)

    # 6. Merge intelligence_config.json
    intel_config = _load_intelligence_config(agent_dir)
    if intel_config:
        config = _deep_merge(config, intel_config)

    # 7. Merge env vars (máxima prioridad)
    env_config = _load_from_env()
    if env_config:
        config = _deep_merge(config, env_config)

    logger.info("Config cargada: profile=%s, llm=%s", active_profile, config["llm"]["model"])
    return UnifiedConfig(config)


def get_profile(project_root: Path | None = None) -> str:
    """Retorna el perfil activo.

    Args:
        project_root: Raíz del proyecto.

    Returns:
        Nombre del perfil activo.
    """
    return os.environ.get("ANTIGRAVITY_PROFILE") or "development"


# =============================================================================
# SINGLETON
# =============================================================================

_unified_config: UnifiedConfig | None = None


def get_unified_config(
    project_root: Path | None = None,
    profile: str | None = None,
) -> UnifiedConfig:
    """Obtiene instancia singleton de UnifiedConfig.

    Args:
        project_root: Raíz del proyecto.
        profile: Perfil activo.

    Returns:
        UnifiedConfig singleton.
    """
    global _unified_config  # noqa: PLW0603
    if _unified_config is None:
        _unified_config = load_config(project_root=project_root, profile=profile)
    return _unified_config
