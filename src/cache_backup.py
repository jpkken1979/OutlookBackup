"""
UNS Backup v3.1 - Cache Backup
================================
Lee los archivos de caché OST/PST de Outlook directamente del disco.
Funciona AUNQUE el servidor IMAP/Exchange esté muerto.

Ubicaciones típicas:
- IMAP/POP: %LOCALAPPDATA%\\Microsoft\\Outlook\\*.ost o *.pst
- Exchange: %LOCALAPPDATA%\\Microsoft\\Outlook\\*.ost
- Outlook Data Files: Documents\\Outlook Files\\*.pst
"""

import datetime
import hashlib
import os
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from path_utils import safe_path

try:
    import winreg

    import win32com.client

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def get_outlook_cache_dirs() -> list[Path]:
    """Devuelve las rutas donde Outlook típicamente guarda OST/PST."""
    dirs: list[Path] = []
    if os.name != "nt":
        return dirs

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Outlook",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Outlook",
        Path(os.path.expanduser("~")) / "Documents" / "Outlook Files",
        Path(os.path.expanduser("~")) / "Documents" / "Outlook ファイル",
    ]
    for c in candidates:
        try:
            if c.exists() and c.is_dir():
                dirs.append(c)
        except Exception:
            continue
    return dirs


def find_cache_files() -> list[dict]:
    """Encuentra todos los archivos OST/PST en las rutas conocidas.
    Devuelve metadata sin abrirlos."""
    results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for d in get_outlook_cache_dirs():
        try:
            for ext in ("*.ost", "*.pst"):
                for f in d.rglob(ext):
                    try:
                        full_path = str(f.resolve())
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)

                        stat = f.stat()
                        results.append(
                            {
                                "path": full_path,
                                "filename": f.name,
                                "extension": f.suffix.lower(),
                                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                                "size_bytes": stat.st_size,
                                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "modified_ts": stat.st_mtime,
                            }
                        )
                    except (OSError, PermissionError):
                        continue
        except Exception as e:
            print(f"Error scanning {d}: {e}")
            continue

    # Ordenar por tamaño descendente (los importantes son los grandes)
    results.sort(key=lambda x: x["size_bytes"], reverse=True)
    return results


def map_cache_to_account(cache_files: list[dict]) -> list[dict]:
    """Trata de asociar cada archivo de caché con una cuenta SMTP.
    Lee el registro de Windows para hacer el match."""
    if not HAS_WIN32:
        return cache_files

    # Leer rutas de cuentas en el registro
    account_map: dict[str, str] = {}  # filename -> smtp_address
    try:
        versions = ["16.0", "15.0", "14.0"]
        for ver in versions:
            try:
                profiles_path = f"Software\\Microsoft\\Office\\{ver}\\Outlook\\Profiles"
                profiles_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, profiles_path)
                i = 0
                while True:
                    try:
                        profile = winreg.EnumKey(profiles_key, i)
                        _scan_profile_for_accounts(f"{profiles_path}\\{profile}", account_map)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(profiles_key)
            except OSError:
                continue
    except Exception as e:
        print(f"map_cache_to_account error: {e}")

    # Aplicar el mapping
    for cf in cache_files:
        fname = cf["filename"].lower()
        cf["account_smtp"] = None
        cf["account_inferred_from"] = None

        # Match exacto del filename
        for k, v in account_map.items():
            if k and k.lower() == fname:
                cf["account_smtp"] = v
                cf["account_inferred_from"] = "registry"
                break

        # Si no, inferir del nombre del archivo
        if not cf["account_smtp"]:
            inferred = _infer_smtp_from_filename(cf["filename"])
            if inferred:
                cf["account_smtp"] = inferred
                cf["account_inferred_from"] = "filename"

    return cache_files


def _scan_profile_for_accounts(path: str, account_map: dict, depth: int = 0) -> None:
    """Escanea recursivamente un perfil buscando datos de cuentas."""
    if depth > 5:
        return
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        smtp = None
        cache_filename = None

        i = 0
        while True:
            try:
                name, value, vtype = winreg.EnumValue(key, i)
                if vtype == winreg.REG_SZ and isinstance(value, str):
                    if "@" in value and "." in value and len(value) < 100:
                        smtp = value
                    elif value.lower().endswith((".ost", ".pst")):
                        cache_filename = os.path.basename(value)
                elif vtype == winreg.REG_BINARY:
                    try:
                        decoded = bytes(value).decode("utf-16-le").rstrip("\x00")
                        if "@" in decoded and "." in decoded and len(decoded) < 100:
                            smtp = decoded
                        elif decoded.lower().endswith((".ost", ".pst")):
                            cache_filename = os.path.basename(decoded)
                    except Exception:
                        pass
                i += 1
            except OSError:
                break

        if smtp and cache_filename:
            account_map[cache_filename] = smtp

        # Recurse
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
                _scan_profile_for_accounts(f"{path}\\{sub}", account_map, depth + 1)
                i += 1
            except OSError:
                break

        winreg.CloseKey(key)
    except OSError:
        pass


def _infer_smtp_from_filename(filename: str) -> str | None:
    """Trata de extraer un email del nombre del archivo cache."""
    base = filename.lower().replace(".ost", "").replace(".pst", "")

    # Patrones comunes:
    # "kenji@uns-kikaku.com.ost"
    # "kenji - uns-kikaku.com.ost"
    # "kenji_at_uns-kikaku_com.ost"

    if "@" in base:
        # Ya tiene formato email
        parts = base.split("@")
        if len(parts) == 2 and "." in parts[1]:
            return f"{parts[0]}@{parts[1]}"

    if "_at_" in base:
        parts = base.split("_at_")
        if len(parts) == 2:
            return f"{parts[0]}@{parts[1].replace('_', '.')}"

    # "user - domain.com" pattern
    if " - " in base:
        parts = base.split(" - ")
        if len(parts) == 2 and "." in parts[1]:
            return f"{parts[0].strip()}@{parts[1].strip()}"

    return None


# ============================================================
# Cache Backup Engine
# ============================================================


class CacheBackupEngine:
    """Backup directo de archivos OST/PST sin pasar por COM/servidor."""

    def __init__(
        self,
        cache_files: list[str],
        output_dir: str,
        verify_integrity: bool = True,
        close_outlook: bool = False,
        use_vss: bool = True,
    ):
        """
        :param cache_files: lista de paths absolutos a OST/PST
        :param output_dir: carpeta destino
        :param verify_integrity: si calcular SHA256 después del copy
        :param close_outlook: si cerrar Outlook antes (necesario para algunos OST)
        :param use_vss: si intentar VSS hot-copy cuando no se cierra Outlook.
            VSS copia el OST "en caliente" sin cerrar Outlook, pero requiere
            admin. Si no es admin o falla, hace fallback al copy clásico.
        """
        self.cache_files = cache_files
        self.output_dir = Path(output_dir)
        self.verify_integrity = verify_integrity
        self.close_outlook = close_outlook
        self.use_vss = use_vss
        self._cancel_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def cancel(self) -> None:
        self._cancel_flag.set()

    def run_async(self, progress_cb: Callable, finish_cb: Callable) -> None:
        self._thread = threading.Thread(
            target=self._run, args=(progress_cb, finish_cb), daemon=True
        )
        self._thread.start()

    def _run(self, progress_cb: Callable, finish_cb: Callable) -> None:
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir = self.output_dir / f"cache_backup_{timestamp}"
            session_dir.mkdir(parents=True, exist_ok=True)

            progress_cb("💾 キャッシュバックアップ開始")
            progress_cb(f"📂 保存先: {session_dir}")

            # Cerrar Outlook si está marcado
            if self.close_outlook:
                progress_cb("⏸️ Outlookを閉じています...")
                self._kill_outlook(progress_cb)

            results = []
            total = len(self.cache_files)

            for idx, src_path in enumerate(self.cache_files, 1):
                if self._cancel_flag.is_set():
                    progress_cb("⛔ キャンセルされました")
                    break

                src = Path(src_path)
                if not src.exists():
                    progress_cb(f"  ⚠️ [{idx}/{total}] ファイル不在: {src.name}")
                    results.append({"file": str(src), "success": False, "error": "Not found"})
                    continue

                size_mb = src.stat().st_size / (1024 * 1024)
                progress_cb(f"\n[{idx}/{total}] 📦 {src.name} ({size_mb:.1f} MB)")

                # Copiar. Si close_outlook=False y use_vss=True, intentamos VSS
                # hot-copy primero (sin cerrar Outlook). Si VSS no aplica o falla,
                # hacemos fallback al copy clásico (que puede dar PermissionError).
                dest = session_dir / src.name
                try:
                    vss_used = False
                    if not self.close_outlook and self.use_vss:
                        try:
                            from vss_copy import vss_copy

                            progress_cb("  ⏳ コピー中 (VSSホットコピー試行)...")
                            result = vss_copy(
                                src,
                                dest,
                                cancel_check=self._cancel_flag.is_set,
                                progress_cb=progress_cb,
                            )
                            if result.success:
                                vss_used = True
                                progress_cb("  ✓ VSSホットコピー成功")
                            else:
                                # Fallback al copy clásico
                                progress_cb(
                                    f"  ℹ️ VSSスキップ ({result.reason}) -> 通常コピー"
                                )
                                progress_cb("  ⏳ コピー中...")
                                self._copy_with_progress(src, dest, progress_cb)
                        except ImportError:
                            progress_cb("  ⏳ コピー中...")
                            self._copy_with_progress(src, dest, progress_cb)
                    else:
                        progress_cb("  ⏳ コピー中...")
                        self._copy_with_progress(src, dest, progress_cb)

                    # Verificar integridad
                    integrity = None
                    if self.verify_integrity:
                        progress_cb("  🔐 整合性チェック中...")
                        integrity = self._verify_copy(src, dest, progress_cb)

                    progress_cb(f"  ✅ 完了: {dest.name}")
                    results.append(
                        {
                            "file": str(src),
                            "dest": str(dest),
                            "success": True,
                            "size_mb": round(size_mb, 2),
                            "integrity": integrity,
                            "vss_used": vss_used,
                        }
                    )
                except PermissionError as e:
                    msg = f"  ❌ アクセス拒否 (Outlookで使用中?): {e}"
                    progress_cb(msg)
                    results.append(
                        {
                            "file": str(src),
                            "success": False,
                            "error": "PermissionError - file in use",
                        }
                    )
                except Exception as e:
                    progress_cb(f"  ❌ エラー: {e}")
                    results.append({"file": str(src), "success": False, "error": str(e)})

            # Generar reporte
            self._write_report(session_dir, results, progress_cb)

            success_count = sum(1 for r in results if r.get("success"))
            progress_cb(f"\n✅ {success_count}/{total} 完了")

            finish_cb(success_count > 0, str(session_dir))

        except Exception as e:
            progress_cb(f"❌ 致命的エラー: {e}")
            finish_cb(False, str(e))

    def _copy_with_progress(self, src: Path, dest: Path, progress_cb: Callable) -> None:
        """Copia archivo grande con feedback periódico."""
        total = src.stat().st_size
        copied = 0
        chunk = 4 * 1024 * 1024  # 4MB chunks
        last_pct = -1

        # safe_path() agrega prefijo \\?\ si el path > 240 chars (Fase 3 plan v3.2).
        # Necesario para OST/PST en backup_dir japones largo.
        with open(safe_path(src), "rb") as fsrc, open(safe_path(dest), "wb") as fdst:
            while True:
                if self._cancel_flag.is_set():
                    raise InterruptedError("Cancelled")
                buf = fsrc.read(chunk)
                if not buf:
                    break
                fdst.write(buf)
                copied += len(buf)
                pct = int(copied * 100 / total) if total > 0 else 100
                if pct != last_pct and pct % 10 == 0:
                    progress_cb(
                        f"    {pct}% ({copied / (1024 * 1024):.0f}/{total / (1024 * 1024):.0f} MB)"
                    )
                    last_pct = pct

        # Preservar mtime
        try:
            shutil.copystat(safe_path(src), safe_path(dest))
        except Exception:
            pass

    def _verify_copy(self, src: Path, dest: Path, progress_cb: Callable) -> dict:
        """Verifica que el archivo copiado tenga el mismo SHA256."""
        try:
            src_hash = self._sha256_of(src)
            dest_hash = self._sha256_of(dest)
            match = src_hash == dest_hash
            if match:
                progress_cb(f"  ✓ SHA256一致: {src_hash[:16]}...")
            else:
                progress_cb("  ⚠️ SHA256不一致! 再試行を推奨")
            return {
                "src_sha256": src_hash,
                "dest_sha256": dest_hash,
                "match": match,
            }
        except Exception as e:
            return {"error": str(e), "match": False}

    @staticmethod
    def _sha256_of(path: Path) -> str:
        h = hashlib.sha256()
        with open(safe_path(path), "rb") as f:
            while chunk := f.read(8192 * 16):
                h.update(chunk)
        return h.hexdigest()

    def _kill_outlook(self, progress_cb: Callable) -> None:
        """Cierra Outlook de forma elegante."""
        try:
            import subprocess

            # Primero intentar gracefully via COM
            try:
                if HAS_WIN32:
                    app = win32com.client.GetActiveObject("Outlook.Application")
                    app.Quit()
                    progress_cb("  ✓ Outlookを終了しました(COM)")
                    import time

                    time.sleep(3)
            except Exception:
                pass

            # Si sigue abierto, force kill
            result = subprocess.run(
                ["taskkill", "/F", "/IM", "OUTLOOK.EXE"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                progress_cb("  ✓ Outlookを強制終了しました")
            import time

            time.sleep(2)
        except Exception as e:
            progress_cb(f"  ⚠️ Outlook終了失敗: {e}")

    def _write_report(self, session_dir: Path, results: list[dict], progress_cb: Callable) -> None:
        """Escribe report.json con info del backup."""
        try:
            import json

            report = {
                "type": "cache_backup",
                "version": "3.1",
                "timestamp": datetime.datetime.now().isoformat(),
                "host_info": {
                    "computer": os.environ.get("COMPUTERNAME", ""),
                    "user": os.environ.get("USERNAME", ""),
                },
                "stats": {
                    "total_files": len(results),
                    "successful": sum(1 for r in results if r.get("success")),
                    "failed": sum(1 for r in results if not r.get("success")),
                    "total_size_mb": round(sum(r.get("size_mb", 0) for r in results), 2),
                },
                "files": results,
                "warning": (
                    "⚠️ This backup contains the LOCAL CACHE of Outlook data files. "
                    "Coverage depends on what was synced to local cache before. "
                    "OST files are tied to the original Outlook profile and may not "
                    "open standalone — use as recovery source if server is dead."
                ),
            }
            (session_dir / "report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            progress_cb("📋 レポート: report.json")
        except Exception as e:
            progress_cb(f"⚠️ Report write failed: {e}")
