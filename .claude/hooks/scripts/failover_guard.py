"""SessionStart guard: avisa cuando la sesion corre SIN failover de provider.

Si ANTHROPIC_BASE_URL no apunta al proxy :4747, la sesion habla directo con
Anthropic y el failover automatico de providers alternativos queda inactivo.
Esto puede pasar por una desconexion manual, un estado legacy o el uso de
Claude nativo sin proxy. Es independiente del estado de Remote Control.

El trade-off es legitimo; que sea silencioso no. Este hook lo hace visible al
arrancar cada sesion. Nunca bloquea: exit 0 siempre.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROXY_MARKER = "/claudeproxy"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _claude_quota_line(proxy_dir: Path) -> str:
    state = _read_json(proxy_dir / "quota_state.json")
    claude = (state.get("providers") or {}).get("claude") or {}
    remaining = claude.get("remaining_percent")
    if not isinstance(remaining, (int, float)):
        return ""
    window = claude.get("window", "?")
    return f" Cuota Claude: {remaining:.0f}% restante (ventana {window})."


def _auto_failover_enabled(state: dict) -> bool:
    """Respeta el override de entorno antes del toggle persistido de Nexus."""
    raw = os.environ.get("ANTIGRAVITY_PROXY_AUTO_FAILOVER", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return state.get("enabled") is True


def main(home: Path | None = None) -> int:
    home = home or Path.home()
    settings = _read_json(home / ".claude" / "settings.json")
    base_url = ((settings.get("env") or {}).get("ANTHROPIC_BASE_URL") or "").strip()
    proxy_connected = PROXY_MARKER in base_url

    proxy_dir = home / ".antigravity" / "proxy"
    failover = _read_json(proxy_dir / "failover.json")
    failover_enabled = _auto_failover_enabled(failover)
    cascade_size = len(failover.get("cascade") or [])
    quota = _claude_quota_line(proxy_dir)

    if proxy_connected and failover_enabled:
        return 0

    if proxy_connected:
        print(
            "[Failover Guard] Proxy :4747 CONECTADO, pero el failover automatico "
            "esta DESACTIVADO. Los requests usan el proxy sin rotacion automatica "
            "de provider. Activalo en Nexus > Preferencias IA > Auto-failover."
        )
        return 0

    print(
        "[Failover Guard] Proxy :4747 DESCONECTADO: esta sesion "
        "habla directo con Anthropic y NO tiene failover automatico"
        + (f" (cascada de {cascade_size} providers inactiva)" if cascade_size else "")
        + "."
        + quota
        + " Si Claude agota su ventana, la sesion se corta. Para failover: "
        "`python .agent/core/provider_switch.py connect` (reiniciar la sesion despues). "
        "Para volver a Claude nativo directo: "
        "`python .agent/core/provider_switch.py disconnect`."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
