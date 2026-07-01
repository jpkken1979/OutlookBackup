"""Tests directos de `shell_extractor.ShellExtractor`.

Cubre:
- _find_unrar: candidatos de WinRAR/7-Zip vs fallback a PATH (shutil.which)
- can_extract_rar: combinacion RARFILE_AVAILABLE + unrar_path
- extract_rar: archivo faltante, sin unrar disponible, happy path (rarfile
  mockeado), cancelacion a mitad de la extraccion, deteccion de scripts
- _is_script: extensiones ejecutables conocidas
- find_rar_files: listado ordenado por tamano desc, directorio inexistente
- run_script: dispatch por extension (.ps1/.bat/.cmd/.vbs/.exe/desconocida),
  timeout y excepcion generica de subprocess (regla shell=False)
- get_extract_dir: crea y devuelve el directorio temporal
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class _FakeRarMember:
    def __init__(self, filename: str) -> None:
        self.filename = filename


class _FakeRarFile:
    def __init__(self, members: list[_FakeRarMember]) -> None:
        self._members = members
        self.extracted: list[tuple[str, str]] = []
        self.raise_on_extract: set[str] = set()

    def __enter__(self) -> _FakeRarFile:
        return self

    def __exit__(self, *_a: Any) -> bool:
        return False

    def infolist(self) -> list[_FakeRarMember]:
        return self._members

    def extract(self, member: _FakeRarMember, output_dir: str) -> None:
        if member.filename in self.raise_on_extract:
            raise RuntimeError("archivo protegido")
        self.extracted.append((member.filename, output_dir))


def _make_extractor(
    monkeypatch: pytest.MonkeyPatch, unrar_path: str | None = "/usr/bin/unrar"
) -> Any:
    import shell_extractor

    monkeypatch.setattr(shell_extractor.ShellExtractor, "_find_unrar", lambda self: unrar_path)
    return shell_extractor.ShellExtractor()


# ---------------------------------------------------------------------------
# _find_unrar
# ---------------------------------------------------------------------------


def test_find_unrar_prefers_known_program_files_candidates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shell_extractor

    program_files = tmp_path / "ProgramFiles"
    winrar_dir = program_files / "WinRAR"
    winrar_dir.mkdir(parents=True)
    (winrar_dir / "unrar.exe").write_bytes(b"fake-exe")

    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "does-not-exist"))
    monkeypatch.setattr(shell_extractor.shutil, "which", lambda _name: None)

    extractor = shell_extractor.ShellExtractor()
    assert extractor.unrar_path == str(winrar_dir / "unrar.exe")


def test_find_unrar_falls_back_to_path_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    monkeypatch.setenv("ProgramFiles", "")
    monkeypatch.setenv("ProgramFiles(x86)", "")
    monkeypatch.setattr(
        shell_extractor.shutil,
        "which",
        lambda name: "/usr/bin/unrar" if name == "unrar.exe" else None,
    )

    extractor = shell_extractor.ShellExtractor()
    assert extractor.unrar_path == "/usr/bin/unrar"


def test_find_unrar_returns_none_when_nothing_found(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    monkeypatch.setenv("ProgramFiles", "")
    monkeypatch.setenv("ProgramFiles(x86)", "")
    monkeypatch.setattr(shell_extractor.shutil, "which", lambda _name: None)

    extractor = shell_extractor.ShellExtractor()
    assert extractor.unrar_path is None


# ---------------------------------------------------------------------------
# can_extract_rar
# ---------------------------------------------------------------------------


def test_can_extract_rar_true_when_available_and_unrar_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shell_extractor

    monkeypatch.setattr(shell_extractor, "RARFILE_AVAILABLE", True)
    extractor = _make_extractor(monkeypatch, unrar_path="/usr/bin/unrar")
    assert extractor.can_extract_rar() is True


def test_can_extract_rar_false_without_unrar_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    monkeypatch.setattr(shell_extractor, "RARFILE_AVAILABLE", True)
    extractor = _make_extractor(monkeypatch, unrar_path=None)
    assert extractor.can_extract_rar() is False


def test_can_extract_rar_false_when_rarfile_lib_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shell_extractor

    monkeypatch.setattr(shell_extractor, "RARFILE_AVAILABLE", False)
    extractor = _make_extractor(monkeypatch, unrar_path="/usr/bin/unrar")
    assert extractor.can_extract_rar() is False


# ---------------------------------------------------------------------------
# extract_rar
# ---------------------------------------------------------------------------


def test_extract_rar_missing_file_returns_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extractor = _make_extractor(monkeypatch)
    result = extractor.extract_rar(str(tmp_path / "ghost.rar"), str(tmp_path / "out"))

    assert result["success"] is False
    assert "Archivo no encontrado" in result["error"]


def test_extract_rar_returns_error_when_unrar_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shell_extractor

    monkeypatch.setattr(shell_extractor, "RARFILE_AVAILABLE", True)
    extractor = _make_extractor(monkeypatch, unrar_path=None)

    rar_path = tmp_path / "backup.rar"
    rar_path.write_bytes(b"fake")

    result = extractor.extract_rar(str(rar_path), str(tmp_path / "out"))

    assert result["success"] is False
    assert "unrar.exe" in result["error"]


def test_extract_rar_happy_path_extracts_and_flags_scripts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shell_extractor

    monkeypatch.setattr(shell_extractor, "RARFILE_AVAILABLE", True)
    extractor = _make_extractor(monkeypatch)

    rar_path = tmp_path / "migration.rar"
    rar_path.write_bytes(b"fake")
    output_dir = tmp_path / "out"

    fake_rf = _FakeRarFile([_FakeRarMember("data.pst"), _FakeRarMember("setup.ps1")])
    monkeypatch.setattr(shell_extractor.rarfile, "RarFile", lambda _path: fake_rf)

    log: list[str] = []
    result = extractor.extract_rar(str(rar_path), str(output_dir), progress_cb=log.append)

    assert result["success"] is True
    assert len(result["files_extracted"]) == 2
    assert any(p.endswith("setup.ps1") for p in result["scripts_found"])
    assert output_dir.exists()
    assert any("展開" in m for m in log)


def test_extract_rar_stops_when_cancel_flag_is_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shell_extractor

    monkeypatch.setattr(shell_extractor, "RARFILE_AVAILABLE", True)
    extractor = _make_extractor(monkeypatch)
    extractor._cancel_flag.set()

    rar_path = tmp_path / "migration.rar"
    rar_path.write_bytes(b"fake")

    fake_rf = _FakeRarFile([_FakeRarMember("a.pst"), _FakeRarMember("b.pst")])
    monkeypatch.setattr(shell_extractor.rarfile, "RarFile", lambda _path: fake_rf)

    result = extractor.extract_rar(str(rar_path), str(tmp_path / "out"))

    assert result["success"] is True  # el loop corta pero igual reporta success
    assert result["files_extracted"] == []
    assert fake_rf.extracted == []


def test_extract_rar_continues_after_individual_member_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shell_extractor

    monkeypatch.setattr(shell_extractor, "RARFILE_AVAILABLE", True)
    extractor = _make_extractor(monkeypatch)

    rar_path = tmp_path / "migration.rar"
    rar_path.write_bytes(b"fake")

    fake_rf = _FakeRarFile([_FakeRarMember("broken.pst"), _FakeRarMember("ok.pst")])
    fake_rf.raise_on_extract = {"broken.pst"}
    monkeypatch.setattr(shell_extractor.rarfile, "RarFile", lambda _path: fake_rf)

    result = extractor.extract_rar(str(rar_path), str(tmp_path / "out"))

    assert result["success"] is True
    assert len(result["files_extracted"]) == 1
    assert result["files_extracted"][0].endswith("ok.pst")


# ---------------------------------------------------------------------------
# _is_script
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("setup.ps1", True),
        ("run.bat", True),
        ("run.cmd", True),
        ("script.vbs", True),
        ("installer.exe", True),
        ("app.msi", True),
        ("data.pst", False),
        ("readme.txt", False),
    ],
)
def test_is_script_detects_executable_extensions(
    monkeypatch: pytest.MonkeyPatch, filename: str, expected: bool
) -> None:
    extractor = _make_extractor(monkeypatch)
    assert extractor._is_script(f"/some/dir/{filename}") is expected


# ---------------------------------------------------------------------------
# find_rar_files
# ---------------------------------------------------------------------------


def test_find_rar_files_returns_empty_for_missing_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extractor = _make_extractor(monkeypatch)
    assert extractor.find_rar_files(str(tmp_path / "ghost")) == []


def test_find_rar_files_sorted_by_size_descending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "small.rar").write_bytes(b"x" * 100)
    (tmp_path / "big.rar").write_bytes(b"x" * 10_000)
    (tmp_path / "not-a-rar.txt").write_bytes(b"x")

    extractor = _make_extractor(monkeypatch)
    files = extractor.find_rar_files(str(tmp_path))

    assert [f["filename"] for f in files] == ["big.rar", "small.rar"]


# ---------------------------------------------------------------------------
# run_script
# ---------------------------------------------------------------------------


def test_run_script_unknown_extension_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    extractor = _make_extractor(monkeypatch)
    result = extractor.run_script("/tmp/weird.xyz")

    assert result["success"] is False
    assert "未知のスクリプト形式" in result["error"]


def test_run_script_ps1_uses_powershell_arg_list(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(shell_extractor.subprocess, "run", fake_run)
    extractor = _make_extractor(monkeypatch)

    result = extractor.run_script("/tmp/setup.ps1")

    assert result["success"] is True
    assert result["output"] == "ok"
    assert captured["cmd"][0] == "powershell"
    assert "-File" in captured["cmd"]
    assert isinstance(captured["cmd"], list)  # nunca string+shell=True


def test_run_script_bat_uses_cmd_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="done", stderr="")

    monkeypatch.setattr(shell_extractor.subprocess, "run", fake_run)
    extractor = _make_extractor(monkeypatch)

    result = extractor.run_script("/tmp/migrate.bat")

    assert result["success"] is True
    assert captured["cmd"] == ["cmd", "/c", "/tmp/migrate.bat"]


def test_run_script_vbs_uses_cscript(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shell_extractor.subprocess, "run", fake_run)
    extractor = _make_extractor(monkeypatch)

    extractor.run_script("/tmp/import.vbs")
    assert captured["cmd"] == ["cscript", "//Nologo", "/tmp/import.vbs"]


def test_run_script_exe_runs_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shell_extractor.subprocess, "run", fake_run)
    extractor = _make_extractor(monkeypatch)

    extractor.run_script("/tmp/installer.exe")
    assert captured["cmd"] == ["/tmp/installer.exe"]


def test_run_cmd_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    monkeypatch.setattr(shell_extractor.subprocess, "run", fake_run)
    extractor = _make_extractor(monkeypatch)

    result = extractor.run_script("/tmp/slow.bat")

    assert result["success"] is True  # run_script solo falla si tira excepcion propia
    assert "タイムアウト" in result["output"]


def test_run_cmd_reports_generic_exception_in_output(monkeypatch: pytest.MonkeyPatch) -> None:
    import shell_extractor

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise OSError("permission denied")

    monkeypatch.setattr(shell_extractor.subprocess, "run", fake_run)
    extractor = _make_extractor(monkeypatch)

    result = extractor.run_script("/tmp/broken.bat")

    assert result["success"] is True
    assert "permission denied" in result["output"]


# ---------------------------------------------------------------------------
# get_extract_dir
# ---------------------------------------------------------------------------


def test_get_extract_dir_creates_and_returns_path(monkeypatch: pytest.MonkeyPatch) -> None:
    extractor = _make_extractor(monkeypatch)
    path = extractor.get_extract_dir()

    assert Path(path).is_dir()
    assert path.endswith("UNS_Shell_Tools")
