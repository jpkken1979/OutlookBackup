"""Gateway mixin — endpoints de conmutacion de provider IA.

Expone `core.provider_switch` via HTTP para disparo remoto (otra PC, bot Telegram,
curl). Reusa exactamente la misma logica que el CLI y el MCP tool.

    GET  /v1/provider/status        — provider activo + lista de disponibles
    POST /v1/provider/switch        — body {provider, model?}
    POST /v1/provider/disable       — volver a Claude nativo
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

from core import model_resolver, models_dev, provider_catalog, provider_switch  # noqa: E402
from core.routing_authority import get_routing_authority  # noqa: E402

logger = logging.getLogger(__name__)

# Providers proxy-ruteables con fetch dinamico de modelos via /v1/models. El refresh
# de cache solo tiene sentido para estos (los locales OpenAI no se cachean asi).
_DYNAMIC_FETCH_PROVIDERS: tuple[str, ...] = ("minimax", "zai")

# Providers OpenAI remotos SIN endpoint /v1/models propio (OpenCode no lo expone; OpenRouter
# sí pero unificamos): su lista de modelos + pricing se descubre vía models.dev.
_MODELS_DEV_PROVIDERS: tuple[str, ...] = ("openrouter", "opencode")


class _ProviderMixin:
    """Endpoints HTTP para conmutar el backend IA de Claude Code."""

    async def handle_provider_status(self, _request: web.Request) -> web.Response:
        """GET /v1/provider/status — estado unificado de providers."""
        try:
            data = provider_switch.get_overview()
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
            data["provider_overview"] = provider_switch.get_overview()
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
            return web.json_response(
                ok(data={"profile_id": profile_id}, source="routing")
            )
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
            provider = str(body.get("provider") or "unknown") if isinstance(body, dict) else "unknown"
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

    async def _refresh_one_provider(self, pid: str, cfg: object) -> tuple[str, str | None]:
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
                ),
            )
        except Exception as exc:  # noqa: BLE001 — un provider no debe tumbar al resto
            logger.warning("refresh-models: fetch de %s fallo: %s", pid, exc)
            return pid, None
        best = models[0] if models else cfg.default_model
        logger.info("refresh-models: %s regenerado (%d modelos)", pid, len(models))
        return pid, best

    async def _refresh_one_provider_via_models_dev(
        self, pid: str, cfg: object
    ) -> tuple[str, str | None]:
        """Refresca el cache de UN provider OpenAI remoto vía models.dev.

        OpenRouter/OpenCode no se descubren con ``/v1/models`` (OpenCode no lo expone).
        Su lista + pricing viene de ``models.dev`` (``models_dev.list_provider_models``), que
        se persiste enriquecida (``[{id,free}]``) con ``model_resolver.write_provider_models_cache``.
        El fetch de models.dev es I/O de red síncrono → va a un thread como ``_refresh_one_provider``.
        Tolerante: cualquier fallo se traduce a un skip (``None``).

        Args:
            pid: Id del provider (``openrouter`` / ``opencode``).
            cfg: Config del provider del catálogo (para el ``default_model`` de fallback).

        Returns:
            ``(pid, best_model)`` si descubrió modelos; ``(pid, None)`` si no hubo ninguno.
        """
        loop = asyncio.get_running_loop()
        try:
            entries = await loop.run_in_executor(
                None, functools.partial(models_dev.list_provider_models, pid)
            )
        except Exception as exc:  # noqa: BLE001 — un provider no debe tumbar al resto
            logger.warning("refresh-models: models.dev de %s falló: %s", pid, exc)
            return pid, None
        if not entries:
            logger.info("refresh-models: %s sin modelos en models.dev, omitido", pid)
            return pid, None
        ids = model_resolver.write_provider_models_cache(pid, entries)
        best = next((mid for mid, free in entries if free), ids[0] if ids else cfg.default_model)
        logger.info("refresh-models: %s regenerado vía models.dev (%d modelos)", pid, len(ids))
        return pid, best

    async def handle_provider_refresh_models(self, _request: web.Request) -> web.Response:
        """POST /v1/provider/refresh-models — regenera el cache de modelos via fetch remoto.

        Para cada provider proxy-ruteable con fetch dinamico (``minimax``, ``zai``) lee su
        config del catalogo, resuelve su API key (env o .env del repo) y fuerza un fetch
        remoto via ``model_resolver.resolve_models(..., allow_fetch=True)``, que reescribe
        ``~/.antigravity/providers/models_cache.json`` con un timestamp fresco. Tolerante:
        un provider sin key se omite (``skipped``) y un fallo de fetch no aborta el resto.

        El fetch de cada provider corre en un thread (``run_in_executor``) para no bloquear
        el event loop del gateway, y ambos providers se paralelizan con ``asyncio.gather``
        (recorta el peor caso de ~20s secuenciales a ~10s).

        Returns:
            ``web.Response`` con envelope ``ok``: ``data.refreshed`` mapea ``{provider: best}``
            por cada provider con cache regenerado y ``data.skipped`` lista los provider ids
            sin API key. Solo devuelve 500 ante un error catastrofico (no por provider).
        """
        try:
            providers = provider_catalog.build_providers()
            refreshed: dict[str, str] = {}
            skipped: list[str] = []

            tasks = []
            for pid in _DYNAMIC_FETCH_PROVIDERS:
                cfg = providers.get(pid)
                if cfg is None:
                    skipped.append(pid)
                    continue
                tasks.append(self._refresh_one_provider(pid, cfg))

            for pid in _MODELS_DEV_PROVIDERS:
                cfg = providers.get(pid)
                if cfg is None:
                    skipped.append(pid)
                    continue
                tasks.append(self._refresh_one_provider_via_models_dev(pid, cfg))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    # Defensa extra: la coroutine ya captura sus errores, pero un fallo
                    # inesperado (p. ej. cancelacion) no debe tumbar al resto.
                    logger.warning("refresh-models: tarea de provider fallo: %s", result)
                    continue
                pid, best = result
                if best is None:
                    skipped.append(pid)
                else:
                    refreshed[pid] = best

            return web.json_response(
                ok(data={"refreshed": refreshed, "skipped": skipped}, source="provider")
            )
        except Exception as exc:  # noqa: BLE001 — boundary HTTP, solo error catastrofico
            return web.json_response(
                err(ErrorCode.PROVIDER_UNAVAILABLE, str(exc), source="provider"),
                status=500,
            )
