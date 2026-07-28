"""Advisor declarativo de routing por clase de modelo (split de costos).

El motor de routing por clase ya vive en ``proxy_state`` + ``_mixin_proxy`` y relee
``class_routing.json`` en cada request (caliente). Este modulo es el **cerebro** que
falta encima de ese musculo: a partir de una intencion declarativa
(``.antigravity/policy.json``) y del catalogo de providers, computa rutas concretas
y capability-aware — p. ej. "las tareas mecanicas (clase haiku) van al modelo mas
barato de ZAI, el razonamiento (opus/sonnet) se queda en Claude".

Filosofia (misma que ``providers.json``): fuente unica declarativa, versionada, sin
duplicar logica. NO toca el proxy: solo persiste rutas via ``set_class_route`` que el
motor existente consume en caliente.

Uso CLI::

    python .agent/core/routing_policy.py preview   # read-only: muestra las rutas
    python .agent/core/routing_policy.py apply      # persiste a class_routing.json
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Marcadores (en minuscula) que delatan la variante barata/rapida de una familia.
# El orden no importa; se elige el ULTIMO modelo del catalogo que matchee (los
# catalogos listan del mas potente al mas chico, asi que el ultimo match = el mas barato).
_CHEAP_MARKERS: tuple[str, ...] = (
    "air",
    "flash",
    "highspeed",
    "turbo",
    "mini",
    "lite",
    "small",
    "nano",
)

# Providers a los que tiene sentido rutear una clase "barata" (Anthropic-compat por
# proxy). Se valida contra esto para no rutear a un backend incompatible.
_PROXY_COMPATIBLE_FALLBACK: tuple[str, ...] = ("claude", "minimax", "zai")


@dataclass
class RoutingPolicy:
    """Intencion declarativa de split de costos por clase de modelo.

    Args:
        name: Nombre legible de la policy.
        description: Que hace, para mostrar en el preview.
        cheap_classes: Clases que van al backend barato (p. ej. ``("haiku",)``).
        strong_classes: Clases que se quedan en Claude (p. ej. ``("sonnet", "opus")``).
        cheap_provider: Backend destino de las clases baratas (proxy-compatible).
        cheap_model: Modelo explicito en el backend barato; ``None`` = auto-pick.
    """

    name: str
    description: str
    cheap_classes: tuple[str, ...]
    strong_classes: tuple[str, ...]
    cheap_provider: str
    cheap_model: str | None = None
    strong_provider: str = "claude"


_DEFAULT_POLICY = RoutingPolicy(
    name="cost-split-default",
    description=(
        "Tareas mecanicas internas (clase haiku) al modelo mas barato del backend "
        "alternativo; el razonamiento (opus/sonnet) se queda en Claude."
    ),
    cheap_classes=("haiku",),
    strong_classes=("sonnet", "opus"),
    cheap_provider="zai",
    cheap_model=None,
)


def default_policy_path() -> Path:
    """Devuelve la ruta canonica de ``.antigravity/policy.json`` en el repo.

    Returns:
        Path al archivo de policy versionado.
    """
    return Path(__file__).resolve().parents[2] / ".antigravity" / "policy.json"


def load_policy(path: Path | None = None) -> RoutingPolicy:
    """Carga la policy declarativa; degrada al default embebido si falta/corrupta.

    Args:
        path: Ruta al ``policy.json``; por defecto la canonica del repo.

    Returns:
        La ``RoutingPolicy`` efectiva (nunca lanza por archivo ausente).
    """
    path = path or default_policy_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.debug("policy.json ausente o corrupta; usando default embebido")
        return _DEFAULT_POLICY
    if not isinstance(data, dict):
        return _DEFAULT_POLICY
    return RoutingPolicy(
        name=str(data.get("name") or _DEFAULT_POLICY.name),
        description=str(data.get("description") or _DEFAULT_POLICY.description),
        cheap_classes=tuple(data.get("cheap_classes") or _DEFAULT_POLICY.cheap_classes),
        strong_classes=tuple(data.get("strong_classes") or _DEFAULT_POLICY.strong_classes),
        cheap_provider=str(data.get("cheap_provider") or _DEFAULT_POLICY.cheap_provider).lower(),
        cheap_model=(str(data["cheap_model"]) if data.get("cheap_model") else None),
        strong_provider=str(data.get("strong_provider") or "claude").lower(),
    )


def pick_cheap_model(models: tuple[str, ...]) -> str | None:
    """Elige el modelo mas barato de una familia segun los marcadores conocidos.

    Heuristica offline (jamas hace red): prefiere la ultima variante que matchee un
    marcador barato (``air``/``flash``/``highspeed``/...); si ninguno matchea, cae al
    ultimo modelo del catalogo (convencion: el mas chico va al final). Lista vacia →
    ``None`` (el caller usara el default del provider).

    Args:
        models: Modelos validos del provider, del mas potente al mas chico.

    Returns:
        Id del modelo barato elegido, o ``None`` si no hay modelos.
    """
    if not models:
        return None
    marked = [m for m in models if any(mk in m.lower() for mk in _CHEAP_MARKERS)]
    if marked:
        return marked[-1]
    return models[-1]


def _proxy_compatible() -> tuple[str, ...]:
    """Devuelve los providers proxy-compatible, con fallback si el import falla."""
    try:
        from core import provider_switch

        return tuple(provider_switch.PROXY_COMPATIBLE)
    except Exception:  # noqa: BLE001 — boundary de import; degradar al fallback
        return _PROXY_COMPATIBLE_FALLBACK


def _provider_models(provider_id: str) -> tuple[str, ...]:
    """Devuelve los modelos conocidos de un provider desde el catalogo."""
    try:
        from core import provider_catalog

        providers = provider_catalog.build_providers()
        cfg = providers.get(provider_id)
        return tuple(cfg.models) if cfg else ()
    except Exception:  # noqa: BLE001 — boundary de import; sin catalogo, sin modelos
        return ()


def resolve_policy_routes(
    policy: RoutingPolicy, models_by_provider: dict[str, tuple[str, ...]] | None = None
) -> dict[str, dict[str, str | None]]:
    """Traduce la intencion declarativa a rutas concretas por clase.

    Args:
        policy: La policy a resolver.
        models_by_provider: Override de modelos por provider (para tests). Si es
            ``None``, se leen del catalogo real.

    Returns:
        Dict ``{clase: {"provider": str, "model": str | None}}`` listo para persistir.

    Raises:
        ValueError: si ``cheap_provider`` no es proxy-compatible o es ``claude``
            (rutear la clase barata a Claude no ahorra nada).
    """
    compatible = _proxy_compatible()
    if policy.cheap_provider not in compatible:
        raise ValueError(
            f"cheap_provider {policy.cheap_provider!r} no es proxy-compatible "
            f"(validos: {compatible})"
        )
    if policy.cheap_provider == "claude":
        raise ValueError("cheap_provider no puede ser 'claude': no hay ahorro")

    if models_by_provider is not None:
        cheap_models = models_by_provider.get(policy.cheap_provider, ())
    else:
        cheap_models = _provider_models(policy.cheap_provider)
    cheap_model = policy.cheap_model or pick_cheap_model(cheap_models)

    routes: dict[str, dict[str, str | None]] = {}
    for cls in policy.cheap_classes:
        routes[cls] = {"provider": policy.cheap_provider, "model": cheap_model}
    for cls in policy.strong_classes:
        # Passthrough a Claude: el modelo lo decide Claude Code (no se pinea).
        routes[cls] = {"provider": policy.strong_provider, "model": None}
    return routes


def apply_policy(
    policy: RoutingPolicy | None = None,
    models_by_provider: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, dict[str, str | None]]:
    """Resuelve y PERSISTE las rutas de la policy a ``class_routing.json``.

    El motor del proxy las relee en caliente — no hace falta reiniciar nada.

    Args:
        policy: Policy a aplicar; por defecto la cargada de ``policy.json``.
        models_by_provider: Override de modelos (para tests).

    Returns:
        Las rutas resueltas y persistidas.
    """
    policy = policy or load_policy()
    routes = resolve_policy_routes(policy, models_by_provider)
    from core import proxy_state

    for cls, entry in routes.items():
        proxy_state.set_class_route(cls, str(entry["provider"]), entry["model"])
    logger.info("policy '%s' aplicada: %d rutas persistidas", policy.name, len(routes))
    return routes


def _format_routes(policy: RoutingPolicy, routes: dict[str, dict[str, str | None]]) -> str:
    """Formatea las rutas resueltas para el preview de CLI."""
    lines = [f"Policy: {policy.name}", f"  {policy.description}", ""]
    for cls, entry in routes.items():
        model = entry["model"] or "(default del provider)"
        lines.append(f"  {cls:<7} -> {entry['provider']}:{model}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Entry point CLI: ``preview`` (read-only) o ``apply`` (persiste).

    Args:
        argv: Argumentos (por defecto ``sys.argv[1:]``).

    Returns:
        Codigo de salida (0 OK, 2 uso incorrecto, 1 error de policy).
    """
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
    args = argv if argv is not None else sys.argv[1:]
    cmd = args[0] if args else "preview"
    if cmd not in {"preview", "apply"}:
        print("uso: routing_policy.py [preview|apply]", file=sys.stderr)
        return 2

    policy = load_policy()
    try:
        if cmd == "apply":
            routes = apply_policy(policy)
            print(_format_routes(policy, routes))
            print("\nAplicada. El proxy la toma en caliente (sin reiniciar).")
        else:
            routes = resolve_policy_routes(policy)
            print(_format_routes(policy, routes))
            print("\n(preview read-only — corré 'apply' para persistir)")
    except ValueError as exc:
        print(f"policy invalida: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
