"""Tests directos del modulo `account_inventory`.

Cubre:
- _read_com_info: lectura de atributos COM + manejo de excepciones
- _scan_registry_values: heuristicas de deteccion de email/servers/puertos
  desde valores REG_BINARY/REG_DWORD del registro de Outlook
- _read_registry_servers: orquestador que matchea por smtp_address
- _read_credential_vault: matching de credenciales por patron + dominio,
  decode de password con fallback utf-16-le -> utf-8
- build_inventory: orquestador COM + filtros + flags de servers/passwords
- save_inventory: archivo plano vs encriptado (roundtrip real con crypto_utils)
- summarize_inventory: resumen legible
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REG_BINARY = 3
REG_DWORD = 4


def _utf16_bytes(s: str) -> bytes:
    """Simula como Outlook guarda strings REG_BINARY: utf-16-le + doble NUL."""
    return s.encode("utf-16-le") + b"\x00\x00"


def _fake_winreg_for_account(email: str) -> SimpleNamespace:
    """Fake winreg con UNA cuenta bajo Outlook/16.0 que matchea `email`."""
    base_path = "Software\\Microsoft\\Office\\16.0\\Outlook\\Profiles\\Outlook"
    sub_name = "0a0d020000000000c000000000000046"
    sub_path = f"{base_path}\\{sub_name}"

    values = [
        ("Email", _utf16_bytes(email), REG_BINARY),
        ("Incoming Mail Server", _utf16_bytes("imap.uns-kikaku.com"), REG_BINARY),
        ("Outgoing Mail Server", _utf16_bytes("smtp.uns-kikaku.com"), REG_BINARY),
        ("IMAP Port", 993, REG_DWORD),
    ]

    def open_key(_root: Any, path: str) -> str:
        if path in (base_path, sub_path):
            return path
        raise OSError("registry key not found")

    def enum_key(handle: str, index: int) -> str:
        if handle == base_path and index == 0:
            return sub_name
        raise OSError("no more subkeys")

    def enum_value(handle: str, index: int) -> tuple[str, Any, int]:
        if handle == sub_path and index < len(values):
            return values[index]
        raise OSError("no more values")

    return SimpleNamespace(
        HKEY_CURRENT_USER="HKCU_FAKE",
        REG_BINARY=REG_BINARY,
        REG_DWORD=REG_DWORD,
        OpenKey=open_key,
        EnumKey=enum_key,
        EnumValue=enum_value,
        CloseKey=lambda _h: None,
    )


# ---------------------------------------------------------------------------
# _read_com_info
# ---------------------------------------------------------------------------


def test_read_com_info_happy_path() -> None:
    import account_inventory

    account = SimpleNamespace(
        SmtpAddress="kenji@uns-kikaku.com",
        DisplayName="Kenji Kaneshiro",
        UserName="kenji",
        AccountType=1,
        DeliveryStore=SimpleNamespace(DisplayName="kenji@uns-kikaku.com"),
    )

    info = account_inventory._read_com_info(account)

    assert info["smtp_address"] == "kenji@uns-kikaku.com"
    assert info["account_type"] == "IMAP"
    assert info["delivery_store"] == "kenji@uns-kikaku.com"
    assert "error" not in info


def test_read_com_info_unknown_account_type_labeled() -> None:
    import account_inventory

    account = SimpleNamespace(SmtpAddress="x@y.com", DisplayName="X", UserName="x", AccountType=99)

    info = account_inventory._read_com_info(account)
    assert info["account_type"] == "Unknown(99)"


def test_read_com_info_delivery_store_exception_is_ignored() -> None:
    """Si DeliveryStore no esta disponible, el resto de la info se conserva."""
    import account_inventory

    class Account:
        SmtpAddress = "kenji@uns-kikaku.com"
        DisplayName = "Kenji"
        UserName = "kenji"
        AccountType = 0

        @property
        def DeliveryStore(self) -> Any:
            raise RuntimeError("no delivery store")

    info = account_inventory._read_com_info(Account())

    assert info["smtp_address"] == "kenji@uns-kikaku.com"
    assert info["delivery_store"] is None


def test_read_com_info_general_exception_sets_error_field() -> None:
    import account_inventory

    class BrokenAccount:
        @property
        def SmtpAddress(self) -> str:
            raise RuntimeError("boom")

    info = account_inventory._read_com_info(BrokenAccount())
    assert "error" in info


# ---------------------------------------------------------------------------
# _scan_registry_values
# ---------------------------------------------------------------------------


def test_scan_registry_values_extracts_email_server_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    values = [
        ("Email", _utf16_bytes("kenji@uns-kikaku.com"), REG_BINARY),
        ("Incoming", _utf16_bytes("imap.uns-kikaku.com"), REG_BINARY),
        ("Outgoing", _utf16_bytes("smtp.uns-kikaku.com"), REG_BINARY),
        ("Port", 993, REG_DWORD),
    ]

    def enum_value(_key: Any, index: int) -> tuple[str, Any, int]:
        if index < len(values):
            return values[index]
        raise OSError("no more")

    fake_winreg = SimpleNamespace(REG_BINARY=REG_BINARY, REG_DWORD=REG_DWORD, EnumValue=enum_value)
    monkeypatch.setattr(account_inventory, "winreg", fake_winreg)

    found = account_inventory._scan_registry_values(object())

    assert found["email"] == "kenji@uns-kikaku.com"
    assert found["incoming_server"] == "imap.uns-kikaku.com"
    assert found["outgoing_server"] == "smtp.uns-kikaku.com"
    assert found["port_imaps"] == 993


def test_scan_registry_values_extra_strings_capped_at_five(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    # 7 strings que matchean el prefijo "outlook." pero no imap/pop/smtp
    # => van todas a _extra_strings, pero el resultado se recorta a 5.
    values = [
        (f"v{i}", _utf16_bytes(f"outlook.server{i}.example.com"), REG_BINARY) for i in range(7)
    ]

    def enum_value(_key: Any, index: int) -> tuple[str, Any, int]:
        if index < len(values):
            return values[index]
        raise OSError("no more")

    fake_winreg = SimpleNamespace(REG_BINARY=REG_BINARY, REG_DWORD=REG_DWORD, EnumValue=enum_value)
    monkeypatch.setattr(account_inventory, "winreg", fake_winreg)

    found = account_inventory._scan_registry_values(object())

    assert len(found["_extra_strings"]) == 5


def test_scan_registry_values_ignores_undecodable_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bytes con largo impar no son utf-16-le validos: se ignoran sin crashear."""
    import account_inventory

    values = [("Weird", b"\x01\x02\x03", REG_BINARY)]

    def enum_value(_key: Any, index: int) -> tuple[str, Any, int]:
        if index < len(values):
            return values[index]
        raise OSError("no more")

    fake_winreg = SimpleNamespace(REG_BINARY=REG_BINARY, REG_DWORD=REG_DWORD, EnumValue=enum_value)
    monkeypatch.setattr(account_inventory, "winreg", fake_winreg)

    found = account_inventory._scan_registry_values(object())
    assert found == {}


# ---------------------------------------------------------------------------
# _read_registry_servers
# ---------------------------------------------------------------------------


def test_read_registry_servers_returns_none_without_smtp() -> None:
    import account_inventory

    assert account_inventory._read_registry_servers("") is None


def test_read_registry_servers_returns_none_on_non_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="posix"))
    assert account_inventory._read_registry_servers("kenji@uns-kikaku.com") is None


def test_read_registry_servers_finds_matching_account(monkeypatch: pytest.MonkeyPatch) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        account_inventory, "winreg", _fake_winreg_for_account("kenji@uns-kikaku.com")
    )

    result = account_inventory._read_registry_servers("kenji@uns-kikaku.com")

    assert result is not None
    assert result["incoming_server"] == "imap.uns-kikaku.com"
    assert result["outgoing_server"] == "smtp.uns-kikaku.com"
    assert {"protocol": "imaps", "port": 993} in result["ports_detected"]


def test_read_registry_servers_returns_none_when_no_account_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        account_inventory, "winreg", _fake_winreg_for_account("otro@uns-kikaku.com")
    )

    result = account_inventory._read_registry_servers("kenji@uns-kikaku.com")
    assert result is None


# ---------------------------------------------------------------------------
# _read_credential_vault
# ---------------------------------------------------------------------------


def test_read_credential_vault_returns_none_without_smtp() -> None:
    import account_inventory

    assert account_inventory._read_credential_vault("") is None


def test_read_credential_vault_returns_none_on_non_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="posix"))
    assert account_inventory._read_credential_vault("kenji@uns-kikaku.com") is None


def test_read_credential_vault_returns_none_when_win32_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(account_inventory, "WIN32_AVAILABLE", False)
    assert account_inventory._read_credential_vault("kenji@uns-kikaku.com") is None


def test_read_credential_vault_matches_by_pattern_and_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(account_inventory, "WIN32_AVAILABLE", True)

    creds = [
        {
            "TargetName": "imap.uns-kikaku.com",
            "UserName": "kenji@uns-kikaku.com",
            "CredentialBlob": "s3cr3t".encode("utf-16-le"),
            "Type": 1,
            "Persist": 2,
        },
        {
            "TargetName": "unrelated_service.example.org",
            "UserName": "someone_else",
            "CredentialBlob": b"",
            "Type": 1,
            "Persist": 2,
        },
    ]
    fake_win32cred = SimpleNamespace(CredEnumerate=lambda *_a, **_k: creds)
    monkeypatch.setattr(account_inventory, "win32cred", fake_win32cred)

    result = account_inventory._read_credential_vault("kenji@uns-kikaku.com")

    assert result is not None
    assert len(result) == 1
    assert result[0]["target"] == "imap.uns-kikaku.com"
    assert result[0]["password"] == "s3cr3t"


def test_read_credential_vault_password_decode_fallback_to_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blob de largo impar no decodifica como utf-16-le: cae a utf-8."""
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(account_inventory, "WIN32_AVAILABLE", True)

    creds = [
        {
            "TargetName": "smtp.uns-kikaku.com",
            "UserName": "kenji@uns-kikaku.com",
            "CredentialBlob": b"abc",  # 3 bytes: invalido para utf-16-le
            "Type": 1,
            "Persist": 2,
        }
    ]
    fake_win32cred = SimpleNamespace(CredEnumerate=lambda *_a, **_k: creds)
    monkeypatch.setattr(account_inventory, "win32cred", fake_win32cred)

    result = account_inventory._read_credential_vault("kenji@uns-kikaku.com")

    assert result is not None
    assert result[0]["password"] == "abc"


def test_read_credential_vault_returns_none_on_credenumerate_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(account_inventory, "WIN32_AVAILABLE", True)

    def raise_error(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("vault locked")

    monkeypatch.setattr(account_inventory, "win32cred", SimpleNamespace(CredEnumerate=raise_error))

    assert account_inventory._read_credential_vault("kenji@uns-kikaku.com") is None


# ---------------------------------------------------------------------------
# build_inventory
# ---------------------------------------------------------------------------


def _fake_outlook_client(accounts: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(namespace=SimpleNamespace(Accounts=accounts))


def test_build_inventory_filters_by_selected_smtp() -> None:
    import account_inventory

    accounts = [
        SimpleNamespace(
            SmtpAddress="kenji@uns-kikaku.com", DisplayName="K", UserName="k", AccountType=1
        ),
        SimpleNamespace(
            SmtpAddress="info@uns-kikaku.com", DisplayName="I", UserName="i", AccountType=1
        ),
    ]
    client = _fake_outlook_client(accounts)

    inventory = account_inventory.build_inventory(
        client,
        selected_smtp_addresses=["kenji@uns-kikaku.com"],
        include_servers=False,
        include_passwords=False,
    )

    assert inventory["total_accounts"] == 1
    assert inventory["accounts"][0]["smtp_address"] == "kenji@uns-kikaku.com"


def test_build_inventory_handles_com_read_exception() -> None:
    import account_inventory

    class BrokenNamespace:
        @property
        def Accounts(self) -> Any:
            raise RuntimeError("Outlook no disponible")

    client = SimpleNamespace(namespace=BrokenNamespace())

    inventory = account_inventory.build_inventory(client)
    assert inventory["total_accounts"] == 0
    assert inventory["accounts"] == []


def test_build_inventory_includes_servers_and_passwords_when_flags_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import account_inventory

    monkeypatch.setattr(account_inventory, "WIN32_AVAILABLE", True)
    monkeypatch.setattr(
        account_inventory,
        "_read_registry_servers",
        lambda smtp: {"incoming_server": "imap.x.com"},
    )
    monkeypatch.setattr(
        account_inventory,
        "_read_credential_vault",
        lambda smtp: [{"target": "x", "username": "y", "password": "z"}],
    )

    accounts = [
        SimpleNamespace(
            SmtpAddress="kenji@uns-kikaku.com", DisplayName="K", UserName="k", AccountType=1
        )
    ]
    client = _fake_outlook_client(accounts)

    inventory = account_inventory.build_inventory(
        client, include_servers=True, include_passwords=True
    )

    acc = inventory["accounts"][0]
    assert acc["server_settings"]["incoming_server"] == "imap.x.com"
    assert acc["credentials"][0]["password"] == "z"
    assert inventory["includes_passwords"] is True
    assert "パスワード" in inventory["warning"]


def test_build_inventory_warning_message_when_no_passwords() -> None:
    import account_inventory

    inventory = account_inventory.build_inventory(_fake_outlook_client([]), include_passwords=False)
    assert "パスワード" not in inventory["warning"]


# ---------------------------------------------------------------------------
# save_inventory
# ---------------------------------------------------------------------------


def test_save_inventory_plain_json_without_password(tmp_path: Path) -> None:
    import account_inventory

    inventory = {"total_accounts": 1, "accounts": [{"smtp_address": "kenji@uns-kikaku.com"}]}
    output_path = account_inventory.save_inventory(inventory, str(tmp_path))

    assert output_path.endswith("accounts.json")
    saved = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert saved == inventory


def test_save_inventory_encrypted_with_password_roundtrips(tmp_path: Path) -> None:
    import account_inventory
    from crypto_utils import decrypt_file_to_dict

    inventory = {"total_accounts": 1, "accounts": [{"smtp_address": "kenji@uns-kikaku.com"}]}
    output_path = account_inventory.save_inventory(inventory, str(tmp_path), password="master-pw")

    assert output_path.endswith("accounts.json.enc")
    decoded = decrypt_file_to_dict(output_path, "master-pw")
    assert decoded == inventory


# ---------------------------------------------------------------------------
# summarize_inventory
# ---------------------------------------------------------------------------


def test_summarize_inventory_lists_accounts_and_flags() -> None:
    import account_inventory

    inventory = {
        "accounts": [
            {
                "smtp_address": "kenji@uns-kikaku.com",
                "account_type": "IMAP",
                "server_settings": {"incoming_server": "imap.uns-kikaku.com"},
                "credentials": [{"password": "x"}],
            }
        ],
        "includes_passwords": True,
        "exported_at": "2026-07-01T00:00:00.000000",
    }

    summary = account_inventory.summarize_inventory(inventory)

    assert "kenji@uns-kikaku.com" in summary
    assert "はい" in summary  # includes_passwords=True
