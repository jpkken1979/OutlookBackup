"""Compatibility shim for gateway mixins.

This module preserves legacy imports used by gateway mixins:
`from .._gateway_main import ...`
"""

from . import gateway_main as _gateway_main

# Re-export every symbol, including private helpers (e.g. _make_response).
for _name, _value in _gateway_main.__dict__.items():
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = _value
