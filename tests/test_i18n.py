"""Tests del modulo i18n — carga desde ja.json compartido con el frontend."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TestI18nLoader:
    def test_loads_known_keys(self) -> None:
        from i18n import t

        # Keys que sabemos que estan en ja.json
        assert t("tab_backup") == "📤 バックアップ"
        assert t("ok") == "OK"

    def test_missing_key_returns_key_as_fallback(self) -> None:
        from i18n import t

        assert t("__nonexistent_key__") == "__nonexistent_key__"

    def test_kwargs_substitution(self) -> None:
        from i18n import t

        # confirm_backup_msg contiene {count} y {dir}
        msg = t("confirm_backup_msg", count=3, dir="C:\\Backup")
        assert "3" in msg
        assert "C:\\Backup" in msg

    def test_kwargs_missing_keys_returns_template(self) -> None:
        from i18n import t

        # Si el template tiene {dir} y no pasamos dir, devuelve el template
        # sin crashear (defensivo).
        result = t("confirm_backup_msg", count=3)  # falta dir
        assert isinstance(result, str)

    def test_all_strings_returns_copy(self) -> None:
        from i18n import all_strings

        strings = all_strings()
        assert isinstance(strings, dict)
        assert len(strings) > 100  # ja.json tiene ~200 keys

    def test_strings_dict_immutable_externally(self) -> None:
        """Modificar el dict devuelto no afecta el cache interno."""
        from i18n import all_strings, t

        copy1 = all_strings()
        copy1["test_key"] = "MUTATED"

        # La proxima llamada a t() no ve la mutacion
        assert t("test_key") == "test_key"  # fallback, no mutated value


class TestI18nKeysAreInSync:
    """Verifica que las keys que la app usa estan en ja.json."""

    def test_critical_keys_exist(self) -> None:
        from i18n import all_strings

        strings = all_strings()
        critical = [
            "tab_backup",
            "tab_restore",
            "tab_history",
            "tab_auto",
            "tab_cache",
            "tab_tools",
            "tab_settings",
            "btn_start_backup",
            "btn_cancel",
            "ok",
            "cancel",
            "company_name",
        ]
        missing = [k for k in critical if k not in strings]
        assert not missing, f"Keys faltantes en ja.json: {missing}"
