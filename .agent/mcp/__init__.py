"""Antigravity gateway source package and installed private namespace.

The historical gateway lives in ``.agent/mcp`` and therefore shares the
top-level package name used by the official Python SDK. Source launchers still
load this tree as ``mcp`` for compatibility, while setuptools maps the same
files to ``antigravity_mcp`` when installed. Extending the source package path
keeps legacy imports working without publishing files into the SDK namespace.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
