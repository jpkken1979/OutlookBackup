"""
UNS Backup v3.1 - Connection Tester
===================================
Testea conectividad IMAP/SMTP con login real.
Socket level — sin librerías externas.
"""

import socket
import ssl
import base64
import time
from dataclasses import dataclass


@dataclass
class TestResult:
    """Resultado de un test de conexión."""
    success: bool
    message: str
    latency_ms: int
    server_banner: str = ""


class ConnectionTester:
    """Testea conexiones IMAP y SMTP con autenticación real."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def test_imap(self, server: str, port: int, ssl_enabled: bool,
                  email: str, password: str) -> TestResult:
        start = time.time()
        try:
            context = ssl.create_default_context() if ssl_enabled else None
            with socket.create_connection((server, port), timeout=self.timeout) as sock:
                if ssl_enabled:
                    sock = context.wrap_socket(sock, server_hostname=server)
                sock.settimeout(self.timeout)
                banner = sock.recv(256).decode('utf-8', errors='ignore').strip()
                latency = int((time.time() - start) * 1000)
                sock.send(f'A1 LOGIN "{email}" "{password}"\r\n'.encode())
                resp = sock.recv(256).decode('utf-8', errors='ignore')
                if '+OK' in resp or 'OK' in resp.upper():
                    sock.send(b'A2 LOGOUT\r\n')
                    return TestResult(success=True, message="OK", latency_ms=latency, server_banner=banner)
                else:
                    err = self._parse_imap_error(resp)
                    return TestResult(success=False, message=err, latency_ms=latency, server_banner=banner)
        except socket.timeout:
            return TestResult(success=False, message=f"接続タイムアウト ({self.timeout}秒)", latency_ms=0, server_banner="")
        except ssl.SSLError:
            return TestResult(success=False, message="SSL証明書のエラー", latency_ms=0, server_banner="")
        except ConnectionRefusedError:
            return TestResult(success=False, message="接続が拒否されました", latency_ms=0, server_banner="")
        except socket.gaierror:
            return TestResult(success=False, message="サーバーが見つかりません", latency_ms=0, server_banner="")
        except Exception as e:
            return TestResult(success=False, message=f"エラー: {str(e)[:50]}", latency_ms=0, server_banner="")

    def test_smtp(self, server: str, port: int, ssl_enabled: bool,
                  email: str, password: str) -> TestResult:
        start = time.time()
        try:
            context = ssl.create_default_context() if ssl_enabled else None
            with socket.create_connection((server, port), timeout=self.timeout) as sock:
                if ssl_enabled:
                    sock = context.wrap_socket(sock, server_hostname=server)
                sock.settimeout(self.timeout)
                banner = sock.recv(256).decode('utf-8', errors='ignore').strip()
                latency = int((time.time() - start) * 1000)
                sock.send(f'EHLO {server}\r\n'.encode())
                sock.recv(512)
                sock.send(b'AUTH LOGIN\r\n')
                resp = sock.recv(256).decode('utf-8', errors='ignore')
                if '334' not in resp:
                    return TestResult(success=False, message="AUTH LOGIN not supported", latency_ms=latency, server_banner=banner)
                sock.send(base64.b64encode(email.encode()) + b'\r\n')
                sock.recv(256)
                sock.send(base64.b64encode(password.encode()) + b'\r\n')
                resp = sock.recv(256).decode('utf-8', errors='ignore')
                if '235' in resp:
                    sock.send(b'QUIT\r\n')
                    return TestResult(success=True, message="OK", latency_ms=latency, server_banner=banner)
                else:
                    err = self._parse_smtp_error(resp)
                    return TestResult(success=False, message=err, latency_ms=latency, server_banner=banner)
        except socket.timeout:
            return TestResult(success=False, message=f"接続タイムアウト ({self.timeout}秒)", latency_ms=0, server_banner="")
        except ssl.SSLError:
            return TestResult(success=False, message="SSL証明書のエラー", latency_ms=0, server_banner="")
        except ConnectionRefusedError:
            return TestResult(success=False, message="接続が拒否されました", latency_ms=0, server_banner="")
        except socket.gaierror:
            return TestResult(success=False, message="サーバーが見つかりません", latency_ms=0, server_banner="")
        except Exception as e:
            return TestResult(success=False, message=f"エラー: {str(e)[:50]}", latency_ms=0, server_banner="")

    @staticmethod
    def _parse_imap_error(resp: str) -> str:
        if 'authentication failed' in resp.lower():
            return "認証失敗 (パスワード錯誤)"
        if 'user' in resp.lower() and 'fail' in resp.lower():
            return "ユーザーが見つかりません"
        return resp.strip()[:80]

    @staticmethod
    def _parse_smtp_error(resp: str) -> str:
        if '535' in resp:
            return "認証失敗 (パスワード錯誤)"
        if '530' in resp:
            return "認証が必要です"
        if '503' in resp:
            return "すでに認証済み"
        return resp.strip()[:80]