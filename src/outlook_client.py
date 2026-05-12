"""
UNS Outlook Backup - Cliente Outlook
=====================================
Maneja toda la interacción con Outlook vía COM (pywin32).
Compatible con Outlook 2016, 2019, 2021, 365.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from outlook.protocols import OutlookAccountInfo

try:
    import pythoncom
    import win32com.client

    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


# Constantes de Outlook (olDefaultFolders)
OL_FOLDER_INBOX = 6
OL_FOLDER_SENT_MAIL = 5
OL_FOLDER_DRAFTS = 16
OL_FOLDER_DELETED = 3
OL_FOLDER_OUTBOX = 4

# Tipo de objeto = MailItem
OL_MAIL_ITEM = 43


class OutlookAccount:
    """Representa una cuenta de correo en Outlook."""

    def __init__(self, smtp_address: str, display_name: str, account_type: str, store_id: str = ""):
        self.smtp_address = smtp_address
        self.display_name = display_name
        self.account_type = account_type
        self.store_id = store_id
        self.folder_count = 0
        self.email_count = 0
        self.size_bytes = 0

    def matches_domain(self, domain: str) -> bool:
        """Verifica si la cuenta pertenece al dominio dado."""
        return self.smtp_address.lower().endswith(f"@{domain.lower()}")

    def to_dict(self) -> dict:
        return {
            "smtp": self.smtp_address,
            "name": self.display_name,
            "type": self.account_type,
            "folders": self.folder_count,
            "emails": self.email_count,
            "size_mb": round(self.size_bytes / (1024 * 1024), 2),
        }


class OutlookClient:
    """Cliente para interactuar con Outlook."""

    def __init__(self) -> None:
        if not WIN32_AVAILABLE:
            raise RuntimeError("pywin32 no instalado. Ejecuta: pip install pywin32")
        self.app: Any = None
        self.namespace: Any = None
        self._connect()

    def _connect(self) -> None:
        """Conecta a la instancia de Outlook (la abre si no está abierta)."""
        try:
            pythoncom.CoInitialize()
            self.app = win32com.client.Dispatch("Outlook.Application")
            self.namespace = self.app.GetNamespace("MAPI")
        except Exception as e:
            raise RuntimeError(f"No se pudo conectar a Outlook. ¿Está instalado?\nError: {e}")

    def list_accounts(self) -> list[OutlookAccount]:
        """Lista todas las cuentas configuradas en Outlook."""
        accounts = []
        try:
            for account in self.namespace.Accounts:
                try:
                    smtp = account.SmtpAddress or ""
                    name = account.DisplayName or smtp
                    acc_type = self._get_account_type(account)

                    acc = OutlookAccount(
                        smtp_address=smtp,
                        display_name=name,
                        account_type=acc_type,
                    )
                    accounts.append(acc)
                except Exception:
                    continue
        except Exception as e:
            print(f"Error listando cuentas: {e}")
        return accounts

    def _get_account_type(self, account: Any) -> str:
        """Detecta el tipo de cuenta (IMAP/POP/Exchange/Otro)."""
        try:
            ol_type = account.AccountType
            types = {
                0: "Exchange",
                1: "IMAP",
                2: "POP3",
                3: "HTTP",
                4: "EAS",
                5: "Otro",
            }
            return types.get(ol_type, "Desconocido")
        except Exception:
            return "Desconocido"

    def list_stores(self) -> list[dict]:
        """Lista todos los stores (PST/OST) configurados."""
        stores = []
        try:
            for store in self.namespace.Stores:
                try:
                    stores.append(
                        {
                            "display_name": store.DisplayName,
                            "file_path": store.FilePath or "",
                            "store_id": store.StoreID,
                            "is_data_file": store.IsDataFileStore,
                        }
                    )
                except Exception:
                    continue
        except Exception as e:
            print(f"Error listando stores: {e}")
        return stores

    def count_emails_for_account(
        self, account: OutlookAccountInfo, progress_cb: Callable | None = None
    ) -> dict:
        """Cuenta los correos de una cuenta específica."""
        result = {"total_emails": 0, "total_folders": 0, "total_size_bytes": 0, "folders": []}

        try:
            # Buscar el store que coincide con esta cuenta
            target_store = None
            for store in self.namespace.Stores:
                try:
                    if (
                        store.DisplayName == account.smtp_address
                        or store.DisplayName == account.display_name
                        or account.smtp_address in store.DisplayName
                    ):
                        target_store = store
                        break
                except Exception:
                    continue

            if target_store is None:
                # Fallback: usar inbox del namespace por defecto
                root = self.namespace.GetDefaultFolder(OL_FOLDER_INBOX).Parent
            else:
                root = target_store.GetRootFolder()

            self._walk_folders(root, result, progress_cb)

        except Exception as e:
            print(f"Error contando correos para {account.smtp_address}: {e}")

        return result

    def _walk_folders(
        self,
        folder: Any,
        result: dict,
        progress_cb: Callable | None = None,
        depth: int = 0,
    ) -> None:
        """Recorre recursivamente todas las carpetas y cuenta correos."""
        try:
            folder_name = folder.Name
            try:
                items = folder.Items
                count = items.Count
            except Exception:
                count = 0

            if count > 0:
                result["folders"].append(
                    {
                        "name": folder_name,
                        "depth": depth,
                        "count": count,
                    }
                )
                result["total_emails"] += count
                result["total_folders"] += 1

                if progress_cb:
                    progress_cb(f"  📁 {folder_name}: {count} correos")

            # Recursión en subcarpetas
            for subfolder in folder.Folders:
                self._walk_folders(subfolder, result, progress_cb, depth + 1)

        except Exception as e:
            print(f"Error en carpeta: {e}")

    def export_account_to_pst(
        self, account: OutlookAccountInfo, output_path: str, progress_cb: Callable | None = None
    ) -> bool:
        """
        Exporta una cuenta completa a un archivo .pst.
        Usa el método estándar de Outlook: AddStore + CopyTo.
        """
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if progress_cb:
                progress_cb(f"📦 Creando PST: {output_path}")

            # Verificar si el archivo ya existe (PST corrupto si existe vacío)
            if os.path.exists(output_path):
                os.remove(output_path)

            # Crear nuevo store PST (formato Unicode = UTF-8 compatible)
            self.namespace.AddStoreEx(output_path, 3)  # 3 = olStoreUnicode

            # Buscar el store recién creado
            new_store = None
            for store in self.namespace.Stores:
                try:
                    if store.FilePath and os.path.normpath(store.FilePath) == os.path.normpath(
                        output_path
                    ):
                        new_store = store
                        break
                except Exception:
                    continue

            if new_store is None:
                if progress_cb:
                    progress_cb("❌ No se pudo crear el PST")
                return False

            new_root = new_store.GetRootFolder()

            # Buscar el store de origen
            source_store = None
            for store in self.namespace.Stores:
                try:
                    if (
                        store.DisplayName == account.smtp_address
                        or account.smtp_address in store.DisplayName
                    ):
                        source_store = store
                        break
                except Exception:
                    continue

            if source_store is None:
                if progress_cb:
                    progress_cb(f"⚠️ No se encontró store para {account.smtp_address}")
                # Cerrar el PST creado
                self.namespace.RemoveStore(new_root)
                return False

            source_root = source_store.GetRootFolder()

            # Copiar todas las carpetas al nuevo PST
            if progress_cb:
                progress_cb("📋 Copiando carpetas...")

            self._copy_folder_recursive(source_root, new_root, progress_cb)

            # Cerrar el PST (importante para que se finalice el archivo)
            if progress_cb:
                progress_cb("💾 Cerrando archivo PST...")
            self.namespace.RemoveStore(new_root)

            if progress_cb:
                progress_cb(f"✅ Backup completado: {output_path}")

            return True

        except Exception as e:
            error_msg = f"❌ Error al exportar: {e}"
            if progress_cb:
                progress_cb(error_msg)
            print(error_msg)
            return False

    def _copy_folder_recursive(
        self, source_folder: Any, dest_folder: Any, progress_cb: Callable | None = None
    ) -> None:
        """Copia una carpeta y todas sus subcarpetas al destino."""
        try:
            for subfolder in source_folder.Folders:
                try:
                    folder_name = subfolder.Name

                    # Saltar carpetas del sistema que no se pueden copiar
                    if folder_name in ["同期の問題", "Sync Issues", "Conflicts"]:
                        continue

                    if progress_cb:
                        progress_cb(f"  📁 Copiando: {folder_name}")

                    # Copiar la carpeta entera (incluye items y subcarpetas)
                    subfolder.CopyTo(dest_folder)

                except Exception as e:
                    if progress_cb:
                        progress_cb(f"  ⚠️ Error copiando {folder_name}: {e}")
                    continue
        except Exception as e:
            print(f"Error en copia recursiva: {e}")

    def export_folder_to_msg_files(
        self, account: OutlookAccountInfo, output_dir: str, progress_cb: Callable | None = None
    ) -> int:
        """
        Exporta correos como archivos .msg individuales (alternativa al PST).
        Más lento pero más seguro, sin riesgo de PST corrupto.
        """
        count = 0
        try:
            os.makedirs(output_dir, exist_ok=True)

            source_store = None
            for store in self.namespace.Stores:
                try:
                    if (
                        store.DisplayName == account.smtp_address
                        or account.smtp_address in store.DisplayName
                    ):
                        source_store = store
                        break
                except Exception:
                    continue

            if source_store is None:
                if progress_cb:
                    progress_cb(f"⚠️ No se encontró store para {account.smtp_address}")
                return 0

            root = source_store.GetRootFolder()
            count = self._save_msg_recursive(root, output_dir, progress_cb)

            if progress_cb:
                progress_cb(f"✅ {count} correos guardados como .msg")

        except Exception as e:
            if progress_cb:
                progress_cb(f"❌ Error: {e}")

        return count

    def _save_msg_recursive(
        self, folder: Any, output_dir: str, progress_cb: Callable | None = None
    ) -> int:
        """Guarda emails como .msg recursivamente."""
        count = 0
        try:
            folder_name = self._sanitize_filename(folder.Name)
            folder_dir = os.path.join(output_dir, folder_name)
            os.makedirs(folder_dir, exist_ok=True)

            for i, item in enumerate(folder.Items):
                try:
                    if hasattr(item, "Class") and item.Class == OL_MAIL_ITEM:
                        subject = self._sanitize_filename((item.Subject or "Sin_Asunto")[:80])
                        try:
                            received = item.ReceivedTime
                            date_prefix = received.strftime("%Y%m%d_%H%M%S")
                        except Exception:
                            date_prefix = f"item_{i:05d}"

                        filename = f"{date_prefix}_{subject}.msg"
                        filepath = os.path.join(folder_dir, filename)

                        # Truncar si es muy largo
                        if len(filepath) > 250:
                            filepath = filepath[:250] + ".msg"

                        # 3 = olMSG (formato MSG)
                        item.SaveAs(filepath, 3)
                        count += 1

                        if count % 50 == 0 and progress_cb:
                            progress_cb(f"  💾 {count} correos guardados...")

                except Exception:
                    continue

            for subfolder in folder.Folders:
                count += self._save_msg_recursive(subfolder, folder_dir, progress_cb)

        except Exception as e:
            print(f"Error guardando msg: {e}")

        return count

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Limpia caracteres ilegales de Windows."""
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip()[:200]

    def close(self) -> None:
        """Cierra la conexión COM."""
        try:
            self.namespace = None
            self.app = None
            pythoncom.CoUninitialize()
        except Exception:
            pass
