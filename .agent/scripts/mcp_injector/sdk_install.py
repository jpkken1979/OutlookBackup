"""SDK installation helpers for the MCP injector."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .path_utils import ensure_dir

logger = logging.getLogger(__name__)


def install_sdk_python(target_dir: Path, repo_root: Path) -> bool:
    """Copia el SDK Python al proyecto destino."""
    sdk_source = repo_root / ".agent" / "sdk" / "client.py"
    sdk_init_source = repo_root / ".agent" / "sdk" / "__init__.py"
    sdk_dest_dir = target_dir / ".antigravity" / "sdk"

    if not sdk_source.exists():
        logger.warning(f"⚠️  [SDK Python] No se encontro el SDK en {sdk_source}")
        return False

    ensure_dir(sdk_dest_dir)
    try:
        shutil.copy2(sdk_source, sdk_dest_dir / "client.py")
        if sdk_init_source.exists():
            shutil.copy2(sdk_init_source, sdk_dest_dir / "__init__.py")
        else:
            (sdk_dest_dir / "__init__.py").write_text(
                'from .client import Client\n__all__ = ["Client"]\n',
                encoding="utf-8",
            )
        logger.info("✅ [SDK Python] Instalado en .antigravity/sdk/")
        return True
    except Exception as exc:
        logger.error(f"❌ [SDK Python] Error al copiar SDK: {exc}")
        return False


def install_sdk_js(target_dir: Path) -> bool:
    """Crea un helper JS/TS para conectarse al gateway REST."""
    sdk_dest_dir = target_dir / ".antigravity" / "sdk"
    ensure_dir(sdk_dest_dir)

    helper_content = """\
// Antigravity SDK - Cliente REST para el ecosistema
const GATEWAY_URL = process.env.ANTIGRAVITY_GATEWAY ?? "http://localhost:4747";

export async function runAgent(agentName, task, timeout = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(`${GATEWAY_URL}/agents/${agentName}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function listAgents() {
  const res = await fetch(`${GATEWAY_URL}/agents`);
  if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
  return res.json();
}

export async function healthCheck() {
  const res = await fetch(`${GATEWAY_URL}/health`);
  if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
  return res.json();
}
"""
    helper_path = sdk_dest_dir / "antigravity.js"
    try:
        helper_path.write_text(helper_content, encoding="utf-8")
        logger.info("✅ [SDK JS] Instalado en .antigravity/sdk/antigravity.js")
        return True
    except Exception as exc:
        logger.error(f"❌ [SDK JS] Error al crear helper: {exc}")
        return False
