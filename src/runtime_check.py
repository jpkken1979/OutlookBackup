"""Deteccion e instalacion del runtime WebView2 (Fase 2 plan v3.2).

Por que existe este modulo
--------------------------
La GUI de UNS Outlook Backup v3.0+ usa pywebview con backend WebView2 (Edge Chromium).
- Win 11 22H2+ y Win 10 22H2+ traen WebView2 preinstalado.
- Win 10 21H2 y anteriores NO. La app abre ventana en blanco sin error visible.

Este modulo detecta el runtime y, si falta:
- Modo interactivo (run_gui): muestra dialogo japones via tkinter (NO WebView2)
  preguntando si instalar. Si acepta, ejecuta el bootstrapper bundleado en el
  installer Inno Setup (~1.7MB redist/MicrosoftEdgeWebview2Setup.exe). Si no
  hay bundle local (modo dev), descarga del enlace evergreen oficial.
- Modo no-interactivo (run_auto_backup): log warning y continua. El backup
  no necesita GUI; solo COM con Outlook.

Referencias canonicas
---------------------
- Registry GUID: https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
- Evergreen bootstrapper: https://go.microsoft.com/fwlink/p/?LinkId=2124703
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

# GUID canonico publicado por Microsoft. NO cambia entre releases.
WEBVIEW2_RUNTIME_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

# URL del bootstrapper evergreen (~1.7MB). Microsoft mantiene este shortlink
# estable; el bootstrapper internamente descarga el runtime full (~150MB).
WEBVIEW2_BOOTSTRAPPER_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

# Nombre del archivo bundleado en el installer Inno Setup (decision 2026-05-13).
BUNDLED_INSTALLER_NAME = "MicrosoftEdgeWebview2Setup.exe"


def is_webview2_installed() -> bool:
    """Detecta si el runtime WebView2 esta instalado en este sistema.

    Lee el registry en 3 ubicaciones (HKLM 32-bit, HKLM 64-bit, HKCU). Si
    cualquiera tiene un value `pv` no-vacio y distinto de "0.0.0.0", el runtime
    esta presente. Esta es la deteccion canonica que recomienda Microsoft.

    Returns:
        True si el runtime esta instalado, False en cualquier otro caso
        (incluye non-Windows y errores de acceso al registry).
    """
    if os.name != "nt":
        return False

    try:
        import winreg
    except ImportError:
        log.warning("winreg no disponible; asumiendo WebView2 ausente")
        return False

    candidates = [
        # HKLM x86 (instalacion machine-wide via 32-bit installer)
        (
            winreg.HKEY_LOCAL_MACHINE,
            rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_RUNTIME_GUID}",
        ),
        # HKLM x64 (instalacion machine-wide via 64-bit installer)
        (
            winreg.HKEY_LOCAL_MACHINE,
            rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_RUNTIME_GUID}",
        ),
        # HKCU (instalacion per-user, comun en empresas con politica restrictiva)
        (
            winreg.HKEY_CURRENT_USER,
            rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_RUNTIME_GUID}",
        ),
    ]

    for root, path in candidates:
        version = _read_pv_value(root, path)
        if version and version != "0.0.0.0":
            log.debug("WebView2 detectado en %s: pv=%s", path, version)
            return True

    log.info("WebView2 no detectado en HKLM ni HKCU")
    return False


def _read_pv_value(root: int, path: str) -> str | None:
    """Lee el value `pv` de una clave del registry. None si no existe."""
    try:
        import winreg
    except ImportError:
        return None

    try:
        with winreg.OpenKey(root, path) as key:
            value, _ = winreg.QueryValueEx(key, "pv")
            return str(value) if value else None
    except OSError:
        return None


def get_bundled_installer_path() -> Path | None:
    """Busca el bootstrapper bundleado en el installer Inno Setup.

    Inno Setup copia el installer a `{app}\\redist\\MicrosoftEdgeWebview2Setup.exe`
    durante la instalacion (decision 2026-05-13). Cuando la app corre desde el
    installer, este path existe. Cuando corre desde dev (run.bat) o desde el
    .exe portable (PyInstaller dist/), no existe — fallback a download.

    Returns:
        Path al bootstrapper si existe, None si no.
    """
    # Buscar en varios paths posibles segun como se ejecute la app
    candidates = [
        # Junto al .exe del installer (PyInstaller standalone)
        Path(sys.executable).parent / "redist" / BUNDLED_INSTALLER_NAME,
        # Junto al modulo en modo dev
        Path(__file__).parent.parent / "redist" / BUNDLED_INSTALLER_NAME,
        # Para PyInstaller _MEIPASS (one-file mode)
        Path(getattr(sys, "_MEIPASS", "")) / "redist" / BUNDLED_INSTALLER_NAME,
    ]

    for path in candidates:
        if path.is_file():
            log.debug("Bootstrapper bundleado encontrado en %s", path)
            return path

    return None


def download_bootstrapper(dest: Path, timeout: float = 30.0) -> bool:
    """Descarga el bootstrapper evergreen oficial de Microsoft.

    Solo se usa como fallback cuando no hay bootstrapper bundleado (modo dev).
    El installer Inno Setup deberia siempre proveer el bundle local.

    Args:
        dest: Path donde guardar el .exe descargado.
        timeout: Timeout total en segundos para la descarga.

    Returns:
        True si descargo exitosamente, False en cualquier error.
    """
    log.info("Descargando WebView2 bootstrapper a %s", dest)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # NOTA: urllib sigue redirects automaticamente. timeout cubre toda la
        # transaccion; si Microsoft cambia el redirect destination, falla con
        # URLError manejable.
        with urllib.request.urlopen(WEBVIEW2_BOOTSTRAPPER_URL, timeout=timeout) as response:
            data = response.read()
        dest.write_bytes(data)
        log.info("Bootstrapper descargado: %d bytes", len(data))
        return True
    except Exception as e:  # noqa: BLE001 — wrapper deliberado, log + return False
        log.error("Error descargando bootstrapper: %s", e)
        return False


def run_installer_silent(installer: Path) -> bool:
    """Ejecuta el bootstrapper en modo silent install.

    Args:
        installer: Path al MicrosoftEdgeWebview2Setup.exe.

    Returns:
        True si el installer salio con codigo 0, False en cualquier otro caso.
    """
    if not installer.is_file():
        log.error("Installer no encontrado: %s", installer)
        return False

    # shell=False obligatorio (regla .claude/rules/security.md). shlex.split no
    # aplica aqui porque ya tenemos lista, pero documentamos la decision.
    cmd = [str(installer), "/silent", "/install"]
    log.info("Ejecutando: %s", shlex.join(cmd))

    try:
        result = subprocess.run(  # noqa: S603 — shell=False, args validados
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max para instalacion full
            check=False,
        )
        if result.returncode == 0:
            log.info("WebView2 instalado exitosamente")
            return True
        log.error(
            "Installer fallo con returncode=%d. stdout=%r stderr=%r",
            result.returncode,
            result.stdout[:500],
            result.stderr[:500],
        )
        return False
    except subprocess.TimeoutExpired:
        log.error("Installer timeout despues de 10 minutos")
        return False
    except OSError as e:
        log.error("Error ejecutando installer: %s", e)
        return False


def show_japanese_install_dialog() -> bool:
    """Dialogo japones preguntando si instalar WebView2.

    Usa tkinter.messagebox que NO depende de WebView2 (es win32 nativo). Funciona
    incluso cuando el runtime que queremos instalar no existe todavia.

    Returns:
        True si el usuario clickea 'はい' (yes), False si clickea 'いいえ' (no)
        o si tkinter no esta disponible.
    """
    try:
        import tkinter
        from tkinter import messagebox
    except ImportError:
        log.warning("tkinter no disponible; saltando dialogo")
        return False

    # Crear root window oculto para que messagebox tenga parent valido
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # forzar al frente

    try:
        result: bool = messagebox.askyesno(
            title="WebView2 ランタイムが必要です",
            message=(
                "このアプリは Microsoft Edge WebView2 ランタイムを必要としますが、"
                "お使いのシステムには未インストールです。\n\n"
                "今すぐインストールしますか?\n"
                "(約 150MB のダウンロードが発生します)"
            ),
            icon=messagebox.QUESTION,
        )
        return result
    finally:
        root.destroy()


def ensure_webview2_runtime(interactive: bool = True) -> bool:
    """Verifica que el runtime WebView2 este instalado; si no, intenta instalarlo.

    Es el entry point publico del modulo. Llamar al inicio de `run_gui()` con
    interactive=True, y al inicio de `run_auto_backup()` con interactive=False.

    Args:
        interactive: Si True, muestra dialogo al usuario cuando falta el runtime.
            Si False, solo loguea warning y devuelve False sin bloquear.

    Returns:
        True si el runtime esta presente al final (ya estaba o se instalo),
        False si falta y no se pudo instalar (o el usuario rechazo).
    """
    if is_webview2_installed():
        return True

    if not interactive:
        log.warning(
            "WebView2 runtime ausente en modo no-interactivo; la GUI no funcionara "
            "pero el backup CLI/auto puede continuar"
        )
        return False

    if not show_japanese_install_dialog():
        log.info("Usuario rechazo instalar WebView2")
        return False

    # Intentar bundle local primero, fallback a download
    installer = get_bundled_installer_path()
    if installer is None:
        log.info("Bootstrapper no bundleado; descargando de Microsoft")
        # En modo dev guardamos en un tmp; en producto Inno Setup ya lo bundlea
        import tempfile

        tmp_path = Path(tempfile.gettempdir()) / BUNDLED_INSTALLER_NAME
        if not download_bootstrapper(tmp_path):
            log.error("No se pudo descargar el bootstrapper")
            return False
        installer = tmp_path

    if not run_installer_silent(installer):
        return False

    # Verificar que la instalacion realmente funciono
    return is_webview2_installed()
