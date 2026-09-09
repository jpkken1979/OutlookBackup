"""Canonical provider/model selection owned by the Python gateway."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from core import routing_store
from core.routing_store import RoutingStore

_CONTINUITY_CAPABILITIES_ENV = "ANTIGRAVITY_PROVIDER_CONTINUITY_JSON"
_ALLOWED_IDEMPOTENCY_HEADERS = frozenset({"Idempotency-Key", "X-Idempotency-Key"})

_QUALITY = {
    "claude": 1.0,
    "openai": 0.95,
    "gemini": 0.90,
    "xai": 0.90,
    "deepseek": 0.88,
    "opencodex": 0.86,
    "antigravity": 0.88,
    "github-copilot": 0.87,
    "opencode": 0.85,
    "mistral": 0.83,
    "openrouter": 0.82,
    "together": 0.80,
    "fireworks": 0.80,
    "huggingface": 0.80,
    "zai": 0.80,
    "groq": 0.78,
    "cerebras": 0.78,
    "minimax": 0.76,
    "nvidia": 0.70,
    "lmstudio": 0.55,
    "ollama": 0.50,
}
_COST = {
    "claude": 1.0,
    "openai": 0.80,
    "xai": 0.60,
    "mistral": 0.35,
    "gemini": 0.30,
    "opencodex": 0.30,
    "antigravity": 0.20,
    "github-copilot": 0.20,
    "opencode": 0.25,
    "openrouter": 0.20,
    "together": 0.18,
    "fireworks": 0.18,
    "huggingface": 0.15,
    "deepseek": 0.15,
    "groq": 0.10,
    "cerebras": 0.10,
    "zai": 0.25,
    "minimax": 0.25,
    "nvidia": 0.20,
    "lmstudio": 0.05,
    "ollama": 0.02,
}
# Tiers de resiliencia: se agota primero lo que ya esta pago, despues lo barato, y
# al final lo local. Idea tomada de OmniRoute/9Router (2026-07-28), sin su codigo.
#
# Antes la prioridad era POSICIONAL (`100 - indice * 8`), o sea dependia del orden
# del diccionario `provider_switch.PROVIDERS`: reordenarlo cambiaba el routing en
# silencio. Ahora es explicita y se lee de un solo lugar.
TIER_SUBSCRIPTION = 100  # ya pagado: usarlo antes que gastar creditos
TIER_API_KEY = 70  # se paga por token
TIER_CHEAP = 50  # remoto barato o con free tier
TIER_LOCAL = 30  # sin costo pero mas lento/limitado
TIER_BRIDGE = 20  # puentes opcionales: solo si estan levantados

_TIERS = {
    "claude": TIER_SUBSCRIPTION,
    "openai": TIER_API_KEY,
    "gemini": TIER_API_KEY,
    "mistral": TIER_API_KEY,
    "xai": TIER_API_KEY,
    "zai": TIER_API_KEY,
    "minimax": TIER_API_KEY,
    "deepseek": TIER_CHEAP,
    "groq": TIER_CHEAP,
    "cerebras": TIER_CHEAP,
    "together": TIER_CHEAP,
    "fireworks": TIER_CHEAP,
    "huggingface": TIER_CHEAP,
    "opencode": TIER_CHEAP,
    "openrouter": TIER_CHEAP,
    "nvidia": TIER_CHEAP,
    "ollama": TIER_LOCAL,
    "lmstudio": TIER_LOCAL,
    "opencodex": TIER_BRIDGE,
    "antigravity": TIER_BRIDGE,
    "github-copilot": TIER_BRIDGE,
}

_CAPABILITIES = {
    "claude": {"coding", "reliable"},
    "openai": {"coding", "reliable"},
    "gemini": {"coding", "fast"},
    "deepseek": {"coding", "cheap"},
    "groq": {"coding", "fast", "cheap"},
    "mistral": {"coding"},
    "xai": {"coding"},
    "cerebras": {"coding", "fast", "cheap"},
    "together": {"coding", "cheap"},
    "fireworks": {"coding", "fast", "cheap"},
    "huggingface": {"coding", "cheap"},
    "opencodex": {"coding", "fast", "cheap"},
    "antigravity": {"coding", "fast", "cheap"},
    "github-copilot": {"coding", "fast", "cheap"},
    "opencode": {"coding", "fast", "cheap"},
    "openrouter": {"coding", "cheap"},
    "zai": {"coding", "fast", "cheap"},
    "minimax": {"coding", "fast", "cheap"},
    "nvidia": {"fast", "cheap"},
    "lmstudio": {"cheap"},
    "ollama": {"cheap"},
}


def _auto_provider_enabled(provider: str) -> bool:
    """Keep optional compatibility bridges out of auto-routing by default."""

    env_names = {
        "opencodex": "ANTIGRAVITY_OPENCODEX_AUTO",
        "antigravity": "ANTIGRAVITY_ANTIGRAVITY_AUTO",
        "github-copilot": "ANTIGRAVITY_GITHUB_COPILOT_AUTO",
    }
    env_name = env_names.get(provider)
    if env_name is None:
        return True
    return os.environ.get(env_name, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    trace_id: str
    route: str
    provider: str
    model: str
    score: float
    manual: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderContinuityCapabilities:
    """Provider-declared guarantees used by retries and stream recovery."""

    idempotency_header: str | None = None
    stream_resume: bool = False


def provider_continuity_capabilities(provider: str) -> ProviderContinuityCapabilities:
    """Read opt-in provider guarantees without assuming OpenAI compatibility.

    Chat Completions compatibility does not imply server-side deduplication or
    partial-stream resume. Providers can be enabled explicitly with a JSON map,
    for example ``{"vendor":{"idempotency_header":"Idempotency-Key"}}``.
    Unknown/invalid declarations fail closed.
    """

    raw = os.environ.get(_CONTINUITY_CAPABILITIES_ENV, "").strip()
    if not raw:
        return ProviderContinuityCapabilities()
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return ProviderContinuityCapabilities()
    if not isinstance(parsed, dict):
        return ProviderContinuityCapabilities()
    declared = parsed.get(provider.strip().lower())
    if not isinstance(declared, dict):
        return ProviderContinuityCapabilities()
    header = declared.get("idempotency_header")
    if header not in _ALLOWED_IDEMPOTENCY_HEADERS:
        header = None
    return ProviderContinuityCapabilities(
        idempotency_header=header,
        stream_resume=declared.get("stream_resume") is True,
    )


class RoutingAuthority:
    def __init__(self, store: RoutingStore | None = None):
        self.store = store or RoutingStore()

    @staticmethod
    def _quota_remaining(provider: str) -> float:
        """Cuota restante del provider, normalizada a [0, 1].

        Args:
            provider: Id del provider.

        Returns:
            Fraccion de cuota restante. ``1.0`` cuando no hay senal confiable
            (poller caido o provider sin cuota reportada): desconocido no debe
            penalizar, porque si no todo provider sin poller quedaria ultimo.
        """
        from core import quota_state

        try:
            restante = quota_state.get_remaining_percent(provider)
        except Exception:  # pragma: no cover - la cuota nunca debe tumbar el routing
            return 1.0
        if restante is None:
            return 1.0
        return max(0.0, min(float(restante) / 100.0, 1.0))

    def _runtime_candidates(self) -> list[dict[str, Any]]:
        from core import provider_cascade, provider_switch, proxy_state

        available = provider_cascade.configured_providers()
        # `store.status()` aporta SOLO observabilidad (latencia). El circuito sale
        # de `proxy_state`, que es el autoritativo: es el mismo estado que consulta
        # `_mixin_proxy._circuit_open()` para decidir su propio failover.
        #
        # Antes se combinaban los dos con OR. Eran dos representaciones del mismo
        # circuito, escritas por el mismo archivo (`_mixin_proxy` persiste en
        # proxy_state y ademas llama a `record_outcome`, que alimenta el espejo del
        # store), pero con umbrales propios: podian discrepar y el router terminaba
        # descartando un provider que el proxy consideraba sano, o al reves.
        health = {entry["provider"]: entry for entry in self.store.status()["providers"]}
        circuit = proxy_state.get_circuit()
        candidates: list[dict[str, Any]] = []
        for provider, config in provider_switch.PROVIDERS.items():
            stored = health.get(provider, {})
            # El estado persistido no trae un flag `open` — se deriva de
            # streak + cooldown. `proxy_state.circuit_open` es la misma cuenta
            # que hace el proxy, para que router y proxy no discrepen.
            is_open = proxy_state.circuit_open(provider, state=circuit)
            candidates.append(
                {
                    "provider": provider,
                    "model": provider_switch.resolve_provider_model(provider),
                    "configured": (available is None or provider in available)
                    and _auto_provider_enabled(provider),
                    "healthy": not is_open,
                    # Antes esto era un 1.0 fijo: la dimension "quota" del scoring
                    # aportaba lo mismo a todos y los perfiles auto/* podian rutear
                    # a un provider sin cuota. quota_state ya tenia el dato real,
                    # alimentado por usage_poller — solo faltaba el cable.
                    "quota_remaining": self._quota_remaining(provider),
                    "latency_ms": stored.get("latency_ms") or 500,
                    "cost": _COST.get(provider, 0.5),
                    "quality": _QUALITY.get(provider, 0.5),
                    "priority": _TIERS.get(provider, TIER_CHEAP),
                    "capabilities": sorted(_CAPABILITIES.get(provider, set())),
                    "routable": bool(config.routable),
                }
            )
        return candidates

    @staticmethod
    def _score(candidate: dict[str, Any], weights: dict[str, Any]) -> float:
        quality = float(candidate.get("quality", _QUALITY.get(candidate["provider"], 0.5)))
        health = 1.0 if candidate.get("healthy", True) else 0.0
        quota = max(0.0, min(float(candidate.get("quota_remaining", 1.0)), 1.0))
        latency = max(0.0, 1.0 - min(float(candidate.get("latency_ms", 500)), 5000) / 5000)
        cost = max(0.0, 1.0 - min(float(candidate.get("cost", 0.5)), 1.0))
        priority = max(0.0, min(float(candidate.get("priority", 50)) / 100, 1.0))
        dimensions = {
            "quality": quality,
            "health": health,
            "quota": quota,
            "latency": latency,
            "cost": cost,
            "priority": priority,
        }
        return round(
            sum(float(weights.get(name, 0.0)) * value for name, value in dimensions.items()),
            6,
        )

    def select(
        self,
        route: str | None = None,
        *,
        candidates: Iterable[dict[str, Any]] | None = None,
        trace_id: str | None = None,
        persist: bool = True,
    ) -> RoutingDecision:
        route = (route or self.store.active_profile()).strip()
        route_key = route.lower() if route.lower().startswith("auto") else route
        trace_id = trace_id or f"route-{uuid.uuid4().hex}"
        candidate_list = list(candidates) if candidates is not None else self._runtime_candidates()
        by_provider = {str(item["provider"]).lower(): item for item in candidate_list}

        if not route_key.lower().startswith("auto"):
            provider, separator, model = route_key.partition("/")
            provider = provider.lower()
            if not separator or not model or provider not in by_provider:
                raise ValueError("Manual route must use provider/model")
            decision = RoutingDecision(
                trace_id=trace_id,
                route=f"{provider}/{model}",
                provider=provider,
                model=model,
                score=1.0,
                manual=True,
                reason="manual_override",
            )
            if persist:
                self.store.record_decision(
                    trace_id=decision.trace_id,
                    route=decision.route,
                    provider=decision.provider,
                    model=decision.model,
                    score=decision.score,
                    manual=decision.manual,
                    detail={"override": True, "reason": decision.reason},
                )
            from core.routing_telemetry import record_routing_decision

            record_routing_decision(
                decision,
                eligible_count=len(candidate_list),
                dry_run=not persist,
            )
            return decision

        route_key = route_key.lower()
        profile = self.store.get_profile(route_key)
        if profile is None:
            raise ValueError("Unknown automatic route")
        required = profile.get("required_capability")
        eligible = [
            candidate
            for candidate in candidate_list
            if candidate.get("configured", False)
            and candidate.get("healthy", True)
            and candidate.get("routable", True)
            and (
                not required
                or required in set(candidate.get("capabilities", ()))
                or (required == "reliable" and candidate["provider"] == "claude")
            )
        ]
        if not eligible:
            raise RuntimeError("No healthy configured provider satisfies the route")

        strategy = str(profile.get("strategy") or routing_store.STRATEGY_SCORE)
        chosen = self._apply_strategy(strategy, route_key, eligible)
        if chosen is not None:
            score = 1.0
            reason = strategy
        else:
            scored = [
                (self._score(candidate, profile.get("weights", {})), candidate)
                for candidate in eligible
            ]
            score, chosen = max(
                scored,
                key=lambda item: (item[0], float(item[1].get("priority", 0))),
            )
            reason = "profile_score"
        decision = RoutingDecision(
            trace_id=trace_id,
            route=route_key,
            provider=str(chosen["provider"]),
            model=str(chosen["model"]),
            score=score,
            manual=False,
            reason=reason,
        )
        if persist:
            self.store.record_decision(
                trace_id=decision.trace_id,
                route=decision.route,
                provider=decision.provider,
                model=decision.model,
                score=decision.score,
                manual=decision.manual,
                detail={
                    "reason": decision.reason,
                    "strategy": strategy,
                    "required_capability": required,
                    "eligible": [candidate["provider"] for candidate in eligible],
                },
            )
        from core.routing_telemetry import record_routing_decision

        record_routing_decision(
            decision,
            eligible_count=len(eligible),
            dry_run=not persist,
        )
        return decision

    def _apply_strategy(
        self,
        strategy: str,
        route_key: str,
        eligible: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Elige por estrategia no basada en scoring.

        Args:
            strategy: `round_robin`, `last_known_good` o cualquier otra (que cae a
                scoring).
            route_key: Perfil activo, usado como namespace del cursor.
            eligible: Candidatos ya filtrados por salud, capacidad y routabilidad.

        Returns:
            El candidato elegido, o ``None`` para que decida el scoring — que es
            tambien el fallback cuando la estrategia no encuentra a quien elegir
            (por ejemplo `sticky` sin exitos previos registrados).
        """
        por_id = {str(c["provider"]): c for c in eligible}

        if strategy == routing_store.STRATEGY_ROUND_ROBIN:
            elegido = self.store.advance_round_robin(route_key, list(por_id))
            return por_id.get(elegido) if elegido else None

        if strategy == routing_store.STRATEGY_LAST_KNOWN_GOOD:
            elegido = self.store.last_successful_provider(list(por_id))
            return por_id.get(elegido) if elegido else None

        return None

    def resolve_request(
        self,
        payload: bytes,
        current_provider: str,
        current_model: str,
        *,
        trace_id: str | None = None,
        route_hint: str | None = None,
    ) -> RoutingDecision | None:
        import json

        try:
            body = json.loads(payload)
        except (TypeError, ValueError):
            return None
        requested = str(body.get("model") or "").strip()
        requested_lower = requested.lower()
        providers = {candidate["provider"] for candidate in self._runtime_candidates()}
        if requested_lower.startswith("auto") or (
            "/" in requested_lower and requested_lower.split("/", 1)[0] in providers
        ):
            return self.select(requested, trace_id=trace_id)
        hint = (route_hint or "").strip()
        if not hint:
            return None
        if hint.lower() == "active":
            hint = self.store.manual_override() or self.store.active_profile()
        return self.select(hint, trace_id=trace_id)


@lru_cache(maxsize=1)
def get_routing_authority() -> RoutingAuthority:
    return RoutingAuthority()


def routing_enabled() -> bool:
    return os.environ.get("ANTIGRAVITY_ROUTING_V2", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }
