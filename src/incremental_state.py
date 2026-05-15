"""State persistente para backup incremental (Feature A plan v3.2).

Por que existe este modulo
--------------------------
Backup incremental ahorra ~95% del tiempo en backups subsecuentes (segun audit
de competidores en docs/COMPETITOR_AUDIT.md). Para implementarlo necesitamos
recordar cuando fue el ultimo backup exitoso por cuenta SMTP.

Este modulo persiste un dict `{smtp: ISO timestamp}` en el config dir del usuario.
Atomico: cada update reescribe el JSON completo (file pequeno, sin race conditions
porque solo el proceso UNS-Outlook-Backup lo escribe).

Estructura del archivo
----------------------
`{config_dir}/incremental_state.json`:
```
{
  "version": 1,
  "last_backup_by_smtp": {
    "kenji@uns-kikaku.com": "2026-05-13T14:23:12",
    "info@uns-kikaku.com": "2026-05-13T14:23:12"
  }
}
```

API publica
-----------
- `IncrementalState.load()` — class method, lee o crea state vacio
- `state.get_last_backup(smtp)` — datetime.datetime | None
- `state.update_last_backup(smtp, ts)` — autosave a disco
- `state.clear(smtp)` — borra una cuenta (forzar full backup)
- `state.clear_all()` — reset completo
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

STATE_VERSION = 1
STATE_FILENAME = "incremental_state.json"


class IncrementalState:
    """Estado persistente del ultimo backup por cuenta SMTP.

    Use `IncrementalState.load(path)` para crear una instancia desde el config dir,
    o `IncrementalState(path)` para path arbitrario (util en tests).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, str] = {}

    @classmethod
    def load(cls, config_dir: Path | None = None) -> IncrementalState:
        """Carga el state desde el config dir del proyecto.

        Args:
            config_dir: Override opcional del config dir (util en tests). Si None,
                usa `config.get_config_dir()`.

        Returns:
            IncrementalState con datos cargados (o vacio si el archivo no existe).
        """
        if config_dir is None:
            from config import get_config_dir

            config_dir = get_config_dir()

        instance = cls(config_dir / STATE_FILENAME)
        instance._read_from_disk()
        return instance

    def _read_from_disk(self) -> None:
        """Lee el archivo JSON. Vacio si no existe o esta corrupto."""
        if not self.path.is_file():
            return

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("State corrupto o ilegible (%s); reset a vacio", e)
            return

        version = raw.get("version", 0)
        if version != STATE_VERSION:
            log.warning(
                "State version %d distinta de %d; reset (no hay migration todavia)",
                version,
                STATE_VERSION,
            )
            return

        last = raw.get("last_backup_by_smtp", {})
        if not isinstance(last, dict):
            log.warning("State formato inesperado; reset")
            return

        self._data = {str(k): str(v) for k, v in last.items()}

    def _write_to_disk(self) -> None:
        """Reescribe el archivo JSON completo (atomic via tempfile + rename)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STATE_VERSION,
            "last_backup_by_smtp": dict(self._data),
        }
        # Atomic write: tmp file + rename
        tmp_path = self.path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(self.path)
        except OSError as e:
            log.error("No se pudo escribir state a disco: %s", e)

    def get_last_backup(self, smtp: str) -> datetime.datetime | None:
        """Devuelve el timestamp del ultimo backup exitoso para esta cuenta.

        Args:
            smtp: SMTP address de la cuenta.

        Returns:
            datetime del ultimo backup, o None si esta cuenta nunca tuvo backup
            exitoso (debe hacerse full).
        """
        iso = self._data.get(smtp)
        if not iso:
            return None
        try:
            return datetime.datetime.fromisoformat(iso)
        except ValueError:
            log.warning("Timestamp corrupto para %s: %r; trato como None", smtp, iso)
            return None

    def update_last_backup(self, smtp: str, ts: datetime.datetime | None = None) -> None:
        """Marca esta cuenta como recien backupeada exitosamente.

        Args:
            smtp: SMTP address de la cuenta.
            ts: Timestamp del backup. Si None, usa now().
        """
        if ts is None:
            ts = datetime.datetime.now()
        self._data[smtp] = ts.isoformat(timespec="seconds")
        self._write_to_disk()

    def clear(self, smtp: str) -> None:
        """Borra una cuenta del state (forzar full backup en proximo run)."""
        if smtp in self._data:
            del self._data[smtp]
            self._write_to_disk()

    def clear_all(self) -> None:
        """Reset completo del state."""
        self._data = {}
        self._write_to_disk()

    def all_tracked_smtps(self) -> list[str]:
        """Devuelve lista de SMTPs trackeadas (para debugging/UI)."""
        return sorted(self._data.keys())
