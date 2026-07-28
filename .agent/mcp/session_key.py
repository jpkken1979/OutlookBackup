"""Compatibility facade for the canonical shared session-key module."""

from core.session_key import (
    DEFAULT_SESSION_KEY_DIR_NAME,
    SESSION_KEY_BYTES,
    SESSION_KEY_DIR_ENV,
    SESSION_KEY_FILENAME,
    _atomic_write_encrypted,
    _cli_print_key,
    ensure_session_key,
    read_session_key,
    session_key_path,
)

__all__ = [
    "DEFAULT_SESSION_KEY_DIR_NAME",
    "SESSION_KEY_BYTES",
    "SESSION_KEY_DIR_ENV",
    "SESSION_KEY_FILENAME",
    "ensure_session_key",
    "read_session_key",
    "session_key_path",
]


if __name__ == "__main__":
    raise SystemExit(_cli_print_key())
