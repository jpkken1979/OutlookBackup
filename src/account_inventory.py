"""
UNS Backup v2.1 - Account Inventory
=====================================
Lee TODAS las cuentas configuradas en Outlook y exporta:
  • Email address, display name, account type (siempre)
  • Server settings desde el registro de Windows (si disponibles)
  • Passwords desde Windows Credential Vault (opcional, encriptado)
"""

import datetime
import json
import os
import socket
from typing import Any

try:
    import winreg

    import win32com.client  # noqa: F401  # availability probe
    import win32cred  # noqa: F401  # availability probe

    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


ACCOUNT_TYPES = {
    0: "Exchange",
    1: "IMAP",
    2: "POP3",
    3: "HTTP",
    4: "EAS",
    5: "Other",
}

# Puertos típicos para inferir protocolo
KNOWN_PORTS = {
    25: "smtp",
    110: "pop3",
    143: "imap",
    465: "smtps",  # SMTP over SSL
    587: "smtp_starttls",
    993: "imaps",  # IMAP over SSL
    995: "pop3s",  # POP3 over SSL
}


def build_inventory(
    outlook_client: Any,
    selected_smtp_addresses: list[str] | None = None,
    include_servers: bool = True,
    include_passwords: bool = False,
) -> dict:
    """
    Genera el inventario completo de cuentas.

    :param outlook_client: instancia de OutlookClient
    :param selected_smtp_addresses: si no es None, solo incluye estas cuentas
    :param include_servers: leer settings del registro
    :param include_passwords: leer passwords del Credential Vault
    """
    accounts = []

    # Leer todas las cuentas vía COM
    try:
        com_accounts = list(outlook_client.namespace.Accounts)
    except Exception as e:
        com_accounts = []
        print(f"Error leyendo cuentas: {e}")

    for acc in com_accounts:
        info = _read_com_info(acc)
        smtp = info.get("smtp_address", "")

        # Filtrar si hay lista de seleccionados
        if selected_smtp_addresses is not None:
            if smtp not in selected_smtp_addresses:
                continue

        if include_servers and WIN32_AVAILABLE:
            servers = _read_registry_servers(smtp)
            if servers:
                info["server_settings"] = servers

        if include_passwords and WIN32_AVAILABLE:
            creds = _read_credential_vault(smtp)
            if creds:
                info["credentials"] = creds

        accounts.append(info)

    inventory = {
        "format_version": "2.1",
        "exported_at": datetime.datetime.now().isoformat(),
        "host_info": {
            "computer_name": os.environ.get("COMPUTERNAME") or socket.gethostname(),
            "user_name": os.environ.get("USERNAME") or os.environ.get("USER", ""),
            "os": "Windows" if os.name == "nt" else "Other",
        },
        "company": "ユニバーサル企画株式会社",
        "total_accounts": len(accounts),
        "includes_passwords": include_passwords,
        "warning": (
            "⚠️ このファイルにはアカウントのパスワードが含まれています。"
            "絶対に第三者に渡さないでください。"
            if include_passwords
            else "このファイルにアカウント設定が含まれています。安全に管理してください。"
        ),
        "accounts": accounts,
    }

    return inventory


def _read_com_info(account: Any) -> dict:
    """Lee info básica de una cuenta vía Outlook COM."""
    info = {
        "smtp_address": "",
        "display_name": "",
        "user_name": "",
        "account_type": "Unknown",
        "delivery_store": None,
    }
    try:
        info["smtp_address"] = str(getattr(account, "SmtpAddress", "") or "")
        info["display_name"] = str(getattr(account, "DisplayName", "") or "")
        info["user_name"] = str(getattr(account, "UserName", "") or "")
        atype = getattr(account, "AccountType", -1)
        info["account_type"] = ACCOUNT_TYPES.get(atype, f"Unknown({atype})")
        try:
            info["delivery_store"] = str(account.DeliveryStore.DisplayName)
        except Exception:
            pass
    except Exception as e:
        info["error"] = str(e)
    return info


def _read_registry_servers(smtp_address: str) -> dict | None:
    """Intenta leer settings del servidor del registro de Outlook."""
    if not smtp_address or os.name != "nt":
        return None

    found: dict[str, Any] = {}
    versions = ["16.0", "15.0", "14.0"]

    for ver in versions:
        try:
            base_path = f"Software\\Microsoft\\Office\\{ver}\\Outlook\\Profiles\\Outlook"
            try:
                base_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path)
            except OSError:
                continue

            try:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(base_key, i)
                        sub_path = f"{base_path}\\{sub_name}"

                        try:
                            sub_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_path)
                            props = _scan_registry_values(sub_key)
                            winreg.CloseKey(sub_key)

                            email_in_props = props.get("email", "").lower()
                            if email_in_props and email_in_props == smtp_address.lower():
                                # Encontramos! Mergear sin sobrescribir
                                for k, v in props.items():
                                    found.setdefault(k, v)
                        except OSError:
                            pass
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(base_key)

            if found.get("email"):
                break
        except Exception:
            continue

    if not found:
        return None

    # Limpiar y estructurar
    result = {
        "outlook_version": found.get("_outlook_version"),
        "incoming_server": found.get("incoming_server"),
        "outgoing_server": found.get("outgoing_server"),
        "ports_detected": [],
        "raw_strings_found": found.get("_extra_strings", []),
    }

    for k, v in found.items():
        if k.startswith("port_"):
            result["ports_detected"].append(
                {
                    "protocol": k.replace("port_", ""),
                    "port": v,
                }
            )

    # Eliminar None
    return {k: v for k, v in result.items() if v}


def _scan_registry_values(reg_key: Any) -> dict:
    """Escanea todos los valores buscando datos útiles (heurísticas)."""
    found: dict[str, Any] = {}
    extra_strings: list[str] = []

    try:
        i = 0
        while True:
            try:
                _, value, vtype = winreg.EnumValue(reg_key, i)
                i += 1

                if vtype == winreg.REG_BINARY and isinstance(value, bytes):
                    try:
                        decoded = value.decode("utf-16-le").rstrip("\x00").strip()
                        if not decoded or len(decoded) > 255:
                            continue

                        decoded_lower = decoded.lower()

                        if "@" in decoded and "." in decoded and " " not in decoded:
                            if 5 < len(decoded) < 100:
                                found.setdefault("email", decoded)
                        elif any(
                            decoded_lower.startswith(p)
                            for p in [
                                "imap.",
                                "pop.",
                                "smtp.",
                                "mail.",
                                "outlook.",
                                "ssl0.",
                                "exchange.",
                            ]
                        ):
                            if "imap." in decoded_lower or "pop." in decoded_lower:
                                found.setdefault("incoming_server", decoded)
                            elif "smtp." in decoded_lower:
                                found.setdefault("outgoing_server", decoded)
                            else:
                                if decoded not in extra_strings:
                                    extra_strings.append(decoded)
                    except Exception:
                        pass

                elif vtype == winreg.REG_DWORD:
                    if isinstance(value, int) and value in KNOWN_PORTS:
                        proto = KNOWN_PORTS[value]
                        found.setdefault(f"port_{proto}", value)
            except OSError:
                break
    except Exception:
        pass

    if extra_strings:
        found["_extra_strings"] = extra_strings[:5]

    return found


def _read_credential_vault(smtp_address: str) -> list[dict] | None:
    """Busca credenciales relacionadas a la cuenta en Windows Credential Vault."""
    if not smtp_address or os.name != "nt" or not WIN32_AVAILABLE:
        return None

    matched = []
    try:
        creds = win32cred.CredEnumerate(None, 0)
    except Exception:
        return None

    smtp_lower = smtp_address.lower()
    domain = smtp_lower.split("@")[-1] if "@" in smtp_lower else ""

    OUTLOOK_PATTERNS = [
        "microsoftoffice",
        "microsoft.exchange",
        "microsoft_oc1",
        "mail.",
        "imap.",
        "pop.",
        "smtp.",
        "outlook.com",
        "office365",
        "exchange.",
        "sspi:",
    ]

    for c in creds:
        try:
            target = c.get("TargetName") or ""
            target_lower = target.lower()
            username = c.get("UserName") or ""
            blob = c.get("CredentialBlob")

            # ¿Es de Outlook?
            is_outlook = any(p in target_lower for p in OUTLOOK_PATTERNS)

            # ¿Está relacionado con esta cuenta?
            related = (
                smtp_lower in target_lower
                or smtp_lower in username.lower()
                or (domain and len(domain) > 3 and domain in target_lower)
            )

            if not (is_outlook and related) and smtp_lower not in target_lower:
                continue

            password = None
            if blob and isinstance(blob, bytes):
                try:
                    password = blob.decode("utf-16-le").rstrip("\x00")
                except Exception:
                    try:
                        password = blob.decode("utf-8").rstrip("\x00")
                    except Exception:
                        password = None

            matched.append(
                {
                    "target": target,
                    "username": username,
                    "password": password,
                    "type_code": c.get("Type"),
                    "persist": c.get("Persist"),
                }
            )
        except Exception:
            continue

    return matched if matched else None


def save_inventory(inventory: dict, output_dir: str, password: str | None = None) -> str:
    """
    Guarda el inventario en disco.
    Si password está dado → archivo `accounts.json.enc` (encriptado)
    Si no → archivo `accounts.json` (plano)
    Devuelve el path del archivo guardado.
    """
    os.makedirs(output_dir, exist_ok=True)

    if password:
        from crypto_utils import encrypt_dict_to_file

        path = os.path.join(output_dir, "accounts.json.enc")
        encrypt_dict_to_file(inventory, path, password)
    else:
        path = os.path.join(output_dir, "accounts.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(inventory, f, ensure_ascii=False, indent=2)

    return path


def summarize_inventory(inventory: dict) -> str:
    """Genera un resumen legible del inventario."""
    accounts = inventory.get("accounts", [])
    has_pwd = inventory.get("includes_passwords", False)

    lines = [
        f"📦 アカウント数: {len(accounts)}",
        f"🔐 パスワード含む: {'はい' if has_pwd else 'いいえ'}",
        f"📅 エクスポート: {inventory.get('exported_at', '')[:19]}",
        "",
        "アカウント一覧:",
    ]
    for i, acc in enumerate(accounts, 1):
        smtp = acc.get("smtp_address", "(不明)")
        atype = acc.get("account_type", "")
        servers = acc.get("server_settings", {})
        srv = ""
        if servers:
            inc = servers.get("incoming_server", "")
            out = servers.get("outgoing_server", "")
            if inc or out:
                srv = f"  📡 {inc or out}"
        creds = "  🔑" if acc.get("credentials") else ""
        lines.append(f"  {i}. [{atype}] {smtp}{srv}{creds}")

    return "\n".join(lines)
