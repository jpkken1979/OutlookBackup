r"""Tests de soporte de paths largos (> MAX_PATH = 260 chars).

Fase 1 del plan v3.2 (docs/PLAN_HARDENING_WIN10_11.md):
- Define el contrato esperado para Fase 3 (long path support con prefijo \\?\).
- Tests xfail hasta que `src/path_utils.py` exista (Fase 3).

Por que importa para UNS-Kikaku:
- Paths japoneses con kanji ocupan mas bytes que ASCII pero el limite MAX_PATH
  cuenta CHARS, no bytes. Un path como
  `デスクトップ\\バックアップ\\2026年5月\\ユニバーサル企画株式会社\\` ya tiene
  ~50 chars que se suman al backup_dir del usuario.
- Si el usuario elige `Documents\\OneDrive\\Trabajo\\backups\\` (~50 chars) +
  `backup_20260513_142312\\kenji_at_uns-kikaku_com.pst` (~50 chars), ya hay
  ~100 chars de overhead constante. Quedan ~160 chars para el backup_dir
  custom — facilmente excedible en clientes con paths de OneDrive sincronizados.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pytestmark = pytest.mark.long_paths


# Limite NTFS sin prefijo \\?\
MAX_PATH = 260
# Limite con prefijo \\?\ (32k - epsilon por overhead)
LONG_PATH_LIMIT = 32_767


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
# Test smoke: paths cortos siempre deben funcionar
# ---------------------------------------------------------------------------


def test_short_japanese_path_works(tmp_path: Path) -> None:
    """Path japones de ~100 chars debe funcionar sin tratamiento especial.

    Sanity check: el comportamiento ACTUAL ya sirve para paths cortos. Si este
    test falla, hay un bug serio en el handling de Unicode en general (no es
    sobre long paths).
    """
    short_dir = tmp_path / "テスト" / "バックアップ"
    short_dir.mkdir(parents=True)
    test_file = short_dir / "test.txt"
    test_file.write_text("hello", encoding="utf-8")

    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "hello"
    assert len(str(test_file)) < MAX_PATH  # confirma que es "corto"


# ---------------------------------------------------------------------------
# Tests xfail — comportamiento que Fase 3 debe implementar
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Fase 3 del plan v3.2: src/path_utils.py:safe_path() debe agregar prefijo \\\\?\\",
    strict=False,
)
def test_path_utils_module_exists() -> None:
    """Fase 3 va a crear `src/path_utils.py`.

    Cuando exista, debe exponer:
        from path_utils import safe_path, validate_backup_dir
    """
    from path_utils import safe_path, validate_backup_dir  # noqa: F401


@pytest.mark.xfail(
    reason="Fase 3: safe_path() debe agregar prefijo \\\\?\\ a paths > 240 chars",
    strict=False,
)
def test_safe_path_adds_long_prefix_when_needed(tmp_path: Path) -> None:
    """`safe_path(p)` debe devolver path con prefijo \\\\?\\\\ si len(p) > 240."""
    try:
        from path_utils import safe_path
    except ImportError:
        pytest.skip("path_utils no existe todavia (Fase 3)")

    long_path = _make_japanese_path(target_chars=270, base=tmp_path)
    safe = safe_path(long_path)
    assert str(safe).startswith("\\\\?\\"), (
        f"Path > 240 chars debe llevar prefijo \\\\?\\\\: {safe}"
    )


@pytest.mark.xfail(
    reason="Fase 3: safe_path() NO debe agregar prefijo a paths cortos (compat APIs viejas)",
    strict=False,
)
def test_safe_path_does_not_add_prefix_for_short_paths(tmp_path: Path) -> None:
    """`safe_path(p)` debe ser pass-through para paths cortos."""
    try:
        from path_utils import safe_path
    except ImportError:
        pytest.skip("path_utils no existe todavia (Fase 3)")

    short_path = tmp_path / "short.pst"
    safe = safe_path(short_path)
    assert not str(safe).startswith("\\\\?\\"), f"Path < 240 chars NO debe llevar prefijo: {safe}"


@pytest.mark.xfail(
    reason="Fase 3: validate_backup_dir() debe avisar si el path final excederia limites",
    strict=False,
)
def test_validate_backup_dir_warns_when_close_to_limit(tmp_path: Path) -> None:
    """`validate_backup_dir(p)` debe devolver (False, msg_japones) si p esta cerca del limite."""
    try:
        from path_utils import validate_backup_dir
    except ImportError:
        pytest.skip("path_utils no existe todavia (Fase 3)")

    long_dir = _make_japanese_path(target_chars=240, base=tmp_path)
    long_dir.mkdir(parents=True, exist_ok=True)
    ok, msg = validate_backup_dir(long_dir)
    assert ok is False
    assert msg, "Debe haber mensaje de error en japones"


@pytest.mark.xfail(
    reason="Fase 3: backup_engine debe usar safe_path() en AddStoreEx para paths largos",
    strict=False,
)
def test_backup_engine_handles_long_destination(tmp_path: Path) -> None:
    """Backup integration test: PST destination > 260 chars debe funcionar via safe_path()."""
    try:
        from path_utils import safe_path  # noqa: F401
    except ImportError:
        pytest.skip("path_utils no existe todavia (Fase 3)")

    pytest.skip("Integration test placeholder — Fase 3 implementa el refactor de engines")


# ---------------------------------------------------------------------------
# Documentacion del contrato (no es un test, es referencia)
# ---------------------------------------------------------------------------


def test_max_path_constants_are_correct() -> None:
    """Sanity check de los limites NTFS — no deben cambiar."""
    assert MAX_PATH == 260, "Windows MAX_PATH es 260 chars (incluye terminador NUL)"
    assert LONG_PATH_LIMIT == 32_767, "Limite con prefijo \\\\?\\\\ es 32767 wchars"
