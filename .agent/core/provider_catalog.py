"""Catalogo declarativo de providers — fuente unica de verdad.

Carga el catalogo de providers/modelos desde ``.antigravity/providers.json`` (versionado
en git) y construye el dict ``{id: ProviderConfig}`` que consume ``provider_switch``. Es la
fuente unica de verdad declarativa: editar el JSON (no el codigo) para agregar/cambiar
providers o modelos.

Diseno de imports: la dataclass ``ProviderConfig`` vive AQUI (no en ``provider_switch``)
para romper el ciclo ``provider_switch -> provider_catalog -> provider_switch``.
``provider_switch`` la reexporta por compatibilidad hacia atras. Asi el catalogo no importa
``provider_switch`` y no hay import circular.

Resolucion del path del catalogo (3-tier):
    1. Parametro explicito ``path``.
    2. Env ``ANTIGRAVITY_PROVIDERS_PATH``.
    3. ``<repo_root>/.antigravity/providers.json`` (repo_root via ``ANTIGRAVITY_ROOT`` o
       inferido desde la ubicacion del modulo, igual que ``provider_switch.default_root``).

Degradacion robusta: si el JSON falta, esta corrupto, o no tiene la forma esperada, se
loguea un WARN y se cae al dict embebido (``_EMBEDDED_PROVIDERS``), que replica fielmente
el dict historico de ``provider_switch.PROVIDERS``. NUNCA crashea en import time.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderConfig:
    """Configuracion estatica de un provider IA.

    Args:
        id: Identificador en minusculas (claude, minimax, zai, ...).
        name: Nombre legible para mostrar.
        base_url: URL directa del provider (usada por el proxy; NO se escribe en el env).
        api_key_env: Nombre de la env var en el .env con la API key ("" si no aplica).
        default_model: Modelo por defecto si no se especifica uno.
        models: Modelos validos conocidos (vacio = se acepta cualquier modelo).
        family: Familia del provider para el resolver dinamico de modelos ("" si no aplica).
        wire: Protocolo nativo del provider ("anthropic" | "openai"). De aca deriva
            ``provider_router.is_openai_compatible`` (openai => requiere traduccion).
        routable: Si el proxy lo puede activar como backend (default True). De aca deriva
            ``provider_switch.PROXY_ROUTABLE``.
    """

    id: str
    name: str
    base_url: str
    api_key_env: str
    default_model: str
    models: tuple[str, ...] = ()
    family: str = ""
    wire: str = "anthropic"
    routable: bool = True


# Dict embebido de fallback: replica EXACTAMENTE el catalogo de
# ``.antigravity/providers.json``. Es la red de seguridad si el JSON falta o esta corrupto;
# garantiza que ``provider_switch.PROVIDERS`` siempre tenga un valor valido. Mantener en
# sync con el JSON (el test de paridad lo verifica).
_EMBEDDED_PROVIDERS: dict[str, ProviderConfig] = {
    "claude": ProviderConfig("claude", "Claude (Anthropic)", "", "", "claude-sonnet-4-6"),
    "minimax": ProviderConfig(
        "minimax",
        "MiniMax",
        "https://api.minimax.io/anthropic",
        "MINIMAX_API_KEY",
        "MiniMax-M2.7",
        (
            "MiniMax-M3",
            "MiniMax-M2.7",
            "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5",
            "MiniMax-M2.5-highspeed",
            "MiniMax-M2.1",
            "MiniMax-M2.1-highspeed",
            "MiniMax-M2",
        ),
        family="MiniMax",
    ),
    "zai": ProviderConfig(
        "zai",
        "z.ai (GLM)",
        "https://api.z.ai/api/anthropic",
        "ZAI_API_KEY",
        "glm-5.2",
        (
            "glm-5.2",
            "glm-5.1",
            "glm-5-turbo",
            "glm-5",
            "glm-4.7",
            "glm-4.6",
            "glm-4.5",
            "glm-4.5-air",
        ),
        family="glm",
    ),
    "nvidia": ProviderConfig(
        "nvidia",
        "NVIDIA NIM",
        "https://integrate.api.nvidia.com/v1",
        "NVIDIA_API_KEY",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        wire="openai",
        routable=True,
    ),
    "ollama": ProviderConfig(
        "ollama", "Ollama (local)", "http://localhost:11434", "", "llama3", wire="openai"
    ),
    "lmstudio": ProviderConfig(
        "lmstudio",
        "LM Studio (local)",
        "http://localhost:1234/v1",
        "",
        "lmstudio-model",
        wire="openai",
    ),
    "opencodex": ProviderConfig(
        "opencodex",
        "OpenCodex Bridge (opcional)",
        "http://127.0.0.1:10100/v1",
        "",
        "default",
        wire="openai",
    ),
    "openrouter": ProviderConfig(
        "openrouter",
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        "qwen/qwen3-coder:free",
        (
            "qwen/qwen3-coder:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "anthropic/claude-opus-4.8",
            "anthropic/claude-sonnet-4.6",
            "deepseek/deepseek-v4-pro",
            "google/gemini-3.1-pro-preview",
        ),
        family="openrouter",
        wire="openai",
        routable=True,
    ),
    "opencode": ProviderConfig(
        "opencode",
        "OpenCode Go",
        "https://opencode.ai/zen/go/v1",
        "OPENCODE_API_KEY",
        "kimi-k2.7-code",
        (
            "kimi-k2.7-code",
            "glm-5.2",
            "glm-5.1",
            "glm-5",
            "minimax-m3",
            "minimax-m2.7",
            "minimax-m2.5",
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "qwen3.7-max",
            "qwen3.7-plus",
            "qwen3.6-plus",
            "qwen3.5-plus",
            "kimi-k2.6",
            "kimi-k2.5",
            "mimo-v2.5-pro",
            "mimo-v2.5",
            "mimo-v2-pro",
            "mimo-v2-omni",
            "hy3-preview",
        ),
        family="opencode",
        wire="openai",
        routable=True,
    ),
}


def _repo_root() -> Path:
    """Resuelve la raiz del repo para ubicar el catalogo por defecto.

    Mismo patron que ``provider_switch.default_root``: ``ANTIGRAVITY_ROOT`` si esta seteada,
    si no infiere desde la ubicacion del modulo (``.agent/core/`` -> raiz dos niveles arriba).

    Returns:
        Path a la raiz del repo.
    """
    env = os.environ.get("ANTIGRAVITY_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def default_catalog_path() -> Path:
    """Resuelve el path del catalogo de providers (3-tier, sin el override por parametro).

    Returns:
        Env ``ANTIGRAVITY_PROVIDERS_PATH`` si esta seteada; si no,
        ``<repo_root>/.antigravity/providers.json``.
    """
    override = os.environ.get("ANTIGRAVITY_PROVIDERS_PATH")
    if override:
        return Path(override)
    return _repo_root() / ".antigravity" / "providers.json"


def load_catalog(path: Path | None = None) -> dict:
    """Carga el catalogo declarativo crudo desde el JSON.

    Resolucion 3-tier: ``path`` explicito > env ``ANTIGRAVITY_PROVIDERS_PATH`` >
    ``<repo_root>/.antigravity/providers.json``.

    Args:
        path: Override explicito del path del catalogo (default: 3-tier).

    Returns:
        El dict crudo del catalogo (claves ``version`` y ``providers``). Si el archivo
        falta, esta corrupto, o no tiene la forma esperada, devuelve un catalogo derivado
        del dict embebido (nunca crashea).
    """
    resolved = path or default_catalog_path()
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "No se pudo leer el catalogo de providers en %s (%s); usando dict embebido.",
            resolved,
            exc,
        )
        return _embedded_catalog()

    if not isinstance(raw, dict) or not isinstance(raw.get("providers"), dict):
        logger.warning(
            "Catalogo de providers en %s con forma invalida; usando dict embebido.",
            resolved,
        )
        return _embedded_catalog()
    return raw


def _embedded_catalog() -> dict:
    """Construye el catalogo crudo a partir del dict embebido (forma del JSON).

    Returns:
        Dict con ``version`` y ``providers`` equivalente al JSON, derivado de
        ``_EMBEDDED_PROVIDERS``.
    """
    providers: dict[str, dict] = {}
    for pid, cfg in _EMBEDDED_PROVIDERS.items():
        if cfg.models:
            models = [
                {"id": mid, **({"default": True} if mid == cfg.default_model else {})}
                for mid in cfg.models
            ]
        else:
            # Provider "libre": models conocida vacia; el default va con known=false.
            models = [{"id": cfg.default_model, "default": True, "known": False}]
        providers[pid] = {
            "label": cfg.name,
            "wire": cfg.wire,
            "routable": cfg.routable,
            "base_url": cfg.base_url,
            "api_key_env": cfg.api_key_env,
            "family": cfg.family,
            "models": models,
        }
    return {"version": 1, "order": list(_EMBEDDED_PROVIDERS), "providers": providers}


def _provider_from_entry(pid: str, entry: dict) -> ProviderConfig:
    """Convierte una entrada cruda del catalogo en un ``ProviderConfig``.

    Args:
        pid: Id del provider (clave en el catalogo).
        entry: Dict crudo del provider (label, base_url, api_key_env, family, models).

    Returns:
        El ``ProviderConfig`` equivalente. El ``default_model`` se toma del modelo marcado
        con ``default: true``; si ninguno lo esta, del primero de la lista. Un modelo con
        ``known: false`` aporta el ``default_model`` pero NO entra a la tupla ``models``
        (replica los providers "libres" historicos como claude/ollama, cuya ``models`` era
        vacia aunque tuvieran un ``default_model``).
    """
    raw_models = entry.get("models")
    model_ids: list[str] = []
    default_model = ""
    if isinstance(raw_models, list):
        for m in raw_models:
            if not isinstance(m, dict):
                continue
            mid = m.get("id")
            if not isinstance(mid, str) or not mid:
                continue
            if m.get("default") and not default_model:
                default_model = mid
            # known=false: el modelo es solo el default offline, no una lista conocida.
            if m.get("known", True):
                model_ids.append(mid)
    if not default_model and model_ids:
        default_model = model_ids[0]

    return ProviderConfig(
        id=pid,
        name=str(entry.get("label") or pid),
        base_url=str(entry.get("base_url") or ""),
        api_key_env=str(entry.get("api_key_env") or ""),
        default_model=default_model,
        models=tuple(model_ids),
        family=str(entry.get("family") or ""),
        wire=str(entry.get("wire") or "anthropic"),
        routable=bool(entry.get("routable", True)),
    )


def build_providers(path: Path | None = None) -> dict[str, ProviderConfig]:
    """Construye el dict ``{id: ProviderConfig}`` desde el catalogo declarativo.

    Es la funcion que ``provider_switch`` usa para derivar ``PROVIDERS`` en import time.
    Reutiliza la dataclass ``ProviderConfig`` (definida en este modulo). Degrada con gracia:
    si el catalogo falla o queda vacio, devuelve el dict embebido completo.

    Args:
        path: Override explicito del path del catalogo (default: 3-tier).

    Returns:
        Dict ``{provider_id: ProviderConfig}`` equivalente al ``PROVIDERS`` historico.
    """
    catalog = load_catalog(path)
    providers_raw = catalog.get("providers")
    if not isinstance(providers_raw, dict) or not providers_raw:
        logger.warning("Catalogo de providers vacio o invalido; usando dict embebido.")
        return dict(_EMBEDDED_PROVIDERS)

    result: dict[str, ProviderConfig] = {}
    for pid, entry in providers_raw.items():
        if not isinstance(pid, str) or not isinstance(entry, dict):
            continue
        result[pid] = _provider_from_entry(pid, entry)

    if not result:
        logger.warning("Catalogo de providers no produjo entradas validas; usando embebido.")
        return dict(_EMBEDDED_PROVIDERS)
    return result
