"""
UNS Backup v2.0 - Motor de Import PST
=======================================
Importa archivos .pst en Outlook con 3 modos:
1. separate_folder: monta el PST como carpeta separada en sidebar
2. merge: copia los items del PST al Inbox de la cuenta destino
3. new_files: cada PST como data file independiente
"""

import os
import threading
from collections.abc import Callable
from pathlib import Path

try:
    import pythoncom  # noqa: F401  # availability probe
    import win32com.client  # noqa: F401  # availability probe
except ImportError:
    pass


class ImportEngine:
    """Motor de import con threading."""

    def __init__(
        self,
        outlook_client,
        pst_files: list[str],
        mode: str = "separate_folder",
        target_smtp: str | None = None,
    ):
        """
        :param outlook_client: instancia de OutlookClient
        :param pst_files: lista de paths absolutos a archivos .pst
        :param mode: 'separate_folder' | 'merge' | 'new_files'
        :param target_smtp: solo para mode='merge', cuenta destino
        """
        self.client = outlook_client
        self.pst_files = pst_files
        self.mode = mode
        self.target_smtp = target_smtp
        self._cancel_flag = threading.Event()
        self._thread: threading.Thread | None = None
        self.results = []

    def run_async(self, progress_cb: Callable, finish_cb: Callable):
        self._thread = threading.Thread(
            target=self._run_internal,
            args=(progress_cb, finish_cb),
            daemon=True,
        )
        self._thread.start()

    def cancel(self):
        self._cancel_flag.set()

    def _run_internal(self, progress_cb, finish_cb):
        try:
            progress_cb(f"📥 インポート開始 ({self.mode})")
            progress_cb(f"  PSTファイル数: {len(self.pst_files)}")

            success_count = 0
            for i, pst_path in enumerate(self.pst_files, 1):
                if self._cancel_flag.is_set():
                    progress_cb("⛔ キャンセルされました")
                    break

                progress_cb(f"\n[{i}/{len(self.pst_files)}] {os.path.basename(pst_path)}")

                try:
                    if self.mode == "separate_folder":
                        ok = self._import_as_separate_folder(pst_path, progress_cb)
                    elif self.mode == "merge":
                        ok = self._import_merge(pst_path, progress_cb)
                    else:  # new_files
                        ok = self._import_as_new_file(pst_path, progress_cb)

                    if ok:
                        success_count += 1
                        self.results.append({"file": pst_path, "success": True})
                    else:
                        self.results.append({"file": pst_path, "success": False})

                except Exception as e:
                    progress_cb(f"  ❌ エラー: {e}")
                    self.results.append({"file": pst_path, "success": False, "error": str(e)})

            progress_cb(f"\n✅ {success_count}/{len(self.pst_files)} 完了")
            finish_cb(success_count > 0, success_count, len(self.pst_files))

        except Exception as e:
            progress_cb(f"❌ 致命的エラー: {e}")
            finish_cb(False, 0, len(self.pst_files))

    # ===== MODE 1: Separate folder (default) =====
    def _import_as_separate_folder(self, pst_path: str, progress_cb) -> bool:
        """Monta el PST como una carpeta separada en el sidebar de Outlook."""
        try:
            progress_cb("  📁 PSTを別フォルダとして開いています...")
            self.client.namespace.AddStore(pst_path)
            progress_cb("  ✅ Outlookのサイドバーに表示されました")
            return True
        except Exception as e:
            progress_cb(f"  ❌ {e}")
            return False

    # ===== MODE 2: New file (similar to mode 1, distinct semantics) =====
    def _import_as_new_file(self, pst_path: str, progress_cb) -> bool:
        """Igual que separate_folder pero usando AddStoreEx con formato Unicode."""
        try:
            progress_cb("  🗂️ 新規データファイルとして開いています...")
            self.client.namespace.AddStoreEx(pst_path, 3)
            progress_cb("  ✅ データファイルが追加されました")
            return True
        except Exception:
            try:
                # Fallback al método simple si AddStoreEx falla
                self.client.namespace.AddStore(pst_path)
                progress_cb("  ✅ データファイルが追加されました(基本モード)")
                return True
            except Exception as e2:
                progress_cb(f"  ❌ {e2}")
                return False

    # ===== MODE 3: Merge into existing account =====
    def _import_merge(self, pst_path: str, progress_cb) -> bool:
        """Mergea items del PST al Inbox de la cuenta target."""
        try:
            if not self.target_smtp:
                progress_cb("  ❌ 復元先アカウントが未指定")
                return False

            progress_cb("  📂 PSTをマウント中...")
            self.client.namespace.AddStore(pst_path)

            # Buscar el store recién montado
            source_store = None
            for store in self.client.namespace.Stores:
                try:
                    if store.FilePath and os.path.normpath(store.FilePath) == os.path.normpath(
                        pst_path
                    ):
                        source_store = store
                        break
                except Exception:
                    continue

            if source_store is None:
                progress_cb("  ❌ マウントしたPSTが見つかりません")
                return False

            # Buscar el store destino (cuenta target)
            target_store = None
            for store in self.client.namespace.Stores:
                try:
                    if (
                        store.DisplayName == self.target_smtp
                        or self.target_smtp in store.DisplayName
                    ):
                        target_store = store
                        break
                except Exception:
                    continue

            if target_store is None:
                progress_cb(f"  ❌ 復元先アカウント({self.target_smtp})が見つかりません")
                self.client.namespace.RemoveStore(source_store.GetRootFolder())
                return False

            source_root = source_store.GetRootFolder()
            target_root = target_store.GetRootFolder()

            # Copiar carpetas recursivamente
            progress_cb("  📋 メールをコピー中...")
            count = self._merge_folders(source_root, target_root, progress_cb)
            progress_cb(f"  ✅ {count}個のフォルダをマージしました")

            # Desmontar el PST origen (el target queda con los datos)
            self.client.namespace.RemoveStore(source_root)
            return True

        except Exception as e:
            progress_cb(f"  ❌ {e}")
            return False

    def _merge_folders(self, source_folder, target_folder, progress_cb) -> int:
        """Copia subcarpetas y items del source al target."""
        count = 0
        try:
            for sub in source_folder.Folders:
                try:
                    name = sub.Name
                    if name in ["同期の問題", "Sync Issues", "Conflicts", "Search Folders"]:
                        continue

                    progress_cb(f"    └─ {name}")
                    sub.CopyTo(target_folder)
                    count += 1
                except Exception as e:
                    progress_cb(f"    ⚠️ {name}: {e}")
                    continue
        except Exception as e:
            print(f"merge error: {e}")
        return count


def find_pst_files(directory: str, recursive: bool = True) -> list[str]:
    """Busca todos los archivos .pst en un directorio."""
    pst_files = []
    try:
        path = Path(directory)
        if not path.exists():
            return []

        if recursive:
            pst_files = [str(p) for p in path.rglob("*.pst")]
        else:
            pst_files = [str(p) for p in path.glob("*.pst")]

    except Exception as e:
        print(f"Error buscando PSTs: {e}")

    return sorted(pst_files)
