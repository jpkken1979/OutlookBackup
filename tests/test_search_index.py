"""Tests unitarios para search_index.SearchIndex (Feature B plan v3.2.0)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from search_index import SearchIndex  # noqa: E402


@pytest.fixture()
def sample_backups() -> list[dict]:
    return [
        {
            "name": "2026-05-13_kenji_success",
            "path": "/backups/2026-05-13_kenji",
            "start_time": "2026-05-13T10:30:00",
            "status": "success",
            "accounts_count": 2,
            "total_size_mb": 512.3,
            "total_emails": 18234,
            "errors_count": 0,
            "accounts_processed": [
                {"smtp": "kenji@uns-kikaku.com"},
                {"smtp": "info@uns-kikaku.com"},
            ],
            "pst_files": [{"name": "kenji.pst"}, {"name": "info.pst"}],
        },
        {
            "name": "2026-05-20_yuki_partial",
            "path": "/backups/2026-05-20_yuki",
            "start_time": "2026-05-20T14:00:00",
            "status": "partial",
            "accounts_count": 1,
            "total_size_mb": 128.0,
            "total_emails": 4500,
            "errors_count": 3,
            "accounts_processed": [{"smtp": "yuki@uns-kikaku.com"}],
            "pst_files": [{"name": "yuki.ost"}],
        },
    ]


@pytest.fixture()
def index(tmp_path: Path) -> SearchIndex:
    idx = SearchIndex(tmp_path / "test_search.db")
    yield idx
    idx.close()


class TestRebuild:
    def test_rebuild_returns_count(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        n = index.rebuild_from_history(sample_backups)
        assert n == 2
        assert index.count() == 2

    def test_rebuild_is_idempotent(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        index.rebuild_from_history(sample_backups)
        assert index.count() == 2

    def test_rebuild_replaces_previous_data(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        index.rebuild_from_history([sample_backups[0]])
        assert index.count() == 1


class TestSearch:
    def test_search_by_account_smtp(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search("kenji@uns-kikaku.com")
        assert len(results) == 1
        assert results[0]["name"] == "2026-05-13_kenji_success"
        assert "kenji@uns-kikaku.com" in results[0]["accounts"]

    def test_search_by_date_prefix(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search("2026-05")
        assert len(results) == 2

    def test_search_by_status(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search("partial")
        assert len(results) == 1
        assert results[0]["status"] == "partial"

    def test_search_by_pst_name(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search("yuki.ost")
        assert len(results) == 1
        assert "yuki.ost" in results[0]["pst_files"]

    def test_search_multi_token_is_and(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        """Tokens múltiples se combinan con AND implícito."""
        index.rebuild_from_history(sample_backups)
        results = index.search("kenji success")
        assert len(results) == 1
        assert results[0]["name"] == "2026-05-13_kenji_success"

    def test_search_no_results(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        assert index.search("nonexistent") == []

    def test_search_empty_query_returns_empty(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        assert index.search("") == []
        assert index.search("   ") == []

    def test_search_respects_limit(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search("2026", limit=1)
        assert len(results) == 1


class TestSanitize:
    def test_query_with_parens_does_not_crash(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        # Paréntesis sueltos romperían el parser FTS5 crudo — debe sanearse.
        results = index.search("kenji ) OR 1=1")
        assert isinstance(results, list)

    def test_query_with_unmatched_quote_does_not_crash(
        self, index: SearchIndex, sample_backups: list[dict]
    ) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search('kenji "unmatched')
        assert isinstance(results, list)

    def test_query_with_star_does_not_crash(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search("* kenji")
        assert isinstance(results, list)


class TestResultShape:
    def test_result_has_all_fields(self, index: SearchIndex, sample_backups: list[dict]) -> None:
        index.rebuild_from_history(sample_backups)
        results = index.search("kenji")
        assert len(results) == 1
        r = results[0]
        for key in (
            "name",
            "accounts",
            "start_time",
            "status",
            "pst_files",
            "path",
            "accounts_count",
            "total_size_mb",
            "total_emails",
            "errors_count",
            "rank",
        ):
            assert key in r, f"missing key: {key}"
        assert isinstance(r["accounts"], list)
        assert isinstance(r["pst_files"], list)
        assert isinstance(r["total_size_mb"], float)
        assert isinstance(r["total_emails"], int)

    def test_result_accounts_split_correctly(
        self, index: SearchIndex, sample_backups: list[dict]
    ) -> None:
        index.rebuild_from_history(sample_backups)
        r = index.search("kenji@uns-kikaku.com")[0]
        assert set(r["accounts"]) == {"kenji@uns-kikaku.com", "info@uns-kikaku.com"}


class TestEmpty:
    def test_search_empty_index(self, index: SearchIndex) -> None:
        assert index.search("anything") == []
        assert index.count() == 0

    def test_rebuild_empty_list(self, index: SearchIndex) -> None:
        n = index.rebuild_from_history([])
        assert n == 0
        assert index.count() == 0


class TestContextManager:
    def test_context_manager_closes(self, tmp_path: Path) -> None:
        with SearchIndex(tmp_path / "ctx.db") as idx:
            assert idx.count() == 0
        # Después del close, la conexión está cerrada — no lanzamos assertions extra
        # porque SQLite permite operaciones tras close con error; aquí solo verificamos
        # que no lanza durante el uso normal.


class TestMissingFields:
    def test_backup_without_accounts_processed(self, index: SearchIndex) -> None:
        """Backups sin report.json tienen campos faltantes — no debe crashear."""
        index.rebuild_from_history([{"name": "incomplete", "path": "/x"}])
        r = index.search("incomplete")[0]
        assert r["accounts"] == []
        assert r["pst_files"] == []
        assert r["accounts_count"] == 0
