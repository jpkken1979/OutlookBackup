r"""Tests de soporte de paths largos (Fase 3 plan v3.2).

Cubre `src/path_utils.py`:
- `safe_path()` agrega prefijo \\?\ si el path supera el umbral conservador.
- `is_long_path()` detecta paths potencialmente problematicos.
- `validate_backup_dir()` chequea writability + length antes del backup.

Notas:
- Los tests corren en Linux Y Windows. En Linux, `safe_path` es passthrough.
- Para forzar comportamiento Windows en Linux, los tests usan `monkeypatch.setattr(os, 'name', 'nt')`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pytestmark = pytest.mark.long_paths


def _make_japanese_path(target_chars: int, base: Path) -> Path:
    """Construye un path con segmentos japoneses para llegar a target_chars."""
    segment = "テスト用フォルダ"  # 8 kanji chars
    parts: list[str] = []
    current = len(str(base))
    while current < target_chars - len(segment) - 1:
        parts.append(segment)
        current += len(segment) + 1  # +1 por el separador
    return Path(base, *parts)


# ---------------------------------------------------------------------------
# Smoke: paths cortos siempre deben funcionar
# ---------------------------------------------------------------------------


def test_short_japanese_path_works(tmp_path: Path) -> None:
    """Path japones de ~100 chars debe funcionar sin tratamiento especial."""
    short_dir = tmp_path / "テスト" / "バックアップ"
    short_dir.mkdir(parents=True)
    test_file = short_dir / "test.txt"
    test_file.write_text("hello", encoding="utf-8")

    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "hello"


# ---------------------------------------------------------------------------
# is_long_path
# ---------------------------------------------------------------------------


def test_is_long_path_short_returns_false(tmp_path: Path) -> None:
    import path_utils

    assert path_utils.is_long_path(tmp_path / "short.txt") is False


def test_is_long_path_above_threshold_returns_true() -> None:
    import path_utils

    long = "C:\\" + ("very_long_segment_" * 20)  # > 240 chars
    assert path_utils.is_long_path(long) is True


def test_is_long_path_discounts_existing_prefix() -> None:
    """Si ya tiene prefijo, lo descuenta antes de comparar."""
    import path_utils

    # Path corto pero con prefijo: NO debe contar el prefijo en el largo
    short_with_prefix = path_utils.LONG_PATH_PREFIX + "C:\\short.txt"
    assert path_utils.is_long_path(short_with_prefix) is False


# ---------------------------------------------------------------------------
# safe_path
# ---------------------------------------------------------------------------


def test_safe_path_passthrough_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """En Linux/Mac no debe modificar el path."""
    import path_utils

    monkeypatch.setattr(path_utils.os, "name", "posix")
    long = "/very/long/" + ("segment/" * 50)  # > 240 chars
    assert path_utils.safe_path(long) == long


def test_safe_path_short_returns_unchanged(tmp_path: Path) -> None:
    """Path corto en Windows: no debe agregar prefijo."""
    import path_utils

    short = tmp_path / "short.pst"
    result = path_utils.safe_path(short)
    assert not result.startswith(path_utils.LONG_PATH_PREFIX)


def test_safe_path_long_adds_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Path largo en Windows: debe agregar prefijo \\\\?\\."""
    import path_utils

    monkeypatch.setattr(path_utils.os, "name", "nt")
    long_path = _make_japanese_path(target_chars=270, base=tmp_path)
    long_path.mkdir(parents=True, exist_ok=True)
    result = path_utils.safe_path(long_path)
    # En non-Windows real, Path.resolve() puede generar algo distinto, pero el
    # contrato es que el resultado deba arrancar con el prefijo cuando os.name=nt
    assert result.startswith(path_utils.LONG_PATH_PREFIX), (
        f"Path largo debe llevar prefijo, got: {result[:50]}..."
    )


def test_safe_path_no_double_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si ya tiene prefijo, no se duplica."""
    import path_utils

    monkeypatch.setattr(path_utils.os, "name", "nt")
    already_prefixed = path_utils.LONG_PATH_PREFIX + "C:\\some\\very\\long\\" + ("seg\\" * 50)
    result = path_utils.safe_path(already_prefixed)
    # Solo UN prefijo
    assert result.count(path_utils.LONG_PATH_PREFIX) == 1


@pytest.mark.skipif(os.name != "nt", reason="UNC paths solo aplican en Windows real")
def test_safe_path_unc_uses_unc_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """UNC paths usan prefijo especial \\\\?\\UNC\\."""
    import path_utils

    monkeypatch.setattr(path_utils.os, "name", "nt")
    unc_long = "\\\\server\\share\\" + ("very_long_segment_" * 20)
    result = path_utils.safe_path(unc_long)
    assert result.startswith(path_utils.LONG_PATH_PREFIX_UNC), (
        f"UNC path debe usar prefijo UNC: {result[:50]}..."
    )


# ---------------------------------------------------------------------------
# validate_backup_dir
# ---------------------------------------------------------------------------


def test_validate_backup_dir_creates_if_missing(tmp_path: Path) -> None:
    """Si el dir no existe, lo crea y retorna True."""
    import path_utils

    new_dir = tmp_path / "subdir" / "deeper"
    assert not new_dir.exists()

    ok, msg = path_utils.validate_backup_dir(new_dir)
    assert ok is True
    assert msg == ""
    assert new_dir.is_dir()


def test_validate_backup_dir_writeability_check(tmp_path: Path) -> None:
    """Crea archivo temp para verificar writability."""
    import path_utils

    ok, msg = path_utils.validate_backup_dir(tmp_path)
    assert ok is True
    assert msg == ""
    # Verificar que el writetest no dejo basura
    leftovers = list(tmp_path.glob(".uns_writetest_*"))
    assert leftovers == []


def test_validate_backup_dir_path_too_long_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si el path final excederia LONG_PATH_LIMIT, retorna False con mensaje japones."""
    import path_utils

    # Forzamos el limite super bajo para que cualquier tmp_path activate la rama
    monkeypatch.setattr(path_utils, "LONG_PATH_LIMIT", 10)

    ok, msg = path_utils.validate_backup_dir(tmp_path)
    assert ok is False
    # Mensaje en japones
    assert "パス" in msg or "長" in msg


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_path_constants_are_correct() -> None:
    """Sanity check de los limites NTFS."""
    import path_utils

    assert path_utils.MAX_PATH == 260
    assert path_utils.LONG_PATH_LIMIT == 32_767
    assert path_utils.LONG_PATH_THRESHOLD < path_utils.MAX_PATH
    assert path_utils.LONG_PATH_PREFIX == "\\\\?\\"
    assert path_utils.LONG_PATH_PREFIX_UNC == "\\\\?\\UNC\\"
