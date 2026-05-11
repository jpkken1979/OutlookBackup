"""
UNS Backup v2.1 - Utilidades de encriptación
==============================================
AES-256-GCM con PBKDF2-HMAC-SHA256 (200K iteraciones).
Formato del archivo encriptado:
   MAGIC(8) + version(1) + iterations(4) + salt(16) + nonce(12) + ciphertext + auth_tag
"""

import json
import os

MAGIC = b"UNSCRYPT"
VERSION = 1
PBKDF2_ITERATIONS = 200_000
KEY_LENGTH = 32  # AES-256
SALT_LENGTH = 16
NONCE_LENGTH = 12  # GCM standard


def encrypt_dict_to_file(data: dict, output_path: str, password: str) -> bool:
    """Encripta un dict como JSON y lo guarda en archivo binario."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")

    salt = os.urandom(SALT_LENGTH)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    key = kdf.derive(password.encode("utf-8"))

    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    header = (
        MAGIC + VERSION.to_bytes(1, "big") + PBKDF2_ITERATIONS.to_bytes(4, "big") + salt + nonce
    )

    with open(output_path, "wb") as f:
        f.write(header + ciphertext)

    return True


def decrypt_file_to_dict(input_path: str, password: str) -> dict:
    """Lee y desencripta un archivo .json.enc y devuelve el dict."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    with open(input_path, "rb") as f:
        data = f.read()

    if len(data) < len(MAGIC) + 1 + 4 + SALT_LENGTH + NONCE_LENGTH:
        raise ValueError("ファイルが破損しています(短すぎる)")

    if not data.startswith(MAGIC):
        raise ValueError("UNS Backup の暗号化ファイルではありません")

    offset = len(MAGIC)
    version = data[offset]
    offset += 1
    if version != VERSION:
        raise ValueError(f"未知のバージョン: {version}")

    iterations = int.from_bytes(data[offset : offset + 4], "big")
    offset += 4
    salt = data[offset : offset + SALT_LENGTH]
    offset += SALT_LENGTH
    nonce = data[offset : offset + NONCE_LENGTH]
    offset += NONCE_LENGTH
    ciphertext = data[offset:]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=iterations,
    )
    key = kdf.derive(password.encode("utf-8"))

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise ValueError("マスターパスワードが間違っています")

    return json.loads(plaintext.decode("utf-8"))


def estimate_password_strength(password: str) -> tuple[int, str]:
    """Devuelve (score 0-100, label japonés) para fuerza del password."""
    if not password:
        return 0, "空"

    score = 0
    length = len(password)

    if length >= 8:
        score += 15
    if length >= 12:
        score += 15
    if length >= 16:
        score += 15
    if length >= 20:
        score += 10

    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)

    if has_lower:
        score += 8
    if has_upper:
        score += 12
    if has_digit:
        score += 12
    if has_symbol:
        score += 13

    score = min(score, 100)

    if score < 30:
        return score, "弱い (危険)"
    elif score < 55:
        return score, "普通"
    elif score < 80:
        return score, "強い"
    else:
        return score, "とても強い"


def is_encrypted_file(path: str) -> bool:
    """Verifica si un archivo es un .json.enc de UNS Backup."""
    try:
        with open(path, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except Exception:
        return False
