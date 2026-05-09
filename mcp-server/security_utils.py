#!/usr/bin/env python3
# =============================================================================
# DO NOT EDIT DIRECTLY - CANONICAL SOURCE IS .agent/mcp/security_utils.py
# =============================================================================
# Este archivo es una COPIA LITERAL (excepto este header) de la fuente canónica.
# Existe como archivo separado porque `mcp-server/` es un deployment PORTÁTIL
# que no puede depender de `.agent/mcp/` en runtime (se distribuye solo).
#
# Para cualquier cambio de seguridad:
#   1. Editar PRIMERO .agent/mcp/security_utils.py (fuente canónica).
#   2. Copiar el contenido (cuerpo) a este archivo preservando este header.
#   3. Correr: python -m pytest tests/mcp/test_security_utils_sync.py -v
#
# El test de sincronización compara hashes SHA256 del cuerpo (sin headers) y
# falla si los dos archivos divergen. Es la red de seguridad contra drift.
# =============================================================================
"""
Security helpers compartidos para servidores MCP y HTTP remotos.

FUENTE CANÓNICA: `.agent/mcp/security_utils.py` — NO editar este archivo directamente.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

# En modo producción (ANTIGRAVITY_ENV=production o ANTIGRAVITY_CORS_STRICT=1)
# se fuerza lista explícita de orígenes sin wildcard.
_PRODUCTION = (
    os.environ.get("ANTIGRAVITY_ENV", "").lower() == "production"
    or os.environ.get("ANTIGRAVITY_CORS_STRICT", "0") == "1"
)

_LOCAL_ORIGINS: list[str] = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:4747",
    "http://localhost:3000",
    "http://127.0.0.1",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4747",
    "https://tauri.localhost",
    "http://tauri.localhost",
    "tauri://localhost",
]

# NOTA DE SEGURIDAD: el wildcard "*" fue removido del default dev (2026-04-11).
# Combinado con el bypass de auth por loopback en gateway_main.py, permitia
# drive-by CORS desde cualquier pagina web abierta en el browser del usuario.
# Para restaurar el comportamiento previo (NO recomendado), setea
# ANTIGRAVITY_CORS_ORIGINS="*,http://localhost:5173,..." explicitamente.
DEFAULT_CORS_ORIGINS: list[str] = _LOCAL_ORIGINS.copy() if _PRODUCTION else _LOCAL_ORIGINS.copy()

LOCALHOST_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost"}


def parse_cors_origins(raw: str | None, default: list[str] | None = None) -> list[str]:
    """Parsea lista de orígenes CORS desde env/entrada textual.

    Args:
        raw: Cadena CSV de orígenes, o None para usar defaults.
        default: Lista de defaults personalizada; usa DEFAULT_CORS_ORIGINS si es None.

    Returns:
        Lista de orígenes CORS válidos.
    """
    defaults = default if default is not None else DEFAULT_CORS_ORIGINS
    source = raw if raw is not None else ",".join(defaults)
    origins = [origin.strip() for origin in source.split(",") if origin.strip()]
    return origins or defaults.copy()


def is_origin_allowed(origin: str, allowed_origins: list[str]) -> bool:
    """Valida origen CORS, aceptando host/scheme con puerto variable.

    Valida el scheme ANTES del wildcard — file://, data://, javascript:
    son siempre rechazados.

    Args:
        origin: El origen HTTP de la solicitud entrante.
        allowed_origins: Lista de orígenes permitidos (puede contener '*').

    Returns:
        True si el origen está permitido, False en caso contrario.
    """
    if not origin:
        return False

    # Validar scheme ANTES del wildcard — file://, data://, javascript: siempre rechazados
    try:
        parsed_origin = urlsplit(origin)
    except ValueError:
        return False

    if not parsed_origin.scheme or not parsed_origin.hostname:
        return False

    # Only allow http/https schemes — reject file://, data://, javascript:, etc.
    if parsed_origin.scheme not in ("http", "https"):
        return False

    if "*" in allowed_origins:
        return True
    if origin in allowed_origins:
        return True

    for allowed in allowed_origins:
        try:
            parsed_allowed = urlsplit(allowed)
        except ValueError:
            continue

        if not parsed_allowed.scheme or not parsed_allowed.hostname:
            continue

        if (
            parsed_allowed.port is None
            and parsed_allowed.scheme == parsed_origin.scheme
            and parsed_allowed.hostname == parsed_origin.hostname
        ):
            return True
    return False


def build_cors_policy(origins: list[str] | None) -> tuple[list[str], str | None]:
    """Construye allow_origins y allow_origin_regex para middlewares CORS.

    Args:
        origins: Lista de orígenes explícitos, o None para usar DEFAULT_CORS_ORIGINS.

    Returns:
        Tupla (allow_origins, allow_origin_regex). El regex es None salvo que
        haya orígenes localhost sin puerto definido (se usa LOCALHOST_ORIGIN_REGEX).
    """
    if origins is None:
        cleaned = DEFAULT_CORS_ORIGINS.copy()
    else:
        cleaned = [origin.strip() for origin in origins if origin and origin.strip()]
        if not cleaned:
            cleaned = DEFAULT_CORS_ORIGINS.copy()

    if "*" in cleaned:
        return ["*"], None

    allow_localhost_regex = False
    for origin in cleaned:
        parsed = urlsplit(origin)
        try:
            port = parsed.port
        except ValueError:
            continue
        if (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"localhost", "127.0.0.1"}
            and port is None
        ):
            allow_localhost_regex = True
            break

    return cleaned, (LOCALHOST_ORIGIN_REGEX if allow_localhost_regex else None)


def is_localhost_client(client_ip: str) -> bool:
    """Retorna True si la IP del cliente corresponde a localhost.

    Args:
        client_ip: Dirección IP del cliente (IPv4 o IPv6).

    Returns:
        True si es localhost (incluye IPv6-mapped IPv4 ::ffff:127.0.0.1).
    """
    if not client_ip:
        return False
    if client_ip in LOCALHOST_IPS:
        return True
    return client_ip.startswith("::ffff:127.0.0.1")


def is_within_root(root: str | Path, candidate: str | Path) -> bool:
    """Verifica que 'candidate' esté dentro de 'root' (previene path traversal).

    Acepta tanto str como Path. Compatible con agents-server.py, skills-server.py
    y ecosystem-server.py.

    Args:
        root: Directorio raíz (str o Path).
        candidate: Ruta candidata a verificar (str o Path).

    Returns:
        True si candidate resuelve dentro de root.
    """
    try:
        Path(candidate).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        return False


# Alias para compatibilidad con verificadores legacy que esperan is_within_project_root
is_within_project_root = is_within_root


def validate_url_for_ssrf(url: str) -> tuple[bool, str]:
    """Valida una URL para prevenir SSRF.

    Bloquea:
    - Schemes distintos de http/https
    - Hostnames que resuelven a IPs privadas (10.x, 172.16-31.x, 192.168.x, 127.x, ::1, etc.)
    - Hostnames internos (localhost, *.local, etc.)

    Args:
        url: URL a validar.

    Returns:
        Tupla (es_valida, razon). Si es_valida=True, razon es "".
        Si es_valida=False, razon describe el motivo del rechazo.
    """
    import ipaddress
    import socket

    try:
        parsed = urlsplit(url)
    except ValueError:
        return False, "URL mal formada"

    # Solo http y https
    if parsed.scheme not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' no permitido (solo http/https)"

    if not parsed.hostname:
        return False, "Hostname ausente"

    hostname = parsed.hostname.lower()

    # Bloquear localhost y variants
    if hostname in ("localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"):
        return False, f"Hostname '{hostname}' no permitido"

    # Bloquear direcciones IPv4 privadas/reservadas
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_multicast:
            return False, f"IP privada '{addr}' no permitida"
    except ValueError:
        pass  # No es IP directa, es hostname — resolver

    # Resolver hostname y verificar que no apunte a IP privada
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
        for info in infos:
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_multicast:
                return False, f"Hostname '{hostname}' resuelve a IP privada '{addr}'"
    except socket.gaierror:
        # No se pudo resolver — rechazar por seguridad
        return False, f"Hostname '{hostname}' no resolved"

    return True, ""
