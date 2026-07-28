#!/usr/bin/env python3
"""Session key efimera para el gateway local Antigravity (:4747).

Cierra el agujero de seguridad documentado el 2026-04-11:

- Antes: si `ANTIGRAVITY_API_KEY` no estaba seteada, el middleware de auth
  daba bypass a cualquier cliente de loopback (`127.0.0.1`/`::1`). Combinado
  con el wildcard `"*"` que estaba en `DEFAULT_CORS_ORIGINS`, una pagina web
  abierta en el browser del usuario podia llamar endpoints sensibles del
  gateway sin credenciales (drive-by CORS / DNS rebinding).

- Ahora: al arrancar, el gateway llama `ensure_session_key()` que carga la
  key existente desde `~/.antigravity/session.key` o genera una nueva.
  La key se almacena **cifrada** en disco:
  - Windows: DPAPI (CryptProtectData / CryptUnprotectData) — la key solo es
    descifrable por el mismo usuario en la misma maquina.
  - Linux/macOS: AES-128-CBC (Fernet) con una clave derivada del path del
    archivo, equivalente en seguridad al esquema de permisos de archivo.

  Cualquier cliente local del ecosistema (Nexus, bot Telegram, CLI) que
  tenga acceso al disco del usuario puede leerla via `read_session_key()`
  y pasarla en el header `X-API-Key`. El descifrado automatico garantiza que
  un atacante que robe el archivo `session.key` no puede usar la key en
  otra maquina ni con otra cuenta de usuario.

Notas:

- La key sobrevive entre reinicios del gateway. Si se quiere rotacion,
  borrar el archivo y reiniciar — la proxima llamada a `ensure_session_key()`
  generara una nueva.
- Si el usuario exporta `ANTIGRAVITY_API_KEY` explicitamente, esa toma
  precedencia y no se usa la session key (compatibilidad hacia atras
  con setups de produccion / CI).
"""

from __future__ import annotations

import logging
import os
import secrets
import sys
import time
from pathlib import Path

# Permite correr este modulo standalone, no solo importado como parte de
# ``core``: sin esto, ``from core.dpapi`` falla si se invoca por ruta.
_agent_dir = Path(__file__).resolve().parents[1]
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

from core.dpapi import decrypt_for_user, encrypt_for_user, is_dpapi_available  # noqa: E402

logger = logging.getLogger(__name__)

SESSION_KEY_DIR_ENV = "ANTIGRAVITY_HOME_DIR"
DEFAULT_SESSION_KEY_DIR_NAME = ".antigravity"
SESSION_KEY_FILENAME = "session.key"
SESSION_KEY_BYTES = 32  # 256 bits → 64 hex chars


def session_key_path() -> Path:
    """Resuelve la ruta al archivo de session key.

    Honra `ANTIGRAVITY_HOME_DIR` (override de tests). Si no esta seteada,
    usa `~/.antigravity/session.key`.

    Returns:
        Path absoluto al archivo (puede no existir todavia).
    """
    override = os.environ.get(SESSION_KEY_DIR_ENV, "").strip()
    if override:
        base = Path(override).expanduser()
    else:
        base = Path.home() / DEFAULT_SESSION_KEY_DIR_NAME
    return base / SESSION_KEY_FILENAME


def _generate_key() -> str:
    """Genera una key hex aleatoria de 256 bits."""
    return secrets.token_hex(SESSION_KEY_BYTES)


def _restrict_permissions(path: Path) -> None:
    """Aplica permisos `0600` al archivo (no-op en Windows nativo)."""
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        logger.warning("No se pudo aplicar 0600 a %s: %s", path, exc)


def _atomic_write_encrypted(path: Path, encrypted: bytes) -> None:
    """Escribe `encrypted` en `path` de forma atomica (tmp + rename).

    Usa un archivo temporal con permisos `0600` y luego `os.replace` para
    evitar ventanas donde otros lectores vean un archivo a medio escribir.
    En Windows reintenta el rename con backoff exponencial (100ms, 200ms,
    400ms) porque antivirus u otros procesos pueden tener un lock momentaneo
    sobre el destino.

    Args:
        path: Ruta destino del archivo de session key.
        encrypted: Contenido cifrado a persistir.

    Raises:
        OSError: Si tras los reintentos no se pudo renombrar el temporal.
    """
    tmp = path.with_suffix(".key.tmp")
    try:
        tmp.write_bytes(encrypted)
        _restrict_permissions(tmp)
        last_err: OSError | None = None
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                last_err = None
                break
            except OSError as exc:
                last_err = exc
                if attempt < 2:
                    time.sleep(0.1 * (2**attempt))
        if last_err is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise last_err
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def ensure_session_key() -> str:
    """Carga la session key existente o genera una nueva.

    Si el archivo existe y la key es descifrable, la devuelve.
    Si no existe o esta corrupta/ilegible, genera una nueva, la **cifra**
    con DPAPI (Windows) o Fernet (fallback), la persiste con permisos
    `0600`, y la devuelve en texto plano (para uso en memoria).

    Returns:
        La session key como string hex.
    """
    path = session_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            raw = path.read_bytes()
            decrypted = decrypt_for_user(raw, path)
            if decrypted is not None:
                key = decrypted.decode("utf-8").strip()
                if len(key) >= 32 and all(c in "0123456789abcdefABCDEF" for c in key):
                    logger.debug(
                        "Session key leida (cifrada, DPAPI=%s)",
                        "si" if is_dpapi_available() else "no",
                    )
                    return key
            logger.warning("session.key existe pero esta corrupta, regenerando")
        except OSError as exc:
            logger.warning("No se pudo leer %s, regenerando: %s", path, exc)

    key = _generate_key()
    encrypted = encrypt_for_user(key.encode("utf-8"), path)
    _atomic_write_encrypted(path, encrypted)

    logger.info("Session key generada y cifrada (DPAPI=%s)", "si" if is_dpapi_available() else "no")
    return key


def read_session_key() -> str | None:
    """Lee la session key actual sin generar una nueva.

    Descifra automaticamente el contenido del archivo. Diseñado para clientes
    (Nexus, bot Telegram, CLI) que necesitan autenticarse contra el gateway.

    Returns:
        La key hex si existe y es descifrable, None en caso contrario.
    """
    path = session_key_path()
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        decrypted = decrypt_for_user(raw, path)
        if decrypted is not None:
            key = decrypted.decode("utf-8").strip()
            if len(key) >= 32:
                return key
    except OSError as exc:
        logger.warning("No se pudo leer session.key: %s", exc)
    return None


def _cli_print_key() -> int:
    """CLI: imprime en stdout la session key YA DESCIFRADA.

    Para clientes bash (skills como ``/provider``, ``/cambiar``, ``/cambio``) que
    necesitan el header ``X-API-Key``: el archivo en disco esta cifrado (Fernet o
    DPAPI), asi que un `cat` directo del path NUNCA sirve como key — manda el
    ciphertext crudo y el gateway responde 403 "API key invalida". Este CLI reusa
    el mismo `read_session_key()` que usan Nexus (Rust) y el bot (TS), sin generar
    una key nueva.

    Returns:
        0 y la key impresa si se pudo leer/descifrar; 1 y un mensaje en stderr
        si el gateway todavia no arranco o el archivo esta corrupto.
    """
    key = read_session_key()
    if key is None:
        print(
            f"No se pudo leer/descifrar {session_key_path()} "
            "(arranca el gateway con 'python start_gateway.py' primero)",
            file=sys.stderr,
        )
        return 1
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_print_key())
