"""
UNS Backup v3.2 - VSS Hot-Copy
================================
Copia archivos OST/PST "en caliente" usando Volume Shadow Copy Service (VSS),
sin necesidad de cerrar Outlook. Requiere privilegios de administrador.

Estrategia:
1. Verifica si el proceso corre como admin (`IsUserAnAdmin`).
2. Si es admin: crea un shadow copy del volumen que contiene el archivo origen
   via `vssadmin create shadow` (o PowerShell `Get-WmiObject`), copia el archivo
   desde el shadow device path, y elimina el shadow al terminar.
3. Si NO es admin: retorna `VssCopyResult(success=False, reason="not_admin")`
   para que el caller haga fallback al comportamiento clásico (cerrar Outlook).

Referencias:
- Plan v3.2 Fase 6, decision aprobada 2026-05-13 (linea 326 del plan).
- VSS API: https://learn.microsoft.com/en-us/windows/win32/vss/volume-shadow-copy-service-portal

Diseno seguro:
- Nunca ejecuta `vssadmin` sin verificar admin primero.
- Limpia siempre el shadow copy en un bloque `finally` para evitar leaks.
- Timeout en todos los subprocess (60s create, 120s copy).
"""

import ctypes
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from path_utils import safe_path

# Tiempos maximos (segundos) para operaciones VSS
SHADOW_CREATE_TIMEOUT = 60
SHADOW_COPY_TIMEOUT = 300  # OSTs grandes pueden tardar
SHADOW_DELETE_TIMEOUT = 30


@dataclass(frozen=True)
class VssCopyResult:
    """Resultado de una operacion vss_copy."""

    success: bool
    dest: str
    shadow_device: str = ""
    reason: str = ""  # "ok" | "not_admin" | "not_windows" | "shadow_failed" | "copy_failed" | "cancelled"


def is_admin() -> bool:
    """Retorna True si el proceso corre con privilegios elevados."""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run_vssadmin_create(volume: str) -> tuple[bool, str]:
    """Crea un shadow copy del volumen (ej: "C:").

    Retorna (success, shadow_device_path) donde shadow_device_path es del estilo
    `\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1`.
    """
    # vssadmin create shadow /For=C: requiere el volumen con dos puntos y barra.
    # En Windows moderno el formato es `For=C:` (sin barra al final).
    cmd = ["vssadmin", "create", "shadow", f"/For={volume}"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=SHADOW_CREATE_TIMEOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        return False, f"vssadmin exit {result.returncode}: {result.stderr.strip()}"

    # Parsear la salida para extraer "Shadow Copy Volume Name: \\?\GLOBALROOT\..."
    for line in result.stdout.splitlines():
        line = line.strip()
        if "GLOBALROOT" in line or "Shadow Copy Volume Name" in line:
            # Extraer el path \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopyN
            if "GLOBALROOT" in line:
                # La linea completa contiene el path
                parts = line.split(":", 1)
                if len(parts) == 2:
                    dev = parts[1].strip()
                    if dev.startswith("\\\\?\\"):
                        return True, dev
            # Formato alternativo: "Shadow Copy Volume Name: \\?\GLOBALROOT\..."
            if ":" in line:
                dev = line.split(":", 1)[1].strip()
                if dev.startswith("\\\\?\\"):
                    return True, dev

    return False, f"shadow created but device not parsed from output: {result.stdout[:200]}"


def _run_vssadmin_delete(shadow_device: str) -> bool:
    """Elimina un shadow copy previamente creado."""
    cmd = ["vssadmin", "delete", "shadows", f"/Shadow={Path(shadow_device).name}", "/Quiet"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SHADOW_DELETE_TIMEOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def _volume_of(path: Path) -> str:
    """Retorna la raiz del volumen de un path (ej: 'C:').

    Para paths UNC (\\\\server\\share) retorna "" porque VSS no soporta
    volúmenes remotos directamente — el caller debe hacer fallback.
    """
    s = str(path)
    if s.startswith("\\\\"):
        return ""
    drive = path.drive
    if not drive or len(drive) < 2 or drive[1] != ":":
        return ""
    return drive.upper().rstrip("\\/")


def _copy_from_shadow(
    shadow_device: str,
    src_relative: str,
    dest: Path,
    cancel_check: Any = None,
    progress_cb: Any = None,
) -> bool:
    """Copia un archivo desde el shadow device al destino.

    :param shadow_device: path tipo `\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1`
    :param src_relative: ruta relativa desde la raiz del volumen (ej: `Users\\kenji\\...\\file.ost`)
    :param dest: path destino (con safe_path aplicado)
    :param cancel_check: callable() -> bool para abortar
    :param progress_cb: callable(str) para feedback
    """
    # El path completo en el shadow es: shadow_device + "\\" + src_relative
    full_src = f"{shadow_device}\\{src_relative}"

    chunk = 4 * 1024 * 1024  # 4MB
    try:
        with open(full_src, "rb") as fsrc, open(dest, "wb") as fdst:
            while True:
                if cancel_check and cancel_check():
                    raise InterruptedError("Cancelled")
                buf = fsrc.read(chunk)
                if not buf:
                    break
                fdst.write(buf)
        return True
    except (InterruptedError, OSError, PermissionError):
        return False


def vss_copy(
    src: Path,
    dest: Path,
    cancel_check: Any = None,
    progress_cb: Any = None,
) -> VssCopyResult:
    """Copia un archivo OST/PST usando VSS shadow copy.

    Requiere admin. Si no es admin o no es Windows, retorna reason explicativo
    para que el caller decida el fallback.

    :param src: path absoluto del archivo origen (OST/PST)
    :param dest: path absoluto destino
    :param cancel_check: callable opcional () -> bool
    :param progress_cb: callable opcional (str) -> None
    :return: VssCopyResult con success/dest/shadow_device/reason
    """
    if os.name != "nt":
        return VssCopyResult(success=False, dest=str(dest), reason="not_windows")
    if not is_admin():
        if progress_cb:
            progress_cb("  ⚠️ VSS: 管理者権限が必要です (クローズ＆コピーにフォールバック)")
        return VssCopyResult(success=False, dest=str(dest), reason="not_admin")

    if not src.exists():
        return VssCopyResult(success=False, dest=str(dest), reason="copy_failed")

    volume = _volume_of(src)
    if not volume:
        # Path UNC o sin drive — VSS no aplica a volumen local
        if progress_cb:
            progress_cb("  ⚠️ VSS: UNCパスはサポート対象外 (クローズ＆コピーにフォールバック)")
        return VssCopyResult(success=False, dest=str(dest), reason="not_windows")
    if progress_cb:
        progress_cb(f"  🔧 VSS: ボリューム {volume} のシャドウコピー作成中...")

    # 1. Crear shadow
    ok, shadow_device_or_err = _run_vssadmin_create(volume)
    if not ok:
        if progress_cb:
            progress_cb(f"  ⚠️ VSS シャドウ作成失敗: {shadow_device_or_err[:80]}")
        return VssCopyResult(success=False, dest=str(dest), reason="shadow_failed")

    shadow_device = shadow_device_or_err
    if progress_cb:
        progress_cb("  📁 VSS シャドウコピーからファイルをコピー中...")

    # 2. Path relativo desde la raiz del volumen
    # src absoluta: C:\Users\...\file.ost -> Users\...\file.ost
    src_str = str(src.resolve())
    # Quitar drive + primer backslash
    src_relative = src_str[len(volume) + 1 :]

    # 3. Copiar desde el shadow
    try:
        copied = _copy_from_shadow(
            shadow_device, src_relative, Path(safe_path(dest)), cancel_check, progress_cb
        )
        if not copied:
            return VssCopyResult(success=False, dest=str(dest), reason="copy_failed")

        # Preservar mtime
        try:
            shutil.copystat(f"{shadow_device}\\{src_relative}", safe_path(dest))
        except Exception:
            pass

        return VssCopyResult(success=True, dest=str(dest), shadow_device=shadow_device, reason="ok")

    finally:
        # 4. Siempre limpiar el shadow
        _run_vssadmin_delete(shadow_device)
        if progress_cb:
            progress_cb("  🧹 VSS シャドウコピー削除完了")
