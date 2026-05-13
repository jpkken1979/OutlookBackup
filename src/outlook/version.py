"""Deteccion de version de Outlook (Fase 4 plan v3.2).

Por que existe este modulo
--------------------------
Outlook puede instalarse de varias maneras en Windows, y cada una pone los
metadatos en un lugar diferente del registry:

1. **M365 Click-to-Run** (M365 Family/Business/Enterprise):
   `HKLM\\SOFTWARE\\Microsoft\\Office\\ClickToRun\\Configuration` value
   `ProductReleaseIds`. Es la instalacion mas comun hoy en empresas.
   Auto-actualiza, version cambia frecuentemente (ej "16.0.17726.20126").

2. **Outlook 2019/2021 perpetual**:
   `HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Office\\16.0\\Outlook\\InstallRoot\\Path`
   (32-bit) o sin `WOW6432Node` (64-bit). Major version es siempre 16 desde
   2016. La distincion 2019 vs 2021 vs M365 se hace via `ProductReleaseIds`.

3. **Outlook 2016 (16.0)** y anteriores (15.0/14.0): NO soportados en v3.2 por
   decision de UNS-Kikaku.

Por que importa para UNS-Kikaku
-------------------------------
- Algunos clientes UNS estan en Outlook 2019/2021 perpetual (~30% del parque).
- M365 Click-to-Run dominante en cuentas nuevas.
- Saber el flavor permite:
  * Logear bug reports con contexto preciso ("M365 16.0.17726 falla en X")
  * Adaptar comportamiento si una API COM cambia entre flavors
  * Warnear al usuario si version no soportada antes de fallar misteriosamente

API publica
-----------
- `detect_outlook_version()` — devuelve `OutlookVersion` dataclass con todo el contexto.
- `is_supported(version)` — helper bool.

Referencias
-----------
- Registry layout: https://learn.microsoft.com/office/troubleshoot/installation/registry-keys-office
- ProductReleaseIds values: https://learn.microsoft.com/microsoft-365-apps/deploy/overview-deploying-languages-microsoft-365-apps
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)


# Versions soportadas (Office 2019/2021/M365 = 16.x). 17.0 es futuro previsto.
MIN_SUPPORTED_MAJOR = 16
SUPPORTED_MAJOR_VERSIONS = (16, 17)

# Major versions a probar en el registry, en orden de preferencia
KNOWN_MAJOR_VERSIONS = ("16.0", "15.0", "14.0")

OutlookFlavor = Literal["M365", "perpetual", "unknown"]


@dataclass(frozen=True)
class OutlookVersion:
    """Resultado de la deteccion de version de Outlook.

    Attributes:
        version_str: Version completa como string (ej "16.0.17726.20126").
            Empty string si no se pudo detectar.
        version_tuple: Version parseada como tupla de ints. Empty tuple si fallo.
        flavor: Tipo de instalacion: "M365" (Click-to-Run) o "perpetual" (Office 2019/2021)
            o "unknown" si no se pudo determinar.
        install_path: Path al directorio de instalacion. None si no detectado.
        supported: True si la app soporta esta version (major >= 16).
        product_release_ids: Para M365, identificadores de productos (ej "O365BusinessRetail").
            Empty para perpetual o unknown.
    """

    version_str: str
    version_tuple: tuple[int, ...]
    flavor: OutlookFlavor
    install_path: Path | None
    supported: bool
    product_release_ids: list[str] = field(default_factory=list)


# Registry paths canonicos
_C2R_CONFIG_PATH = r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration"
_PERPETUAL_PATHS_TEMPLATES = [
    # 64-bit installer en Win 64-bit
    r"SOFTWARE\Microsoft\Office\{ver}\Outlook\InstallRoot",
    # 32-bit installer en Win 64-bit
    r"SOFTWARE\WOW6432Node\Microsoft\Office\{ver}\Outlook\InstallRoot",
]


def is_supported(version: OutlookVersion) -> bool:
    """True si la version esta dentro del rango soportado (major >= 16)."""
    if not version.version_tuple:
        return False
    major = version.version_tuple[0]
    return major in SUPPORTED_MAJOR_VERSIONS


def _parse_version_tuple(s: str) -> tuple[int, ...]:
    """Parsea '16.0.17726.20126' a (16, 0, 17726, 20126). Vacio si falla."""
    if not s:
        return ()
    try:
        return tuple(int(p) for p in s.split("."))
    except ValueError:
        log.warning("No se pudo parsear version: %r", s)
        return ()


def _read_string(root: int, path: str, value_name: str) -> str | None:
    """Lee un value REG_SZ del registry. None si no existe."""
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(root, path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value) if value else None
    except OSError:
        return None


def _detect_m365() -> OutlookVersion | None:
    """Detecta M365 Click-to-Run via ClickToRun\\Configuration."""
    try:
        import winreg
    except ImportError:
        return None

    version_str = _read_string(winreg.HKEY_LOCAL_MACHINE, _C2R_CONFIG_PATH, "VersionToReport")
    if not version_str:
        return None

    install_path_str = _read_string(winreg.HKEY_LOCAL_MACHINE, _C2R_CONFIG_PATH, "InstallationPath")
    install_path = Path(install_path_str) if install_path_str else None

    product_ids_str = _read_string(winreg.HKEY_LOCAL_MACHINE, _C2R_CONFIG_PATH, "ProductReleaseIds")
    product_release_ids = product_ids_str.split(",") if product_ids_str else []

    version_tuple = _parse_version_tuple(version_str)
    return OutlookVersion(
        version_str=version_str,
        version_tuple=version_tuple,
        flavor="M365",
        install_path=install_path,
        supported=bool(version_tuple) and version_tuple[0] in SUPPORTED_MAJOR_VERSIONS,
        product_release_ids=product_release_ids,
    )


def _detect_perpetual() -> OutlookVersion | None:
    """Detecta Outlook 2019/2021 perpetual via Office\\{ver}\\Outlook\\InstallRoot."""
    try:
        import winreg
    except ImportError:
        return None

    for ver in KNOWN_MAJOR_VERSIONS:
        for template in _PERPETUAL_PATHS_TEMPLATES:
            path = template.format(ver=ver)
            install_path_str = _read_string(winreg.HKEY_LOCAL_MACHINE, path, "Path")
            if install_path_str:
                version_tuple = _parse_version_tuple(ver)
                return OutlookVersion(
                    version_str=ver,
                    version_tuple=version_tuple,
                    flavor="perpetual",
                    install_path=Path(install_path_str),
                    supported=bool(version_tuple) and version_tuple[0] in SUPPORTED_MAJOR_VERSIONS,
                )
    return None


def detect_outlook_version() -> OutlookVersion:
    """Detecta la version de Outlook instalada en este sistema.

    Estrategia:
    1. Intenta M365 (Click-to-Run) primero — es la instalacion mas comun.
    2. Si no, intenta perpetual (2019/2021) iterando 16.0/15.0/14.0.
    3. Si nada matchea, devuelve OutlookVersion con flavor="unknown".

    En non-Windows siempre devuelve unknown (no hay Outlook).

    Returns:
        OutlookVersion con todos los campos. Nunca raisea.
    """
    if os.name != "nt":
        return OutlookVersion(
            version_str="",
            version_tuple=(),
            flavor="unknown",
            install_path=None,
            supported=False,
        )

    m365 = _detect_m365()
    if m365 is not None:
        log.info("Outlook M365 detectado: %s", m365.version_str)
        return m365

    perpetual = _detect_perpetual()
    if perpetual is not None:
        log.info(
            "Outlook perpetual detectado: %s en %s", perpetual.version_str, perpetual.install_path
        )
        return perpetual

    log.warning("No se detecto ninguna instalacion de Outlook")
    return OutlookVersion(
        version_str="",
        version_tuple=(),
        flavor="unknown",
        install_path=None,
        supported=False,
    )
