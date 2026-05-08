"""
UNS Backup v2.0 - Configuración persistente
============================================
Guarda settings del usuario en %APPDATA%/UNS-Kikaku/Backup/config.json
"""

import os
import json
from pathlib import Path
from typing import Any, Dict


def get_config_dir() -> Path:
    """Directorio donde guardamos config y logs."""
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA', os.path.expanduser('~')))
    else:
        base = Path(os.path.expanduser('~/.config'))
    cfg_dir = base / "UNS-Kikaku" / "Backup"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def get_default_backup_dir() -> str:
    """Carpeta por defecto para backups."""
    docs = Path(os.path.expanduser('~')) / "Documents" / "UNS_Backup"
    return str(docs)


DEFAULT_CONFIG = {
    "version": "2.0.0",
    "domain_filter": "uns-kikaku.com",
    "backup_all_accounts": False,  # Si True ignora el filtro de dominio
    "default_backup_dir": get_default_backup_dir(),
    "default_format": "pst",       # 'pst' | 'msg'
    "default_import_mode": "separate_folder",  # 'separate_folder' | 'merge' | 'new_files'

    # Schedule
    "schedule_enabled": False,
    "schedule_frequency": "weekly",   # 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'custom'
    "schedule_day_of_week": "MON",    # MON, TUE, ...
    "schedule_time": "02:00",         # HH:MM 24h
    "schedule_custom_days": 7,
    "schedule_save_to": "",           # carpeta destino del backup automático
    "schedule_scope": "uns_only",     # 'uns_only' | 'all' | 'custom'
    "schedule_custom_accounts": [],   # lista de SMTP si scope='custom'
    "schedule_keep_last": 4,          # mantener últimos N backups (0 = todos)

    # Account inventory (v2.1)
    "export_account_inventory": False,    # exportar JSON con inventario
    "inventory_include_servers": True,    # incluir settings de servidor
    "inventory_include_passwords": False, # incluir passwords (encriptado)

    # Última ejecución
    "last_run_time": None,
    "last_run_status": None,
}


class Config:
    """Manejador de configuración persistente."""

    def __init__(self):
        self.path = get_config_dir() / "config.json"
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge con defaults (para añadir keys nuevos en updates)
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(loaded)
                    return cfg
            except Exception as e:
                print(f"Error leyendo config: {e}, usando defaults")
        return DEFAULT_CONFIG.copy()

    def save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando config: {e}")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value

    def update(self, **kwargs):
        self.data.update(kwargs)
