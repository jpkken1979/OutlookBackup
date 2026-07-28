#!/usr/bin/env python3
"""
Antigravity LLM Provider Setup - Interactive configuration wizard.

Authenticates to LLM providers, lists available models,
and saves the selected configuration to .env

Usage:
    python .agent/scripts/setup_llm.py
    python .agent/scripts/setup_llm.py --provider github
    python .agent/scripts/setup_llm.py --provider openrouter --list-models
    python .agent/scripts/setup_llm.py --provider free --list-models
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / ".agent"))

from core.llm import LLMClient, LLMConfig  # noqa: E402

# Provider information for the interactive wizard
PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "signup_url": "https://console.anthropic.com/",
        "auth_type": "api_key",
        "description": "Claude Opus, Sonnet, Haiku. Requiere API key pagada.",
        "default_model": "claude-sonnet-4-20250514",
    },
    "openai": {
        "name": "OpenAI (ChatGPT)",
        "env_key": "OPENAI_API_KEY",
        "signup_url": "https://platform.openai.com/api-keys",
        "auth_type": "api_key",
        "description": "GPT-4o, GPT-4o-mini. Requiere API key pagada.",
        "default_model": "gpt-4o",
    },
    "gemini": {
        "name": "Google Gemini (GRATIS con login Google)",
        "env_key": "GEMINI_API_KEY",
        "signup_url": "https://aistudio.google.com/apikey",
        "auth_type": "api_key",
        "description": "Gemini 2.5 Pro/Flash. API key GRATIS con cuenta Google.",
        "default_model": "gemini-2.0-flash",
    },
    "github": {
        "name": "GitHub Models (GRATIS con tu cuenta GitHub)",
        "env_key": "GITHUB_TOKEN",
        "signup_url": "https://github.com/settings/tokens",
        "auth_type": "token",
        "description": "GPT-4o, Llama, Mistral GRATIS. Usa tu GITHUB_TOKEN.",
        "default_model": "gpt-4o",
    },
    "openrouter": {
        "name": "OpenRouter (300+ modelos, algunos GRATIS)",
        "env_key": "OPENROUTER_API_KEY",
        "signup_url": "https://openrouter.ai/settings/keys",
        "auth_type": "api_key",
        "description": "Acceso a 300+ modelos. Modelos :free son gratis.",
        "default_model": "openrouter/free",
    },
    "kilocode": {
        "name": "Kilo AI ($20 GRATIS al registrarte)",
        "env_key": "KILO_API_KEY",
        "signup_url": "https://kilo.ai",
        "auth_type": "api_key",
        "description": "300+ modelos inc. Claude, GPT. $20 créditos gratis.",
        "default_model": "anthropic/claude-sonnet-4.5",
    },
    "free": {
        "name": "Modo GRATIS (g4f - sin registro)",
        "env_key": None,
        "signup_url": None,
        "auth_type": "none",
        "description": "ChatGPT, Claude, Gemini gratis via g4f. Sin API key.",
        "default_model": "gpt-4o-mini",
    },
    "ollama": {
        "name": "Ollama (modelos locales, GRATIS)",
        "env_key": None,
        "signup_url": "https://ollama.com/download",
        "auth_type": "none",
        "description": "Modelos locales en tu máquina. Totalmente gratis.",
        "default_model": "llama3.1",
    },
}

# Providers that are free / login-based (highlighted)
FREE_PROVIDERS = ["github", "gemini", "free", "ollama", "openrouter", "kilocode"]


def print_header() -> None:
    """Print the setup wizard header."""
    print()
    print("=" * 60)
    print("  ANTIGRAVITY - Configuración de Proveedor LLM")
    print("=" * 60)
    print()


def print_providers() -> None:
    """Print available providers with free options highlighted."""
    print("Proveedores disponibles:\n")

    # Free first
    print("  --- GRATIS / Con Login ---")
    for i, (key, info) in enumerate(PROVIDERS.items(), 1):
        if key in FREE_PROVIDERS:
            marker = " [GRATIS]" if info["auth_type"] == "none" else " [LOGIN]"
            print(f"  {i:2d}. {info['name']}{marker}")
            print(f"      {info['description']}")

    print()
    print("  --- Con API Key ---")
    for i, (key, info) in enumerate(PROVIDERS.items(), 1):
        if key not in FREE_PROVIDERS:
            print(f"  {i:2d}. {info['name']}")
            print(f"      {info['description']}")

    print()


def choose_provider() -> str:
    """Let user choose a provider interactively."""
    provider_keys = list(PROVIDERS.keys())

    while True:
        try:
            choice = input("Elige proveedor (número o nombre, q=salir): ").strip().lower()
            if choice in ("q", "quit", "exit"):
                sys.exit(0)
            if choice in provider_keys:
                return choice
            idx = int(choice) - 1
            if 0 <= idx < len(provider_keys):
                return provider_keys[idx]
        except (ValueError, IndexError):
            pass
        print(f"  Opción inválida. Elige 1-{len(provider_keys)} o el nombre.")


def setup_auth(provider_key: str) -> str | None:
    """Guide user through authentication for the chosen provider."""
    info = PROVIDERS[provider_key]

    if info["auth_type"] == "none":
        if provider_key == "free":
            print("\n  No necesitas nada. g4f funciona sin API key.")
            print("  Instalando g4f si no está...")
            # Cierra el INFO [I1] del reporte 2026-04-11: antes este script
            # usaba `os.system(f"{sys.executable} -m pip install -q g4f[openai]")`
            # que viola la regla `.claude/rules/security.md` (prohibe os.system).
            # Ahora usa subprocess.run con shell=False y argv-as-list.
            import subprocess

            subprocess.run(  # noqa: S603 — args validados, sin shell injection
                [sys.executable, "-m", "pip", "install", "-q", "g4f[openai]"],
                shell=False,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif provider_key == "ollama":
            print("\n  Necesitas Ollama instalado localmente.")
            print(f"  Descárgalo en: {info['signup_url']}")
        return None

    env_key = info["env_key"]
    existing = os.getenv(env_key)

    if existing:
        masked = existing[:8] + "..." + existing[-4:] if len(existing) > 12 else "***"
        print(f"\n  Ya tenés {env_key} configurada: {masked}")
        use_existing = input("  ¿Usar esta? (s/n): ").strip().lower()
        if use_existing in ("s", "si", "sí", "y", "yes", ""):
            return existing

    print("\n  Para obtener tu key/token:")
    print(f"  -> {info['signup_url']}")
    print()

    api_key = input(f"  Pega tu {env_key} aquí: ").strip()
    if not api_key:
        print("  Key vacía. Abortando.")
        return None

    return api_key


async def list_and_choose_model(provider_key: str, api_key: str | None) -> str | None:
    """List models and let user choose one."""
    info = PROVIDERS[provider_key]

    print(f"\n  Consultando modelos disponibles en {info['name']}...")

    config_kwargs: dict = {"provider": provider_key}
    if api_key:
        config_kwargs["api_key"] = api_key

    try:
        config = LLMConfig(**config_kwargs)
        client = LLMClient(config)
        models = await client.list_models()
    except Exception as e:
        print(f"  Error al listar modelos: {e}")
        models = []

    if not models:
        print("  No se pudieron listar modelos automáticamente.")
        print(f"  Modelo por defecto: {info['default_model']}")
        custom = input("  ¿Usar modelo por defecto? (s/n): ").strip().lower()
        if custom in ("n", "no"):
            model = input("  Escribe el nombre del modelo: ").strip()
            return model or info["default_model"]
        return info["default_model"]

    # Show models (limit to 30 for readability)
    print(f"\n  {len(models)} modelos encontrados:")
    display_models = models[:30]
    for i, m in enumerate(display_models, 1):
        model_id = m.get("id", "unknown")
        owner = m.get("owned_by", "")
        label = f"{model_id}"
        if owner:
            label += f" ({owner})"
        print(f"  {i:3d}. {label}")

    if len(models) > 30:
        print(f"  ... y {len(models) - 30} más")

    print(f"\n  Default: {info['default_model']}")

    while True:
        choice = input("  Elige modelo (número, nombre, o Enter=default): ").strip()
        if not choice:
            return info["default_model"]
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(display_models):
                return display_models[idx]["id"]
        except ValueError:
            # Treat as model name
            return choice
        print("  Opción inválida.")


def save_config(provider_key: str, api_key: str | None, model: str) -> None:
    """Save the chosen configuration."""
    info = PROVIDERS[provider_key]
    env_file = project_root / ".env"

    print("\n  Configuración seleccionada:")
    print(f"    Provider: {info['name']}")
    print(f"    Modelo:   {model}")
    if api_key:
        masked = api_key[:8] + "..." if len(api_key) > 8 else "***"
        print(f"    API Key:  {masked}")

    # Read existing .env or create
    env_lines = []
    if env_file.exists():
        env_lines = env_file.read_text(encoding="utf-8").splitlines()

    def set_env_var(lines: list[str], key: str, value: str) -> list[str]:
        """Set or update an env var in the lines."""
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        return lines

    # Set provider and model
    env_lines = set_env_var(env_lines, "ANTIGRAVITY_LLM_PROVIDER", provider_key)
    env_lines = set_env_var(env_lines, "ANTIGRAVITY_LLM_MODEL", model)

    # Set API key if provided
    if api_key and info["env_key"]:
        env_lines = set_env_var(env_lines, info["env_key"], api_key)

    save = input("\n  ¿Guardar en .env? (s/n): ").strip().lower()
    if save in ("s", "si", "sí", "y", "yes", ""):
        env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        print(f"  Guardado en {env_file}")
    else:
        print("\n  Para configurar manualmente, agrega esto a tu .env:")
        print(f"    ANTIGRAVITY_LLM_PROVIDER={provider_key}")
        print(f"    ANTIGRAVITY_LLM_MODEL={model}")
        if api_key and info["env_key"]:
            print(f"    {info['env_key']}=tu-key-aqui")

    print()
    print("  Listo. Los agentes de Antigravity usarán esta configuración.")
    print()


async def list_models_only(provider_key: str) -> None:
    """Just list models for a provider without full setup."""
    info = PROVIDERS.get(provider_key)
    if not info:
        print(f"Provider '{provider_key}' no reconocido.")
        return

    env_key = info.get("env_key")
    api_key = os.getenv(env_key) if env_key else None

    config_kwargs: dict = {"provider": provider_key}
    if api_key:
        config_kwargs["api_key"] = api_key

    try:
        config = LLMConfig(**config_kwargs)
        client = LLMClient(config)
        models = await client.list_models()
    except Exception as e:
        print(f"Error: {e}")
        return

    if not models:
        print(f"No se encontraron modelos para {info['name']}.")
        return

    print(f"\nModelos disponibles en {info['name']} ({len(models)}):\n")
    for m in models:
        model_id = m.get("id", "unknown")
        owner = m.get("owned_by", "")
        print(f"  {model_id}" + (f"  ({owner})" if owner else ""))


async def main() -> None:
    """Run the interactive setup wizard."""
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity LLM Provider Setup")
    parser.add_argument("--provider", "-p", help="Provider to configure directly")
    parser.add_argument(
        "--list-models",
        "-l",
        action="store_true",
        help="Just list available models for the provider",
    )
    args = parser.parse_args()

    # Just list models
    if args.list_models and args.provider:
        await list_models_only(args.provider)
        return

    # Direct provider setup
    if args.provider:
        if args.provider not in PROVIDERS:
            print(f"Provider '{args.provider}' no reconocido.")
            print(f"Opciones: {', '.join(PROVIDERS.keys())}")
            return
        provider_key = args.provider
    else:
        # Interactive mode
        print_header()
        print_providers()
        provider_key = choose_provider()

    info = PROVIDERS[provider_key]
    print(f"\n  Configurando: {info['name']}")
    print(f"  {info['description']}")

    # Step 1: Auth
    api_key = setup_auth(provider_key)

    # Step 2: List models and choose
    model = await list_and_choose_model(provider_key, api_key)
    if not model:
        print("  Sin modelo seleccionado. Abortando.")
        return

    # Step 3: Save
    save_config(provider_key, api_key, model)


if __name__ == "__main__":
    asyncio.run(main())
