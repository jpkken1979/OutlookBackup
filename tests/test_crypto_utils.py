"""Tests directos del modulo `crypto_utils`.

Cubre:
- Roundtrip encrypt/decrypt con password correcta
- Password incorrecta -> ValueError explicito (no descifra basura silenciosamente)
- Archivo corrupto: muy corto, sin MAGIC, version desconocida
- estimate_password_strength: scoring y labels japoneses
- is_encrypted_file: deteccion por MAGIC, incluido archivo inexistente
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# encrypt_dict_to_file / decrypt_file_to_dict
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip_preserves_data(tmp_path: Path) -> None:
    """Cifrar y descifrar con la misma password devuelve el dict original."""
    from crypto_utils import decrypt_file_to_dict, encrypt_dict_to_file

    original = {
        "accounts": [{"smtp": "kenji@uns-kikaku.com", "password": "s3cr3t"}],
        "generated_at": "2026-07-01T00:00:00",
    }
    output_path = tmp_path / "accounts.json.enc"

    assert encrypt_dict_to_file(original, str(output_path), "master-password") is True
    assert output_path.exists()

    decoded = decrypt_file_to_dict(str(output_path), "master-password")
    assert decoded == original


def test_encrypt_decrypt_roundtrip_with_unicode_content(tmp_path: Path) -> None:
    """El JSON conserva caracteres japoneses (ensure_ascii=False)."""
    from crypto_utils import decrypt_file_to_dict, encrypt_dict_to_file

    original = {"display_name": "田中太郎", "note": "受信トレイ"}
    output_path = tmp_path / "accounts.json.enc"

    encrypt_dict_to_file(original, str(output_path), "パスワード123")
    decoded = decrypt_file_to_dict(str(output_path), "パスワード123")

    assert decoded == original


def test_decrypt_with_wrong_password_raises_value_error(tmp_path: Path) -> None:
    """Password incorrecta debe fallar explicito, no devolver basura."""
    from crypto_utils import decrypt_file_to_dict, encrypt_dict_to_file

    output_path = tmp_path / "accounts.json.enc"
    encrypt_dict_to_file({"key": "value"}, str(output_path), "correct-password")

    with pytest.raises(ValueError, match="マスターパスワードが間違っています"):
        decrypt_file_to_dict(str(output_path), "wrong-password")


def test_decrypt_file_too_short_raises_value_error(tmp_path: Path) -> None:
    """Archivo mas corto que el header minimo se rechaza como corrupto."""
    from crypto_utils import decrypt_file_to_dict

    broken = tmp_path / "broken.json.enc"
    broken.write_bytes(b"UNSCRYPT")  # solo el magic, sin el resto del header

    with pytest.raises(ValueError, match="短すぎる"):
        decrypt_file_to_dict(str(broken), "any-password")


def test_decrypt_file_without_magic_raises_value_error(tmp_path: Path) -> None:
    """Archivo sin el MAGIC correcto no es reconocido como propio."""
    from crypto_utils import decrypt_file_to_dict

    not_ours = tmp_path / "not_ours.enc"
    not_ours.write_bytes(b"X" * 64)

    with pytest.raises(ValueError, match="UNS Backup の暗号化ファイルではありません"):
        decrypt_file_to_dict(str(not_ours), "any-password")


def test_decrypt_unknown_version_raises_value_error(tmp_path: Path) -> None:
    """Version de formato desconocida se rechaza en vez de intentar parsear."""
    from crypto_utils import MAGIC, decrypt_file_to_dict

    bad_version = tmp_path / "bad_version.enc"
    # MAGIC + version=99 + resto de bytes de relleno para pasar el chequeo de largo
    bad_version.write_bytes(MAGIC + bytes([99]) + b"\x00" * 40)

    with pytest.raises(ValueError, match="未知のバージョン"):
        decrypt_file_to_dict(str(bad_version), "any-password")


# ---------------------------------------------------------------------------
# estimate_password_strength
# ---------------------------------------------------------------------------


def test_estimate_password_strength_empty_password() -> None:
    from crypto_utils import estimate_password_strength

    assert estimate_password_strength("") == (0, "空")


def test_estimate_password_strength_short_weak_password() -> None:
    from crypto_utils import estimate_password_strength

    score, label = estimate_password_strength("abc")
    assert score < 30
    assert label == "弱い (危険)"


def test_estimate_password_strength_long_mixed_password_is_strong() -> None:
    from crypto_utils import estimate_password_strength

    score, label = estimate_password_strength("Az9!Az9!Az9!Az9!Az9!")
    assert score == 100
    assert label == "とても強い"


# ---------------------------------------------------------------------------
# is_encrypted_file
# ---------------------------------------------------------------------------


def test_is_encrypted_file_true_for_real_encrypted_file(tmp_path: Path) -> None:
    from crypto_utils import encrypt_dict_to_file, is_encrypted_file

    output_path = tmp_path / "accounts.json.enc"
    encrypt_dict_to_file({"a": 1}, str(output_path), "pw")

    assert is_encrypted_file(str(output_path)) is True


def test_is_encrypted_file_false_for_plain_file(tmp_path: Path) -> None:
    from crypto_utils import is_encrypted_file

    plain = tmp_path / "plain.json"
    plain.write_text('{"a": 1}', encoding="utf-8")

    assert is_encrypted_file(str(plain)) is False


def test_is_encrypted_file_false_for_missing_file(tmp_path: Path) -> None:
    from crypto_utils import is_encrypted_file

    assert is_encrypted_file(str(tmp_path / "does_not_exist.enc")) is False
