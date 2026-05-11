"""
UNS Backup v3.1 - Connection Tester
=====================================
Tests IMAP/SMTP connectivity to mail servers using only stdlib.
No external dependencies — pure socket, ssl, time.
"""

import logging
import socket
import ssl
import time
from typing import Any

logger = logging.getLogger(__name__)

# Ports configuration
IMAP_PORT_SSL = 993
IMAP_PORT_PLAIN = 143
SMTP_PORT_SSL = 465
SMTP_PORT_STARTTLS = 587
SMTP_PORT_PLAIN = 25

KNOWN_PORTS = {
    25: "smtp",
    110: "pop3",
    143: "imap",
    465: "smtps",
    587: "smtp_starttls",
    993: "imaps",
    995: "pop3s",
}

# Registry parsing support
WIN32_AVAILABLE = False
try:
    import winreg

    WIN32_AVAILABLE = True
except ImportError:
    pass


def test_imap_connection(host: str, port: int, timeout: int = 10) -> dict:
    """Test IMAP connection.

    Args:
        host: Server hostname
        port: 993 (IMAPS) or 143 (IMAP)
        timeout: Connection timeout in seconds

    Returns:
        {"success": bool, "latency_ms": int, "server_banner": str, "error": str}
    """
    result: dict = {
        "success": False,
        "latency_ms": 0,
        "server_banner": "",
        "error": "",
    }

    start_time = time.time()
    raw_socket = None

    try:
        logger.info(f"Testing IMAP connection to {host}:{port}")

        # Create socket
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_socket.settimeout(timeout)

        # Connect and measure latency
        raw_socket.connect((host, port))
        result["latency_ms"] = int((time.time() - start_time) * 1000)

        # Wrap with SSL if port 993
        if port == IMAP_PORT_SSL:
            try:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE  # Skip cert verification for testing
                ssl_socket = context.wrap_socket(raw_socket, server_hostname=host)
                raw_socket = ssl_socket
                logger.debug("SSL handshake completed")
            except ssl.SSLError as e:
                result["error"] = f"SSL error: {e}"
                return result

        # Read server banner (IMAP greeting)
        banner = _read_line(raw_socket)
        result["server_banner"] = banner or ""
        logger.debug(f"IMAP banner: {banner}")

        # Send NOOP to verify server is responsive
        if raw_socket:
            raw_socket.send(b"NOOP\r\n")
            # Read response (should be OK)
            response = _read_line(raw_socket)
            logger.debug(f"NOOP response: {response}")

        result["success"] = True
        logger.info(f"IMAP connection OK ({result['latency_ms']}ms)")

    except TimeoutError:
        result["error"] = "Connection timed out"
        logger.warning(f"IMAP timeout to {host}:{port}")
    except socket.gaierror as e:
        result["error"] = f"DNS resolution failed: {e}"
        logger.warning(f"IMAP DNS error to {host}:{port} - {e}")
    except ConnectionRefusedError:
        result["error"] = "Connection refused"
        logger.warning(f"IMAP connection refused {host}:{port}")
    except ssl.SSLError as e:
        result["error"] = f"SSL error: {e}"
        logger.warning(f"IMAP SSL error {host}:{port} - {e}")
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        logger.error(f"IMAP unexpected error {host}:{port} - {e}")
    finally:
        if raw_socket:
            try:
                raw_socket.close()
            except Exception:
                pass

    return result


def test_smtp_connection(host: str, port: int, timeout: int = 10) -> dict:
    """Test SMTP connection.

    Args:
        host: Server hostname
        port: 465 (SMTPS), 587 (STARTTLS), or 25
        timeout: Connection timeout in seconds

    Returns:
        {"success": bool, "latency_ms": int, "server_banner": str, "error": str}
    """
    result: dict = {
        "success": False,
        "latency_ms": 0,
        "server_banner": "",
        "error": "",
    }

    start_time = time.time()
    raw_socket = None

    try:
        logger.info(f"Testing SMTP connection to {host}:{port}")

        # Create socket
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_socket.settimeout(timeout)

        # Connect and measure latency
        raw_socket.connect((host, port))
        result["latency_ms"] = int((time.time() - start_time) * 1000)

        # Wrap with SSL if port 465
        if port == SMTP_PORT_SSL:
            try:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                ssl_socket = context.wrap_socket(raw_socket, server_hostname=host)
                raw_socket = ssl_socket
                logger.debug("SMTP SSL handshake completed")
            except ssl.SSLError as e:
                result["error"] = f"SSL error: {e}"
                return result

        # Read server banner (SMTP greeting)
        banner = _read_line(raw_socket)
        result["server_banner"] = banner or ""
        logger.debug(f"SMTP banner: {banner}")

        # Send EHLO to verify server is responsive
        if raw_socket:
            # Use domain from host or placeholder
            domain = host if host else "localhost"
            raw_socket.send(f"EHLO {domain}\r\n".encode())
            # Read response (multiple lines until 250)
            while True:
                line = _read_line(raw_socket)
                if not line:
                    break
                logger.debug(f"EHLO response: {line}")
                # 250 means success, other codes mean continue
                if line.startswith("250"):
                    break
                if line.startswith("5"):
                    break

        result["success"] = True
        logger.info(f"SMTP connection OK ({result['latency_ms']}ms)")

    except TimeoutError:
        result["error"] = "Connection timed out"
        logger.warning(f"SMTP timeout to {host}:{port}")
    except socket.gaierror as e:
        result["error"] = f"DNS resolution failed: {e}"
        logger.warning(f"SMTP DNS error to {host}:{port} - {e}")
    except ConnectionRefusedError:
        result["error"] = "Connection refused"
        logger.warning(f"SMTP connection refused {host}:{port}")
    except ssl.SSLError as e:
        result["error"] = f"SSL error: {e}"
        logger.warning(f"SMTP SSL error {host}:{port} - {e}")
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        logger.error(f"SMTP unexpected error {host}:{port} - {e}")
    finally:
        if raw_socket:
            try:
                raw_socket.close()
            except Exception:
                pass

    return result


def test_account_connection(smtp: str, protocol: str = "auto", timeout: int = 10) -> dict:
    """Test connection for an account by reading server info from registry.

    Args:
        smtp: Email address (e.g. "kenji@uns-kikaku.com")
        protocol: "auto" (both), "imap", or "smtp"
        timeout: Connection timeout in seconds

    Returns:
        {
            "success": True,
            "tests": {
                "imap": {...},
                "smtp": {...}
            },
            "summary": "IMAP OK · SMTP failed"
        }
    """
    result: dict = {
        "success": True,
        "tests": {},
        "summary": "",
    }

    logger.info(f"Testing connection for account: {smtp}")

    # Read server info from registry
    servers = _read_registry_servers(smtp)

    if not servers:
        result["success"] = False
        result["summary"] = "No server info found in registry"
        logger.warning(f"No registry data for {smtp}")
        return result

    # Determine which protocols to test
    test_imap = protocol in ("auto", "imap")
    test_smtp = protocol in ("auto", "smtp")

    # Test IMAP
    if test_imap:
        imap_host = servers.get("incoming_server", "")
        imap_port = _infer_port(servers, "incoming", IMAP_PORT_SSL, IMAP_PORT_PLAIN)

        if imap_host:
            logger.info(f"Testing IMAP: {imap_host}:{imap_port}")
            imap_result = test_imap_connection(imap_host, imap_port, timeout)
            result["tests"]["imap"] = imap_result
        else:
            result["tests"]["imap"] = {
                "success": False,
                "error": "No IMAP server found in registry",
            }

    # Test SMTP
    if test_smtp:
        smtp_host = servers.get("outgoing_server", "")
        smtp_port = _infer_port(servers, "outgoing", SMTP_PORT_STARTTLS, SMTP_PORT_PLAIN)

        if smtp_host:
            logger.info(f"Testing SMTP: {smtp_host}:{smtp_port}")
            smtp_result = test_smtp_connection(smtp_host, smtp_port, timeout)
            result["tests"]["smtp"] = smtp_result
        else:
            result["tests"]["smtp"] = {
                "success": False,
                "error": "No SMTP server found in registry",
            }

    # Generate summary
    summary_parts = []
    if "imap" in result["tests"]:
        imap_test = result["tests"]["imap"]
        if imap_test.get("success"):
            summary_parts.append(f"IMAP OK ({imap_test.get('latency_ms', 0)}ms)")
        else:
            summary_parts.append(f"IMAP failed: {imap_test.get('error', 'unknown')}")

    if "smtp" in result["tests"]:
        smtp_test = result["tests"]["smtp"]
        if smtp_test.get("success"):
            summary_parts.append(f"SMTP OK ({smtp_test.get('latency_ms', 0)}ms)")
        else:
            summary_parts.append(f"SMTP failed: {smtp_test.get('error', 'unknown')}")

    result["summary"] = " · ".join(summary_parts)

    # Overall success if at least one test passed
    imap_ok = result["tests"].get("imap", {}).get("success", False)
    smtp_ok = result["tests"].get("smtp", {}).get("success", False)
    result["success"] = imap_ok or smtp_ok

    logger.info(f"Connection test summary: {result['summary']}")
    return result


def _read_registry_servers(smtp_address: str) -> dict | None:
    """Read server settings from Outlook registry for a given email.

    Copy the logic from account_inventory.py:_read_registry_servers (lines 136-205).

    Args:
        smtp_address: Email address to look up in registry

    Returns:
        Dict with incoming_server, outgoing_server, ports_detected, or None
    """
    if not smtp_address:
        return None

    if not WIN32_AVAILABLE:
        return None

    found: dict = {}
    versions = ["16.0", "15.0", "14.0"]

    for ver in versions:
        try:
            base_path = f"Software\\Microsoft\\Office\\{ver}\\Outlook\\Profiles\\Outlook"
            try:
                base_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path)
            except OSError:
                continue

            try:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(base_key, i)
                        sub_path = f"{base_path}\\{sub_name}"

                        try:
                            sub_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_path)
                            props = _scan_registry_values(sub_key)
                            winreg.CloseKey(sub_key)

                            email_in_props = props.get("email", "").lower()
                            if email_in_props and email_in_props == smtp_address.lower():
                                # Found matching account
                                for k, v in props.items():
                                    found.setdefault(k, v)
                        except OSError:
                            pass
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(base_key)

            if found.get("email"):
                break
        except Exception:
            continue

    if not found:
        return None

    # Build result dict
    result: dict = {
        "incoming_server": found.get("incoming_server"),
        "outgoing_server": found.get("outgoing_server"),
        "ports_detected": [],
        "outlook_version": found.get("_outlook_version"),
    }

    # Extract port information
    for k, v in found.items():
        if k.startswith("port_"):
            result["ports_detected"].append(
                {
                    "protocol": k.replace("port_", ""),
                    "port": v,
                }
            )

    # Remove None values
    return {k: v for k, v in result.items() if v is not None}


def _scan_registry_values(reg_key: Any) -> dict:
    """Scan all values in a registry key looking for email/server data.

    Args:
        reg_key: Open winreg key (winreg.HKEYType, tipado como Any para Linux compat)

    Returns:
        Dict with email, incoming_server, outgoing_server, port_*, _outlook_version
    """
    found: dict = {}
    extra_strings: list = []

    try:
        i = 0
        while True:
            try:
                _, value, vtype = winreg.EnumValue(reg_key, i)
                i += 1

                if vtype == winreg.REG_BINARY and isinstance(value, bytes):
                    try:
                        decoded = value.decode("utf-16-le").rstrip("\x00").strip()
                        if not decoded or len(decoded) > 255:
                            continue

                        decoded_lower = decoded.lower()

                        # Email detection
                        if "@" in decoded and "." in decoded and " " not in decoded:
                            if 5 < len(decoded) < 100:
                                found.setdefault("email", decoded)

                        # Server detection
                        elif any(
                            decoded_lower.startswith(p)
                            for p in [
                                "imap.",
                                "pop.",
                                "smtp.",
                                "mail.",
                                "outlook.",
                                "ssl0.",
                                "exchange.",
                            ]
                        ):
                            if "imap." in decoded_lower or "pop." in decoded_lower:
                                found.setdefault("incoming_server", decoded)
                            elif "smtp." in decoded_lower:
                                found.setdefault("outgoing_server", decoded)
                            else:
                                if decoded not in extra_strings:
                                    extra_strings.append(decoded)
                    except Exception:
                        pass

                elif vtype == winreg.REG_DWORD:
                    if isinstance(value, int) and value in KNOWN_PORTS:
                        proto = KNOWN_PORTS[value]
                        found.setdefault(f"port_{proto}", value)
            except OSError:
                break
    except Exception:
        pass

    if extra_strings:
        found["_extra_strings"] = extra_strings[:5]

    return found


def _read_line(sock: socket.socket) -> str:
    """Read a single line from a socket (until \\r\\n or \\n).

    Args:
        sock: Connected socket

    Returns:
        Line content as string (stripped), empty string on timeout
    """
    try:
        data = b""
        while True:
            chunk = sock.recv(1)
            if not chunk:
                break
            data += chunk
            # Check for line ending
            if b"\r\n" in data:
                break
            if data.endswith(b"\n"):
                break
            # Safety: don't read forever
            if len(data) > 1024:
                break

        return data.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _infer_port(servers: dict, direction: str, ssl_port: int, plain_port: int) -> int:
    """Infer port from registry data or use default.

    Args:
        servers: Registry servers dict
        direction: "incoming" or "outgoing"
        ssl_port: Default SSL port
        plain_port: Default plain port

    Returns:
        Port number to use
    """
    # Check if we have explicit port info
    ports = servers.get("ports_detected", [])
    for p in ports:
        proto = p.get("protocol", "")
        if direction == "incoming" and proto in ("imaps", "imap"):
            return int(p.get("port", ssl_port))
        if direction == "outgoing" and proto in ("smtps", "smtp_starttls", "smtp"):
            return int(p.get("port", ssl_port))

    # Default: use SSL port for imaps/smtps, plain for others
    if direction == "incoming":
        return ssl_port  # 993
    else:
        return plain_port  # 587 for SMTP


def format_test_result(result: dict) -> str:
    """Format a test result for display.

    Args:
        result: Test result dict from test_imap_connection or test_smtp_connection

    Returns:
        Human-readable string with status, latency, and banner/error
    """
    if result.get("success"):
        latency = result.get("latency_ms", 0)
        banner = result.get("server_banner", "")
        # Truncate banner if too long
        if len(banner) > 80:
            banner = banner[:80] + "..."
        return f"OK ({latency}ms) | {banner}"
    else:
        return f"FAILED | {result.get('error', 'unknown error')}"
