"""Provider switch core — conmuta el backend de Claude Code entre providers.

Porta la logica de `nexus-app/src-tauri/src/commands/provider_manager.rs` (Tauri) a
Python como **fuente unica reutilizable** para tres canales:

- CLI (`python .agent/core/provider_switch.py switch minimax`)
- MCP tool (`.agent/mcp/provider-server.py`)
- Endpoint del gateway (`POST :4747/v1/provider/switch`)

Modelo PROXY-ALWAYS (revisado 2026-07-05): todos los providers —incluido Claude—
pasan por el proxy local (http://127.0.0.1:4747/claudeproxy). El proxy hace
passthrough crudo a https://api.anthropic.com cuando el backend activo es
Claude, preservando el header `Authorization`/`x-api-key` que Claude Code
inyecta via OAuth. ANTHROPIC_BASE_URL permanece SIEMPRE apuntando al proxy;
cruzar claude<->alternativo es un hot-swap en caliente (proxy_state.json se
relee por request) y NUNCA requiere reiniciar Claude Code. Este modelo replica
el comportamiento de OpenCode/Roo Code/Cursor: el cliente nunca pierde contexto
al cambiar de backend.

`disconnect_proxy(root)` queda como camino de soporte explicito para salir del
ecosistema (restaura desde backup, sin proxy). `_activate_claude_direct` se
mantiene como referencia historica/compatibilidad pero no se invoca desde el
camino normal (ver Fase 1.1 del plan).

Variables de entorno relevantes:
    ANTIGRAVITY_ROOT            Raiz del proyecto (para resolver el .env). Default: auto.
    ANTIGRAVITY_CLAUDE_SETTINGS Override del path de settings.json (util para tests).
    ANTIGRAVITY_PROXY_STATE     Override del path del proxy state JSON (util para tests).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import urllib.request
from pathlib import Path

from core.provider_catalog import ProviderConfig, build_providers

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Reexportado por compatibilidad hacia atras: la dataclass vive ahora en provider_catalog
# (para romper el import circular provider_switch<->provider_catalog), pero los consumidores
# historicos siguen importandola desde aca.
__all__ = ["ProviderConfig"]

# URL canonica del proxy local — SIEMPRE se usa esta, nunca la del provider directo.
PROXY_BASE_URL = "http://127.0.0.1:4747/claudeproxy"

# Env vars que el switch escribe/limpia en modo directo (deben coincidir con
# provider_manager.rs). En modo proxy-always, el env solo tiene ANTHROPIC_BASE_URL
# apuntando al proxy y API_TIMEOUT_MS; el resto se limpia.
PROVIDER_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "API_TIMEOUT_MS",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
)

# Keys de token de provider que NO deben estar en el env cuando el proxy esta conectado.
# Si estuvieran, romperían el passthrough OAuth de Claude.
_DIRECT_PROVIDER_KEYS: tuple[str, ...] = (
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_API_KEY",
)

# Claves top-level legacy por-provider que limpiamos por compatibilidad.
PROVIDER_TOP_KEYS: tuple[str, ...] = (
    "_minimax_model",
    "_minimax_backup_env",
    "_zai_model",
    "_zai_backup_env",
    "_nvidia_model",
    "_nvidia_backup_env",
    "_ollama_model",
    "_ollama_backup_env",
)
API_TIMEOUT_MS = "3000000"

# `ENABLE_TOOL_SEARCH=auto:5` evita que Claude Code cargue todas las definiciones
# MCP upfront cuando ANTHROPIC_BASE_URL apunta al proxy local. Claude Code desactiva
# Tool Search por defecto en gateways no first-party, justo nuestro caso; con muchas
# tools/skills eso infla el primer request y rompe providers alternativos.
ENABLE_TOOL_SEARCH = "auto:5"

# `API_FORCE_IDLE_TIMEOUT=0` desactiva el watchdog de inactividad de 5 minutos que
# Claude Code aplica por defecto a CUALQUIER conexion que no sea Anthropic/AWS directo
# (i.e. esta activo en nuestra conexion de proxy salvo que lo pisemos). Sin esto, un
# modelo local lento (Ollama/LM Studio) que tarde >5min entre chunks del stream aborta
# la respuesta aunque API_TIMEOUT_MS (el timeout total) sea generoso. Ver
# https://code.claude.com/docs/en/env-vars — no aplica a zai/minimax/opencode/openrouter
# (responden rapido), pero setearlo global es inocuo: API_TIMEOUT_MS sigue acotando el
# caso patologico de una conexion realmente colgada.
API_FORCE_IDLE_TIMEOUT = "0"


# `models` es una lista CONOCIDA (hint + fallback offline), NO una whitelist: si el
# provider saca un modelo nuevo (p. ej. MiniMax-M3), se acepta igual. El default real
# lo resuelve `model_resolver.resolve_default_model` (override env -> cache -> fetch
# /v1/models -> el mas nuevo de esta lista). `default_model` es solo el ultimo recurso.
#
# Fuente unica de verdad: `.antigravity/providers.json` (3-tier, ver provider_catalog).
# `PROVIDERS` se DERIVA del catalogo en import time; si el JSON falta/corrupto, build_providers
# cae al dict embebido (mismos valores), garantizando backward compat para los consumidores.
PROVIDERS: dict[str, ProviderConfig] = build_providers()


def _is_local_url(url: str) -> bool:
    """True si la base_url apunta a un servicio local (localhost/loopback).

    Args:
        url: base_url del provider.

    Returns:
        True si es un host local (Ollama/LM Studio), False si es remoto.
    """
    return any(host in url for host in ("localhost", "127.0.0.1", "0.0.0.0"))


# Las tres tuplas de routability se DERIVAN del catalogo (campos `wire`/`routable` de cada
# ProviderConfig), no se hardcodean. Asi agregar un provider = editar providers.json, sin
# tocar este modulo. Deben ir DESPUES de `PROVIDERS` porque dependen de el.
#
# - PROXY_COMPATIBLE: hablan Anthropic Messages API DIRECTO (wire="anthropic", routable).
#   Base de shadow mode y routing por clase, que asumen payload Anthropic sin traducir.
# - OPENAI_LOCAL: OpenAI-compatible LOCALES (Ollama/LM Studio). El proxy hace de bridge
#   traduciendo Anthropic<->OpenAI (core.openai_translator). No requieren API key.
# - PROXY_ROUTABLE: todo lo que el proxy puede activar como backend (todos los `routable`).
#   switch_provider/set_hotswap validan contra esta (NO contra PROXY_COMPATIBLE, reservada
#   para shadow/class-routing en formato Anthropic). Incluye los OpenAI remotos ruteables
#   (OpenRouter, OpenCode Zen). NVIDIA queda afuera (routable=False en el catalogo).
PROXY_COMPATIBLE: tuple[str, ...] = tuple(
    pid for pid, cfg in PROVIDERS.items() if cfg.routable and cfg.wire == "anthropic"
)
OPENAI_LOCAL: tuple[str, ...] = tuple(
    pid
    for pid, cfg in PROVIDERS.items()
    if cfg.routable and cfg.wire == "openai" and _is_local_url(cfg.base_url)
)
PROXY_ROUTABLE: tuple[str, ...] = tuple(pid for pid, cfg in PROVIDERS.items() if cfg.routable)


class ProviderError(ValueError):
    """Error de validacion al conmutar provider (provider/modelo/API key)."""


# Aliases que el usuario/skill puede escribir para un provider ya existente en PROVIDERS.
# Los 3 comandos de switch (/provider, /cambiar, /cambio) prometen "glm -> zai" en sus
# instrucciones de prompt, pero eso depende de que el modelo orquestador siga esa
# instruccion al pie de la letra en cada sesion. Sin este mapa, un "glm" que llegue crudo
# al endpoint HTTP explota con ProviderError("Provider desconocido: glm"). Resuelto en
# codigo para no depender de la disciplina del prompt.
_PROVIDER_ALIASES: dict[str, str] = {
    "glm": "zai",
}


def normalize_provider_id(provider_id: str) -> str:
    """Normaliza un id de provider crudo: trim + lowercase + resolucion de alias.

    Args:
        provider_id: Id tal como lo escribio el usuario o el skill (p. ej. "GLM").

    Returns:
        El id listo para buscar en ``PROVIDERS`` (p. ej. "glm" -> "zai").
    """
    pid = provider_id.strip().lower()
    return _PROVIDER_ALIASES.get(pid, pid)


def _discover_local_model(provider_id: str, base_url: str) -> str | None:
    """Descubre el primer modelo cargado en un backend local OpenAI-compatible.

    Pega al endpoint de listado del servicio local (Ollama ``/api/tags``, LM Studio
    ``/v1/models``) y devuelve el id del primer modelo util (descarta embeddings).
    Best-effort: si el servicio no responde, devuelve respuesta no parseable, o si
    ``ANTIGRAVITY_DISABLE_MODEL_FETCH`` esta activo (tests herméticos), devuelve
    ``None`` para que el caller use el fallback estatico del provider.

    Args:
        provider_id: ``ollama`` o ``lmstudio``.
        base_url: URL base del servicio local (p. ej. ``http://localhost:11434``).

    Returns:
        Id del modelo descubierto, o ``None`` si no se pudo descubrir.
    """
    if os.environ.get("ANTIGRAVITY_DISABLE_MODEL_FETCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None

    base = base_url.rstrip("/")
    # Ollama lista en /api/tags (clave "models", id en "name"); LM Studio en /v1/models
    # (clave "data", id en "id", formato OpenAI). La base de LM Studio ya incluye /v1.
    if provider_id == "ollama":
        url = f"{base[:-3]}/api/tags" if base.endswith("/v1") else f"{base}/api/tags"
        list_key = "models"
    else:
        url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
        list_key = "data"

    try:
        # URL derivada de config interna y siempre localhost; no es input del usuario.
        with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — best-effort: cualquier fallo cae al fallback
        return None

    items = data.get(list_key) if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id") or ""
        if not isinstance(name, str) or not name:
            continue
        if "embed" in name.lower():  # los modelos de embedding no sirven para chat
            continue
        return name
    return None


def _resolve_model(cfg: ProviderConfig, model: str | None, root: Path) -> str:
    """Resuelve el modelo a usar para un provider alternativo.

    Si `model` viene explicito, se respeta tal cual (el provider lo valida). Si no,
    delega en `model_resolver` que elige el mas nuevo (override env -> cache -> fetch
    /v1/models -> el mas nuevo de la lista conocida). La lista `cfg.models` ya NO es
    una whitelist bloqueante: un modelo nuevo no listado se acepta, solo se loguea.

    Args:
        cfg: Configuracion del provider.
        model: Modelo pedido explicitamente (None = auto-resolver el mejor).
        root: Raiz del proyecto (para leer la API key del .env en el fetch).

    Returns:
        El id del modelo elegido.
    """
    from core import model_resolver

    if model and model.strip():
        chosen = model.strip()
        if cfg.models and chosen not in cfg.models:
            logger.warning(
                "Modelo '%s' no esta en la lista conocida de %s %s; se acepta igual "
                "(el provider lo valida).",
                chosen,
                cfg.id,
                list(cfg.models),
            )
        return chosen

    # Locales OpenAI (ollama/lmstudio): descubrir el modelo cargado en vivo del endpoint
    # local. model_resolver apunta a /v1/models estilo Anthropic/OpenAI remoto y no cubre
    # el formato propio de Ollama (/api/tags), por eso se resuelve aparte aca.
    if cfg.id in OPENAI_LOCAL:
        return _discover_local_model(cfg.id, cfg.base_url) or cfg.default_model

    api_key = get_api_key_from_env(root, cfg.api_key_env) if cfg.api_key_env else None
    return model_resolver.resolve_default_model(
        cfg.id,
        known_models=cfg.models,
        fallback=cfg.default_model,
        base_url=cfg.base_url,
        api_key=api_key,
        family=cfg.family,
    )


# ── Resolucion de paths ──────────────────────────────────────────────────────


def default_root() -> Path:
    """Resuelve la raiz del proyecto.

    Returns:
        ANTIGRAVITY_ROOT si esta seteada; si no, infiere desde la ubicacion
        del modulo (.agent/core/ -> raiz dos niveles arriba).
    """
    env = os.environ.get("ANTIGRAVITY_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def user_settings_path() -> Path:
    """Path de ~/.claude/settings.json (o el override de tests)."""
    override = os.environ.get("ANTIGRAVITY_CLAUDE_SETTINGS")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "settings.json"


def project_settings_path(root: Path) -> Path:
    """Path de <root>/.claude/settings.local.json."""
    return root / ".claude" / "settings.local.json"


def backup_path() -> Path:
    """Path del backup full de settings, junto al settings activo."""
    return user_settings_path().parent / "settings.backup-before-provider.json"


# ── IO de settings / .env ────────────────────────────────────────────────────


def _read_json(path: Path) -> dict:
    """Lee JSON tolerando ausencia/corrupcion (devuelve {})."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    """Escribe JSON indentado de forma atómica usando un archivo temporal."""
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


# Ventana de proteccion contra race con el sidecar monitor (start_monitor.py).
# Cualquier escritura a settings.json hecha por provider_switch refresca el stamp;
# el monitor no pisara la escritura durante los proximos RACE_WINDOW_S segundos.
_RACE_WINDOW_S = 5.0


def _mark_user_command(reason: str) -> None:
    """Refresca ``last_user_command.json`` (timestamp unix).

    El sidecar monitor (``scripts/start_monitor.py``) lee este stamp antes de
    mutar settings.json (modo degraded/restore). Si fue refrescado hace menos
    de ``_RACE_WINDOW_S`` segundos, el monitor NO pisa — asi un switch_provider
    que esta corriendo no se ve interrumpido por el gateway cayendo o volviendo.

    Args:
        reason: Etiqueta legible del motivo (para debugging del stamp).
    """
    stamp_path = Path.home() / ".antigravity" / "proxy" / "last_user_command.json"
    try:
        stamp_path.parent.mkdir(parents=True, exist_ok=True)
        stamp_path.write_text(
            json.dumps(
                {
                    "at": time.time(),
                    "reason": reason,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("No se pudo escribir last_user_command.json: %s", exc)


def get_api_key_from_env(root: Path, key_name: str) -> str | None:
    """Lee una API key del .env del proyecto, con fallback al entorno del proceso.

    El .env del repo es la fuente primaria; si la key no esta ahi pero el usuario
    la exporto en su shell/entorno, el switch no debe fallar con "no encontrada".

    Args:
        root: Raiz del proyecto donde vive el .env.
        key_name: Nombre de la variable (p. ej. MINIMAX_API_KEY).

    Returns:
        El valor (sin comillas) o None si no existe / esta vacio.
    """
    env_path = root / ".env"
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            prefix = f"{key_name}="
            if line.startswith(prefix):
                val = line[len(prefix) :].strip().strip('"').strip("'")
                if val:
                    return val
    except OSError:
        pass
    fallback = os.environ.get(key_name, "").strip()
    return fallback or None


# ── Helpers del modelo proxy-always ─────────────────────────────────────────


def _ensure_proxy_base_url(settings: dict, already_connected: bool = False) -> bool:
    """Setea ANTHROPIC_BASE_URL al proxy y limpia tokens de provider del env.

    En el modelo proxy-always, el env solo debe tener ANTHROPIC_BASE_URL=PROXY_BASE_URL
    y controles del cliente (timeouts + Tool Search). Cualquier token de provider
    (ANTHROPIC_AUTH_TOKEN, etc.) rompe el passthrough OAuth nativo de Claude.

    Ademas, marca ``last_user_command.json`` para que el monitor sidecar del
    gateway (:4747) NO pise esta escritura durante la ventana de race.

    Args:
        settings: Dict de settings.json (modificado in-place).
        already_connected: True si el proxy ya estaba conectado ANTES de cualquier
            limpieza del dict (evita falso positivo cuando _strip_all borro la URL).

    Returns:
        True si la base URL cambio (requiere reiniciar Claude Code para que tome efecto).
        False si ya estaba apuntando al proxy (hot-swap en caliente, sin reinicio).
    """
    env = settings.get("env")
    if not isinstance(env, dict):
        env = {}
        settings["env"] = env

    # Si ya_connected es True, el proxy estaba activo antes de _strip_all → no hay
    # cambio real en la base URL (ya apuntaba al proxy), no se necesita reiniciar.
    if already_connected:
        for key in _DIRECT_PROVIDER_KEYS:
            env.pop(key, None)
        env["ANTHROPIC_BASE_URL"] = PROXY_BASE_URL
        env["API_TIMEOUT_MS"] = API_TIMEOUT_MS
        env["API_FORCE_IDLE_TIMEOUT"] = API_FORCE_IDLE_TIMEOUT
        env["ENABLE_TOOL_SEARCH"] = ENABLE_TOOL_SEARCH
        return False

    current_base = env.get("ANTHROPIC_BASE_URL", "") or ""
    base_changed = current_base != PROXY_BASE_URL

    # Limpiar tokens de provider directos — el proxy los inyecta desde .env
    for key in _DIRECT_PROVIDER_KEYS:
        env.pop(key, None)

    env["ANTHROPIC_BASE_URL"] = PROXY_BASE_URL
    env["API_TIMEOUT_MS"] = API_TIMEOUT_MS
    env["API_FORCE_IDLE_TIMEOUT"] = API_FORCE_IDLE_TIMEOUT
    env["ENABLE_TOOL_SEARCH"] = ENABLE_TOOL_SEARCH

    # Marca para el sidecar monitor (start_monitor.py): no pisar esta escritura
    # durante los proximos RACE_WINDOW_S segundos (5s default).
    _mark_user_command("ensure_proxy_base_url")

    return base_changed


def _remove_proxy_base_url(settings: dict) -> bool:
    """Quita ANTHROPIC_BASE_URL y limpia las vars de provider del env.

    Deja el env en estado "Claude nativo puro": sin base URL ni tokens de provider.
    Marca ``last_user_command.json`` para que el monitor sidecar no interfiera.

    Args:
        settings: Dict de settings.json (modificado in-place).

    Returns:
        True si habia algo que quitar (se modifico el dict).
    """
    env = settings.get("env")
    if not isinstance(env, dict):
        return False

    changed = False
    for key in (
        *_DIRECT_PROVIDER_KEYS,
        "ANTHROPIC_BASE_URL",
        "API_TIMEOUT_MS",
        "API_FORCE_IDLE_TIMEOUT",
        "ENABLE_TOOL_SEARCH",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    ):
        if key in env:
            env.pop(key)
            changed = True

    for key in PROVIDER_TOP_KEYS:
        if key in settings:
            settings.pop(key)
            changed = True

    if changed:
        # Marca para el sidecar monitor (start_monitor.py): ventana de race
        # contra mutaciones concurrentes del monitor.
        _mark_user_command("remove_proxy_base_url")

    return changed


# ── Deteccion / mutacion de settings ─────────────────────────────────────────


def detect_active(settings: dict) -> tuple[str, str]:
    """Detecta el provider activo y el modelo en uso.

    Si el proxy esta conectado (base URL == PROXY_BASE_URL), el backend activo
    se lee de proxy_state (fuente de verdad en modo hot-swap).
    Si la base URL es la de un provider directo (modo legacy), se detecta por URL.
    Si no hay base URL, se asume Claude nativo.

    Args:
        settings: Contenido de settings.json.

    Returns:
        Tupla (provider_id, model). Default ("claude", "claude-sonnet-4-6").
    """
    from core import proxy_state as _ps

    env = settings.get("env") or {}
    base = env.get("ANTHROPIC_BASE_URL", "") or ""

    if base == PROXY_BASE_URL:
        # Proxy conectado: la fuente de verdad es proxy_state. Saneamos contra la
        # whitelist de PROVIDERS para no propagar un provider corrupto/desconocido
        # (evita KeyError aguas abajo en get_overview con un proxy_state editado a mano).
        state = _ps.get_active()
        pid = state["provider"]
        if pid not in PROVIDERS:
            return "claude", "claude-sonnet-4-6"
        return pid, state["model"]

    # Compatibilidad lectura legacy (modo directo o migración)
    if "minimax" in base:
        return "minimax", env.get("ANTHROPIC_MODEL") or settings.get(
            "_minimax_model"
        ) or "MiniMax-M2.7"
    if "z.ai" in base or "bigmodel" in base:
        return "zai", settings.get("_zai_model") or env.get(
            "ANTHROPIC_DEFAULT_SONNET_MODEL"
        ) or "glm-5.1"
    if "nvidia" in base:
        return "nvidia", env.get("ANTHROPIC_MODEL") or "nvidia/llama-3.1-nemotron-70b-instruct"
    if "11434" in base:
        return "ollama", env.get("ANTHROPIC_MODEL") or "llama3"
    if "1234" in base:
        return "lmstudio", env.get("ANTHROPIC_MODEL") or "lmstudio-model"
    sonnet = env.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "") or ""
    if sonnet.startswith("glm"):
        return "zai", sonnet
    return "claude", "claude-sonnet-4-6"


def _strip_all(settings: dict) -> None:
    """Quita todas las env vars y claves legacy de provider de los settings."""
    env = settings.get("env")
    if isinstance(env, dict):
        for key in PROVIDER_ENV_KEYS:
            env.pop(key, None)
    for key in PROVIDER_TOP_KEYS:
        settings.pop(key, None)


def _clear_project_provider_env(root: Path) -> None:
    """Quita SOLO las env vars de provider del settings.local.json del proyecto.

    Mejora sobre el Rust (que borraba todo el bloque `env`): preserva variables
    no relacionadas como PATH para no romper la config local del usuario.
    """
    path = project_settings_path(root)
    if not path.exists():
        return
    settings = _read_json(path)
    env = settings.get("env")
    if not isinstance(env, dict):
        return
    changed = False
    for key in PROVIDER_ENV_KEYS:
        if key in env:
            env.pop(key, None)
            changed = True
    if changed:
        _write_json(path, settings)


# ── API publica ──────────────────────────────────────────────────────────────


def get_overview(root: Path | None = None) -> dict:
    """Devuelve el estado unificado de los providers.

    Args:
        root: Raiz del proyecto (default: auto).

    Returns:
        Dict con active_provider, active_model, proxy_connected, needs_restart,
        providers[], diagnosis, etc.
    """
    root = root or default_root()
    settings_path = user_settings_path()
    settings = _read_json(settings_path)
    active, active_model = detect_active(settings)

    env = settings.get("env") or {}
    proxy_connected = (env.get("ANTHROPIC_BASE_URL", "") or "") == PROXY_BASE_URL

    from core import proxy_state as _ps

    fallback = _ps.get_fallback() if proxy_connected else None
    circuit = _ps.get_circuit() if proxy_connected else {}
    recovery_events = _ps.get_recovery_events(limit=5) if proxy_connected else []
    backup_available = bool(settings.get("_provider_backup_env")) or backup_path().exists()

    providers = []
    for pid, cfg in PROVIDERS.items():
        has_key = True
        if cfg.api_key_env:
            has_key = get_api_key_from_env(root, cfg.api_key_env) is not None
        providers.append(
            {
                "id": cfg.id,
                "name": cfg.name,
                "available": True,
                "has_api_key": has_key,
                # allow_fetch=False: el overview lo consulta la UI en cada
                # render — usa cache compartido o lista conocida, nunca la red.
                "models": list_models(pid, root=root, allow_fetch=False),
                "active": pid == active,
                "active_model": active_model if pid == active else None,
                "wire": cfg.wire,
                "routable": cfg.routable,
                "free_models": [
                    model
                    for model in list_models(pid, root=root, allow_fetch=False)
                    if model.endswith(":free")
                ],
            }
        )

    if proxy_connected:
        if active == "claude":
            diagnosis = (
                "Proxy conectado (proxy-always). Claude activo via passthrough OAuth al gateway "
                "(hot-swap en caliente, sin reiniciar Claude Code)."
            )
        else:
            diagnosis = (
                f"Proxy conectado (proxy-always). {PROVIDERS[active].name} activo con modelo "
                f"{active_model}. Cambio de backend en caliente, sin reiniciar."
            )
    elif active == "claude":
        diagnosis = (
            "Claude nativo (sin proxy conectado). "
            "Conecta un alternativo con /provider <id> para entrar al modo proxy-always."
        )
    else:
        diagnosis = (
            f"{PROVIDERS[active].name} activo con modelo {active_model} "
            "(modo directo legacy; reiniciar para re-entrar al modelo proxy-always)."
        )

    if fallback:
        from_id = str(fallback.get("from") or "")
        from_name = PROVIDERS[from_id].name if from_id in PROVIDERS else from_id
        count = fallback.get("count", 1)
        diagnosis += (
            f" Aviso: el ultimo turno de {from_name} se rescato a Claude "
            f"(motivo: {fallback.get('reason', 'desconocido')}; rescates seguidos: {count}). "
            "El proximo prompt reintenta el backend elegido."
        )

    # Visibilidad de las decisiones autonomas del proxy: el usuario tiene que
    # poder ver POR QUE sus turnos van a Claude o llegan sin contexto, sin tener
    # que grepear logs del gateway (auditoria 2026-06-11).
    if circuit:
        detalle = ", ".join(
            f"{pid} (fallos seguidos: {entry.get('streak', '?')}, "
            f"ultimo: {entry.get('last_failure_at', '?')})"
            for pid, entry in circuit.items()
        )
        diagnosis += (
            f" Aviso: circuit breaker con fallos de salud recientes en {detalle}. "
            "Los turnos pueden estar rescatandose a Claude hasta que el backend responda sano."
        )
    precompacts = [e for e in recovery_events if e.get("event") == "precompact_alt_provider"]
    if precompacts:
        last = precompacts[-1]
        diagnosis += (
            f" Aviso: el proxy pre-compacto el historial hacia "
            f"{last.get('provider') or 'el backend alternativo'} ({last.get('at', '?')}): "
            "los turnos largos se recortan antes del envio. Umbral configurable con "
            "ANTIGRAVITY_PROXY_ALT_MAX_MESSAGES (0 en ANTIGRAVITY_PROXY_ALT_PRECOMPACT desactiva)."
        )

    return {
        "active_provider": active,
        "active_provider_name": PROVIDERS[active].name,
        "active_model": active_model,
        "proxy_connected": proxy_connected,
        "needs_restart": False,
        "has_api_key": active != "claude",
        "backup_available": backup_available,
        "providers": providers,
        "diagnosis": diagnosis,
        "fallback": fallback,
        "circuit": circuit,
        "recovery_events": recovery_events,
        "settings_path": str(settings_path),
        "preflight_ok": None,
    }


def _activate_claude_via_proxy(root: Path) -> dict:
    """Activa Claude MANTENIENDO el proxy como punto de routing (proxy-always).

    En el modelo proxy-always, ``ANTHROPIC_BASE_URL`` permanece SIEMPRE apuntando al
    proxy local. Cuando el backend activo es Claude, el gateway hace passthrough crudo
    a ``https://api.anthropic.com/v1/messages`` preservando el header ``Authorization``
    o ``x-api-key`` que Claude Code inyecta via OAuth (ver ``provider_router.py:96-102``
    y ``_mixin_proxy.py:2419-2424``: el handler ya soporta el caso). El proxy relee
    ``proxy_state.json`` en cada request, asi que un cambio de backend es efectivo
    en el siguiente prompt, sin reiniciar Claude Code.

    Args:
        root: Raiz del proyecto (para limpiar el override del .claude del proyecto).

    Returns:
        Overview actualizado. ``needs_restart`` es ``True`` solo si ``already_connected``
        es ``False`` (estado legacy sin proxy; el primer switch SI requiere reiniciar
        Claude Code para que lea la nueva ``ANTHROPIC_BASE_URL``). En estado normal
        (proxy conectado) es siempre ``False``. Idempotente si ya estamos en
        claude-via-proxy: no produce cambios observables.
    """
    from core import proxy_state

    settings_path = user_settings_path()
    bak = backup_path()
    if not bak.exists():
        _write_json(bak, _read_json(settings_path))

    settings = _read_json(settings_path)
    env_before = settings.get("env") or {}
    already_connected = (env_before.get("ANTHROPIC_BASE_URL", "") or "") == PROXY_BASE_URL

    # Asegurar el proxy en settings.json (siempre hacia PROXY_BASE_URL — nunca nula).
    _ensure_proxy_base_url(settings, already_connected=already_connected)
    settings["_active_provider"] = "claude"
    settings["_active_model"] = "claude-sonnet-4-6"
    _write_json(settings_path, settings)

    # El proxy relee proxy_state por request — escribir aqui es suficiente para
    # que el siguiente prompt use Claude nativo via passthrough.
    proxy_state.set_active("claude", "claude-sonnet-4-6")
    _clear_project_provider_env(root)

    logger.info(
        "Claude activado via proxy (proxy-always, hot-swap), already_connected=%s",
        already_connected,
    )
    result = get_overview(root)
    # La base URL NO cambia. Pero si nunca la habiamos seteado (estado legacy),
    # Claude Code tendra que reiniciar UNA vez para leer la nueva env var.
    result["needs_restart"] = not already_connected
    return result


def _activate_claude_direct(root: Path) -> dict:
    """DEPRECATED — alias legado del antiguo modelo bypass; redirige a via-proxy.

    Se mantiene por compatibilidad con consumidores externos (Tauri/Rust/tests
    viejos) que puedan importar el nombre historico. El comportamiento nuevo es
    siempre ``_activate_claude_via_proxy``: el modelo proxy-always es la unica via
    soportada para cruzar claude<->alternativo en caliente.

    Args:
        root: Raiz del proyecto.

    Returns:
        Overview actualizado. Mismo contrato que ``_activate_claude_via_proxy``.
    """
    return _activate_claude_via_proxy(root)


def switch_provider(
    provider_id: str,
    model: str | None = None,
    root: Path | None = None,
    scope: str = "global",
) -> dict:
    """Activa un provider via hot-swap por el proxy.

    En el modelo proxy-always, switch_provider:
    1. Valida provider/modelo/api_key.
    2. Escribe el backend en proxy_state (hot-swap; efectivo en el proximo prompt).
    3. Asegura que ANTHROPIC_BASE_URL apunte al proxy (conectando si no estaba).
    4. Limpia el settings.local.json del proyecto de vars de provider directas.

    Para provider_id="claude" NO es disable: es hot-swap a claude por el proxy
    (passthrough OAuth nativo de Claude Code, sin token en el env).

    Args:
        provider_id: claude | minimax | zai | nvidia | ollama | lmstudio.
        model: Modelo a usar (default: el del provider).
        root: Raiz del proyecto (default: auto).
        scope: "global" (~/.claude/settings.json, default) o "project"
            (<root>/.claude/settings.local.json, override solo para este proyecto).

    Returns:
        El overview actualizado con needs_restart indicando si hay que reiniciar
        Claude Code (True solo en la primera conexion del proxy).

    Raises:
        ProviderError: provider desconocido, modelo invalido o API key faltante.
    """
    from core import proxy_state

    root = root or default_root()
    pid = normalize_provider_id(provider_id)

    cfg = PROVIDERS.get(pid)
    if cfg is None:
        raise ProviderError(f"Provider desconocido: {provider_id}")

    if pid not in PROXY_ROUTABLE:
        raise ProviderError(
            f"{cfg.name} no se puede enrutar por el proxy todavia "
            f"(formato OpenAI remoto sin bridge de traduccion). "
            f"Routables: {list(PROXY_ROUTABLE)}."
        )

    # Claude via proxy: la base URL apunta siempre al proxy local; el gateway hace
    # passthrough crudo a api.anthropic.com cuando el backend activo es claude. Cruzar
    # desde un alternativo es un hot-swap (no cambia base URL) -> sin reiniciar.
    if pid == "claude":
        if scope == "project":
            return disable_provider(root, scope="project")
        return _activate_claude_via_proxy(root)

    # Validar API key (claude no requiere; el proxy hace passthrough OAuth). Se valida
    # ANTES de resolver el modelo porque el resolver usa la key para el fetch dinamico.
    if cfg.api_key_env:
        key = get_api_key_from_env(root, cfg.api_key_env)
        if not key:
            raise ProviderError(f"{cfg.api_key_env} no encontrada en {root / '.env'}")

    chosen = _resolve_model(cfg, model, root)

    if scope == "project":
        # Scope proyecto: solo escribir proxy_state y apuntar el local al proxy.
        proxy_state.set_active(pid, chosen)
        path = project_settings_path(root)
        proj_settings = _read_json(path)
        _ensure_proxy_base_url(proj_settings)
        _write_json(path, proj_settings)
        logger.info("Hot-swap de provider (proyecto): %s (%s)", cfg.name, chosen)
        return {
            "scope": "project",
            "active_provider": pid,
            "active_provider_name": cfg.name,
            "active_model": chosen,
            "proxy_connected": True,
            "needs_restart": False,
            "settings_path": str(path),
            "diagnosis": (
                f"Hot-swap a {cfg.name} ({chosen}) por el proxy. "
                "Efectivo en el proximo prompt, sin reiniciar."
            ),
        }

    # Scope global
    settings_path = user_settings_path()
    bak = backup_path()
    if not bak.exists():
        _write_json(bak, _read_json(settings_path))

    settings = _read_json(settings_path)

    # Capturar si el proxy ya estaba conectado ANTES de _strip_all, porque
    # _strip_all borra ANTHROPIC_BASE_URL del dict y _ensure_proxy_base_url
    # no podria distinguir "primera conexion" de "hot-swap posterior".
    env_before = settings.get("env") or {}
    already_connected = (env_before.get("ANTHROPIC_BASE_URL", "") or "") == PROXY_BASE_URL

    _strip_all(settings)

    # Hot-swap: escribir backend en proxy_state ANTES de conectar el proxy
    proxy_state.set_active(pid, chosen)

    # Conectar el proxy (devuelve True si la base URL cambio -> necesita reinicio)
    base_changed = _ensure_proxy_base_url(settings, already_connected=already_connected)

    settings["_active_provider"] = pid
    settings["_active_model"] = chosen
    _write_json(settings_path, settings)
    _clear_project_provider_env(root)

    logger.info(
        "Provider activado via proxy: %s (%s), needs_restart=%s", cfg.name, chosen, base_changed
    )
    result = get_overview(root)
    result["needs_restart"] = base_changed
    return result


def disable_provider(root: Path | None = None, scope: str = "global") -> dict:
    """Activa Claude MANTENIENDO el proxy como routing (proxy-always), scope global o project.

    En el modelo proxy-always, ``disable_provider`` es sinonimo de "volver a Claude
    via passthrough del gateway": la base URL sigue apuntando al proxy y solo cambia
    el backend activo en ``proxy_state``. NUNCA requiere reiniciar Claude Code.

    Args:
        root: Raiz del proyecto (default: auto).
        scope: "global" o "project" (limpia el override del proyecto).
    """
    root = root or default_root()

    if scope == "project":
        _clear_project_provider_env(root)
        connected = (_read_json(user_settings_path()).get("env") or {}).get(
            "ANTHROPIC_BASE_URL", ""
        ) == PROXY_BASE_URL
        logger.info("Override de provider del proyecto removido")
        return {
            "scope": "project",
            "active_provider": "claude",
            "active_provider_name": "Claude (Anthropic)",
            "active_model": "claude-sonnet-4-6",
            "proxy_connected": connected,
            "needs_restart": False,
            "settings_path": str(project_settings_path(root)),
            "diagnosis": "Override de provider del proyecto removido; hereda el provider global.",
        }

    # Global: Claude via proxy (proxy-always). needs_restart siempre False.
    return _activate_claude_via_proxy(root)


def reset_to_proxy_always(root: Path | None = None) -> dict:
    """Restaura el modelo proxy-always: settings.json limpio y backend=claude via proxy.

    En el modelo proxy-always, este es el unico "rollback" util: si el state esta
    corrupto (settings.json mal escrito, base URL apuntaba a un provider directo
    legacy, etc.), esta funcion lo restaura al estado canonico (proxy conectado,
    tokens directos limpios, backend=claude via passthrough OAuth). No es "salir del
    ecosistema" (eso ya no existe en proxy-always: el proxy es permanente).

    NO requiere reiniciar Claude Code salvo en el caso raro de que ANTHROPIC_BASE_URL
    haya cambiado de vacia a poblada (estado legacy -> proxy-always por primera vez).

    Args:
        root: Raiz del proyecto (default: auto).

    Returns:
        Overview actualizado con `proxy_connected=True` y `active_provider=claude`.
        `needs_restart` refleja si la base URL cambio (True la primera vez).
    """
    root = root or default_root()
    settings_path = user_settings_path()
    bak = backup_path()

    if bak.exists():
        # Hay backup del estado pre-proxy. Restaurar y re-conectar al proxy (no
        # quedarse en "Claude nativo puro" — eso era del modelo viejo).
        base = _read_json(bak)
        # Si el backup era del modelo proxy-always (varios switches), restaurar
        # su base URL actual intacta; si era legacy directo, el _ensure_proxy_base_url
        # de abajo lo arregla.
        _ensure_proxy_base_url(
            base, already_connected=base.get("env", {}).get("ANTHROPIC_BASE_URL") == PROXY_BASE_URL
        )
        for key in ("_provider_backup_env", "_active_provider", "_active_model"):
            base.pop(key, None)
        _write_json(settings_path, base)
        logger.info("Proxy-always restaurado desde backup")
    else:
        # Sin backup: limpiar manualmente vars de provider y reconectar el proxy.
        settings = _read_json(settings_path)
        # _ensure_proxy_base_url detecta ya-conectado y solo limpia tokens.
        _ensure_proxy_base_url(settings, already_connected=_is_proxy_connected(settings))
        for key in ("_provider_backup_env", "_active_provider", "_active_model"):
            settings.pop(key, None)
        _write_json(settings_path, settings)
        logger.info("Proxy-always restaurado (sin backup previo)")

    _clear_project_provider_env(root)

    # Backend canonico del reset: claude via proxy. Eso devuelve `proxy_connected=True`
    # y un overview consistente.
    result = _activate_claude_via_proxy(root)
    result["diagnosis"] = (
        "Estado restaurado al modelo proxy-always: Claude activo via passthrough OAuth "
        "del gateway, base URL estable, sin perdida de contexto."
    )
    return result


def _is_proxy_connected(settings: dict) -> bool:
    """Helper: True si ANTHROPIC_BASE_URL apunta al proxy."""
    env = settings.get("env") or {}
    base = env.get("ANTHROPIC_BASE_URL", "") or ""
    return base == PROXY_BASE_URL


def disconnect_proxy(root: Path | None = None) -> dict:
    """DEPRECATED — use :func:`reset_to_proxy_always` en su lugar.

    El "desconectar proxy" era del modelo bypass viejo (Claude nativo sin proxy).
    En el modelo proxy-always (revisado 2026-07-05) el proxy es permanente: el unico
    "rollback" util es restaurar el state canonico, que ahora hace ``reset_to_proxy_always``.

    Se conserva por compat con scripts externos que puedan llamar el nombre viejo;
    la implementacion es un alias que delega + emite ``DeprecationWarning`` (visible
    por ``warnings.catch_warnings``) + loguea en logger.
    Devuelve un overview con ``proxy_connected=True`` (mismo contrato que
    ``reset_to_proxy_always``).
    """
    import warnings as _w

    logger.warning(
        "disconnect_proxy() esta deprecado; use reset_to_proxy_always() en su lugar. "
        "En el modelo proxy-always no hay 'salir del ecosistema': el proxy es permanente."
    )
    _w.warn(
        "disconnect_proxy() is deprecated; use reset_to_proxy_always() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return reset_to_proxy_always(root)


def get_class_routes() -> dict:
    """Devuelve el routing por clase activo (para CLI/overview)."""
    from core import proxy_state

    return {
        "routes": proxy_state.get_class_routing(),
        "routing_path": str(proxy_state.routing_path()),
    }


def route_class(model_class: str, provider_id: str, model: str | None = None) -> dict:
    """Setea una ruta de clase de modelo (haiku/sonnet/opus -> provider).

    Args:
        model_class: Clase a rutear (``haiku`` | ``sonnet`` | ``opus``).
        provider_id: Backend destino — debe ser proxy-compatible (claude/minimax/zai).
        model: Modelo a usar en el destino; ``None`` = default dinamico del provider.

    Returns:
        El routing completo persistido.

    Raises:
        ProviderError: provider no proxy-compatible o clase desconocida.
    """
    from core import proxy_state

    pid = normalize_provider_id(provider_id)
    if pid not in PROXY_COMPATIBLE:
        raise ProviderError(
            f"Provider no proxy-compatible para routing: {provider_id} "
            f"(validos: {', '.join(PROXY_COMPATIBLE)})"
        )
    try:
        routes = proxy_state.set_class_route(model_class, pid, model)
    except ValueError as exc:
        raise ProviderError(str(exc)) from exc
    return {"routes": routes, "routing_path": str(proxy_state.routing_path())}


def clear_class_route(model_class: str | None = None) -> dict:
    """Borra una ruta de clase (o todas) del routing del proxy."""
    from core import proxy_state

    routes = proxy_state.clear_class_routes(model_class)
    return {"routes": routes, "routing_path": str(proxy_state.routing_path())}


def shadow_mode(
    action: str,
    provider_id: str | None = None,
    model: str | None = None,
) -> dict:
    """ON/OFF del shadow mode (A/B testing pasivo de Claude vs alternativo).

    Args:
        action: ``on`` | ``off`` | ``status``.
        provider_id: Backend a sombrear con ``on`` (default: zai).
        model: Modelo en el shadow; ``None`` = default dinamico del provider.

    Returns:
        Dict con el estado resultante + path del log de comparaciones.

    Raises:
        ProviderError: accion desconocida o provider no proxy-compatible.
    """
    from core import proxy_state

    act = action.strip().lower()
    if act == "on":
        pid = normalize_provider_id(provider_id or "zai")
        if pid not in PROXY_COMPATIBLE or pid == "claude":
            raise ProviderError(
                f"Shadow requiere un alternativo proxy-compatible (minimax|zai), no: {pid}"
            )
        state = proxy_state.set_shadow(True, pid, model)
    elif act == "off":
        state = proxy_state.set_shadow(False)
    elif act == "status":
        state = proxy_state.get_shadow()
    else:
        raise ProviderError(f"Accion desconocida: {action} (validas: on, off, status)")
    return {
        "shadow": state,
        "log_path": str(proxy_state.state_path().parent / "shadow_log.jsonl"),
    }


def shadow_report(last: int = 5, log_path: Path | None = None) -> dict:
    """Resumen agregado del shadow log (comparaciones Claude vs alternativo).

    Lee ``shadow_log.jsonl`` y devuelve totales, latencias y largos promedio,
    desglose por modelo sombreado y las ultimas comparaciones lado a lado —
    la materia prima para decidir si el alternativo rinde.

    Args:
        last: Cuantas comparaciones recientes incluir con texto (0 = ninguna).
        log_path: Override del path del JSONL (tests).

    Returns:
        Dict con ``total``, ``shadow_ok``, ``shadow_failed``,
        ``avg_latency_ms``, ``avg_text_chars``, ``by_shadow_model`` y
        ``recent``.
    """
    from core import proxy_state

    path = log_path or proxy_state.state_path().parent / "shadow_log.jsonl"
    records: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                continue  # linea corrupta (write parcial): se ignora, no se rompe
            if isinstance(rec, dict):
                records.append(rec)

    ok = [r for r in records if r.get("shadow_status") == 200]

    def _avg(values: list) -> int | None:
        nums = [v for v in values if isinstance(v, int | float)]
        return round(sum(nums) / len(nums)) if nums else None

    by_model: dict[str, int] = {}
    for r in records:
        key = f"{r.get('shadow_provider') or '?'}/{r.get('shadow_model') or '?'}"
        by_model[key] = by_model.get(key, 0) + 1

    return {
        "log_path": str(path),
        "total": len(records),
        "shadow_ok": len(ok),
        "shadow_failed": len(records) - len(ok),
        "avg_latency_ms": {
            "claude": _avg([r.get("claude_latency_ms") for r in records]),
            "shadow": _avg([r.get("shadow_latency_ms") for r in ok]),
        },
        "avg_text_chars": {
            "claude": _avg([len(r.get("claude_text") or "") for r in records]),
            "shadow": _avg([len(r.get("shadow_text") or "") for r in ok]),
        },
        "by_shadow_model": by_model,
        "recent": records[-last:] if last > 0 else [],
    }


def resolve_provider_model(provider_id: str) -> str:
    """Resuelve el modelo default de un provider SIN salir a la red (hot path).

    Para el proxy (routing por clase, que corre en cada request): aplica solo
    override env -> cache compartido -> el mas nuevo de la lista conocida. El
    fetch real lo disparan el switch o el CLI, nunca este camino.

    Args:
        provider_id: Id del provider (``minimax``, ``zai``, ...).

    Returns:
        Id del modelo, o cadena vacia si el provider es desconocido.
    """
    from core import model_resolver

    pid = normalize_provider_id(provider_id)
    cfg = PROVIDERS.get(pid)
    if cfg is None:
        return ""
    return model_resolver.resolve_default_model(
        pid,
        known_models=cfg.models,
        fallback=cfg.default_model,
        family=cfg.family,
        # Sin base_url/api_key: el fetch queda deshabilitado por diseno.
    )


def list_models(
    provider_id: str,
    root: Path | None = None,
    allow_fetch: bool = True,
) -> list[str]:
    """Lista los modelos de un provider (dinamica: cache -> fetch -> conocida).

    Para providers con familia declarada (minimax/zai) la lista ya NO es la
    constante hardcodeada: se resuelve con la misma cascada del default
    (cache compartido -> ``/v1/models`` real del provider -> lista conocida
    como fallback offline). Providers "libres" (claude, ollama, lmstudio)
    siguen devolviendo vacio; los sin familia devuelven su lista estatica.

    Args:
        provider_id: Id del provider (``minimax``, ``zai``, ...).
        root: Raiz del proyecto para leer la API key del ``.env`` (default: auto).
        allow_fetch: ``False`` para contextos no bloqueantes (overview/UI).

    Returns:
        Ids ordenados newest-first, o vacia si el provider es libre/desconocido.
    """
    from core import model_resolver

    pid = normalize_provider_id(provider_id)
    cfg = PROVIDERS.get(pid)
    if cfg is None:
        return []
    if not cfg.family:
        # Sin familia no hay discovery confiable: estatica tal cual (o "libre").
        return list(cfg.models)

    api_key = None
    if cfg.api_key_env:
        api_key = get_api_key_from_env(root or default_root(), cfg.api_key_env)
    return model_resolver.resolve_models(
        pid,
        known_models=cfg.models,
        base_url=cfg.base_url,
        api_key=api_key,
        family=cfg.family,
        allow_fetch=allow_fetch,
    )


def discover_models(provider_id: str, root: Path | None = None) -> dict:
    """Descubre EN VIVO los modelos del provider (diagnostico del resolver dinamico).

    Pega a los endpoints reales del provider y reporta que encontro y cual elegiria
    como default. Util para verificar que el autodetect funciona en una maquina con
    red (no modifica estado ni cache de switch).

    Args:
        provider_id: Id del provider (``minimax``, ``zai``, ...).
        root: Raiz del proyecto (para leer la API key del .env).

    Returns:
        Dict con ``provider``, ``live`` (bool, si la red devolvio algo), ``best``
        (el que se elegiria) y ``models`` (lista descubierta o la conocida si offline).

    Raises:
        ProviderError: provider desconocido.
    """
    from core import model_resolver

    root = root or default_root()
    pid = normalize_provider_id(provider_id)
    cfg = PROVIDERS.get(pid)
    if cfg is None:
        raise ProviderError(f"Provider desconocido: {provider_id}")

    api_key = get_api_key_from_env(root, cfg.api_key_env) if cfg.api_key_env else None
    entries = model_resolver.fetch_remote_models(pid, cfg.base_url, api_key) if api_key else []
    live_ids = [mid for mid, _ in entries]
    best = model_resolver.best_entry(entries, cfg.family) if entries else None
    return {
        "provider": pid,
        "live": bool(live_ids),
        "best": best or model_resolver.latest_model(list(cfg.models), cfg.family),
        "models": live_ids or list(cfg.models),
    }


def set_hotswap(provider_id: str, model: str | None = None, root: Path | None = None) -> dict:
    """Cambia el backend activo del proxy (hot-swap, sin reiniciar Claude Code).

    Para providers alternativos solo escribe proxy_state; no modifica settings.json,
    y requiere que el proxy ya este conectado (ANTHROPIC_BASE_URL == PROXY_BASE_URL).
    Para ``provider_id="claude"`` activa el modo proxy-always (Claude via passthrough
    OAuth del gateway); nunca requiere reiniciar Claude Code.

    Args:
        provider_id: claude | minimax | zai | nvidia | ollama | lmstudio.
        model: Modelo (default: el del provider).
        root: Raiz del proyecto (default: auto).

    Returns:
        Estado del hot-swap aplicado.

    Raises:
        ProviderError: provider/modelo invalido o API key faltante.
    """
    from core import proxy_state

    root = root or default_root()
    pid = normalize_provider_id(provider_id)
    cfg = PROVIDERS.get(pid)
    if cfg is None:
        raise ProviderError(f"Provider desconocido: {provider_id}")
    if pid not in PROXY_ROUTABLE:
        raise ProviderError(
            f"{cfg.name} no se puede enrutar por el proxy todavia "
            f"(formato OpenAI remoto sin bridge de traduccion). "
            f"Routables: {list(PROXY_ROUTABLE)}."
        )
    if pid == "claude":
        # Hot-swap a Claude via proxy (proxy-always): passthrough OAuth al gateway.
        # Sin reinicio de Claude Code (la base URL no cambia).
        return _activate_claude_via_proxy(root)
    if cfg.api_key_env and not get_api_key_from_env(root, cfg.api_key_env):
        raise ProviderError(f"{cfg.api_key_env} no encontrada en {root / '.env'}")
    chosen = _resolve_model(cfg, model, root)
    proxy_state.set_active(pid, chosen)
    # proxy_connected real: el hot-swap solo tiene efecto si CC apunta al proxy.
    env = _read_json(user_settings_path()).get("env") or {}
    connected = env.get("ANTHROPIC_BASE_URL") == PROXY_BASE_URL
    logger.info("Hot-swap a %s (%s), proxy_connected=%s", cfg.name, chosen, connected)
    diagnosis = (
        f"Hot-swap a {cfg.name} ({chosen}). Efectivo en el proximo prompt, sin reiniciar."
        if connected
        else (
            f"Backend {cfg.name} ({chosen}) escrito en proxy_state, pero el proxy NO esta "
            f"conectado (ANTHROPIC_BASE_URL != proxy). Conecta con switch_provider y reinicia "
            f"Claude Code una vez."
        )
    )
    return {
        "hotswap": True,
        "active_provider": pid,
        "active_provider_name": cfg.name,
        "active_model": chosen,
        "proxy_connected": connected,
        "needs_restart": False,
        "diagnosis": diagnosis,
        "settings_path": str(proxy_state.state_path()),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def _print_human(result: dict, cmd: str) -> None:
    """Imprime un resumen legible del resultado."""
    if cmd == "models":
        models = result.get("models", [])
        print(f"Modelos de {result.get('provider')}: {', '.join(models) or '(libre)'}")
        if "best" in result:
            origen = "en vivo del provider" if result.get("live") else "fallback (sin red)"
            print(f"Elegiria por defecto : {result['best']}  [{origen}]")
        return
    if cmd == "shadow" and "total" in result:
        total = result["total"]
        if not total:
            print("Shadow report: sin comparaciones registradas todavia.")
            print(f"log: {result.get('log_path')}")
            return
        lat = result["avg_latency_ms"]
        chars = result["avg_text_chars"]
        print(
            f"Shadow report — {total} comparaciones "
            f"({result['shadow_ok']} ok, {result['shadow_failed']} fallidas)"
        )
        print(
            f"  latencia promedio : claude {lat['claude'] or '?'}ms vs shadow {lat['shadow'] or '?'}ms"
        )
        print(
            f"  largo promedio    : claude {chars['claude'] or '?'} chars vs shadow {chars['shadow'] or '?'} chars"
        )
        for key, count in sorted(result["by_shadow_model"].items()):
            print(f"  {key}: {count}")
        for rec in result.get("recent", []):
            prompt = (rec.get("prompt_tail") or "").replace("\n", " ")[:80]
            print(f"\n  [{rec.get('ts')}] prompt: {prompt}")
            claude_text = (rec.get("claude_text") or "").replace("\n", " ")[:160]
            shadow_text = (rec.get("shadow_text") or "").replace("\n", " ")[:160]
            print(
                f"    claude ({rec.get('claude_model')}, {rec.get('claude_latency_ms')}ms): {claude_text}"
            )
            if rec.get("shadow_status") == 200:
                print(
                    f"    shadow ({rec.get('shadow_model')}, {rec.get('shadow_latency_ms')}ms): {shadow_text}"
                )
            else:
                err = (rec.get("shadow_error") or "")[:120]
                print(
                    f"    shadow ({rec.get('shadow_model')}): FALLO status={rec.get('shadow_status')} {err}"
                )
        print(f"\nlog: {result.get('log_path')}")
        return
    if cmd == "shadow":
        st = result.get("shadow", {})
        if st.get("enabled"):
            model = st.get("model") or "(default del provider)"
            print(f"Shadow mode: ON -> {st.get('provider')} {model}")
            print("Cada turno de Claude se duplica al alternativo para comparar.")
        else:
            print("Shadow mode: OFF (modo normal, sin costo extra)")
        print(f"log de comparaciones: {result.get('log_path')}")
        return
    if cmd == "route":
        routes = result.get("routes", {})
        if not routes:
            print("Routing por clase: (vacio - todo el trafico va al backend activo)")
        else:
            print("Routing por clase de modelo:")
            for cls, entry in routes.items():
                model = entry.get("model") or "(default del provider)"
                print(f"  {cls:<7} -> {entry.get('provider'):<8} {model}")
        print(f"archivo: {result.get('routing_path')}")
        return
    print(f"Provider activo : {result['active_provider_name']} ({result['active_provider']})")
    print(f"Modelo          : {result['active_model']}")
    print(f"Proxy conectado : {result.get('proxy_connected', False)}")
    if result.get("needs_restart"):
        print("AVISO           : Reiniciar Claude Code para que tome efecto.")
    print(f"Diagnostico     : {result['diagnosis']}")
    print(f"settings        : {result['settings_path']}")
    if "providers" not in result:  # scope project: no hay lista global de providers
        return
    print("Providers:")
    for p in result["providers"]:
        mark = "*" if p["active"] else " "
        key = "" if p["has_api_key"] else "  (sin API key)"
        print(f"  {mark} {p['id']:<9} {p['name']}{key}")


def main(argv: list[str] | None = None) -> int:
    """Entry point de la CLI."""
    parser = argparse.ArgumentParser(
        description="Conmuta el provider IA de Claude Code via proxy (modelo proxy-always)."
    )
    parser.add_argument("--root", default=None, help="Antigravity root (default: auto)")
    parser.add_argument("--json", action="store_true", help="Salida JSON cruda")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Mostrar provider activo + lista")

    switch = sub.add_parser("switch", help="Activar un provider por hot-swap via proxy")
    switch.add_argument("provider", help="claude|minimax|zai|nvidia|ollama|lmstudio")
    switch.add_argument("--model", default=None, help="Modelo (default: el del provider)")
    switch.add_argument(
        "--scope",
        choices=("global", "project"),
        default="global",
        help="global (~/.claude) o project (override local en settings.local.json)",
    )

    disable = sub.add_parser("disable", help="Hot-swap a Claude nativo (proxy sigue conectado)")
    disable.add_argument(
        "--scope",
        choices=("global", "project"),
        default="global",
        help="global o project (quita solo el override del proyecto)",
    )

    models_cmd = sub.add_parser("models", help="Listar modelos de un provider")
    models_cmd.add_argument("provider")
    models_cmd.add_argument(
        "--live",
        action="store_true",
        help="Descubrir en vivo via /v1/models del provider (verifica el autodetect)",
    )

    hotswap = sub.add_parser(
        "hotswap", help="Cambiar backend del proxy en caliente (solo proxy_state)"
    )
    hotswap.add_argument("provider", help="claude|minimax|zai|nvidia|ollama|lmstudio")
    hotswap.add_argument("--model", default=None, help="Modelo (default: el del provider)")

    connect = sub.add_parser(
        "connect",
        help="Conectar el proxy (setea ANTHROPIC_BASE_URL al proxy) + opcional hot-swap",
    )
    connect.add_argument(
        "provider",
        nargs="?",
        default=None,
        help="Provider a activar (default: claude). Mismo efecto que switch.",
    )
    connect.add_argument("--model", default=None, help="Modelo (default: el del provider)")

    sub.add_parser(
        "disconnect",
        help="Desconectar el proxy y volver a Claude nativo puro (requiere reinicio)",
    )

    route = sub.add_parser(
        "route",
        help="Routing por clase de modelo: el trafico haiku/sonnet/opus a otro backend",
    )
    route.add_argument(
        "model_class",
        nargs="?",
        default=None,
        help="haiku|sonnet|opus (vacio: mostrar routing actual)",
    )
    route.add_argument(
        "provider",
        nargs="?",
        default=None,
        help="Backend destino (claude|minimax|zai)",
    )
    route.add_argument(
        "model",
        nargs="?",
        default=None,
        help="Modelo en el destino (default: el mas nuevo del provider)",
    )
    route.add_argument(
        "--clear",
        action="store_true",
        help="Borrar la ruta de la clase dada (o todas si no se da clase)",
    )

    shadow = sub.add_parser(
        "shadow",
        help="Shadow mode ON/OFF: duplicar turnos de Claude al alternativo para comparar",
    )
    shadow.add_argument(
        "action",
        nargs="?",
        default="status",
        help="on | off | status | report (default: status)",
    )
    shadow.add_argument(
        "provider",
        nargs="?",
        default=None,
        help="Backend a sombrear con 'on' (default: zai)",
    )
    shadow.add_argument("--model", default=None, help="Modelo del shadow (default: auto)")
    shadow.add_argument(
        "--last",
        type=int,
        default=3,
        help="Comparaciones recientes a mostrar en 'report' (default: 3)",
    )

    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else default_root()

    try:
        if args.cmd == "status":
            result = get_overview(root)
        elif args.cmd == "switch":
            result = switch_provider(args.provider, args.model, root, scope=args.scope)
        elif args.cmd == "disable":
            result = disable_provider(root, scope=args.scope)
        elif args.cmd == "models":
            if getattr(args, "live", False):
                result = discover_models(args.provider, root)
            else:
                result = {"provider": args.provider.lower(), "models": list_models(args.provider)}
        elif args.cmd == "hotswap":
            result = set_hotswap(args.provider, args.model, root)
        elif args.cmd == "connect":
            provider = args.provider or "claude"
            result = switch_provider(provider, getattr(args, "model", None), root)
        elif args.cmd == "disconnect":
            result = disconnect_proxy(root)
        elif args.cmd == "route":
            if args.clear:
                result = clear_class_route(args.model_class)
            elif args.model_class and args.provider:
                result = route_class(args.model_class, args.provider, args.model)
            elif args.model_class:
                parser.error("falta el provider destino (route <clase> <provider> [modelo])")
                return 2
            else:
                result = get_class_routes()
        elif args.cmd == "shadow":
            if args.action.strip().lower() == "report":
                result = shadow_report(max(args.last, 0))
            else:
                result = shadow_mode(args.action, args.provider, args.model)
        else:  # pragma: no cover
            parser.error("comando desconocido")
            return 2
    except ProviderError as exc:
        logger.error("%s", exc)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result, args.cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
