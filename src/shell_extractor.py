"""
UNS Backup v3.1 - Shell Extractor
=================================
Extrae archivos RAR y ejecuta comandos shell automáticamente.
Diseñado para herramientas de migración como Microsoft Office 365.
"""

import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

# rarfile necesita unrar.exe o winrar
try:
    import rarfile

    RARFILE_AVAILABLE = True
except ImportError:
    RARFILE_AVAILABLE = False


class ShellExtractor:
    """Extrae RAR y ejecuta comandos shell."""

    def __init__(self):
        self._cancel_flag = threading.Event()
        self._thread: threading.Thread | None = None
        self._result = None

        # Buscar unrar.exe
        self.unrar_path = self._find_unrar()

    def _find_unrar(self) -> str | None:
        """Busca unrar.exe en rutas comunes de Windows."""
        candidates = [
            # WinRAR instalado
            Path(os.environ.get("ProgramFiles", "")) / "WinRAR" / "unrar.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "WinRAR" / "unrar.exe",
            Path(os.environ.get("ProgramFiles", "")) / "7-Zip" / "7z.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "7-Zip" / "7z.exe",
        ]

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        # Buscar en PATH
        for name in ["unrar.exe", "7z.exe"]:
            try:
                result = shutil.which(name)
                if result:
                    return result
            except Exception:
                continue

        return None

    def can_extract_rar(self) -> bool:
        """Verifica si se puede extraer RAR."""
        return RARFILE_AVAILABLE and self.unrar_path is not None

    def extract_rar(
        self, rar_path: str, output_dir: str, progress_cb: Callable | None = None
    ) -> dict:
        """Extrae un archivo RAR al directorio especificado.

        Args:
            rar_path: Path al archivo .rar
            output_dir: Directorio de extracción
            progress_cb: Callback de progreso

        Returns:
            Dict con success, files_extracted, output_dir, scripts_found
        """
        result: dict[str, Any] = {
            "success": False,
            "rar_path": rar_path,
            "output_dir": output_dir,
            "files_extracted": [],
            "scripts_found": [],
            "error": None,
        }

        try:
            if not os.path.exists(rar_path):
                result["error"] = f"Archivo no encontrado: {rar_path}"
                return result

            if not self.can_extract_rar():
                result["error"] = "unrar.exe o 7z.exe no encontrado. Instale WinRAR o 7-Zip."
                return result

            os.makedirs(output_dir, exist_ok=True)

            if progress_cb:
                progress_cb(f"📦 RARを展開中: {os.path.basename(rar_path)}")

            # Extraer con rarfile
            with rarfile.RarFile(rar_path) as rf:
                file_list = rf.infolist()

                if progress_cb:
                    progress_cb(f"  📁 {len(file_list)}個のファイル")

                for i, member in enumerate(file_list):
                    if self._cancel_flag.is_set():
                        if progress_cb:
                            progress_cb("⛔ キャンセルされました")
                        break

                    try:
                        rf.extract(member, output_dir)
                        extracted_path = os.path.join(output_dir, member.filename)
                        result["files_extracted"].append(extracted_path)

                        # Detectar scripts ejecutables
                        if self._is_script(extracted_path):
                            result["scripts_found"].append(extracted_path)
                            if progress_cb:
                                progress_cb(f"  ⚡ スクリ립ト検出: {member.filename}")

                    except Exception as e:
                        if progress_cb:
                            progress_cb(f"  ⚠️ 展開エラー {member.filename}: {e}")

            result["success"] = True
            if progress_cb:
                progress_cb(f"✅ {len(result['files_extracted'])}個のファイルを展開")

        except Exception as e:
            result["error"] = str(e)

        return result

    def _is_script(self, file_path: str) -> bool:
        """Determina si un archivo es un script ejecutable."""
        ext = os.path.splitext(file_path)[1].lower()
        script_extensions = {
            ".ps1",
            ".bat",
            ".cmd",
            ".vbs",
            ".vbe",
            ".exe",
            ".msi",
            ".reg",
            ".py",
            ".pyw",
            ".sh",
            ".bash",
        }
        return ext in script_extensions

    def find_rar_files(self, directory: str) -> list[dict]:
        """Busca archivos RAR en un directorio.

        Args:
            directory: Directorio a buscar

        Returns:
            Lista de dicts con {path, filename, size_mb, modified}
        """
        results: list[dict[str, Any]] = []

        try:
            path = Path(directory)
            if not path.exists():
                return results

            for f in path.rglob("*.rar"):
                try:
                    stat = f.stat()
                    results.append(
                        {
                            "path": str(f),
                            "filename": f.name,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified": Path(f).stat().st_mtime,
                        }
                    )
                except Exception:
                    continue

        except Exception as e:
            print(f"Error buscando RARs: {e}")

        return sorted(results, key=lambda x: x["size_mb"], reverse=True)

    def run_script(self, script_path: str, progress_cb: Callable | None = None) -> dict:
        """Ejecuta un script de migración.

        Args:
            script_path: Path al script a ejecutar
            progress_cb: Callback de progreso

        Returns:
            Dict con success, output, error
        """
        result = {
            "success": False,
            "script_path": script_path,
            "output": "",
            "error": None,
        }

        try:
            ext = os.path.splitext(script_path)[1].lower()
            filename = os.path.basename(script_path)

            if progress_cb:
                progress_cb(f"🚀 スクリプトを実行中: {filename}")

            if ext == ".ps1":
                cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path]
                result["output"] = self._run_powershell(script_path, progress_cb)
            elif ext in (".bat", ".cmd"):
                cmd = ["cmd", "/c", script_path]
                result["output"] = self._run_cmd(cmd, progress_cb)
            elif ext == ".vbs":
                cmd = ["cscript", "//Nologo", script_path]
                result["output"] = self._run_cmd(cmd, progress_cb)
            elif ext == ".exe":
                result["output"] = self._run_cmd([script_path], progress_cb)
            else:
                result["error"] = f"未知のスクリプト形式: {ext}"
                return result

            result["success"] = True
            if progress_cb:
                progress_cb("✅ スクリプト完了")

        except Exception as e:
            result["error"] = str(e)

        return result

    def _run_powershell(self, script_path: str, progress_cb: Callable | None = None) -> str:
        """Ejecuta un script PowerShell."""
        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            script_path,
        ]

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                timeout=300,  # 5 min timeout
            )
            return (result.stdout or "") + (result.stderr or "")
        except subprocess.TimeoutExpired:
            return "⏱️ スクリプトがタイムアウトしました (5分)"
        except Exception as e:
            return f"❌ エラー: {e}"

    def _run_cmd(self, cmd: list[str], progress_cb: Callable | None = None) -> str:
        """Ejecuta un comando CMD."""
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                timeout=300,
            )
            return (result.stdout or "") + (result.stderr or "")
        except subprocess.TimeoutExpired:
            return "⏱️ タイムアウトしました (5分)"
        except Exception as e:
            return f"❌ エラー: {e}"

    def get_extract_dir(self) -> str:
        """Devuelve el directorio temporal de extracción."""
        base = Path(tempfile.gettempdir()) / "UNS_Shell_Tools"
        base.mkdir(parents=True, exist_ok=True)
        return str(base)
