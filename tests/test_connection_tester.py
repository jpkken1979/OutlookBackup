"""Tests directos del modulo `connection_tester` (sockets/SSL puros para IMAP/SMTP).

Cubre:
- test_imap_connection / test_smtp_connection: happy path (plano y SSL),
  errores de timeout/DNS/conexion rechazada/SSL/excepcion generica, y que
  el socket siempre se cierra en el finally
- test_account_connection: orquestador que lee registry + arma summary
- _infer_port: puerto por defecto vs puerto detectado en registry
- _read_line / format_test_result: helpers puros

No se toca la red real: se monkeypatchea `connection_tester.socket.socket`
con un FakeSocket in-memory, y `connection_tester.ssl.create_default_context`
con un contexto que envuelve el socket de forma transparente (sin TLS real).
"""

from __future__ import annotations

import socket
import ssl
import sys
from pathlib import Path
from typing import Any

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class FakeSocket:
    """Socket in-memory: recv(1) consume un buffer byte a byte."""

    def __init__(self, recv_bytes: bytes = b"", connect_error: Exception | None = None) -> None:
        self._buffer = bytearray(recv_bytes)
        self._connect_error = connect_error
        self.sent: list[bytes] = []
        self.closed = False
        self.timeout: float | None = None

    def settimeout(self, t: float) -> None:
        self.timeout = t

    def connect(self, _addr: tuple[str, int]) -> None:
        if self._connect_error:
            raise self._connect_error

    def send(self, data: bytes) -> int:
        self.sent.append(data)
        return len(data)

    def recv(self, n: int) -> bytes:
        if not self._buffer:
            return b""
        chunk = bytes(self._buffer[:n])
        del self._buffer[:n]
        return chunk

    def close(self) -> None:
        self.closed = True


def _fake_socket_factory(fake: FakeSocket) -> Any:
    def _factory(*_a: Any, **_k: Any) -> FakeSocket:
        return fake

    return _factory


def _passthrough_ssl_context(monkeypatch: pytest.MonkeyPatch, module: Any) -> None:
    """SSL wrap transparente: wrap_socket devuelve el mismo socket, sin TLS real."""

    class FakeContext:
        check_hostname = True
        verify_mode = None

        def wrap_socket(self, sock: Any, server_hostname: str | None = None) -> Any:
            return sock

    monkeypatch.setattr(module.ssl, "create_default_context", lambda: FakeContext())


# ---------------------------------------------------------------------------
# test_imap_connection
# ---------------------------------------------------------------------------


def test_imap_connection_happy_path_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    import connection_tester

    fake = FakeSocket(recv_bytes=b"* OK IMAP4rev1 ready\r\n* OK NOOP completed\r\n")
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))

    result = connection_tester.test_imap_connection("imap.uns-kikaku.com", 143)

    assert result["success"] is True
    assert result["server_banner"] == "* OK IMAP4rev1 ready"
    assert result["latency_ms"] >= 0
    assert fake.sent == [b"NOOP\r\n"]
    assert fake.closed is True


def test_imap_connection_happy_path_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    import connection_tester

    fake = FakeSocket(recv_bytes=b"* OK IMAP4rev1 ready\r\n* OK NOOP completed\r\n")
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))
    _passthrough_ssl_context(monkeypatch, connection_tester)

    result = connection_tester.test_imap_connection("imap.uns-kikaku.com", 993)

    assert result["success"] is True
    assert result["server_banner"] == "* OK IMAP4rev1 ready"


def test_imap_connection_ssl_error_returns_early(monkeypatch: pytest.MonkeyPatch) -> None:
    import connection_tester

    fake = FakeSocket(recv_bytes=b"should not be read")
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))

    class FailingContext:
        check_hostname = True
        verify_mode = None

        def wrap_socket(self, _sock: Any, server_hostname: str | None = None) -> Any:
            raise ssl.SSLError("handshake failed")

    monkeypatch.setattr(connection_tester.ssl, "create_default_context", lambda: FailingContext())

    result = connection_tester.test_imap_connection("imap.uns-kikaku.com", 993)

    assert result["success"] is False
    assert "SSL error" in result["error"]
    assert fake.sent == []  # nunca llego a mandar NOOP


@pytest.mark.parametrize(
    ("exc", "expected_fragment"),
    [
        (TimeoutError(), "Connection timed out"),
        (socket.gaierror("no address"), "DNS resolution failed"),
        (ConnectionRefusedError(), "Connection refused"),
        (RuntimeError("boom"), "Unexpected error"),
    ],
)
def test_imap_connection_error_paths(
    monkeypatch: pytest.MonkeyPatch, exc: Exception, expected_fragment: str
) -> None:
    import connection_tester

    fake = FakeSocket(connect_error=exc)
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))

    result = connection_tester.test_imap_connection("imap.uns-kikaku.com", 143)

    assert result["success"] is False
    assert expected_fragment in result["error"]
    assert fake.closed is True  # el finally siempre cierra el socket


# ---------------------------------------------------------------------------
# test_smtp_connection
# ---------------------------------------------------------------------------


def test_smtp_connection_happy_path_multiline_ehlo(monkeypatch: pytest.MonkeyPatch) -> None:
    import connection_tester

    banner = b"220 smtp.uns-kikaku.com ESMTP ready\r\n"
    ehlo_multiline = b"250-smtp.uns-kikaku.com\r\n250-STARTTLS\r\n250 OK\r\n"
    fake = FakeSocket(recv_bytes=banner + ehlo_multiline)
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))

    result = connection_tester.test_smtp_connection("smtp.uns-kikaku.com", 587)

    assert result["success"] is True
    assert result["server_banner"].startswith("220 smtp.uns-kikaku.com")
    assert fake.sent == [b"EHLO smtp.uns-kikaku.com\r\n"]


def test_smtp_connection_stops_on_5xx_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codigo 5xx en EHLO corta el loop de lectura pero igual marca success."""
    import connection_tester

    banner = b"220 ready\r\n"
    ehlo_error = b"550 Access denied\r\n"
    fake = FakeSocket(recv_bytes=banner + ehlo_error)
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))

    result = connection_tester.test_smtp_connection("smtp.uns-kikaku.com", 25)

    assert result["success"] is True  # solo verifica que el server respondio, no el codigo


def test_smtp_connection_happy_path_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    import connection_tester

    fake = FakeSocket(recv_bytes=b"220 ready\r\n250 OK\r\n")
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))
    _passthrough_ssl_context(monkeypatch, connection_tester)

    result = connection_tester.test_smtp_connection("smtp.uns-kikaku.com", 465)
    assert result["success"] is True


def test_smtp_connection_empty_host_uses_localhost_in_ehlo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import connection_tester

    fake = FakeSocket(recv_bytes=b"220 ready\r\n250 OK\r\n")
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))

    connection_tester.test_smtp_connection("", 25)
    assert fake.sent == [b"EHLO localhost\r\n"]


def test_smtp_connection_connection_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    import connection_tester

    fake = FakeSocket(connect_error=ConnectionRefusedError())
    monkeypatch.setattr(connection_tester.socket, "socket", _fake_socket_factory(fake))

    result = connection_tester.test_smtp_connection("smtp.uns-kikaku.com", 25)
    assert result["success"] is False
    assert "Connection refused" in result["error"]


# ---------------------------------------------------------------------------
# _read_line
# ---------------------------------------------------------------------------


def test_read_line_stops_at_crlf() -> None:
    import connection_tester

    fake = FakeSocket(recv_bytes=b"hello\r\ngarbage-after")
    line = connection_tester._read_line(fake)  # type: ignore[arg-type]
    assert line == "hello"


def test_read_line_returns_empty_on_closed_socket() -> None:
    import connection_tester

    fake = FakeSocket(recv_bytes=b"")
    assert connection_tester._read_line(fake) == ""  # type: ignore[arg-type]


def test_read_line_safety_cutoff_past_1024_bytes() -> None:
    """Sin terminador, no debe leer para siempre — corta apenas supera 1024 bytes."""
    import connection_tester

    fake = FakeSocket(recv_bytes=b"x" * 2000)
    line = connection_tester._read_line(fake)  # type: ignore[arg-type]
    assert len(line) == 1025  # corta en cuanto len(data) > 1024, no vuelve a leer los 2000


# ---------------------------------------------------------------------------
# _infer_port
# ---------------------------------------------------------------------------


def test_infer_port_uses_explicit_registry_port() -> None:
    import connection_tester

    servers = {"ports_detected": [{"protocol": "imaps", "port": 993}]}
    port = connection_tester._infer_port(
        servers, "incoming", connection_tester.IMAP_PORT_SSL, connection_tester.IMAP_PORT_PLAIN
    )
    assert port == 993


def test_infer_port_incoming_default_is_ssl_port() -> None:
    import connection_tester

    port = connection_tester._infer_port(
        {}, "incoming", connection_tester.IMAP_PORT_SSL, connection_tester.IMAP_PORT_PLAIN
    )
    assert port == connection_tester.IMAP_PORT_SSL


def test_infer_port_outgoing_default_returns_plain_port_param() -> None:
    """Documenta el comportamiento actual: sin puerto detectado, 'outgoing'
    devuelve el parametro `plain_port` (SMTP_PORT_PLAIN=25), pese a que el
    comentario en el codigo fuente dice "587 for SMTP". El caller
    (test_account_connection) invoca con ssl_port=SMTP_PORT_STARTTLS(587) y
    plain_port=SMTP_PORT_PLAIN(25), asi que el default real termina siendo 25.
    """
    import connection_tester

    port = connection_tester._infer_port(
        {},
        "outgoing",
        connection_tester.SMTP_PORT_STARTTLS,
        connection_tester.SMTP_PORT_PLAIN,
    )
    assert port == connection_tester.SMTP_PORT_PLAIN


# ---------------------------------------------------------------------------
# test_account_connection
# ---------------------------------------------------------------------------


def test_account_connection_no_registry_data_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    import connection_tester

    monkeypatch.setattr(connection_tester, "_read_registry_servers", lambda _smtp: None)

    result = connection_tester.test_account_connection("kenji@uns-kikaku.com")

    assert result["success"] is False
    assert result["summary"] == "No server info found in registry"


def test_account_connection_combines_imap_and_smtp_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import connection_tester

    monkeypatch.setattr(
        connection_tester,
        "_read_registry_servers",
        lambda _smtp: {
            "incoming_server": "imap.uns-kikaku.com",
            "outgoing_server": "smtp.uns-kikaku.com",
        },
    )
    monkeypatch.setattr(
        connection_tester,
        "test_imap_connection",
        lambda host, port, timeout=10: {"success": True, "latency_ms": 42},
    )
    monkeypatch.setattr(
        connection_tester,
        "test_smtp_connection",
        lambda host, port, timeout=10: {"success": False, "error": "Connection refused"},
    )

    result = connection_tester.test_account_connection("kenji@uns-kikaku.com", protocol="auto")

    assert result["success"] is True  # al menos uno paso (IMAP)
    assert "IMAP OK" in result["summary"]
    assert "SMTP failed" in result["summary"]


def test_account_connection_protocol_imap_only_skips_smtp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import connection_tester

    monkeypatch.setattr(
        connection_tester,
        "_read_registry_servers",
        lambda _smtp: {"incoming_server": "imap.uns-kikaku.com"},
    )
    calls: list[str] = []
    monkeypatch.setattr(
        connection_tester,
        "test_imap_connection",
        lambda host, port, timeout=10: calls.append("imap") or {"success": True},
    )
    monkeypatch.setattr(
        connection_tester,
        "test_smtp_connection",
        lambda host, port, timeout=10: calls.append("smtp") or {"success": True},
    )

    connection_tester.test_account_connection("kenji@uns-kikaku.com", protocol="imap")

    assert calls == ["imap"]


def test_account_connection_missing_server_in_registry_reports_specific_error() -> None:
    import connection_tester

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            connection_tester, "_read_registry_servers", lambda _smtp: {"incoming_server": ""}
        )
        result = connection_tester.test_account_connection("kenji@uns-kikaku.com", protocol="imap")

    assert result["tests"]["imap"]["error"] == "No IMAP server found in registry"


# ---------------------------------------------------------------------------
# format_test_result
# ---------------------------------------------------------------------------


def test_format_test_result_success_truncates_long_banner() -> None:
    import connection_tester

    result = {"success": True, "latency_ms": 15, "server_banner": "x" * 100}
    formatted = connection_tester.format_test_result(result)

    assert formatted.startswith("OK (15ms)")
    assert "..." in formatted
    assert len(formatted) < 100  # se trunco, no se mostro el banner completo


def test_format_test_result_failure_shows_error() -> None:
    import connection_tester

    result = {"success": False, "error": "Connection refused"}
    assert connection_tester.format_test_result(result) == "FAILED | Connection refused"
