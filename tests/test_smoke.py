"""Smoke tests — verifica que la suite arranca y los imports funcionan.

Estos tests son la prueba de vida del toolchain. Si fallan, todo el resto
falla. Si pasan, podes empezar a agregar tests de logica de negocio.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Agregar src/ al path para que `import config`, `import crypto_utils` funcione.
SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_pytest_works() -> None:
    """Caso trivial — confirma que pytest descubre y ejecuta tests."""
    assert 1 + 1 == 2


def test_can_import_crypto_utils() -> None:
    """crypto_utils no depende de win32com — debe importar sin mocks."""
    import crypto_utils

    assert hasattr(crypto_utils, "encrypt_dict_to_file")
    assert hasattr(crypto_utils, "decrypt_file_to_dict")
    assert hasattr(crypto_utils, "estimate_password_strength")


def test_can_import_config(tmp_appdata: Path) -> None:
    """config.py importable con APPDATA mockeado."""
    import config

    assert hasattr(config, "DEFAULT_CONFIG")
    assert config.DEFAULT_CONFIG["domain_filter"] == "uns-kikaku.com"


def test_can_import_connection_tester() -> None:
    """connection_tester usa stdlib (socket+ssl) — sin deps Win."""
    import connection_tester

    assert hasattr(connection_tester, "KNOWN_PORTS")
    assert connection_tester.IMAP_PORT_SSL == 993


@pytest.mark.windows
def test_real_win32com_marker() -> None:
    """Sanity check del marker. En Linux CI debe skipearse via -m 'not windows'."""
    assert True
