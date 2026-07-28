#!/usr/bin/env python3
"""
Daemon Worker — proceso separado que carga core.agent_daemon sin bloquear el gateway.

Ejecuta un servidor HTTP en :4748 que expone un endpoint RPC genérico.
El gateway se comunica con este worker via HTTP en vez de importar
core.agent_daemon directamente (lo cual bloquea el GIL por 3-5s).

Uso:
    python daemon_worker.py                  # Puerto 4748
    python daemon_worker.py --port 4749      # Puerto custom
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Asegurar que core/ sea importable
_agent_dir = str(Path(__file__).resolve().parent.parent)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from aiohttp import web

# Runtime profile — determina daemon_lite y log level
try:
    from gateway_profiles import load_profile
except ImportError:
    try:
        from mcp.gateway_profiles import load_profile
    except ImportError:
        load_profile = None  # type: ignore[assignment]

_WORKER_PROFILE = load_profile() if load_profile is not None else None

logging.basicConfig(
    level=getattr(logging, _WORKER_PROFILE.log_level, logging.INFO)
    if _WORKER_PROFILE
    else logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [daemon-worker] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("daemon-worker")

# ---- Globals ----
_daemon = None
_daemon_ready = False
_init_attempts = 0
_last_init_error: str | None = None
_worker_state = "starting"

WORKER_PORT = 4748
MAX_INIT_ATTEMPTS = 3
RETRY_BASE_SECONDS = 1.5
INIT_TIMEOUT_SECONDS = 8.0

# Mapping: método RPC → subsistema que debe estar cargado.
# Antes de despachar un método, el worker llama ensure_subsystem() si aplica.
# Esto permite que lite=True cargue subsistemas bajo demanda (lazy loading).
METHOD_SUBSYSTEM_MAP: dict[str, str] = {
    # Sprint 6 — Reputation
    "record_reputation_outcome": "agent_reputation",
    "get_agent_trust": "agent_reputation",
    "get_agent_reputation_profile": "agent_reputation",
    "get_reputation_rankings": "agent_reputation",
    "vouch_for_agent": "agent_reputation",
    "get_reputation_stats": "agent_reputation",
    "get_reputation_history": "agent_reputation",
    # Sprint 6 — Topology
    "record_topology_interaction": "adaptive_topology",
    "get_topology_neighbors": "adaptive_topology",
    "recommend_collaborator": "adaptive_topology",
    "get_topology_clusters": "adaptive_topology",
    "get_topology_bottlenecks": "adaptive_topology",
    "get_topology_graph": "adaptive_topology",
    "get_topology_rebalance": "adaptive_topology",
    "get_topology_stats": "adaptive_topology",
    # Sprint 6 — Chronicle
    "chronicle_record": "event_chronicle",
    "chronicle_trace_cause": "event_chronicle",
    "chronicle_trace_effects": "event_chronicle",
    "chronicle_query": "event_chronicle",
    "chronicle_root_cause": "event_chronicle",
    "chronicle_create_snapshot": "event_chronicle",
    "chronicle_get_state_at": "event_chronicle",
    "chronicle_list_snapshots": "event_chronicle",
    "get_chronicle_stats": "event_chronicle",
    # Sprint 7 — Circuit Breaker
    "breaker_can_execute": "circuit_breaker",
    "breaker_record_success": "circuit_breaker",
    "breaker_record_failure": "circuit_breaker",
    "breaker_get_status": "circuit_breaker",
    "breaker_get_all": "circuit_breaker",
    "breaker_get_open": "circuit_breaker",
    "breaker_force_reset": "circuit_breaker",
    "breaker_configure": "circuit_breaker",
    "breaker_get_fallback": "circuit_breaker",
    "breaker_health": "circuit_breaker",
    "get_breaker_stats": "circuit_breaker",
    # Sprint 7 — Predictive Prefetch
    "prefetch_record": "predictive_prefetch",
    "prefetch_predict": "predictive_prefetch",
    "prefetch_warmup": "predictive_prefetch",
    "prefetch_sequences": "predictive_prefetch",
    "prefetch_matrix": "predictive_prefetch",
    "prefetch_accuracy": "predictive_prefetch",
    "get_prefetch_stats": "predictive_prefetch",
    # Sprint 7 — Contracts
    "contract_create": "contract_manager",
    "contract_record_execution": "contract_manager",
    "contract_check_compliance": "contract_manager",
    "contract_check_all": "contract_manager",
    "contract_get": "contract_manager",
    "contract_list": "contract_manager",
    "contract_auto_generate": "contract_manager",
    "contract_get_violations": "contract_manager",
    "contract_non_compliant": "contract_manager",
    "get_contract_stats": "contract_manager",
    # Sprint 8 — Genome
    "genome_register": "genome_manager",
    "genome_evaluate": "genome_manager",
    "genome_evolve": "genome_manager",
    "genome_get": "genome_manager",
    "genome_get_all": "genome_manager",
    "genome_optimal_config": "genome_manager",
    "genome_ranking": "genome_manager",
    "genome_distribution": "genome_manager",
    "get_genome_stats": "genome_manager",
    # Sprint 8 — Knowledge Distillation
    "distill_knowledge": "knowledge_distiller",
    "transfer_knowledge": "knowledge_distiller",
    "get_knowledge": "knowledge_distiller",
    "find_experts": "knowledge_distiller",
    "get_distillation_stats": "knowledge_distiller",
    # Sprint 8 — Adversarial Arena
    "arena_create_challenge": "adversarial_arena",
    "arena_submit_response": "adversarial_arena",
    "arena_get_rankings": "adversarial_arena",
    "arena_get_profile": "adversarial_arena",
    "arena_get_matchups": "adversarial_arena",
    "arena_battle_history": "adversarial_arena",
    "arena_pending": "adversarial_arena",
    "get_arena_stats": "adversarial_arena",
    # Sprint 9A — WebSocket Bridge
    "ws_broadcast": "ws_bridge",
    "ws_connect": "ws_bridge",
    "ws_subscribe": "ws_bridge",
    "ws_get_clients": "ws_bridge",
    "get_ws_stats": "ws_bridge",
    # Sprint 9A — Dashboard Feed
    "dashboard_snapshot": "dashboard_feed",
    "dashboard_timeline": "dashboard_feed",
    "dashboard_add_entry": "dashboard_feed",
    "get_dashboard_stats": "dashboard_feed",
    # Sprint 9A — Alert Engine
    "alert_fire": "alert_engine",
    "alert_resolve": "alert_engine",
    "alert_get_active": "alert_engine",
    "alert_acknowledge": "alert_engine",
    "get_alert_stats": "alert_engine",
    # Sprint 9B — Federation
    "federation_register_local": "agent_federation",
    "federation_register_peer": "agent_federation",
    "federation_delegate": "agent_federation",
    "federation_get_peers": "agent_federation",
    "get_federation_stats": "agent_federation",
    # Sprint 9B — Marketplace
    "marketplace_publish": "capability_marketplace",
    "marketplace_search": "capability_marketplace",
    "marketplace_acquire": "capability_marketplace",
    "marketplace_trending": "capability_marketplace",
    "get_marketplace_stats": "capability_marketplace",
    # Sprint 9B — Trust Network
    "trust_set": "trust_network",
    "trust_calculate": "trust_network",
    "trust_is_trusted": "trust_network",
    "trust_get_graph": "trust_network",
    "get_trust_stats": "trust_network",
    # Sprint 9C — Metacognition
    "meta_record": "metacognition",
    "meta_diagnose": "metacognition",
    "meta_recommendations": "metacognition",
    "get_metacognition_stats": "metacognition",
    # Sprint 9C — Goal Autonomy
    "goal_create": "goal_autonomy",
    "goal_get_active": "goal_autonomy",
    "goal_update_progress": "goal_autonomy",
    "goal_complete": "goal_autonomy",
    "get_goal_stats": "goal_autonomy",
    # Sprint 9C — Emergent Behavior
    "emergent_observe": "emergent_behavior",
    "emergent_detect": "emergent_behavior",
    "emergent_get_patterns": "emergent_behavior",
    "get_emergent_stats": "emergent_behavior",
}


def _init_daemon_sync() -> None:
    """Inicializa el daemon de forma síncrona (se ejecuta en thread).

    El flag ``daemon_lite`` del perfil activo determina si arranca en modo
    lite (~2s, subsistemas lazy) o full (~30s, todos los subsistemas).
    """
    global _daemon, _daemon_ready, _last_init_error
    use_lite = _WORKER_PROFILE.daemon_lite if _WORKER_PROFILE else True
    try:
        import asyncio as _aio
        from core.agent_daemon import get_daemon

        loop = _aio.new_event_loop()
        _daemon = loop.run_until_complete(get_daemon(lite=use_lite))
        loop.close()
        _daemon_ready = _daemon is not None
        _last_init_error = None
        mode_label = "lite" if use_lite else "full"
        log.info(
            "Daemon inicializado (%s mode, profile=%s)",
            mode_label,
            _WORKER_PROFILE.name if _WORKER_PROFILE else "default",
        )
    except Exception as e:
        log.error("Error inicializando daemon: %s", e)
        _last_init_error = f"{type(e).__name__}: {e}"
        _daemon_ready = False


async def _init_daemon() -> None:
    """Carga el daemon en un thread para no bloquear el HTTP server."""
    global _daemon_ready, _last_init_error

    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, _init_daemon_sync),
            timeout=INIT_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        _daemon_ready = False
        _last_init_error = f"TimeoutError: init excedió {INIT_TIMEOUT_SECONDS:.0f}s"
        log.warning("Inicialización de daemon superó timeout de %.1fs", INIT_TIMEOUT_SECONDS)


async def handle_health(_request: web.Request) -> web.Response:
    """GET /health — Estado del worker."""
    ready = _daemon_ready or _daemon is not None
    return web.json_response(
        {
            "ok": ready,
            "state": "ready" if ready else _worker_state,
            "init_attempts": _init_attempts,
            "max_attempts": MAX_INIT_ATTEMPTS,
            "last_error": _last_init_error,
            "service": "daemon-worker",
            "port": WORKER_PORT,
            "profile": _WORKER_PROFILE.name if _WORKER_PROFILE else "default",
        }
    )


async def _ensure_required_subsystem(method_name: str) -> None:
    """Lazy-load del subsistema requerido por `method_name`, si lo hay.

    Consulta `METHOD_SUBSYSTEM_MAP` y, si el metodo necesita un subsistema,
    intenta inicializarlo. Los errores se loguean pero no se propagan: el
    despacho del metodo sigue su curso aunque el lazy-load falle.

    Args:
        method_name: Nombre del metodo del daemon a despachar.
    """
    required_subsystem = METHOD_SUBSYSTEM_MAP.get(method_name)
    if not required_subsystem:
        return
    try:
        await _daemon.ensure_subsystem(required_subsystem)
    except Exception as e:
        log.warning("ensure_subsystem(%s) falló para %s: %s", required_subsystem, method_name, e)


async def _invoke_daemon_method(method_name: str, args: list, kwargs: dict) -> web.Response:
    """Resuelve y ejecuta un metodo del daemon, serializando el resultado.

    Si el metodo no existe devuelve 404. Si la ejecucion lanza, devuelve 500.
    El resultado se serializa a JSON; si no es serializable se convierte a str.

    Args:
        method_name: Nombre del metodo a invocar sobre el daemon.
        args: Argumentos posicionales.
        kwargs: Argumentos por nombre.

    Returns:
        Respuesta HTTP con `{"ok": True, "result": ...}` o error.
    """
    method = getattr(_daemon, method_name, None)
    if method is None:
        return web.json_response(
            {"ok": False, "error": f"Metodo '{method_name}' no encontrado en daemon"},
            status=404,
        )

    try:
        result = method(*args, **kwargs)
        # Si es coroutine, await
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            result = await result

        # Intentar serializar — si falla, convertir a string
        try:
            json.dumps(result)
        except (TypeError, ValueError):
            result = str(result)

        return web.json_response({"ok": True, "result": result})

    except Exception as e:
        log.warning("Error en RPC %s: %s", method_name, e)
        return web.json_response(
            {"ok": False, "error": f"{type(e).__name__}: {e}"},
            status=500,
        )


async def handle_rpc(request: web.Request) -> web.Response:
    """POST /rpc — Ejecutar método del daemon.

    Body: {"method": "get_status", "args": [], "kwargs": {}}
    Response: {"ok": true, "result": {...}} o {"ok": false, "error": "..."}
    """
    if _daemon is None:
        return web.json_response(
            {"ok": False, "error": "Daemon no inicializado"},
            status=503,
        )

    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"ok": False, "error": "Body JSON requerido"},
            status=400,
        )

    method_name = body.get("method", "")
    args = body.get("args", [])
    kwargs = body.get("kwargs", {})

    if not method_name:
        return web.json_response(
            {"ok": False, "error": "Campo 'method' requerido"},
            status=400,
        )

    # Comando especial: lazy-load de subsistemas
    if method_name == "ensure_subsystem" and args:
        try:
            ok = await _daemon.ensure_subsystem(args[0])
            return web.json_response({"ok": True, "result": ok})
        except Exception as e:
            return web.json_response(
                {"ok": False, "error": f"ensure_subsystem error: {e}"},
                status=500,
            )

    # Lazy-load del subsistema requerido antes de despachar el método
    await _ensure_required_subsystem(method_name)

    return await _invoke_daemon_method(method_name, args, kwargs)


async def on_startup(app: web.Application) -> None:
    """Inicializar daemon en background — HTTP server listo primero."""
    asyncio.create_task(_init_daemon_background())


async def _init_daemon_background() -> None:
    """Carga daemon después de que el HTTP server esté escuchando.

    Si el perfil define ``auto_load_subsystems``, los carga eagerly
    después de la inicialización del daemon.
    """
    global _init_attempts, _worker_state

    await asyncio.sleep(0.1)  # Dejar que el server haga bind

    for attempt in range(1, MAX_INIT_ATTEMPTS + 1):
        _init_attempts = attempt
        _worker_state = "initializing"
        await _init_daemon()

        if _daemon_ready or _daemon is not None:
            _worker_state = "ready"
            break

        if attempt < MAX_INIT_ATTEMPTS:
            backoff = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            log.warning(
                "Init daemon intento %d/%d falló; retry en %.1fs",
                attempt,
                MAX_INIT_ATTEMPTS,
                backoff,
            )
            _worker_state = "retrying"
            await asyncio.sleep(backoff)

    if not (_daemon_ready or _daemon is not None):
        _worker_state = "error"

    # Auto-load de subsistemas según perfil
    if (_daemon_ready or _daemon is not None) and _WORKER_PROFILE:
        subs = _WORKER_PROFILE.auto_load_subsystems
        if subs and subs != []:
            await _auto_load_subsystems(subs)


async def _auto_load_subsystems(subsystems: list[str]) -> None:
    """Carga subsistemas eagerly después del init del daemon.

    Args:
        subsystems: Lista de nombres. ``["all"]`` carga todos los conocidos.
    """
    if _daemon is None:
        return

    if subsystems == ["all"]:
        # Extraer todos los subsistemas únicos del METHOD_SUBSYSTEM_MAP
        targets = sorted(set(METHOD_SUBSYSTEM_MAP.values()))
    else:
        targets = subsystems

    log.info("Auto-loading %d subsistemas: %s", len(targets), ", ".join(targets))
    for name in targets:
        try:
            await _daemon.ensure_subsystem(name)
            log.debug("Subsistema '%s' cargado", name)
        except Exception as e:
            log.warning("Error cargando subsistema '%s': %s", name, e)


def main() -> None:
    """Entry point."""
    global WORKER_PORT

    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            WORKER_PORT = int(args[i + 1])
            i += 2
        else:
            i += 1

    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_post("/rpc", handle_rpc)
    app.on_startup.append(on_startup)

    log.info("Daemon Worker iniciando en :%d", WORKER_PORT)
    web.run_app(
        app,
        host="127.0.0.1",
        port=WORKER_PORT,
        print=None,
        keepalive_timeout=3,
    )


if __name__ == "__main__":
    main()
