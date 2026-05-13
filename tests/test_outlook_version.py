"""Tests directos del modulo `outlook.version` (Fase 4 plan v3.2).

Cubre:
- `OutlookVersion` dataclass — inmutable, fields correctos
- `is_supported(v)` — helper de version major
- `_parse_version_tuple(s)` — parsing de "16.0.x.x"
- `_detect_m365()` — registry HKLM\\...\\ClickToRun\\Configuration
- `_detect_perpetual()` — registry HKLM\\...\\Office\\{ver}\\Outlook\\InstallRoot
- `detect_outlook_version()` — orquestador (M365 first, perpetual fallback)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pytestmark = pytest.mark.outlook_version


# ---------------------------------------------------------------------------
# OutlookVersion dataclass
# ---------------------------------------------------------------------------


def test_outlook_version_is_immutable() -> None:
    """frozen=True para evitar modificaciones accidentales."""
    import dataclasses

    from outlook.version import OutlookVersion

    v = OutlookVersion(
        version_str="16.0.17726.20126",
        version_tuple=(16, 0, 17726, 20126),
        flavor="M365",
        install_path=None,
        supported=True,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.version_str = "other"  # type: ignore[misc]


def test_outlook_version_default_product_release_ids() -> None:
    """product_release_ids default es lista vacia."""
    from outlook.version import OutlookVersion

    v = OutlookVersion(
        version_str="16.0.0.0",
        version_tuple=(16, 0, 0, 0),
        flavor="perpetual",
        install_path=None,
        supported=True,
    )
    assert v.product_release_ids == []


# ---------------------------------------------------------------------------
# is_supported
# ---------------------------------------------------------------------------


def test_is_supported_returns_true_for_office_2019() -> None:
    """Major 16 (Office 2016+) debe estar soportado."""
    from outlook.version import OutlookVersion, is_supported

    v = OutlookVersion(
        version_str="16.0.10380.20002",
        version_tuple=(16, 0, 10380, 20002),
        flavor="perpetual",
        install_path=None,
        supported=True,
    )
    assert is_supported(v) is True


def test_is_supported_returns_false_for_office_2013() -> None:
    """Major 15 (Office 2013) NO esta soportado en v3.2."""
    from outlook.version import OutlookVersion, is_supported

    v = OutlookVersion(
        version_str="15.0.0.0",
        version_tuple=(15, 0, 0, 0),
        flavor="perpetual",
        install_path=None,
        supported=False,
    )
    assert is_supported(v) is False


def test_is_supported_returns_false_for_unknown() -> None:
    """version_tuple vacio (deteccion fallida) → no soportado."""
    from outlook.version import OutlookVersion, is_supported

    v = OutlookVersion(
        version_str="",
        version_tuple=(),
        flavor="unknown",
        install_path=None,
        supported=False,
    )
    assert is_supported(v) is False


def test_is_supported_accepts_future_version_17() -> None:
    """Major 17 (Office 2025? futuro) ya esta soportado preventivamente."""
    from outlook.version import OutlookVersion, is_supported

    v = OutlookVersion(
        version_str="17.0.0.0",
        version_tuple=(17, 0, 0, 0),
        flavor="perpetual",
        install_path=None,
        supported=True,
    )
    assert is_supported(v) is True


# ---------------------------------------------------------------------------
# _parse_version_tuple
# ---------------------------------------------------------------------------


def test_parse_version_tuple_full_version() -> None:
    from outlook.version import _parse_version_tuple

    assert _parse_version_tuple("16.0.17726.20126") == (16, 0, 17726, 20126)


def test_parse_version_tuple_short_version() -> None:
    from outlook.version import _parse_version_tuple

    assert _parse_version_tuple("16.0") == (16, 0)


def test_parse_version_tuple_invalid_returns_empty() -> None:
    from outlook.version import _parse_version_tuple

    assert _parse_version_tuple("abc") == ()
    assert _parse_version_tuple("") == ()
    assert _parse_version_tuple("16.x.0") == ()


# ---------------------------------------------------------------------------
# _detect_m365 — mock registry
# ---------------------------------------------------------------------------


def test_detect_m365_returns_none_when_no_clicktorun(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin ClickToRun en registry → None."""
    from outlook import version

    monkeypatch.setattr(version, "_read_string", lambda *_a, **_kw: None)
    assert version._detect_m365() is None


def test_detect_m365_returns_version_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con ClickToRun configurado → devuelve OutlookVersion con flavor=M365."""
    from outlook import version

    fake_values = {
        "VersionToReport": "16.0.17726.20126",
        "InstallationPath": "C:\\Program Files\\Microsoft Office\\root",
        "ProductReleaseIds": "O365BusinessRetail,GrooveRetail",
    }

    def fake_read(_root: Any, _path: str, value_name: str) -> str | None:
        return fake_values.get(value_name)

    monkeypatch.setattr(version, "_read_string", fake_read)

    result = version._detect_m365()
    assert result is not None
    assert result.flavor == "M365"
    assert result.version_str == "16.0.17726.20126"
    assert result.version_tuple == (16, 0, 17726, 20126)
    assert result.supported is True
    assert result.install_path == Path("C:\\Program Files\\Microsoft Office\\root")
    assert "O365BusinessRetail" in result.product_release_ids
    assert "GrooveRetail" in result.product_release_ids


# ---------------------------------------------------------------------------
# _detect_perpetual — mock registry
# ---------------------------------------------------------------------------


def test_detect_perpetual_returns_none_when_no_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin InstallRoot en ningun major version → None."""
    from outlook import version

    monkeypatch.setattr(version, "_read_string", lambda *_a, **_kw: None)
    assert version._detect_perpetual() is None


def test_detect_perpetual_returns_office_2019(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con InstallRoot en 16.0 → devuelve OutlookVersion con flavor=perpetual."""
    from outlook import version

    install_path = "C:\\Program Files\\Microsoft Office\\Office16"

    def fake_read(_root: Any, path: str, value_name: str) -> str | None:
        if value_name == "Path" and "16.0" in path:
            return install_path
        return None

    monkeypatch.setattr(version, "_read_string", fake_read)

    result = version._detect_perpetual()
    assert result is not None
    assert result.flavor == "perpetual"
    assert result.version_str == "16.0"
    assert result.version_tuple == (16, 0)
    assert result.supported is True
    assert result.install_path == Path(install_path)


def test_detect_perpetual_skips_15_when_16_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si tanto 16.0 como 15.0 estan presentes, prefiere 16.0 (orden KNOWN_MAJOR_VERSIONS)."""
    from outlook import version

    def fake_read(_root: Any, path: str, value_name: str) -> str | None:
        if value_name == "Path":
            if "16.0" in path:
                return "C:\\Office16"
            if "15.0" in path:
                return "C:\\Office15"
        return None

    monkeypatch.setattr(version, "_read_string", fake_read)
    result = version._detect_perpetual()
    assert result is not None
    assert "16" in str(result.install_path)


def test_detect_perpetual_marks_office_2013_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Office 2013 (15.0) sin 16.0: detectado pero supported=False."""
    from outlook import version

    def fake_read(_root: Any, path: str, value_name: str) -> str | None:
        if value_name == "Path" and "15.0" in path:
            return "C:\\Office15"
        return None

    monkeypatch.setattr(version, "_read_string", fake_read)
    result = version._detect_perpetual()
    assert result is not None
    assert result.flavor == "perpetual"
    assert result.version_str == "15.0"
    assert result.supported is False  # 15 no esta en SUPPORTED_MAJOR_VERSIONS


# ---------------------------------------------------------------------------
# detect_outlook_version — orquestador
# ---------------------------------------------------------------------------


def test_detect_returns_unknown_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """En POSIX siempre devuelve unknown."""
    from outlook import version

    monkeypatch.setattr(version.os, "name", "posix")
    result = version.detect_outlook_version()
    assert result.flavor == "unknown"
    assert result.supported is False
    assert result.version_tuple == ()


def test_detect_prefers_m365_over_perpetual(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si ambos M365 y perpetual estan presentes, M365 gana."""
    from outlook import version

    monkeypatch.setattr(version.os, "name", "nt")

    fake_m365 = version.OutlookVersion(
        version_str="16.0.17726.20126",
        version_tuple=(16, 0, 17726, 20126),
        flavor="M365",
        install_path=None,
        supported=True,
    )
    monkeypatch.setattr(version, "_detect_m365", lambda: fake_m365)
    monkeypatch.setattr(
        version,
        "_detect_perpetual",
        lambda: pytest.fail("No deberia llamarse si M365 detectado"),
    )

    result = version.detect_outlook_version()
    assert result.flavor == "M365"


def test_detect_falls_back_to_perpetual(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si M365 no detectado, prueba perpetual."""
    from outlook import version

    monkeypatch.setattr(version.os, "name", "nt")
    monkeypatch.setattr(version, "_detect_m365", lambda: None)

    fake_perpetual = version.OutlookVersion(
        version_str="16.0",
        version_tuple=(16, 0),
        flavor="perpetual",
        install_path=Path("C:\\Office16"),
        supported=True,
    )
    monkeypatch.setattr(version, "_detect_perpetual", lambda: fake_perpetual)

    result = version.detect_outlook_version()
    assert result.flavor == "perpetual"


def test_detect_returns_unknown_when_nothing_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin M365 ni perpetual: unknown."""
    from outlook import version

    monkeypatch.setattr(version.os, "name", "nt")
    monkeypatch.setattr(version, "_detect_m365", lambda: None)
    monkeypatch.setattr(version, "_detect_perpetual", lambda: None)

    result = version.detect_outlook_version()
    assert result.flavor == "unknown"
    assert result.supported is False
