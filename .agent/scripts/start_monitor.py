"""Sidecar monitor del gateway :4747 — modo degraded automatico.

Complementa a ``scripts/gateway_watchdog.py`` (que KILLA y relanza el gateway).
Este NO mata nada: cuando detecta caida, DEGRADA ``~/.claude/settings.json``
quitando ``ANTHROPIC_BASE_URL`` para que Claude Code use Claude nativo directo
(modo degraded). Cuando el gateway vuelve, restaura el proxy de forma atomica.

Esto elimina el SPOF del modelo proxy-always: cruzar cualquier alternativo
sigue caliente, pero si el gateway cae los turnos siguen funcionando contra
Claude nativo (sin perdida de contexto ni reinicio manual). El unico costo
es que se "pierde" el routing por cuota / failover durante la caida, y al
volver el gateway re-servira a Claude via passthrough (modelo proxy-always
recuperado).

Uso:
    python .agent/scripts/start_monitor.py                # defaults
    python .agent/scripts/start_monitor.py --interval 5  # check cada 5s
    python .agent/scripts/start_monitor.py --dry-run     # solo loggear, no tocar settings
    python .agent/scripts/start_monitor.py --once        # chequear una vez y salir (test)

Race protection:
- Si ``$ANTIGRAVITY_PROXY/last_user_command.json`` tiene un stamp de hace <5s
  (un comando de usuario escribiendo settings.json), el monitor NO modifica
  settings.json. Asi un `switch_provider` que esta corriendo no se pisa.
- Lock file para single-instance (``monitor.lock``).

Estado:
- Persiste ``degraded.json`` con la ``base_url`` que se quito al degradar, para
  restaurarla al volver el gateway. Asi un restart del monitor sigue funcionando.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# Logging estructurado JSONL (consistente con el watchdog viejo).
logger = logging.getLogger("start_monitor")

PROXY_STATE_DIR = Path.home() / ".antigravity" / "proxy"
MONITOR_LOCK = PROXY_STATE_DIR / "monitor.lock"
DEGRADED_RECORD = PROXY_STATE_DIR / "degraded.json"
USER_COMMAND_STAMP = PROXY_STATE_DIR / "last_user_command.json"

# Ventana de proteccion contra race con comandos de usuario. Cualquier edicion
# a settings.json hecha por /provider, /cambiar, /cambio, o por el usuario a mano
# actualiza USER_COMMAND_STAMP; si fue hace < RACE_WINDOW_S, no pisar.
RACE_WINDOW_S = 5.0


# ---------------------------------------------------------------------------
# Helpers reusables
# ---------------------------------------------------------------------------


def _check_health(url: str, timeout: float = 2.0) -> bool:
    """Devuelve True si /v1/health responde 200 y status='healthy'.

    Args:
        url: Endpoint completo (p. ej. http://127.0.0.1:4747/v1/health).
        timeout: Timeout de la request.

    Returns:
        True si el gateway responde healthy; False en cualquier otro caso
        (connection refused, timeout, status != healthy, JSON corrupto).
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — endpoint fijo
            payload = json.loads(resp.read().decode("utf-8"))
            return isinstance(payload, dict) and payload.get("data", {}).get("status") == "healthy"
    except Exception:  # noqa: BLE001 — health check es best-effort
        return False


def _acquire_single_instance_lock() -> object | None:
    """Lock no-bloqueante: devuelve el handle si somos los unicos; None si ya hay uno.

    Returns:
        Objeto con .release() si adquirio el lock; None si ya existia.
    """
    try:
        MONITOR_LOCK.parent.mkdir(parents=True, exist_ok=True)
        # O_CREAT | O_EXCL | O_WRONLY es atomico cross-platform (Windows + Linux).
        fd = os.open(str(MONITOR_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
    except OSError:
        return None

    class _Lock:
        def release(self) -> None:
            try:
                MONITOR_LOCK.unlink()
            except OSError:
                pass

    return _Lock()


def _user_command_recent() -> bool:
    """True si el usuario escribio settings.json hace < RACE_WINDOW_S.

    El provider_switch escribe ``last_user_command.json`` antes de modificar
    settings.json; si lo hace <5s antes, no pisamos.
    """
    try:
        payload = json.loads(USER_COMMAND_STAMP.read_text(encoding="utf-8"))
        ts = float(payload.get("at", 0))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    return (time.time() - ts) < RACE_WINDOW_S


def _settings_paths() -> tuple[Path, dict]:
    """Lee el settings.json activo (override ANTIGRAVITY_CLAUDE_SETTINGS o default)."""
    override = os.environ.get("ANTIGRAVITY_CLAUDE_SETTINGS")
    path = Path(override) if override else (Path.home() / ".claude" / "settings.json")
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}


def _atomic_write_settings(path: Path, data: dict) -> None:
    """Escribe settings.json de forma atomica (tmp + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Logica principal
# ---------------------------------------------------------------------------


def _read_degraded() -> dict | None:
    """Devuelve el state degraded persistido (base_url guardada al degradar), o None."""
    try:
        raw = json.loads(DEGRADED_RECORD.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _write_degraded(record: dict) -> None:
    PROXY_STATE_DIR.mkdir(parents=True, exist_ok=True)
    DEGRADED_RECORD.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _clear_degraded() -> None:
    try:
        DEGRADED_RECORD.unlink()
    except OSError:
        pass


def _log_event(event: str, **fields: object) -> None:
    """Loguea un evento estructurado (JSONL en stdout)."""
    payload = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _perform_degradation(dry_run: bool) -> bool:
    """Quita ANTHROPIC_BASE_URL de settings.json y guarda el valor para restaurar.

    Returns:
        True si se degrado (estaba conectado), False si ya estaba degraded o no
        hacia falta actuar.
    """
    path, settings = _settings_paths()
    env = settings.get("env") or {}
    base_url = env.get("ANTHROPIC_BASE_URL")
    if not base_url:
        # Ya no esta conectado al proxy: nada que degradar.
        _clear_degraded()
        return False

    record = {
        "base_url": base_url,
        "degraded_at": datetime.now(UTC).isoformat(),
        "previous_active_provider": (
            json.loads((PROXY_STATE_DIR / "active_provider.json").read_text(encoding="utf-8")).get(
                "provider", "claude"
            )
            if (PROXY_STATE_DIR / "active_provider.json").exists()
            else "claude"
        ),
    }

    if dry_run:
        _log_event("degrade_skipped_dry_run", base_url=base_url, path=str(path))
        return False

    env.pop("ANTHROPIC_BASE_URL", None)
    settings["env"] = env
    _atomic_write_settings(path, settings)
    _write_degraded(record)
    _log_event(
        "degraded",
        base_url=base_url,
        path=str(path),
        previous_provider=record["previous_active_provider"],
    )
    return True


def _perform_restoration(dry_run: bool) -> bool:
    """Restaura ANTHROPIC_BASE_URL desde degraded.json si el gateway volvio.

    Returns:
        True si restauro, False si no habia que restaurar.
    """
    record = _read_degraded()
    if record is None:
        return False

    base_url = record.get("base_url", "")
    if not base_url:
        _clear_degraded()
        return False

    if dry_run:
        _log_event("restore_skipped_dry_run", base_url=base_url)
        return False

    path, settings = _settings_paths()
    env = settings.get("env") or {}
    env["ANTHROPIC_BASE_URL"] = base_url
    env.setdefault("API_TIMEOUT_MS", "3000000")
    env.setdefault("API_FORCE_IDLE_TIMEOUT", "0")
    settings["env"] = env
    _atomic_write_settings(path, settings)
    _log_event("restored", base_url=base_url, path=str(path))
    _clear_degraded()
    return True


def _tick(
    health_url: str,
    *,
    dry_run: bool,
    check_health_fn: callable | None = None,
) -> str:
    """Un tick del loop de monitoreo.

    Returns:
        Estado resultante: 'healthy' | 'degraded' | 'restored' | 'skipped_race'.
    """
    if _user_command_recent():
        return "skipped_race"

    health_ok = (check_health_fn or _check_health)(health_url)
    was_degraded = _read_degraded() is not None

    if health_ok:
        if was_degraded:
            _perform_restoration(dry_run)
            return "restored"
        return "healthy"

    if not was_degraded:
        _perform_degradation(dry_run)
        return "degraded"
    return "degraded"


def run_monitor(
    health_url: str,
    interval_s: float,
    *,
    dry_run: bool = False,
    once: bool = False,
    check_health_fn: callable | None = None,
) -> int:
    """Loop principal del sidecar monitor.

    Args:
        health_url: URL del endpoint de health del gateway.
        interval_s: Segundos entre checks.
        dry_run: Si True, loggea pero no modifica settings.json.
        once: Si True, hace UN check y sale (util para tests/smoke).
        check_health_fn: Override inyectable para tests.

    Returns:
        Codigo de salida (0 = OK, 2 = ya hay otra instancia, 1 = error fatal).
    """
    lock = _acquire_single_instance_lock()
    if lock is None:
        logger.warning("Ya hay otro monitor corriendo (lock: %s); saliendo.", MONITOR_LOCK)
        return 2

    _log_event(
        "monitor_started",
        health_url=health_url,
        interval_s=interval_s,
        dry_run=dry_run,
        once=once,
    )

    try:
        if once:
            state = _tick(health_url, dry_run=dry_run, check_health_fn=check_health_fn)
            _log_event("monitor_tick", state=state)
            return 0

        while True:
            try:
                state = _tick(
                    health_url,
                    dry_run=dry_run,
                    check_health_fn=check_health_fn,
                )
                _log_event("monitor_tick", state=state)
            except Exception as exc:  # noqa: BLE001 — el monitor NUNCA muere solo
                _log_event("monitor_tick_error", error=str(exc))
            time.sleep(interval_s)
    except KeyboardInterrupt:
        _log_event("monitor_interrupted")
        return 0
    finally:
        lock.release()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sidecar monitor del gateway :4747 (modo degraded automatico)."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:4747/v1/health",
        help="Endpoint de health (default: %(default)s).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Segundos entre checks (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo loggear, NO modificar settings.json.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Hacer UN check y salir (util para smoke / tests).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return run_monitor(
        args.url,
        args.interval,
        dry_run=args.dry_run,
        once=args.once,
    )


if __name__ == "__main__":
    sys.exit(main())
