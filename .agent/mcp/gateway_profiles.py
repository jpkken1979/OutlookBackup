"""
Runtime profile system for the Antigravity gateway/daemon.

Profiles control gateway behavior via the ``ANTIGRAVITY_PROFILE`` env var.
Three profiles are available:

- **minimal** — Fast, lightweight, for development.
- **standard** — Balanced, default for daily operation.
- **strict** — Full security, for shared/production environments.

Usage::

    import os
    os.environ["ANTIGRAVITY_PROFILE"] = "minimal"

    from gateway_profiles import load_profile, ProfileConfig
    profile = load_profile()
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger("antigravity-gateway")

VALID_PROFILES = ("minimal", "standard", "strict")
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
        require_auth: If True, --no-auth flag is ignored.
    """

    name: str = DEFAULT_PROFILE
    rate_limit: int = 60
    cors_mode: str = "standard"
    log_level: str = "INFO"
    daemon_lite: bool = True
    auto_load_subsystems: list[str] = field(default_factory=list)
    require_auth: bool = False


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

PROFILES: dict[str, ProfileConfig] = {
    "minimal": ProfileConfig(
        name="minimal",
        rate_limit=0,
        cors_mode="permissive",
        log_level="WARNING",
        daemon_lite=True,
        auto_load_subsystems=[],
        require_auth=False,
    ),
    "standard": ProfileConfig(
        name="standard",
        rate_limit=60,
        cors_mode="standard",
        log_level="INFO",
        daemon_lite=True,
        auto_load_subsystems=["skill_registry", "memory_engine"],
        require_auth=False,
    ),
    "strict": ProfileConfig(
        name="strict",
        rate_limit=30,
        cors_mode="strict",
        log_level="DEBUG",
        daemon_lite=False,
        auto_load_subsystems=["all"],
        require_auth=True,
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

    if raw not in VALID_PROFILES:
        log.warning(
            "ANTIGRAVITY_PROFILE='%s' no es un perfil válido (%s). Usando '%s' por defecto.",
            raw,
            ", ".join(VALID_PROFILES),
            DEFAULT_PROFILE,
        )
        return PROFILES[DEFAULT_PROFILE]

    return PROFILES[raw]
