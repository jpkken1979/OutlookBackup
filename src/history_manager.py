"""
UNS Backup v2.0 - Manejador de historial
==========================================
Escanea la carpeta de backups y lista todas las sesiones previas.
Se basa en los report.json que genera backup_engine.
"""

import datetime
import json
import shutil
from pathlib import Path
from typing import Any


class BackupHistory:
    """Lee el historial de backups previos."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def list_backups(self) -> list[dict]:
        """Devuelve lista de backups previos, ordenados por fecha desc."""
        backups: list[dict] = []
        if not self.base_dir.exists():
            return backups

        for entry in self.base_dir.iterdir():
            if not entry.is_dir():
                continue
            if not entry.name.startswith("backup_"):
                continue

            backup_info = self._read_backup(entry)
            if backup_info:
                backups.append(backup_info)

        backups.sort(key=lambda b: b.get("start_time", ""), reverse=True)
        return backups

    def _read_backup(self, backup_dir: Path) -> dict | None:
        """Lee el report.json y devuelve info estructurada."""
        report_path = backup_dir / "report.json"
        info: dict[str, Any] = {
            "path": str(backup_dir),
            "name": backup_dir.name,
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0,
            "accounts_count": 0,
            "total_emails": 0,
            "total_size_mb": 0,
            "errors_count": 0,
            "status": "unknown",
            "pst_files": [],
            "html_report": None,
        }

        try:
            if report_path.exists():
                with open(report_path, encoding="utf-8") as f:
                    data = json.load(f)

                info["start_time"] = data.get("start_time")
                info["end_time"] = data.get("end_time")
                info["duration_seconds"] = data.get("duration_seconds", 0)

                accounts = data.get("accounts_processed", [])
                info["accounts_count"] = len(accounts)
                info["total_emails"] = data.get("total_emails", 0)

                total_size = sum(a.get("size_mb", 0) for a in accounts)
                info["total_size_mb"] = round(total_size, 2)

                errors = data.get("errors", [])
                info["errors_count"] = len(errors)

                # Status
                success_accounts = sum(1 for a in accounts if a.get("success"))
                if success_accounts == 0:
                    info["status"] = "failed"
                elif success_accounts < len(accounts):
                    info["status"] = "partial"
                else:
                    info["status"] = "success"
            else:
                # Sin report.json → tratar de inferir desde nombre
                info["status"] = "incomplete"

            # Buscar archivos PST y HTML report.
            # Nota: nombre `pst_file` (no `f`) para evitar shadowing del `f`
            # del `with open() as f:` arriba — mypy quedaba confundido con el tipo.
            for pst_file in backup_dir.glob("*.pst"):
                size_mb = round(pst_file.stat().st_size / (1024 * 1024), 2)
                info["pst_files"].append(
                    {
                        "name": pst_file.name,
                        "size_mb": size_mb,
                        "path": str(pst_file),
                    }
                )

            html_path = backup_dir / "report.html"
            if html_path.exists():
                info["html_report"] = str(html_path)

            # Si el start_time no está, usar mtime de la carpeta
            if info["start_time"] is None:
                mtime = backup_dir.stat().st_mtime
                info["start_time"] = datetime.datetime.fromtimestamp(mtime).isoformat()

            return info

        except Exception as e:
            print(f"Error leyendo {backup_dir}: {e}")
            return None

    def delete_backup(self, backup_path: str) -> bool:
        """Borra una sesión de backup completa."""
        try:
            target = Path(backup_path)
            if not target.exists():
                return False
            # Seguridad: solo borrar si el path está dentro de base_dir
            try:
                target.resolve().relative_to(self.base_dir.resolve())
            except ValueError:
                print(f"Path fuera de base_dir, no se borra: {target}")
                return False

            if not target.name.startswith("backup_"):
                print(f"Nombre no es de backup: {target.name}")
                return False

            shutil.rmtree(target)
            return True
        except Exception as e:
            print(f"Error borrando: {e}")
            return False

    def cleanup_old(self, keep_last: int) -> list[str]:
        """Borra backups viejos manteniendo solo los últimos N. Devuelve los borrados."""
        if keep_last <= 0:
            return []

        backups = self.list_backups()
        if len(backups) <= keep_last:
            return []

        deleted = []
        # Solo borrar exitosos para no perder los que fallaron por revisar
        successful = [b for b in backups if b.get("status") == "success"]

        if len(successful) <= keep_last:
            return []

        to_delete = successful[keep_last:]
        for backup in to_delete:
            if self.delete_backup(backup["path"]):
                deleted.append(backup["path"])

        return deleted
