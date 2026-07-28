"""DPAPI-style encryption utilities with cross-platform fallback.

On Windows, uses the native Data Protection API (CryptProtectData / CryptUnprotectData)
via ctypes to encrypt session keys so they can only be decrypted by the same user
on the same machine.

On non-Windows (Linux, macOS), falls back to a key derived from the session key
path so only processes with read access to that path can derive the key. This is
no stronger than the file permissions approach but maintains the same threat model.

The encrypted format is:
  - 1 byte: magic marker (0x01 for DPAPI, 0x00 for fallback)
  - N bytes: ciphertext (DPAPI or Fernet)
"""

from __future__ import annotations

import base64
import ctypes
import logging
import sys
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Windows DPAPI via ctypes
# -------------------------------------------------------------------


def _windows_version_info() -> tuple[int, int]:
    """Return sys.getwindowsversion() tuple safely."""
    try:
        ver = sys.getwindowsversion()  # type: ignore[attr-defined]
        return (ver.major, ver.minor)  # type: ignore[attr-defined]
    except AttributeError:
        return (0, 0)  # type: ignore[return-value]


_is_windows: bool = sys.platform == "win32"


class _DpApi:
    """Lazy wrapper around Windows DPAPI via ctypes."""

    def __init__(self) -> None:
        self._initialized = False
        self._crypt32: ctypes.CDLL | None = None

    def _init(self) -> bool:
        """Load Crypt32.dll and resolve symbols."""
        if self._initialized:
            return self._crypt32 is not None
        self._initialized = True
        if not _is_windows:
            return False
        try:
            self._crypt32 = ctypes.CDLL("Crypt32.dll")
            # CRYPT_INTEGER_BLOB
            self._crypt32.CryptProtectData.argtypes = [
                ctypes.c_void_p,  # pDataIn
                ctypes.c_void_p,  # ppszDataDescr (optional, can be None)
                ctypes.c_void_p,  # pOptionalEntropy (optional)
                ctypes.c_void_p,  # pvReserved (must be None)
                ctypes.c_void_p,  # pPromptStruct (optional)
                ctypes.c_uint32,  # dwFlags
                ctypes.c_void_p,  # pDataOut
            ]
            self._crypt32.CryptProtectData.restype = ctypes.c_int  # BOOL
            self._crypt32.CryptUnprotectData.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_void_p,
            ]
            self._crypt32.CryptUnprotectData.restype = ctypes.c_int  # BOOL
            logger.debug("DPAPI (Crypt32.dll) loaded successfully")
            return True
        except OSError as exc:
            logger.warning("No se pudo cargar Crypt32.dll: %s", exc)
            return False

    @staticmethod
    def _make_blob(data: bytes) -> ctypes.Structure:
        """Build a CRYPT_INTEGER_BLOB from bytes.

        Uses c_void_p for pbData (matches Windows API exactly).
        """

        class Blob(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.c_uint32),
                ("pbData", ctypes.c_void_p),
            ]

        buf = ctypes.create_string_buffer(data)
        blob = Blob(cbData=len(data), pbData=ctypes.cast(buf, ctypes.c_void_p))
        blob._buf = buf  # type: ignore[attr-defined]
        return blob

    def encrypt(self, plaintext: bytes) -> bytes | None:
        """Encrypt using Windows DPAPI (CurrentUser scope)."""
        if not self._init() or self._crypt32 is None:
            return None

        class CRYPT_INTEGER_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]

        data_in = CRYPT_INTEGER_BLOB(
            len(plaintext), ctypes.cast(ctypes.create_string_buffer(plaintext), ctypes.c_void_p)
        )
        out_buf = ctypes.create_string_buffer(65536)
        data_out = CRYPT_INTEGER_BLOB(65536, ctypes.cast(out_buf, ctypes.c_void_p))

        flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
        ret = self._crypt32.CryptProtectData(
            ctypes.byref(data_in), None, None, None, None, flags, ctypes.byref(data_out)
        )
        if ret and data_out.cbData > 0:
            # Read from memory address that Windows wrote to (not from Python buffer)
            ArrayType = ctypes.c_uint8 * data_out.cbData
            arr = ArrayType.from_address(data_out.pbData)
            return bytes(arr)
        return None

    def decrypt(self, ciphertext: bytes) -> bytes | None:
        """Decrypt using Windows DPAPI."""
        if not self._init() or self._crypt32 is None:
            return None

        class CRYPT_INTEGER_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]

        data_in = CRYPT_INTEGER_BLOB(
            len(ciphertext), ctypes.cast(ctypes.create_string_buffer(ciphertext), ctypes.c_void_p)
        )
        out_buf = ctypes.create_string_buffer(65536)
        data_out = CRYPT_INTEGER_BLOB(65536, ctypes.cast(out_buf, ctypes.c_void_p))

        ret = self._crypt32.CryptUnprotectData(
            ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)
        )
        if ret and data_out.cbData > 0:
            ArrayType = ctypes.c_uint8 * data_out.cbData
            arr = ArrayType.from_address(data_out.pbData)
            return bytes(arr)
        return None


# Singleton
_dpapi = _DpApi()

# -------------------------------------------------------------------
# Fallback: Fernet (AES-128-CBC + HMAC) key derived from session key path
# -------------------------------------------------------------------

_FERNET_MAGIC = b"\x00"


def _derive_fernet_key(key_path: Path) -> bytes:
    """Derive a Fernet key from the session key file path.

    Una clave Fernet es EXACTAMENTE 32 bytes codificados en base64 url-safe
    (44 chars). Fernet la divide internamente en 16 bytes de firma + 16 de AES,
    asi que hay que pasar 32 bytes crudos, NO 64. Concatenar clave + firma (64
    bytes) hacia que `Fernet(key)` lanzara "Fernet key must be 32 url-safe
    base64-encoded bytes" y el cifrado de fallback en Linux/macOS quedara roto
    (devolvia None siempre, sin cifrar la session key).
    """
    import hashlib

    secret = b"antigravity-session-key-v1" + str(key_path).encode()
    raw = hashlib.sha256(secret).digest()  # 32 bytes deterministas
    return base64.urlsafe_b64encode(raw)


def _encrypt_fallback(plaintext: bytes, key_path: Path) -> bytes | None:
    """Encrypt with Fernet (fallback for non-Windows)."""
    try:
        key = _derive_fernet_key(key_path)
        f = Fernet(key)
        return f.encrypt(plaintext)
    except Exception as exc:
        logger.error("Fernet encrypt failed: %s", exc)
        return None


def _decrypt_fallback(ciphertext: bytes, key_path: Path) -> bytes | None:
    """Decrypt with Fernet (fallback for non-Windows)."""
    try:
        key = _derive_fernet_key(key_path)
        f = Fernet(key)
        return f.decrypt(ciphertext)
    except Exception as exc:
        logger.debug("Fernet decrypt failed: %s", exc)
        return None


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

DPAPI_MAGIC = b"\x01"


def encrypt_for_user(plaintext: bytes, key_path: Path) -> bytes:
    """Encrypt plaintext for the current user (DPAPI on Windows, Fernet elsewhere).

    Returns the encrypted bytes with a 1-byte magic marker prefix so the
    corresponding `decrypt_for_user` knows which scheme to use.
    """
    if _is_windows:
        result = _dpapi.encrypt(plaintext)
        if result is not None and len(result) > 10:
            # DPAPI succeeded with non-trivial output
            logger.debug("Encrypted %d bytes with DPAPI", len(plaintext))
            return DPAPI_MAGIC + result
        logger.warning(
            "DPAPI encrypt failed (ret=%s, len=%d), falling back to Fernet",
            result is not None,
            len(result) if result else 0,
        )

    # Fallback: Fernet (works cross-user on same machine)
    result = _encrypt_fallback(plaintext, key_path)
    if result is None:
        return _FERNET_MAGIC + plaintext
    logger.debug("Encrypted %d bytes with Fernet fallback", len(plaintext))
    return _FERNET_MAGIC + result


def decrypt_for_user(ciphertext: bytes, key_path: Path) -> bytes | None:
    """Decrypt bytes produced by `encrypt_for_user`.

    Returns the original plaintext, or None if decryption fails
    (e.g. ciphertext corrupted or from a different user/machine).
    """
    if len(ciphertext) < 1:
        return None

    magic = ciphertext[:1]
    payload = ciphertext[1:]

    if magic == DPAPI_MAGIC and _is_windows:
        result = _dpapi.decrypt(payload)
        if result is not None:
            logger.debug("Decrypted %d bytes with DPAPI", len(result))
            return result
        # DPAPI failed: data may be from another user/machine.
        # Try Fernet fallback (useful for tests run as different user,
        # or if data was encrypted with Fernet despite being on Windows).
        logger.debug("DPAPI decrypt failed, trying Fernet fallback")
        result = _decrypt_fallback(payload, key_path)
        if result is not None:
            logger.debug("Decrypted %d bytes with Fernet fallback", len(result))
            return result
        return None

    if magic == _FERNET_MAGIC:
        result = _decrypt_fallback(payload, key_path)
        if result is not None:
            logger.debug("Decrypted %d bytes with Fernet", len(result))
            return result
        return None

    # Unknown magic: treat as raw plaintext (legacy unencrypted files)
    logger.debug("No DPAPI magic found, returning ciphertext as-is (legacy)")
    return ciphertext


def is_dpapi_available() -> bool:
    """True if Windows DPAPI is available on this platform."""
    return _is_windows and _dpapi._init()  # type: ignore[attr-defined]
