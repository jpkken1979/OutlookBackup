"""Gateway mixin — endpoints de conmutacion de provider IA.

Expone `core.provider_switch` via HTTP para disparo remoto (otra PC, bot Telegram,
curl). Reusa exactamente la misma logica que el CLI y el MCP tool.

    GET  /v1/provider/status        — provider activo + lista de disponibles
    POST /v1/provider/switch        — body {provider, model?}
    POST /v1/provider/disable       — hot-swap a Claude conservando el proxy
    POST /v1/provider/native        — Claude OAuth directo, sin proxy
    POST /v1/proxy/circuit/reset    — body {provider?}: cerrar circuit breaker
    GET  /v1/proxy/quota            — cuota restante por provider (auto-rotate)

Seguridad: estos paths NO estan en `public_paths` del gateway, asi que el
middleware de auth exige `X-API-Key`. Critico, porque mutan ~/.claude/settings.json.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import sys
import time
from pathlib import Path

from aiohttp import web

from ._response import ok, err, ErrorCode  # noqa: E402

# core vive en .agent/core; este archivo en .agent/mcp/gateway/ -> parents[2] = .agent
_agent_dir = Path(__file__).resolve().parents[2]
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

from core import (  # noqa: E402
    model_resolver,
    models_dev,
    provider_catalog,
    provider_switch,
    turn_checkpoint,
)
from core.routing_authority import get_routing_authority  # noqa: E402
from core.routing_fault_lab import run_routing_fault_lab  # noqa: E402

logger = logging.getLogger(__name__)

# Providers cuya lista de modelos y protocolo ya se validaron contra el adaptador
# actual de Nexus. Los demás conservan sus modelos compatibles declarados hasta
# que se valide su endpoint uno a uno; así no se exhibe como seleccionable un
# modelo de audio, embedding o Responses en un camino Chat.
_DYNAMIC_FETCH_PROVIDERS: tuple[str, ...] = ("minimax", "zai")

# Catálogos con una fuente oficial/propia. OpenRouter incluye pricing y orden
# newest-first; OpenCode Go se consulta contra la URL del plan configurado.
# OpenCodex lista sólo los modelos que su bridge local ya puede servir, por lo
# que se consulta sin API key y sin exponer credenciales de Codex.
_OFFICIAL_CATALOG_PROVIDERS: tuple[str, ...] = ("openrouter", "opencode", "opencodex")


def _model_fetch_disabled() -> bool:
    """True cuando el usuario pidió no consultar catálogos remotos."""
    return os.environ.get("ANTIGRAVITY_DISABLE_MODEL_FETCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _overview_async() -> dict:
    """Corre `get_overview()` fuera del event loop.

    El overview sondea los endpoints de loopback con sockets sincronicos (150 ms
    de timeout cada uno). Llamarlo directo desde un handler async congelaba el
    gateway entero —y con el, todos los clientes MCP— mientras la UI de Nexus
    polleaba cada 15-20s.

    Returns:
        El dict del overview, identico al del CLI.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, provider_switch.get_overview)


def _delegation_aware_overview(overview: dict, manual_override: str | None) -> dict:
    """Overlay the gateway's manual delegation route onto a native Claude overview.

    ``provider_switch.get_overview`` intentionally reports the effective Claude
    settings. Nexus delegation is separate: it changes the gateway routing
    authority without injecting ``ANTHROPIC_BASE_URL``. The HTTP status needs to
    expose both facts so a refresh does not make the delegated provider disappear.
    """
    if overview.get("proxy_connected") or not manual_override:
        return overview

    provider_id, separator, model = manual_override.partition("/")
    provider_id = provider_id.strip().lower()
    model = model.strip()
    providers = overview.get("providers")
    if not separator or not provider_id or not model or not isinstance(providers, list):
        logger.warning("Ignoring malformed routing manual override in provider status")
        return overview

    selected = next(
        (
            provider
            for provider in providers
            if isinstance(provider, dict)
            and str(provider.get("id") or "").lower() == provider_id
            and bool(provider.get("routable", True))
        ),
        None,
    )
    if selected is None:
        logger.warning("Ignoring unknown routing manual override provider: %s", provider_id)
        return overview

    result = dict(overview)
    result["providers"] = [
        {
            **provider,
            "active": str(provider.get("id") or "").lower() == provider_id,
            "active_model": (
                model if str(provider.get("id") or "").lower() == provider_id else None
            ),
        }
        if isinstance(provider, dict)
        else provider
        for provider in providers
    ]
    provider_name = str(selected.get("name") or provider_id)
    result.update(
        {
            "active_provider": provider_id,
            "active_provider_name": provider_name,
            "active_model": model,
            "has_api_key": bool(selected.get("has_api_key")),
            "proxy_scope": "delegation",
            "needs_restart": False,
            "diagnosis": (
                f"Delegacion Nexus activa: {provider_name} ({model}). "
                "Claude permanece nativo y Remote Control no se modifica."
            ),
        }
    )
    return result


class _ProviderMixin:
    """Endpoints HTTP para conmutar el backend IA de Claude Code."""

    async def handle_provider_status(self, _request: web.Request) -> web.Response:
        """GET /v1/provider/status — estado unificado de providers."""
        try:
            data = await _overview_async()
            try:
                manual_override = get_routing_authority().store.manual_override()
            except Exception as exc:  # noqa: BLE001 — routing is auxiliary to status
                logger.warning("Could not read routing manual override: %s", exc)
                manual_override = None
            data = _delegation_aware_overview(data, manual_override)
            return web.json_response(ok(data=data, source="provider"))
        except Exception as exc:  # noqa: BLE001 — boundary HTTP
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )

    async def handle_routing_status(self, _request: web.Request) -> web.Response:
        """GET /v1/routing/status — canonical routing authority snapshot."""
        try:
            authority = get_routing_authority()
            data = authority.store.status()
            data["provider_overview"] = _delegation_aware_overview(
                await _overview_async(), data.get("manual_override")
            )
            return web.json_response(ok(data=data, source="routing"))
        except Exception as exc:  # noqa: BLE001 — HTTP boundary
            logger.exception("routing status failed")
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="routing"),
                status=500,
            )

    async def handle_routing_profiles(self, request: web.Request) -> web.Response:
        """GET/POST /v1/routing/profiles — list or upsert a routing profile."""
        authority = get_routing_authority()
        if request.method == "GET":
            return web.json_response(
                ok(data={"profiles": authority.store.list_profiles()}, source="routing")
            )
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
            profile_id = str(body.get("profile_id") or "")
            payload = body.get("profile")
            if not isinstance(payload, dict):
                raise ValueError("profile must be an object")
            profile = authority.store.put_profile(profile_id, payload)
            return web.json_response(ok(data=profile, source="routing"))
        except (ValueError, TypeError, web.HTTPBadRequest) as exc:
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, str(exc), source="routing"),
                status=400,
            )

    async def handle_routing_active_profile(self, request: web.Request) -> web.Response:
        """GET/PUT /v1/routing/active-profile — hot profile selection."""
        authority = get_routing_authority()
        if request.method == "GET":
            return web.json_response(
                ok(
                    data={"profile_id": authority.store.active_profile()},
                    source="routing",
                )
            )
        try:
            body = await request.json()
            profile_id = authority.store.set_active_profile(
                str(body.get("profile_id") if isinstance(body, dict) else "")
            )
            return web.json_response(ok(data={"profile_id": profile_id}, source="routing"))
        except (ValueError, TypeError, web.HTTPBadRequest) as exc:
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, str(exc), source="routing"),
                status=400,
            )

    async def handle_routing_probe(self, request: web.Request) -> web.Response:
        """POST /v1/routing/probe — probe one account/provider without switching."""
        authority = get_routing_authority()
        body: dict[str, object] = {}
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
            provider = str(body.get("provider") or "").strip().lower()
            account_id = str(body.get("account_id") or "").strip() or None
            started = time.monotonic()
            result = await asyncio.get_running_loop().run_in_executor(
                None,
                functools.partial(provider_switch.discover_models, provider),
            )
            latency_ms = round((time.monotonic() - started) * 1000)
            authority.store.record_outcome(
                provider,
                account_id=account_id,
                status_code=200,
                latency_ms=latency_ms,
            )
            return web.json_response(
                ok(
                    data={"provider": provider, "latency_ms": latency_ms, **result},
                    source="routing",
                )
            )
        except provider_switch.ProviderError as exc:
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, str(exc), source="routing"),
                status=400,
            )
        except (ValueError, TypeError, web.HTTPBadRequest) as exc:
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, str(exc), source="routing"),
                status=400,
            )
        except Exception as exc:  # noqa: BLE001 — probe boundary
            provider = (
                str(body.get("provider") or "unknown") if isinstance(body, dict) else "unknown"
            )
            try:
                authority.store.record_outcome(
                    provider,
                    account_id=(
                        str(body.get("account_id") or "").strip() or None
                        if isinstance(body, dict)
                        else None
                    ),
                    error_kind="transport",
                )
            except ValueError:
                pass
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="routing"),
                status=502,
            )

    async def handle_routing_events(self, request: web.Request) -> web.Response:
        """GET /v1/routing/events — recent redacted decisions and outcomes."""
        try:
            limit = int(request.query.get("limit", "100"))
        except ValueError:
            limit = 100
        events = get_routing_authority().store.list_events(limit)
        return web.json_response(ok(data={"events": events}, source="routing"))

    async def handle_routing_turns(self, request: web.Request) -> web.Response:
        """GET /v1/routing/turns — redacted checkpoint and continuity history."""

        try:
            limit = int(request.query.get("limit", "100"))
        except ValueError:
            limit = 100
        turns = turn_checkpoint.get_turn_checkpoint_store().recent(limit)
        return web.json_response(ok(data={"turns": turns}, source="routing"))

    async def handle_routing_fault_lab(self, _request: web.Request) -> web.Response:
        """GET /v1/routing/fault-lab — deterministic dry-run resilience drills."""

        report = run_routing_fault_lab(get_routing_authority())
        return web.json_response(ok(data=report.model_dump(mode="json"), source="routing"))

    async def handle_routing_models(self, request: web.Request) -> web.Response:
        """GET /v1/routing/models/{provider} — canonical model catalog."""
        provider = request.match_info["provider"].strip().lower()
        try:
            models = provider_switch.list_models(provider, allow_fetch=False)
            return web.json_response(
                ok(data={"provider": provider, "models": models}, source="routing")
            )
        except provider_switch.ProviderError as exc:
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, str(exc), source="routing"),
                status=400,
            )

    async def handle_provider_switch(self, request: web.Request) -> web.Response:
        """POST /v1/provider/switch — body {provider, model?}."""
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, f"json invalido: {exc}", source="provider"),
                status=400,
            )
        if not isinstance(body, dict):
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, "body debe ser objeto", source="provider"),
                status=400,
            )
        provider = str(body.get("provider") or body.get("provider_id") or "").strip()
        if not provider:
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, "provider es requerido", source="provider"),
                status=400,
            )
        model = body.get("model")
        scope = body.get("scope") or "global"
        try:
            data = provider_switch.switch_provider(provider, model, scope=scope)
            get_routing_authority().store.set_manual_override(
                str(data.get("active_provider") or provider).lower(),
                str(data.get("active_model") or model or ""),
            )
        except provider_switch.ProviderError as exc:
            return web.json_response(
                err(ErrorCode.PROVIDER_SWITCH_FAILED, str(exc), source="provider"),
                status=400,
            )
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )
        return web.json_response(ok(data=data, source="provider"))

    async def handle_provider_disable(self, request: web.Request) -> web.Response:
        """POST /v1/provider/disable — volver a Claude (o quitar override de proyecto)."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 — body opcional
            body = {}
        scope = (body.get("scope") if isinstance(body, dict) else None) or "global"
        try:
            data = provider_switch.disable_provider(scope=scope)
            get_routing_authority().store.clear_manual_override()
            return web.json_response(ok(data=data, source="provider"))
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )

    async def handle_provider_native(self, _request: web.Request) -> web.Response:
        """POST /v1/provider/native — Claude OAuth directo y Remote Control.

        Limpia los overrides de provider en los scopes global y de proyecto. No
        expone ni modifica la credencial OAuth guardada por Claude Code.
        """
        try:
            data = provider_switch.activate_claude_native()
            get_routing_authority().store.clear_manual_override()
            return web.json_response(ok(data=data, source="provider"))
        except Exception as exc:  # noqa: BLE001 — boundary HTTP
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )

    async def handle_provider_reset(self, _request: web.Request) -> web.Response:
        """POST /v1/provider/reset — restaura el modelo proxy-always.

        En el modelo proxy-always (revisado 2026-07-05) este es el unico "rollback"
        util: limpia tokens de provider directos del env, ASEGURA la base URL al
        proxy y deja ``active_provider=claude`` via passthrough OAuth. Util cuando
        el settings.json quedo inconsistente (edicion manual que metio variables
        de provider directos, etc.).

        Reemplaza al antiguo ``disconnect_proxy`` del modelo bypass (que SI quitaba
        la base URL). En proxy-always el proxy es permanente.
        """
        try:
            data = provider_switch.reset_to_proxy_always()
            get_routing_authority().store.clear_manual_override()
            return web.json_response(ok(data=data, source="provider"))
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )

    async def handle_provider_circuit_reset(self, request: web.Request) -> web.Response:
        """POST /v1/proxy/circuit/reset — body {provider}. Cierra el circuito.

        Resetea el streak de fallos del circuit breaker para ``provider`` (lo
        pone en 0, cierra el circuito y persiste ``circuit_breaker.json``). Si no
        se pasa ``provider`` se resetea el breaker completo. Usado por el botón
        "resetear" del badge inestable en Nexus.
        """
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 — body opcional
            body = {}
        provider = ""
        if isinstance(body, dict):
            provider = str(body.get("provider") or body.get("provider_id") or "").strip()
        try:
            from . import _mixin_proxy as _proxy

            if provider:
                # Reusa la ruta del camino feliz: cerrar circuito = respuesta sana.
                _proxy._record_provider_success(provider)
            else:
                _proxy.reset_circuit_state()
            snapshot = _proxy.get_circuit_snapshot()
            return web.json_response(
                ok(data={"provider": provider, "circuit": snapshot}, source="provider")
            )
        except Exception as exc:  # noqa: BLE001 — boundary HTTP
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )

    async def handle_proxy_quota(self, _request: web.Request) -> web.Response:
        """GET /v1/proxy/quota — cuota restante por provider (señal del auto-rotate).

        Devuelve el estado persistido de ``quota_state`` (``{providers: {...}}``), que
        alimentan el usage_poller y la captura passiva de headers. Lo consume la UI de
        Nexus (Fase 2) para mostrar el % restante y por qué el proxy rotó de provider.
        """
        try:
            from core import quota_state

            return web.json_response(ok(data=quota_state.read_quota_state(), source="provider"))
        except Exception as exc:  # noqa: BLE001 — boundary HTTP
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )

    async def handle_provider_hotswap(self, request: web.Request) -> web.Response:
        """POST /v1/provider/hotswap — body {provider, model?}. Cambio en caliente.

        Cambia el backend activo del proxy (lo relee en cada request). No reinicia
        la sesion de Claude Code; aplica en el proximo prompt si CC apunta a /claudeproxy.
        """
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, f"json invalido: {exc}", source="provider"),
                status=400,
            )
        if not isinstance(body, dict):
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, "body debe ser objeto", source="provider"),
                status=400,
            )
        provider = str(body.get("provider") or body.get("provider_id") or "").strip()
        if not provider:
            return web.json_response(
                err(ErrorCode.CONFIG_INVALID, "provider es requerido", source="provider"),
                status=400,
            )
        model = body.get("model")
        try:
            data = provider_switch.set_hotswap(provider, model)
            get_routing_authority().store.set_manual_override(
                str(data.get("active_provider") or provider).lower(),
                str(data.get("active_model") or model or ""),
            )
        except provider_switch.ProviderError as exc:
            return web.json_response(
                err(ErrorCode.PROVIDER_SWITCH_FAILED, str(exc), source="provider"),
                status=400,
            )
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )
        return web.json_response(ok(data=data, source="provider"))

    @staticmethod
    def _resolve_api_key(api_key_env: str) -> str | None:
        """Resuelve la API key de un provider desde el entorno o el .env del repo.

        Busca primero en ``os.environ``; si no esta presente, intenta leerla del
        archivo ``.env`` en la raiz del repo (``ANTIGRAVITY_ROOT`` o inferida desde
        ``provider_switch.default_root``), parseando linea por linea ``KEY=VALUE``.
        Nunca loguea el valor de la key.

        Args:
            api_key_env: Nombre de la env var con la API key ("" si no aplica).

        Returns:
            El valor de la key, o ``None`` si no esta seteada ni en env ni en .env.
        """
        if not api_key_env:
            return None
        value = os.environ.get(api_key_env)
        if value and value.strip():
            return value.strip()

        root = os.environ.get("ANTIGRAVITY_ROOT")
        env_path = Path(root) / ".env" if root else provider_switch.default_root() / ".env"
        try:
            content = env_path.read_text(encoding="utf-8")
        except OSError:
            return None
        prefix = f"{api_key_env}="
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or not line.startswith(prefix):
                continue
            parsed = line[len(prefix) :].strip().strip('"').strip("'")
            return parsed or None
        return None

    async def _refresh_one_provider(
        self, pid: str, cfg: provider_catalog.ProviderConfig
    ) -> tuple[str, str | None]:
        """Refresca el cache de modelos de UN provider en un thread (I/O no bloqueante).

        ``model_resolver.resolve_models`` hace I/O de red SINCRONO (urllib bloqueante);
        ejecutarlo directo en el handler async congelaria todo el event loop del gateway.
        Por eso se descarga a un executor de thread via ``run_in_executor``. Tolerante:
        cualquier excepcion del fetch se traduce a un skip (``None``), sin propagarse.

        Args:
            pid: Id del provider (p. ej. ``"minimax"`` o ``"zai"``).
            cfg: Config del provider tomada del catalogo (``provider_catalog``).

        Returns:
            Tupla ``(pid, best_model)`` si el fetch tuvo exito, o ``(pid, None)`` si se
            debe omitir (provider sin key o fetch fallido).
        """
        api_key = self._resolve_api_key(cfg.api_key_env)
        if not api_key:
            logger.info("refresh-models: %s sin API key, omitido", pid)
            return pid, None
        loop = asyncio.get_running_loop()
        try:
            models = await loop.run_in_executor(
                None,
                functools.partial(
                    model_resolver.resolve_models,
                    pid,
                    known_models=cfg.models,
                    base_url=cfg.base_url,
                    api_key=api_key,
                    family=cfg.family,
                    allow_fetch=True,
                    force_refresh=True,
                ),
            )
        except Exception as exc:  # noqa: BLE001 — un provider no debe tumbar al resto
            logger.warning("refresh-models: fetch de %s fallo: %s", pid, exc)
            return pid, None
        best = models[0] if models else cfg.default_model
        logger.info("refresh-models: %s regenerado (%d modelos)", pid, len(models))
        return pid, best

    async def _refresh_one_provider_via_official_catalog(
        self, pid: str, cfg: provider_catalog.ProviderConfig
    ) -> tuple[str, str | None]:
        """Refresca catálogos propios de OpenRouter, OpenCode Go y OpenCodex.

        OpenRouter entrega precio y orden newest-first en su API de modelos. Para
        OpenCode Go se consulta exactamente ``cfg.base_url`` y se cruza con el
        manifiesto Chat verificado. OpenCodex se consulta únicamente en loopback;
        sus IDs ya son la lista servible por el bridge y no requiere API key.
        Los resultados se guardan sin modificar el modelo activo.
        """
        api_key = self._resolve_api_key(cfg.api_key_env) or ""
        loop = asyncio.get_running_loop()
        try:
            if pid == "openrouter":
                entries = await loop.run_in_executor(
                    None,
                    functools.partial(model_resolver.fetch_openrouter_models, api_key),
                )
            else:
                remote = await loop.run_in_executor(
                    None,
                    functools.partial(
                        model_resolver.fetch_remote_models,
                        pid,
                        cfg.base_url,
                        api_key,
                    ),
                )
                advertised_entries = [
                    (model_id, models_dev.model_is_free(model_id)) for model_id, _created in remote
                ]
                if pid == "opencode":
                    allowed_models = set(cfg.models)
                    entries = [entry for entry in advertised_entries if entry[0] in allowed_models]
                    ignored = len(advertised_entries) - len(entries)
                    if ignored:
                        logger.info(
                            "refresh-models: %s omitió %d modelo(s) sin ruta Chat verificada",
                            pid,
                            ignored,
                        )
                else:
                    # OpenCodex expone desde su propio bridge sólo los IDs que
                    # acepta su endpoint Chat. No usa API key: la sesión OAuth
                    # permanece dentro de OpenCodex.
                    entries = advertised_entries
        except Exception as exc:  # noqa: BLE001 — un provider no debe tumbar al resto
            logger.warning("refresh-models: catálogo oficial de %s falló: %s", pid, exc)
            return pid, None
        if not entries:
            logger.info("refresh-models: %s no devolvió modelos oficiales, omitido", pid)
            return pid, None
        ids = model_resolver.write_provider_models_cache(pid, entries)
        best = ids[0] if ids else cfg.default_model
        logger.info(
            "refresh-models: %s actualizado desde catálogo oficial (%d modelos)", pid, len(ids)
        )
        return pid, best

    async def handle_provider_refresh_models(self, _request: web.Request) -> web.Response:
        """POST /v1/provider/refresh-models — regenera el cache de modelos via fetch remoto.

        Para cada provider proxy-ruteable con fetch dinámico ya validado
        (``minimax``, ``zai``) lee su config y fuerza un fetch remoto. Además refresca
        OpenRouter, OpenCode Go y OpenCodex: el bridge se consulta sólo en loopback,
        sin API key, y devuelve sus propios modelos Chat disponibles. Todo se persiste en
        ``~/.antigravity/providers/models_cache.json`` sin tocar el modelo activo.
        Es tolerante: un provider sin key cuando la necesita se omite (``skipped``) y
        un fallo de fetch no aborta el resto.

        Cada consulta corre en un thread (``run_in_executor``) para no bloquear el
        event loop del gateway, pero se espera de forma serial: todas actualizan el
        mismo cache y así no pueden perderse entradas por una carrera read-modify-write.

        Returns:
            ``web.Response`` con envelope ``ok``: ``data.refreshed`` mapea ``{provider: best}``
            por cada provider con cache regenerado y ``data.skipped`` lista los provider ids
            sin API key. Solo devuelve 500 ante un error catastrofico (no por provider).
        """
        try:
            providers = provider_catalog.build_providers()
            refreshed: dict[str, str] = {}
            skipped: list[str] = []

            provider_ids = (*_DYNAMIC_FETCH_PROVIDERS, *_OFFICIAL_CATALOG_PROVIDERS)
            if _model_fetch_disabled():
                logger.info("refresh-models omitido por ANTIGRAVITY_DISABLE_MODEL_FETCH")
                return web.json_response(
                    ok(
                        data={"refreshed": refreshed, "skipped": list(dict.fromkeys(provider_ids))},
                        source="provider",
                    )
                )

            for pid in _DYNAMIC_FETCH_PROVIDERS:
                cfg = providers.get(pid)
                if cfg is None:
                    skipped.append(pid)
                    continue
                result = await self._refresh_one_provider(pid, cfg)
                provider_id, best = result
                if best is None:
                    skipped.append(provider_id)
                else:
                    refreshed[provider_id] = best

            for pid in _OFFICIAL_CATALOG_PROVIDERS:
                cfg = providers.get(pid)
                if cfg is None:
                    skipped.append(pid)
                    continue
                provider_id, best = await self._refresh_one_provider_via_official_catalog(pid, cfg)
                if best is None:
                    skipped.append(provider_id)
                else:
                    refreshed[provider_id] = best

            return web.json_response(
                ok(data={"refreshed": refreshed, "skipped": skipped}, source="provider")
            )
        except Exception as exc:  # noqa: BLE001 — boundary HTTP, solo error catastrofico
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )
