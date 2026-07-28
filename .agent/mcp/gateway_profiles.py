"""
Runtime profile system for the Antigravity gateway/daemon.

Profiles control gateway behavior via the ``ANTIGRAVITY_PROFILE`` env var.
Three profiles are available:

- **minimal** — Liviano, para exploración local rápida. Sin auth, CORS permisivo.
- **standard** — Balanceado, default para operación diaria.
- **strict** — Seguridad completa, para entornos compartidos/producción.

Usage::

    import os
    os.environ["ANTIGRAVITY_PROFILE"] = "minimal_INSECURE"  # o "standard" (default seguro)

    from gateway_profiles import load_profile, ProfileConfig
    profile = load_profile()
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger("antigravity-gateway")

VALID_PROFILES = ("minimal_INSECURE", "standard", "strict")
# DEPRECATED alias: "minimal" redirige a "minimal_INSECURE" por retro-compatibilidad
DEPRECATED_ALIASES: dict[str, str] = {"minimal": "minimal_INSECURE"}
DEFAULT_PROFILE = "standard"


@dataclass(frozen=True)
class ProfileConfig:
    """Immutable configuration derived from a runtime profile.

    Attributes:
        name: Profile identifier (minimal, standard, strict).
        rate_limit: Requests per minute per IP. 0 means disabled.
        cors_mode: One of 'permissive', 'standard', 'strict'.
        log_level: Python logging level name.
        daemon_lite: Whether daemon starts in lite mode (lazy subsystems).
        auto_load_subsystems: Subsystems to eagerly load after daemon init.
            Empty list = none. ``["all"]`` = every subsystem.
        allow_no_auth_flag: If True, the ``--no-auth`` CLI flag is honored
            (auth can be disabled). If False, ``--no-auth`` is rejected and
            authentication stays forced. NOTE: this does NOT toggle auth by
            itself — auth is controlled by ``GatewayConfig.require_auth``
            (default True); this field only gates whether ``--no-auth`` works.
    """

    name: str = DEFAULT_PROFILE
    rate_limit: int = 60
    cors_mode: str = "standard"
    log_level: str = "INFO"
    daemon_lite: bool = True
    auto_load_subsystems: list[str] = field(default_factory=list)
    allow_no_auth_flag: bool = True


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

PROFILES: dict[str, ProfileConfig] = {
    # ATENCION: este perfil deshabilita auth y usa CORS permisivo.
    # Solo usar en entornos locales completamente aislados.
    "minimal_INSECURE": ProfileConfig(
        name="minimal_INSECURE",
        rate_limit=0,
        cors_mode="permissive",
        log_level="WARNING",
        daemon_lite=True,
        auto_load_subsystems=[],
        allow_no_auth_flag=True,
    ),
    "standard": ProfileConfig(
        name="standard",
        rate_limit=60,
        cors_mode="standard",
        log_level="INFO",
        daemon_lite=True,
        auto_load_subsystems=["skill_registry", "memory_engine"],
        allow_no_auth_flag=True,
    ),
    "strict": ProfileConfig(
        name="strict",
        rate_limit=30,
        cors_mode="strict",
        log_level="DEBUG",
        daemon_lite=False,
        auto_load_subsystems=["all"],
        allow_no_auth_flag=False,
    ),
}


def load_profile(env_var: str = "ANTIGRAVITY_PROFILE") -> ProfileConfig:
    """Load the active profile from the environment.

    Args:
        env_var: Name of the environment variable to read.

    Returns:
        The resolved ``ProfileConfig``.  Falls back to *standard* when
        the variable is unset or contains an invalid value.
    """
    raw = os.environ.get(env_var, "").strip().lower()

    if not raw:
        return PROFILES[DEFAULT_PROFILE]

    # Resolver alias deprecados para retro-compatibilidad
    if raw in DEPRECATED_ALIASES:
        resolved = DEPRECATED_ALIASES[raw]
        log.warning(
            "ANTIGRAVITY_PROFILE='%s' es un alias deprecado. Usar '%s' en su lugar.",
            raw,
            resolved,
        )
        raw = resolved

    if raw not in VALID_PROFILES:
        log.warning(
            "ANTIGRAVITY_PROFILE='%s' no es un perfil válido (%s). Usando '%s' por defecto.",
            raw,
            ", ".join(VALID_PROFILES),
            DEFAULT_PROFILE,
        )
        return PROFILES[DEFAULT_PROFILE]

    return PROFILES[raw]
