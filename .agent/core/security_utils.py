"""Compatibility re-export for shared MCP security helpers.

The canonical implementation lives in ``.agent/mcp/security_utils.py``.  Some
legacy core modules still import ``core.security_utils`` or run as direct
scripts from ``.agent/core``; this shim keeps those entry points working without
duplicating the SSRF/CORS logic.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_canonical_path = Path(__file__).resolve().parents[1] / "mcp" / "security_utils.py"
_spec = importlib.util.spec_from_file_location("_antigravity_mcp_security_utils", _canonical_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load canonical security helpers: {_canonical_path}")

_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_module, _name)

# Exports usados por módulos core. Se declaran explícitamente para que los
# analizadores estáticos vean la misma API que se reexporta dinámicamente.
validate_url_for_ssrf = _module.validate_url_for_ssrf
is_within_root = _module.is_within_root

__all__ = [name for name in globals() if not name.startswith("_")]
