"""Selección del próximo provider sano para el failover automático del proxy.

Cierra el lazo observar→actuar: hoy, cuando el provider activo falla, el proxy rescata
SIEMPRE a Claude (un salto). Si el que se cayó ES Claude (rate-limit 429), ese rescate
no sirve. Este módulo agrega una **cascada configurable**: ante un fallo, rota al próximo
provider de la cascada cuyo circuito esté **cerrado** (sano), saltando el que acaba de
fallar.

Reusa el circuit breaker existente (`proxy_state` / `_mixin_proxy`): no reinventa estado,
solo decide el destino. La lógica de selección es **pura** (sin I/O) para testearla
determinísticamente.

**Opt-in**: `ANTIGRAVITY_PROXY_AUTO_FAILOVER` (default OFF). Con OFF, el comportamiento
histórico (rescate a Claude) queda intacto. Cascada configurable por
`ANTIGRAVITY_PROXY_CASCADE` (lista separada por comas).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_AUTO_FAILOVER_ENV = "ANTIGRAVITY_PROXY_AUTO_FAILOVER"
_CASCADE_ENV = "ANTIGRAVITY_PROXY_CASCADE"

# Orden por defecto: Claude primero (mejor calidad), luego los alternativos. Si el
# que falló es Claude (429), se lo saltea y baja por la cascada. Solo se incluyen
# providers proxy-routables. opencode/openrouter entran porque el proxy los traduce
# (bridge Anthropic<->OpenAI); ollama queda como último refugio local.
_DEFAULT_CASCADE: tuple[str, ...] = (
    "claude",
    "zai",
    "minimax",
    "opencode",
    "openrouter",
    "ollama",
)

# Fallback si no se puede importar provider_switch (boundary de import).
_ROUTABLE_FALLBACK: tuple[str, ...] = ("claude", "minimax", "zai", "ollama", "lmstudio")


def is_auto_failover_enabled() -> bool:
    """Indica si el failover automático en cascada está activo.

    Precedencia (igual que el class-routing): env ``ANTIGRAVITY_PROXY_AUTO_FAILOVER``
    (override / kill-switch en ambos sentidos si está seteado) → estado persistido en
    ``failover.json`` (lo que prende/apaga Nexus en caliente) → default OFF (opt-in).

    Returns:
        True si el failover está habilitado por env o por el toggle persistido.
    """
    raw = os.environ.get(_AUTO_FAILOVER_ENV, "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    try:
        from core import proxy_state

        return bool(proxy_state.get_failover().get("enabled"))
    except Exception:  # noqa: BLE001 — boundary de import; sin estado, default OFF
        return False


def _routable() -> tuple[str, ...]:
    """Devuelve los providers proxy-routables, con fallback si el import falla."""
    try:
        from core import provider_switch

        return tuple(provider_switch.PROXY_ROUTABLE)
    except Exception:  # noqa: BLE001 — boundary de import; degradar al fallback
        return _ROUTABLE_FALLBACK


def configured_providers() -> set[str] | None:
    """Providers con credenciales listas (o que no necesitan ninguna).

    Filtro de salud "de configuración" para el failover por circuito (pre-flight y
    in-flight): sin esto, la cascada puede elegir un provider con el circuito cerrado
    pero sin API key seteada (p. ej. mientras ``OPENROUTER_API_KEY``/``OPENCODE_API_KEY``
    siguen sin rotar tras quemarse) — el salto falla de entrada y solo agrega latencia
    y ruido de log antes de seguir bajando la cascada. La rotación por cuota
    (``_quota_available_providers``) ya resuelve esto para su propio predicado; esta
    función cubre los otros dos call-sites (circuito y in-flight).

    Returns:
        Set de provider ids con ``api_key_env`` vacío o con la key presente en el
        ``.env``, o ``None`` si no se pudo determinar (boundary de import) — en ese
        caso el caller no filtra, igual que antes de este chequeo.
    """
    try:
        from core import provider_switch

        root = provider_switch.default_root()
        return {
            pid
            for pid, cfg in provider_switch.PROVIDERS.items()
            if not cfg.api_key_env or provider_switch.get_api_key_from_env(root, cfg.api_key_env)
        }
    except Exception:  # noqa: BLE001 — boundary de import; sin filtro, no romper el failover
        return None


def get_cascade() -> tuple[str, ...]:
    """Devuelve el orden de cascada efectivo.

    Precedencia: env ``ANTIGRAVITY_PROXY_CASCADE`` (lista por comas) → default. En ambos
    casos se filtran entradas no proxy-routables y se deduplica preservando el orden.

    Returns:
        Tupla de provider ids en orden de preferencia para el failover.
    """
    raw = os.environ.get(_CASCADE_ENV, "").strip()
    candidates = [p.strip().lower() for p in raw.split(",")] if raw else list(_DEFAULT_CASCADE)
    routable = set(_routable())
    seen: set[str] = set()
    out: list[str] = []
    for p in candidates:
        if p and p in routable and p not in seen:
            seen.add(p)
            out.append(p)
    return tuple(out) if out else _DEFAULT_CASCADE


def select_failover_target(
    failed_provider: str,
    cascade: tuple[str, ...],
    open_circuits: set[str],
    available: set[str] | None = None,
) -> str | None:
    """Elige el próximo provider sano de la cascada tras un fallo. Función pura.

    Recorre la cascada en orden y devuelve el primer provider que:
    no sea el que acaba de fallar, no tenga el circuito abierto, y (si se pasa
    ``available``) esté disponible/configurado.

    Args:
        failed_provider: Provider que acaba de fallar (se saltea).
        cascade: Orden de preferencia de providers.
        open_circuits: Providers con el circuito abierto (no sanos).
        available: Si se da, restringe a providers presentes en este set
            (p. ej. los que tienen API key / están corriendo). ``None`` = sin filtro.

    Returns:
        El próximo provider sano, o ``None`` si ninguno califica.
    """
    failed = failed_provider.strip().lower()
    for provider in cascade:
        if provider == failed:
            continue
        if provider in open_circuits:
            continue
        if available is not None and provider not in available:
            continue
        return provider
    return None


def next_healthy_provider(
    failed_provider: str,
    open_circuits: set[str],
    available: set[str] | None = None,
) -> str | None:
    """Conveniencia: combina ``get_cascade`` + ``select_failover_target``.

    Args:
        failed_provider: Provider que acaba de fallar.
        open_circuits: Providers con circuito abierto.
        available: Filtro opcional de providers disponibles.

    Returns:
        El próximo provider sano según la cascada efectiva, o ``None``.
    """
    target = select_failover_target(failed_provider, get_cascade(), open_circuits, available)
    if target is not None:
        logger.info(
            "auto-failover: %s caído → rotando a %s (cascada %s)",
            failed_provider,
            target,
            get_cascade(),
        )
    else:
        logger.warning(
            "auto-failover: %s caído pero no hay provider sano en la cascada",
            failed_provider,
        )
    return target
