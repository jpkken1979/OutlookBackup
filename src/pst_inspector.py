"""
UNS Backup v2.0 - PST Inspector
=================================
Permite ver el contenido de un PST sin importarlo permanentemente.
Lo monta temporalmente, recorre carpetas, lo desmonta.
"""

import os
from typing import Any

from path_utils import safe_path


class PSTInspector:
    """Inspecciona el contenido de un PST sin agregarlo permanentemente."""

    def __init__(self, outlook_client: Any) -> None:
        self.client = outlook_client

    def inspect(self, pst_path: str) -> dict:
        """
        Monta el PST, recorre su contenido, lo desmonta.
        Devuelve estadísticas: carpetas, total emails, top folders.
        """
        result: dict[str, Any] = {
            "file": pst_path,
            "filename": os.path.basename(pst_path),
            "size_mb": 0,
            "exists": False,
            "mounted": False,
            "total_emails": 0,
            "total_folders": 0,
            "folders": [],  # [{name, count, depth}]
            "date_range": {"oldest": None, "newest": None},
            "senders": {},  # {"sender@x.com": count}
            "error": None,
        }

        try:
            if not os.path.exists(pst_path):
                result["error"] = "ファイルが存在しません"
                return result

            result["exists"] = True
            result["size_mb"] = round(os.path.getsize(pst_path) / (1024 * 1024), 2)

            # Montar PST. safe_path() agrega prefijo \\?\ si pst_path > 240 chars (Fase 3).
            self.client.namespace.AddStore(safe_path(pst_path))
            result["mounted"] = True

            # Encontrar el store que acabamos de montar
            target_store = None
            for store in self.client.namespace.Stores:
                try:
                    if store.FilePath and os.path.normpath(store.FilePath) == os.path.normpath(
                        pst_path
                    ):
                        target_store = store
                        break
                except Exception:
                    continue

            if target_store is None:
                result["error"] = "PSTをマウントできませんでした"
                return result

            root = target_store.GetRootFolder()
            self._walk(root, result, depth=0)

            # Desmontar
            try:
                self.client.namespace.RemoveStore(root)
                result["mounted"] = False
            except Exception:
                pass

            # Top 5 senders
            sorted_senders = sorted(result["senders"].items(), key=lambda x: x[1], reverse=True)[:5]
            result["top_senders"] = sorted_senders

        except Exception as e:
            result["error"] = str(e)

        return result

    def _walk(self, folder: Any, result: dict, depth: int) -> None:
        """Recorre carpetas recursivamente."""
        try:
            name = folder.Name
            try:
                items = folder.Items
                count = items.Count
            except Exception:
                count = 0

            if count > 0:
                result["folders"].append(
                    {
                        "name": name,
                        "count": count,
                        "depth": depth,
                    }
                )
                result["total_emails"] += count
                result["total_folders"] += 1

                # Sample de senders y fechas (no escanear todos por velocidad)
                sample_size = min(count, 50)
                try:
                    for i in range(1, sample_size + 1):
                        try:
                            item = items.Item(i)
                            if hasattr(item, "SenderEmailAddress"):
                                sender = item.SenderEmailAddress or "(unknown)"
                                result["senders"][sender] = result["senders"].get(sender, 0) + 1

                            if hasattr(item, "ReceivedTime"):
                                rt = item.ReceivedTime
                                rt_iso = rt.strftime("%Y-%m-%d") if rt else None
                                if rt_iso:
                                    if (
                                        result["date_range"]["oldest"] is None
                                        or rt_iso < result["date_range"]["oldest"]
                                    ):
                                        result["date_range"]["oldest"] = rt_iso
                                    if (
                                        result["date_range"]["newest"] is None
                                        or rt_iso > result["date_range"]["newest"]
                                    ):
                                        result["date_range"]["newest"] = rt_iso
                        except Exception:
                            continue
                except Exception:
                    pass

            # Recursión
            for sub in folder.Folders:
                self._walk(sub, result, depth + 1)

        except Exception as e:
            print(f"walk error: {e}")
