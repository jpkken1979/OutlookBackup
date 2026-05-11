"""Check de actualizaciones contra GitHub Releases.

Diseno minimalista:
- Una sola llamada HTTP a /releases/latest (3s timeout).
- Comparacion semver simple (tag_name vs version).
- Devuelve UpdateInfo con url y notas si hay version nueva. No auto-instala.

El caller decide que hacer: log + UI banner es lo mas comun. No interrumpir.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/releases/latest"


@dataclass
class UpdateInfo:
    """Resultado del check.

    Attributes:
        available: True si hay version mas nueva que la actual.
        latest_version: tag_name del release (ej. "v3.2.0").
        current_version: version de la app que pasamos al check.
        download_url: URL del primer asset .exe en el release, si existe.
        release_url: URL HTML del release en GitHub.
        notes: body del release (changelog).
        error: si el check fallo, mensaje. Si hay error, available=False.
    """

    available: bool = False
    latest_version: str = ""
    current_version: str = ""
    download_url: str = ""
    release_url: str = ""
    notes: str = ""
    error: str = ""


def _parse_version(v: str) -> tuple[int, ...]:
    """Parsea 'v3.1.1' o '3.1.1' a tuple (3, 1, 1). Tolera prefijo 'v'."""
    cleaned = v.lstrip("vV").strip()
    parts = re.split(r"[.\-]", cleaned)
    out: list[int] = []
    for p in parts:
        m = re.match(r"^(\d+)", p)
        if not m:
            break
        out.append(int(m.group(1)))
    return tuple(out)


def _is_newer(latest: str, current: str) -> bool:
    """True si `latest` > `current` (semver simple)."""
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return False


def check_for_updates(
    *,
    current_version: str,
    owner: str = "jpkken1979",
    repo: str = "OutlookBackup",
    timeout: float = 3.0,
) -> UpdateInfo:
    """Consulta la GitHub Releases API.

    Args:
        current_version: version actual de la app (ej. "3.1.1" o "v3.1.1").
        owner: dueno del repo en GitHub.
        repo: nombre del repo.
        timeout: segundos. Default 3s para no bloquear startup si la red esta mal.

    Returns:
        UpdateInfo con available=True si hay version nueva. Si la red falla,
        available=False y error trae el motivo. No lanza excepciones.
    """
    url = GITHUB_API.format(owner=owner, repo=repo)
    info = UpdateInfo(current_version=current_version)

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "uns-outlook-backup-updater",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data: dict[str, Any] = json.load(resp)
    except urllib.error.URLError as e:
        info.error = f"network: {e.reason}" if hasattr(e, "reason") else str(e)
        return info
    except (TimeoutError, json.JSONDecodeError) as e:
        info.error = f"timeout-or-parse: {e}"
        return info

    info.latest_version = str(data.get("tag_name", ""))
    info.release_url = str(data.get("html_url", ""))
    info.notes = str(data.get("body", ""))[:1000]  # limitar tamano

    # Buscar primer .exe en assets
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".exe"):
            info.download_url = str(asset.get("browser_download_url", ""))
            break

    info.available = _is_newer(info.latest_version, current_version)
    return info
