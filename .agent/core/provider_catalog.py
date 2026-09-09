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

VALID_PROTOCOLS = frozenset(
    {"anthropic_messages", "openai_chat", "openai_responses", "local_openai"}
)
VALID_TRANSPORTS = frozenset({"remote", "loopback", "native"})
VALID_REMOTE_CONTROL = frozenset({"native_only", "current_session", "unsupported"})
VALID_CATEGORIES = frozenset({"native", "cloud", "aggregator", "local", "bridge"})


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
        auth_mode: Mecanismo de acceso mostrado por Nexus
            (``oauth`` | ``oauth_bridge`` | ``api_key`` | ``local``).
        setup_hint: Instruccion breve y segura para habilitar el provider.
        protocol: Contrato de payload del upstream, mas preciso que ``wire``.
        transport: Donde vive el upstream (remoto, loopback o cliente nativo).
        remote_control: Compatibilidad con el Remote Control de la sesion actual.
        category: Grupo de presentación en Nexus.
        default_visible: Si Nexus muestra el provider en la lista compacta inicial.
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
    auth_mode: str = "api_key"
    setup_hint: str = ""
    protocol: str = "anthropic_messages"
    transport: str = "remote"
    remote_control: str = "current_session"
    category: str = "cloud"
    default_visible: bool = False


# Dict embebido de fallback: replica EXACTAMENTE el catalogo de
# ``.antigravity/providers.json``. Es la red de seguridad si el JSON falta o esta corrupto;
# garantiza que ``provider_switch.PROVIDERS`` siempre tenga un valor valido. Mantener en
# sync con el JSON (el test de paridad lo verifica).
_EMBEDDED_PROVIDERS: dict[str, ProviderConfig] = {
    "claude": ProviderConfig(
        "claude",
        "Claude (Anthropic)",
        "",
        "",
        "claude-sonnet-4-6",
        auth_mode="oauth",
        setup_hint="Usa la sesión OAuth de Claude Code; no necesita API key.",
        protocol="anthropic_messages",
        transport="native",
        remote_control="native_only",
        category="native",
        default_visible=True,
    ),
    "openai": ProviderConfig(
        "openai",
        "OpenAI API",
        "https://api.openai.com/v1",
        "OPENAI_API_KEY",
        "gpt-4o",
        ("gpt-4o", "gpt-4o-mini"),
        wire="openai",
        setup_hint=(
            "Configura OPENAI_API_KEY. Este camino usa Chat Completions; "
            "GPT-5.6 Sol requiere el flujo Responses/Codex."
        ),
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "gemini": ProviderConfig(
        "gemini",
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_API_KEY",
        "gemini-3.6-flash",
        ("gemini-3.6-flash",),
        wire="openai",
        setup_hint="Configura GEMINI_API_KEY desde Google AI Studio.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
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
        protocol="anthropic_messages",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
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
        protocol="anthropic_messages",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "deepseek": ProviderConfig(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com",
        "DEEPSEEK_API_KEY",
        "deepseek-v4-pro",
        ("deepseek-v4-pro", "deepseek-v4-flash"),
        wire="openai",
        setup_hint="Configura DEEPSEEK_API_KEY; usa modelos V4 vigentes.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "groq": ProviderConfig(
        "groq",
        "Groq",
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
        "openai/gpt-oss-120b",
        ("openai/gpt-oss-120b", "llama-3.3-70b-versatile"),
        wire="openai",
        setup_hint="Configura GROQ_API_KEY desde Groq Console.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "mistral": ProviderConfig(
        "mistral",
        "Mistral AI",
        "https://api.mistral.ai/v1",
        "MISTRAL_API_KEY",
        "mistral-large-latest",
        ("mistral-large-latest", "mistral-small-latest"),
        wire="openai",
        setup_hint="Configura MISTRAL_API_KEY desde La Plateforme.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "xai": ProviderConfig(
        "xai",
        "xAI",
        "https://api.x.ai/v1",
        "XAI_API_KEY",
        "grok-4.5",
        ("grok-4.5",),
        wire="openai",
        setup_hint="Configura XAI_API_KEY desde xAI Console.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "nvidia": ProviderConfig(
        "nvidia",
        "NVIDIA NIM",
        "https://integrate.api.nvidia.com/v1",
        "NVIDIA_API_KEY",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        wire="openai",
        routable=True,
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "cerebras": ProviderConfig(
        "cerebras",
        "Cerebras Inference",
        "https://api.cerebras.ai/v1",
        "CEREBRAS_API_KEY",
        "gpt-oss-120b",
        ("gpt-oss-120b", "zai-glm-4.7"),
        wire="openai",
        setup_hint="Configura CEREBRAS_API_KEY desde Cerebras Cloud.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "together": ProviderConfig(
        "together",
        "Together AI",
        "https://api.together.xyz/v1",
        "TOGETHER_API_KEY",
        "Qwen/Qwen3.5-9B",
        (
            "Qwen/Qwen3.5-9B",
            "moonshotai/Kimi-K2.6",
            "deepseek-ai/DeepSeek-V4-Pro",
        ),
        wire="openai",
        setup_hint="Configura TOGETHER_API_KEY; revisa deprecaciones del catálogo.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "fireworks": ProviderConfig(
        "fireworks",
        "Fireworks AI",
        "https://api.fireworks.ai/inference/v1",
        "FIREWORKS_API_KEY",
        "accounts/fireworks/models/kimi-k2-instruct-0905",
        ("accounts/fireworks/models/kimi-k2-instruct-0905",),
        wire="openai",
        setup_hint="Configura FIREWORKS_API_KEY desde Fireworks AI.",
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="cloud",
        default_visible=False,
    ),
    "huggingface": ProviderConfig(
        "huggingface",
        "Hugging Face Router",
        "https://router.huggingface.co/v1",
        "HF_TOKEN",
        "openai/gpt-oss-120b:fastest",
        (
            "openai/gpt-oss-120b:fastest",
            "deepseek-ai/DeepSeek-V4-Pro:fastest",
        ),
        wire="openai",
        setup_hint=(
            "Configura HF_TOKEN con permiso para Inference Providers; "
            "puedes usar sufijos :fastest, :cheapest o :preferred."
        ),
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="aggregator",
        default_visible=False,
    ),
    "ollama": ProviderConfig(
        "ollama",
        "Ollama (local)",
        "http://localhost:11434",
        "",
        "llama3",
        wire="openai",
        auth_mode="local",
        setup_hint="Inicia Ollama y carga un modelo de chat con soporte de herramientas.",
        protocol="local_openai",
        transport="loopback",
        remote_control="current_session",
        category="local",
        default_visible=True,
    ),
    "lmstudio": ProviderConfig(
        "lmstudio",
        "LM Studio (local)",
        "http://localhost:1234/v1",
        "",
        "lmstudio-model",
        wire="openai",
        auth_mode="local",
        setup_hint="Inicia el servidor local OpenAI-compatible de LM Studio.",
        protocol="local_openai",
        transport="loopback",
        remote_control="current_session",
        category="local",
        default_visible=True,
    ),
    "opencodex": ProviderConfig(
        "opencodex",
        "OpenAI / Codex OAuth",
        "http://127.0.0.1:10100/v1",
        "",
        "gpt-5.6-sol",
        (
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
            "gpt-5.5",
            "gpt-5.3-codex-spark",
        ),
        wire="openai",
        auth_mode="oauth_bridge",
        setup_hint=(
            "Usa el inicio de sesión ChatGPT de Codex mediante el puente local "
            "OpenCodex; requiere que el servicio escuche en :10100."
        ),
        # El router actual envia /v1/chat/completions. Declarar Responses sin
        # un adaptador real haria que la UI prometiera una compatibilidad falsa.
        protocol="openai_chat",
        transport="loopback",
        remote_control="current_session",
        category="bridge",
        default_visible=True,
    ),
    "antigravity": ProviderConfig(
        "antigravity",
        "Google Antigravity (OAuth)",
        "http://127.0.0.1:10100/v1",
        "",
        "google-antigravity/gemini-3.6-flash",
        (
            "google-antigravity/gemini-3.6-flash",
            "google-antigravity/gemini-3.1-pro",
            "google-antigravity/claude-sonnet-4-6",
            "google-antigravity/claude-opus-4-6-thinking",
            "google-antigravity/gpt-oss-120b-medium",
        ),
        family="google-antigravity",
        wire="openai",
        auth_mode="oauth_bridge",
        setup_hint=(
            "Inicia OAuth de Google Antigravity desde OpenCodex. Nexus no guarda ni "
            "muestra el token; esta integración externa puede estar sujeta a las "
            "condiciones de Google."
        ),
        protocol="openai_chat",
        transport="loopback",
        remote_control="current_session",
        category="bridge",
        default_visible=False,
    ),
    "github-copilot": ProviderConfig(
        "github-copilot",
        "GitHub Copilot (OAuth)",
        "http://127.0.0.1:10100/v1",
        "",
        "github-copilot/claude-sonnet-4",
        (
            "github-copilot/claude-sonnet-4",
            "github-copilot/gemini-2.5-pro",
            "github-copilot/gpt-4.1",
            "github-copilot/gpt-4.1-mini",
            "github-copilot/gpt-4o",
        ),
        family="github-copilot",
        wire="openai",
        auth_mode="oauth_bridge",
        setup_hint=(
            "Inicia OAuth de GitHub Copilot desde OpenCodex. Nexus no guarda ni muestra el token."
        ),
        protocol="openai_chat",
        transport="loopback",
        remote_control="current_session",
        category="bridge",
        default_visible=False,
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
        family="",
        wire="openai",
        routable=True,
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="aggregator",
        default_visible=True,
    ),
    "opencode": ProviderConfig(
        "opencode",
        "OpenCode Go (remoto)",
        "https://opencode.ai/zen/go/v1",
        "OPENCODE_API_KEY",
        "glm-5.2",
        (
            "glm-5.2",
            "kimi-k3",
            "kimi-k2.7-code",
            "kimi-k2.6",
            "glm-5.1",
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "mimo-v2.5-pro",
            "mimo-v2.5",
            "hy3",
            "grok-4.5",
        ),
        family="",
        wire="openai",
        routable=True,
        setup_hint=(
            "Plan OpenCode Go. Nexus solo muestra los modelos Chat verificados; "
            "usa OpenCode directo para los modelos Zen con otros protocolos."
        ),
        protocol="openai_chat",
        transport="remote",
        remote_control="current_session",
        category="aggregator",
        default_visible=True,
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
            "auth_mode": cfg.auth_mode,
            "setup_hint": cfg.setup_hint,
            "protocol": cfg.protocol,
            "transport": cfg.transport,
            "remote_control": cfg.remote_control,
            "category": cfg.category,
            "default_visible": cfg.default_visible,
            "models": models,
        }
    return {"version": 1, "order": list(_EMBEDDED_PROVIDERS), "providers": providers}


def _validated_enum(
    entry: dict,
    field: str,
    allowed: frozenset[str],
    default: str,
) -> str:
    """Valida un campo contractual del catalogo sin aceptar valores ambiguos."""
    value = str(entry.get(field) or default)
    if value not in allowed:
        raise ValueError(f"{field} desconocido para provider: {value}")
    return value


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

    wire = str(entry.get("wire") or "anthropic")
    base_url = str(entry.get("base_url") or "")
    default_protocol = "anthropic_messages" if wire == "anthropic" else "openai_chat"
    default_transport = (
        "native"
        if not base_url
        else "loopback"
        if any(host in base_url for host in ("localhost", "127.0.0.1", "::1"))
        else "remote"
    )
    default_remote_control = "native_only" if pid == "claude" else "current_session"

    return ProviderConfig(
        id=pid,
        name=str(entry.get("label") or pid),
        base_url=base_url,
        api_key_env=str(entry.get("api_key_env") or ""),
        default_model=default_model,
        models=tuple(model_ids),
        family=str(entry.get("family") or ""),
        wire=wire,
        routable=bool(entry.get("routable", True)),
        auth_mode=str(entry.get("auth_mode") or "api_key"),
        setup_hint=str(entry.get("setup_hint") or ""),
        protocol=_validated_enum(entry, "protocol", VALID_PROTOCOLS, default_protocol),
        transport=_validated_enum(entry, "transport", VALID_TRANSPORTS, default_transport),
        remote_control=_validated_enum(
            entry,
            "remote_control",
            VALID_REMOTE_CONTROL,
            default_remote_control,
        ),
        category=_validated_enum(
            entry,
            "category",
            VALID_CATEGORIES,
            "cloud",
        ),
        default_visible=bool(entry.get("default_visible", False)),
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
        try:
            result[pid] = _provider_from_entry(pid, entry)
        except ValueError as exc:
            logger.warning(
                "Contrato invalido en provider %s (%s); usando catalogo embebido completo.",
                pid,
                exc,
            )
            return dict(_EMBEDDED_PROVIDERS)

    if not result:
        logger.warning("Catalogo de providers no produjo entradas validas; usando embebido.")
        return dict(_EMBEDDED_PROVIDERS)
    return result
