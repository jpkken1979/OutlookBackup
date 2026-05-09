"""
UNS Backup v3.0 - API Bridge Python ↔ JavaScript
=================================================
Todas las funciones que la UI HTML/JS puede llamar a través de pywebview.
"""

import os
import sys
import json
import datetime
import threading
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

# Asegurar que src/ esté en path
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

log = logging.getLogger("uns-api")


class API:
    """Bridge entre el frontend HTML/JS y el backend Python.

    Todas las funciones públicas (sin guion bajo) son accesibles desde JS
    vía `window.pywebview.api.<function_name>(args)`.
    """

    def __init__(self):
        from config import Config
        self.config = Config()
        self.outlook_client = None
        self.accounts = []

        # Estado del backup actual
        self._backup_engine = None
        self._backup_log = []
        self._backup_state = "idle"   # idle | running | success | failed
        self._backup_result = None    # str con la ruta cuando terminó
        self._backup_lock = threading.Lock()

        # Estado del import actual
        self._import_engine = None
        self._import_log = []
        self._import_state = "idle"
        self._import_result = None
        self._import_lock = threading.Lock()

    # ========================================================
    # Conexión a Outlook
    # ========================================================

    def connect_outlook(self) -> Dict:
        """Inicia conexión a Outlook. Devuelve estado."""
        try:
            from outlook_client import OutlookClient, WIN32_AVAILABLE
            if not WIN32_AVAILABLE:
                return {"success": False, "error": "pywin32 not available"}

            self.outlook_client = OutlookClient()
            return {"success": True, "message": "Connected to Outlook"}
        except Exception as e:
            log.exception("connect_outlook")
            return {"success": False, "error": str(e)}

    def detect_accounts(self) -> Dict:
        """Detecta todas las cuentas configuradas en Outlook."""
        if not self.outlook_client:
            r = self.connect_outlook()
            if not r["success"]:
                return r

        try:
            accounts = self.outlook_client.list_accounts()
            self.accounts = accounts
            domain = self.config.get("domain_filter", "uns-kikaku.com")

            return {
                "success": True,
                "accounts": [
                    {
                        "smtp": a.smtp_address,
                        "display_name": a.display_name,
                        "type": a.account_type,
                        "matches_domain": a.matches_domain(domain),
                    }
                    for a in accounts
                ],
            }
        except Exception as e:
            log.exception("detect_accounts")
            return {"success": False, "error": str(e), "accounts": []}

    # ========================================================
    # Configuración
    # ========================================================

    def get_config(self) -> Dict:
        """Devuelve toda la configuración actual."""
        return dict(self.config.data)

    def set_config(self, key: str, value: Any) -> Dict:
        """Actualiza un setting y persiste."""
        try:
            self.config.set(key, value)
            self.config.save()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_config(self, updates: Dict) -> Dict:
        """Actualiza varios settings de una vez."""
        try:
            for k, v in updates.items():
                self.config.set(k, v)
            self.config.save()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================
    # File system helpers (diálogos nativos)
    # ========================================================

    def choose_folder(self, initial: str = None) -> Optional[str]:
        """Abre un diálogo nativo para elegir carpeta."""
        try:
            import webview
            window = webview.windows[0] if webview.windows else None
            if not window:
                return None
            result = window.create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=initial or str(Path.home()),
            )
            if result:
                return result[0] if isinstance(result, (list, tuple)) else result
            return None
        except Exception as e:
            log.exception("choose_folder")
            return None

    def choose_files(self, initial: str = None,
                     extensions: List[str] = None) -> List[str]:
        """Abre diálogo para elegir múltiples archivos."""
        try:
            import webview
            window = webview.windows[0] if webview.windows else None
            if not window:
                return []
            file_types = ()
            if extensions:
                desc = "Outlook Data Files"
                pattern = ";".join(f"*.{e}" for e in extensions)
                file_types = (f"{desc} ({pattern})", "All files (*.*)")
            result = window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=initial or str(Path.home()),
                allow_multiple=True,
                file_types=file_types,
            )
            return list(result) if result else []
        except Exception as e:
            log.exception("choose_files")
            return []

    def open_path(self, path: str) -> Dict:
        """Abre una carpeta o archivo en el explorador."""
        try:
            os.startfile(path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================
    # BACKUP
    # ========================================================

    def estimate_backup_size(self, smtp_addresses: List[str]) -> Dict:
        """Estima cuántos emails y MB tienen las cuentas seleccionadas."""
        if not self.accounts:
            return {"success": False, "error": "No accounts detected yet"}

        total_emails = 0
        try:
            for acc in self.accounts:
                if acc.smtp_address not in smtp_addresses:
                    continue
                try:
                    inbox = self.outlook_client.get_account_inbox(acc)
                    if inbox:
                        total_emails += inbox.Items.Count
                except Exception:
                    pass

            return {
                "success": True,
                "total_emails": total_emails,
                "estimated_mb": total_emails * 0.05,  # ~50KB/email avg
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_backup(self, params: Dict) -> Dict:
        """Inicia un backup en background. Devuelve un ID para polling."""
        with self._backup_lock:
            if self._backup_state == "running":
                return {"success": False, "error": "Already running"}

            try:
                from backup_engine import BackupEngine

                output_dir = params.get("output_dir", "")
                smtp_list = params.get("accounts", [])
                fmt = params.get("format", "pst")

                if not output_dir:
                    return {"success": False, "error": "output_dir required"}

                selected = [
                    a for a in self.accounts if a.smtp_address in smtp_list
                ]
                if not selected:
                    return {"success": False, "error": "No accounts selected"}

                os.makedirs(output_dir, exist_ok=True)
                self._backup_log = []
                self._backup_state = "running"
                self._backup_result = None

                self._backup_engine = BackupEngine(
                    outlook_client=self.outlook_client,
                    output_dir=output_dir,
                    selected_accounts=selected,
                    export_format=fmt,
                )

                def progress(msg):
                    self._backup_log.append({
                        "ts": datetime.datetime.now().isoformat(),
                        "msg": msg,
                    })

                def finish(success, info):
                    with self._backup_lock:
                        self._backup_state = "success" if success else "failed"
                        self._backup_result = info

                    # Si se pidió inventario, ejecutarlo
                    if success and params.get("export_inventory"):
                        self._auto_export_inventory(
                            backup_dir=info,
                            smtp_list=smtp_list,
                            include_servers=params.get("inv_servers", True),
                            include_passwords=params.get("inv_passwords", False),
                            master_password=params.get("master_password"),
                        )

                self._backup_engine.run_async(progress, finish)
                return {"success": True}
            except Exception as e:
                self._backup_state = "failed"
                log.exception("start_backup")
                return {"success": False, "error": str(e)}

    def get_backup_progress(self) -> Dict:
        """Polling: estado actual del backup."""
        with self._backup_lock:
            return {
                "state": self._backup_state,
                "log": self._backup_log[-50:],   # últimos 50 mensajes
                "log_count": len(self._backup_log),
                "result": self._backup_result,
            }

    def cancel_backup(self) -> Dict:
        """Cancela el backup en curso."""
        if self._backup_engine:
            try:
                self._backup_engine.cancel()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No backup running"}

    def _auto_export_inventory(self, backup_dir, smtp_list,
                                  include_servers, include_passwords,
                                  master_password):
        try:
            from account_inventory import build_inventory, save_inventory
            inventory = build_inventory(
                outlook_client=self.outlook_client,
                selected_smtps=smtp_list,
                include_servers=include_servers,
                include_passwords=include_passwords,
            )
            path = save_inventory(inventory, backup_dir, master_password)
            self._backup_log.append({
                "ts": datetime.datetime.now().isoformat(),
                "msg": f"📋 Inventario exportado: {os.path.basename(path)}",
            })
        except Exception as e:
            self._backup_log.append({
                "ts": datetime.datetime.now().isoformat(),
                "msg": f"⚠️ Error inventario: {e}",
            })

    # ========================================================
    # IMPORT (RESTORE)
    # ========================================================

    def search_pst_files(self, folder: str) -> Dict:
        """Busca PSTs en una carpeta y devuelve lista con metadata."""
        try:
            from import_engine import find_pst_files
            files = find_pst_files(folder, recursive=True)
            result = []
            for path in files:
                try:
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    mtime = os.path.getmtime(path)
                    fname = os.path.basename(path)

                    # Inferir cuenta del nombre
                    account = ""
                    if "_at_" in fname:
                        parts = fname.replace(".pst", "").split("_at_")
                        if len(parts) == 2:
                            account = f"{parts[0]}@" + parts[1].replace("_", ".")

                    result.append({
                        "path": path,
                        "filename": fname,
                        "account": account,
                        "size_mb": round(size_mb, 1),
                        "created": datetime.datetime.fromtimestamp(
                            mtime).strftime("%Y-%m-%d %H:%M"),
                    })
                except Exception:
                    continue
            return {"success": True, "files": result}
        except Exception as e:
            return {"success": False, "error": str(e), "files": []}

    def preview_pst(self, pst_path: str) -> Dict:
        """Inspecciona un PST sin importarlo permanentemente."""
        try:
            from pst_inspector import PSTInspector
            if not self.outlook_client:
                self.connect_outlook()
            inspector = PSTInspector(self.outlook_client)
            info = inspector.inspect(pst_path)
            return {"success": True, "info": info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_import(self, params: Dict) -> Dict:
        """Inicia importación de PSTs."""
        with self._import_lock:
            if self._import_state == "running":
                return {"success": False, "error": "Already running"}

            try:
                from import_engine import ImportEngine

                files = params.get("files", [])
                mode = params.get("mode", "separate_folder")
                target = params.get("target_smtp")

                if not files:
                    return {"success": False, "error": "No files selected"}

                if not self.outlook_client:
                    self.connect_outlook()

                self._import_log = []
                self._import_state = "running"
                self._import_result = None

                self._import_engine = ImportEngine(
                    outlook_client=self.outlook_client,
                    pst_files=files,
                    mode=mode,
                    target_smtp=target,
                )

                def progress(msg):
                    self._import_log.append({
                        "ts": datetime.datetime.now().isoformat(),
                        "msg": msg,
                    })

                def finish(success, ok_count, total):
                    with self._import_lock:
                        self._import_state = "success" if success else "failed"
                        self._import_result = {
                            "ok_count": ok_count, "total": total
                        }

                self._import_engine.run_async(progress, finish)
                return {"success": True}
            except Exception as e:
                self._import_state = "failed"
                return {"success": False, "error": str(e)}

    def get_import_progress(self) -> Dict:
        with self._import_lock:
            return {
                "state": self._import_state,
                "log": self._import_log[-50:],
                "log_count": len(self._import_log),
                "result": self._import_result,
            }

    # ========================================================
    # HISTORY
    # ========================================================

    def list_history(self, base_dir: str = None) -> Dict:
        """Lista todos los backups previos."""
        try:
            from history_manager import BackupHistory
            base = base_dir or self.config.get("default_backup_dir")
            history = BackupHistory(base)
            return {"success": True, "backups": history.list_backups()}
        except Exception as e:
            return {"success": False, "error": str(e), "backups": []}

    def delete_history(self, path: str) -> Dict:
        try:
            from history_manager import BackupHistory
            base = self.config.get("default_backup_dir")
            history = BackupHistory(base)
            if history.delete_backup(path):
                return {"success": True}
            return {"success": False, "error": "Could not delete"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================
    # SCHEDULER
    # ========================================================

    def get_schedule_info(self) -> Dict:
        try:
            from scheduler import task_exists, get_task_info, calculate_next_run
            exists = task_exists()
            info = get_task_info() if exists else None
            return {
                "success": True,
                "active": exists,
                "info": info,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "active": False}

    def save_schedule(self, params: Dict) -> Dict:
        try:
            from scheduler import create_task

            updates = {
                "schedule_enabled": True,
                "schedule_frequency": params.get("frequency"),
                "schedule_day_of_week": params.get("day_of_week"),
                "schedule_time": params.get("time"),
                "schedule_custom_days": params.get("custom_days", 7),
                "schedule_save_to": params.get("save_to"),
                "schedule_scope": params.get("scope"),
                "schedule_keep_last": params.get("keep_last", 4),
            }
            for k, v in updates.items():
                self.config.set(k, v)
            self.config.save()

            ok = create_task(
                frequency=params.get("frequency"),
                time_hhmm=params.get("time"),
                day_of_week=params.get("day_of_week"),
                custom_days=params.get("custom_days", 7),
            )
            return {"success": ok}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_schedule(self) -> Dict:
        try:
            from scheduler import delete_task
            ok = delete_task()
            self.config.set("schedule_enabled", False)
            self.config.save()
            return {"success": ok}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_schedule_now(self) -> Dict:
        try:
            from scheduler import run_task_now
            return {"success": run_task_now()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================
    # ACCOUNT INVENTORY (manual export)
    # ========================================================

    def export_inventory(self, params: Dict) -> Dict:
        try:
            from account_inventory import build_inventory, save_inventory
            output_dir = params.get("output_dir")
            smtp_list = params.get("accounts", [])
            include_servers = params.get("include_servers", True)
            include_passwords = params.get("include_passwords", False)
            master_password = params.get("master_password")

            if include_passwords and not master_password:
                return {"success": False, "error": "Master password required"}

            inventory = build_inventory(
                outlook_client=self.outlook_client,
                selected_smtps=smtp_list,
                include_servers=include_servers,
                include_passwords=include_passwords,
            )

            os.makedirs(output_dir, exist_ok=True)
            path = save_inventory(inventory, output_dir, master_password)
            return {"success": True, "path": path, "count": len(inventory)}
        except Exception as e:
            log.exception("export_inventory")
            return {"success": False, "error": str(e)}

    # ========================================================
    # ACCOUNT DETAILS (single account)
    # ========================================================

    def get_account_details(self, smtp: str) -> Dict:
        """Devuelve detalles completos de una cuenta."""
        try:
            from outlook_client import WIN32_AVAILABLE

            if not self.outlook_client:
                self.connect_outlook()

            # Buscar en las cuentas ya detectadas
            account = None
            for a in self.accounts:
                if a.smtp_address == smtp:
                    account = a
                    break

            if not account:
                return {"success": False, "error": "Account not found"}

            from account_inventory import _read_registry_servers, _read_credential_vault

            servers = _read_registry_servers(smtp) if WIN32_AVAILABLE else None
            creds = _read_credential_vault(smtp) if WIN32_AVAILABLE else None

            return {
                "success": True,
                "smtp": smtp,
                "display_name": account.display_name,
                "account_type": account.account_type,
                "matches_domain": account.matches_domain(self.config.get("domain_filter", "uns-kikaku.com")),
                "server_settings": servers or {},
                "credential_count": len(creds) if creds else 0,
                "inventory_exportable": True,
            }
        except Exception as e:
            log.exception("get_account_details")
            return {"success": False, "error": str(e)}

    # ========================================================
    # CONNECTION TESTER
    # ========================================================

    def test_connection(self, params: Dict) -> Dict:
        """Testea conectividad IMAP/SMTP de una cuenta."""
        try:
            smtp = params.get("smtp")
            if not smtp:
                return {"success": False, "error": "smtp required"}

            from connection_tester import ConnectionTester
            from account_inventory import _read_registry_servers, _read_credential_vault
            from outlook_client import WIN32_AVAILABLE

            timeout = params.get("timeout", 10)
            protocol = params.get("protocol", "auto")  # "auto", "imap", "smtp"

            servers = _read_registry_servers(smtp) if WIN32_AVAILABLE else None
            if not servers:
                return {"success": False, "error": "No server settings found for this account"}

            tester = ConnectionTester(timeout=timeout)
            results = {"imap": None, "smtp": None}

            if protocol in ("auto", "imap"):
                imap_s = servers.get("imap_server", "")
                imap_p = servers.get("imap_port", 993)
                imap_ssl = servers.get("imap_ssl", True)
                if imap_s:
                    imap_creds = _read_credential_vault(smtp) if WIN32_AVAILABLE else None
                    password = imap_creds[0].get("password", "") if imap_creds else ""
                    result = tester.test_imap(imap_s, imap_p, imap_ssl, smtp, password)
                    results["imap"] = {
                        "success": result.success,
                        "message": result.message,
                        "latency_ms": result.latency_ms,
                        "server_banner": result.server_banner,
                    }

            if protocol in ("auto", "smtp"):
                smtp_s = servers.get("smtp_server", "")
                smtp_p = servers.get("smtp_port", 587)
                smtp_ssl = servers.get("smtp_ssl", False)
                if smtp_s:
                    smtp_creds = _read_credential_vault(smtp) if WIN32_AVAILABLE else None
                    password = smtp_creds[0].get("password", "") if smtp_creds else ""
                    result = tester.test_smtp(smtp_s, smtp_p, smtp_ssl, smtp, password)
                    results["smtp"] = {
                        "success": result.success,
                        "message": result.message,
                        "latency_ms": result.latency_ms,
                        "server_banner": result.server_banner,
                    }

            return {"success": True, "smtp": smtp, "results": results}
        except Exception as e:
            log.exception("test_connection")
            return {"success": False, "error": str(e)}

    # ========================================================
    # EXPORT SINGLE ACCOUNT INVENTORY
    # ========================================================

    def export_account_inventory(self, params: Dict) -> Dict:
        """Exporta inventario de UNA cuenta especifica."""
        try:
            smtp = params.get("smtp")
            if not smtp:
                return {"success": False, "error": "smtp required"}

            from account_inventory import build_inventory, save_inventory

            if not self.outlook_client:
                self.connect_outlook()

            include_passwords = params.get("include_passwords", False)
            master_password = params.get("master_password")

            if include_passwords and not master_password:
                return {"success": False, "error": "Master password required"}

            inventory = build_inventory(
                outlook_client=self.outlook_client,
                selected_smtp_addresses=[smtp],
                include_servers=True,
                include_passwords=include_passwords,
            )

            output_dir = params.get("output_dir", self.config.get("default_backup_dir", str(Path.home())))
            os.makedirs(output_dir, exist_ok=True)

            saved = save_inventory(inventory, output_dir, master_password)
            return {"success": True, "path": saved, "count": len(inventory.get("accounts", []))}
        except Exception as e:
            log.exception("export_account_inventory")
            return {"success": False, "error": str(e)}

    # ========================================================
    # CACHE BACKUP (offline, sin servidor)
    # ========================================================

    def scan_cache_files(self) -> Dict:
        """Escanea las carpetas de Outlook buscando OST/PST locales.
        NO requiere conexión a servidor."""
        try:
            from cache_backup import find_cache_files, map_cache_to_account
            files = find_cache_files()
            files = map_cache_to_account(files)
            return {"success": True, "files": files, "count": len(files)}
        except Exception as e:
            log.exception("scan_cache_files")
            return {"success": False, "error": str(e), "files": []}

    def start_cache_backup(self, params: Dict) -> Dict:
        """Inicia backup directo de archivos OST/PST."""
        with self._backup_lock:
            if self._backup_state == "running":
                return {"success": False, "error": "Already running"}

            try:
                from cache_backup import CacheBackupEngine

                files = params.get("files", [])
                output_dir = params.get("output_dir", "")
                verify = params.get("verify_integrity", True)
                close_outlook = params.get("close_outlook", False)

                if not files:
                    return {"success": False, "error": "No files selected"}
                if not output_dir:
                    return {"success": False, "error": "output_dir required"}

                os.makedirs(output_dir, exist_ok=True)
                self._backup_log = []
                self._backup_state = "running"
                self._backup_result = None

                self._backup_engine = CacheBackupEngine(
                    cache_files=files,
                    output_dir=output_dir,
                    verify_integrity=verify,
                    close_outlook=close_outlook,
                )

                def progress(msg):
                    self._backup_log.append({
                        "ts": datetime.datetime.now().isoformat(),
                        "msg": msg,
                    })

                def finish(success, info):
                    with self._backup_lock:
                        self._backup_state = "success" if success else "failed"
                        self._backup_result = info

                self._backup_engine.run_async(progress, finish)
                return {"success": True}
            except Exception as e:
                self._backup_state = "failed"
                log.exception("start_cache_backup")
                return {"success": False, "error": str(e)}

    # ========================================================
    # SHELL EXTRACTOR (RAR + Migration Scripts)
    # ========================================================

    def can_extract_rar(self) -> Dict:
        """Verifica si se puede extraer RAR (unrar/7z instalado)."""
        try:
            from shell_extractor import ShellExtractor
            extractor = ShellExtractor()
            return {
                "success": True,
                "available": extractor.can_extract_rar(),
                "unrar_path": extractor.unrar_path,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "available": False}

    def find_rar_files(self, directory: str) -> Dict:
        """Busca archivos RAR en un directorio."""
        try:
            from shell_extractor import ShellExtractor
            extractor = ShellExtractor()
            files = extractor.find_rar_files(directory)
            return {"success": True, "files": files, "count": len(files)}
        except Exception as e:
            log.exception("find_rar_files")
            return {"success": False, "error": str(e), "files": []}

    def extract_rar(self, params: Dict) -> Dict:
        """Extrae un archivo RAR al directorio temporal."""
        try:
            from shell_extractor import ShellExtractor

            rar_path = params.get("rar_path", "")
            if not rar_path:
                return {"success": False, "error": "rar_path required"}

            extractor = ShellExtractor()
            output_dir = extractor.get_extract_dir()

            if not extractor.can_extract_rar():
                return {
                    "success": False,
                    "error": "unrar.exe o 7z.exe no encontrado. Instale WinRAR o 7-Zip."
                }

            def progress(msg):
                self._shell_log.append({
                    "ts": datetime.datetime.now().isoformat(),
                    "msg": msg,
                })

            def finish(success, info):
                with self._shell_lock:
                    self._shell_state = "success" if success else "failed"
                    self._shell_result = info

            self._shell_log = []
            self._shell_state = "running"
            self._shell_result = None
            self._shell_lock = threading.Lock()

            result = extractor.extract_rar(rar_path, output_dir, progress)
            return result

        except Exception as e:
            log.exception("extract_rar")
            return {"success": False, "error": str(e)}

    def get_shell_progress(self) -> Dict:
        """Polling del estado de extraccion/ejecucion."""
        with getattr(self, '_shell_lock', threading.Lock()):
            return {
                "state": getattr(self, '_shell_state', "idle"),
                "log": getattr(self, '_shell_log', [])[-50:],
                "result": getattr(self, '_shell_result', None),
            }

    def run_migration_script(self, params: Dict) -> Dict:
        """Ejecuta un script de migracion (PowerShell, batch, etc)."""
        try:
            from shell_extractor import ShellExtractor

            script_path = params.get("script_path", "")
            if not script_path:
                return {"success": False, "error": "script_path required"}

            if not os.path.exists(script_path):
                return {"success": False, "error": f"Script no encontrado: {script_path}"}

            extractor = ShellExtractor()

            self._shell_log = []
            self._shell_state = "running"
            self._shell_result = None
            self._shell_lock = threading.Lock()

            def progress(msg):
                self._shell_log.append({
                    "ts": datetime.datetime.now().isoformat(),
                    "msg": msg,
                })

            result = extractor.run_script(script_path, progress)

            with self._shell_lock:
                self._shell_state = "success" if result.get("success") else "failed"
                self._shell_result = result

            return result

        except Exception as e:
            log.exception("run_migration_script")
            return {"success": False, "error": str(e)}

    def open_extracted_folder(self) -> Dict:
        """Abre la carpeta de extraccion en el explorador."""
        try:
            from shell_extractor import ShellExtractor
            extractor = ShellExtractor()
            folder = extractor.get_extract_dir()
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
            return {"success": True, "path": folder}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================
    # App lifecycle
    # ========================================================

    def get_app_info(self) -> Dict:
        return {
            "version": "3.1.1",
            "company": "ユニバーサル企画株式会社",
            "company_short": "UNS-Kikaku",
        }
