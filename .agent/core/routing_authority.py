"""Canonical provider/model selection owned by the Python gateway."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from core.routing_store import RoutingStore

_QUALITY = {
    "claude": 1.0,
    "opencodex": 0.86,
    "opencode": 0.85,
    "openrouter": 0.82,
    "zai": 0.80,
    "minimax": 0.76,
    "nvidia": 0.70,
    "lmstudio": 0.55,
    "ollama": 0.50,
}
_COST = {
    "claude": 1.0,
    "opencodex": 0.30,
    "opencode": 0.25,
    "openrouter": 0.20,
    "zai": 0.25,
    "minimax": 0.25,
    "nvidia": 0.20,
    "lmstudio": 0.05,
    "ollama": 0.02,
}
_CAPABILITIES = {
    "claude": {"coding", "reliable"},
    "opencodex": {"coding", "fast", "cheap"},
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

    if provider != "opencodex":
        return True
    return os.environ.get("ANTIGRAVITY_OPENCODEX_AUTO", "").strip().lower() in {
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
        health = {entry["provider"]: entry for entry in self.store.status()["providers"]}
        legacy_circuit = proxy_state.get_circuit()
        candidates: list[dict[str, Any]] = []
        for priority, (provider, config) in enumerate(provider_switch.PROVIDERS.items()):
            stored = health.get(provider, {})
            legacy = legacy_circuit.get(provider, {})
            is_open = stored.get("circuit_status") == "OPEN" or bool(legacy.get("open"))
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
                    "priority": max(1, 100 - priority * 8),
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
            self.store.record_decision(
                trace_id=decision.trace_id,
                route=decision.route,
                provider=decision.provider,
                model=decision.model,
                score=decision.score,
                manual=decision.manual,
                detail={"override": True, "reason": decision.reason},
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
        scored = [
            (self._score(candidate, profile.get("weights", {})), candidate)
            for candidate in eligible
        ]
        score, chosen = max(
            scored,
            key=lambda item: (item[0], float(item[1].get("priority", 0))),
        )
        decision = RoutingDecision(
            trace_id=trace_id,
            route=route_key,
            provider=str(chosen["provider"]),
            model=str(chosen["model"]),
            score=score,
            manual=False,
            reason="profile_score",
        )
        self.store.record_decision(
            trace_id=decision.trace_id,
            route=decision.route,
            provider=decision.provider,
            model=decision.model,
            score=decision.score,
            manual=decision.manual,
            detail={
                "reason": decision.reason,
                "required_capability": required,
                "eligible": [candidate["provider"] for candidate in eligible],
            },
        )
        return decision

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
