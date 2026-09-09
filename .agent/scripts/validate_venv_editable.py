#!/usr/bin/env python3
"""Validate that the active venv has antigravity-agents installed in editable mode.

This prevents the recurring bug where tests run against stale bytecode instead of
the current source code. The validation checks:
  1. Is a venv active?
  2. Is antigravity-agents installed?
  3. Is it installed as editable (-e)?

If any check fails, prints a diagnostic message and exits with code 1.
Silently exits 0 if validation passes.

Usage:
  python .agent/scripts/validate_venv_editable.py
"""

import sys
import subprocess
import json
from importlib import metadata
from pathlib import Path


def check_venv_active() -> bool:
    """Check if a virtual environment is currently active."""
    return sys.prefix != sys.base_prefix


def get_site_packages() -> Path | None:
    """Get the site-packages directory from the active Python."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import site; [print(path) for path in site.getsitepackages()]",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        candidates = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        return next(
            (candidate for candidate in candidates if candidate.name == "site-packages"),
            candidates[-1] if candidates else None,
        )
    except (subprocess.CalledProcessError, IndexError):
        return None


def is_package_editable(package_name: str) -> bool:
    """Check if package is installed as editable by looking for .pth file or direct.txt."""
    for distribution in metadata.distributions(name=package_name):
        direct_url = distribution.read_text("direct_url.json")
        if direct_url:
            try:
                data = json.loads(direct_url)
            except json.JSONDecodeError:
                continue
            else:
                if data.get("dir_info", {}).get("editable", False):
                    return True

    site_packages = get_site_packages()
    if not site_packages:
        return False

    # Look for .pth file pointing to development directory
    for pth_file in site_packages.glob("*.pth"):
        with open(pth_file) as f:
            content = f.read()
            if "site-packages" not in content and (".." in content or "/" in content):
                return True

    # Fallback: check if installed in editable location with setup.py/pyproject.toml
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "-f", package_name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            output = result.stdout
            # If .pth entries point outside site-packages, it's editable
            if "pyproject.toml" in output or "setup.py" in output:
                return (
                    "Location:" in output
                    and "site-packages" not in output.split("Location:")[1].split("\n")[0]
                )
    except Exception:
        pass

    return False


def get_package_location(package_name: str) -> str | None:
    """Get the installation location of a package."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Location:"):
                    return line.split("Location:")[1].strip()
    except Exception:
        pass
    return None


def main() -> int:
    """Validate venv editable install status. Exit 0 if OK, 1 if invalid."""

    # Check 1: venv active
    if not check_venv_active():
        print(
            "ERROR: No virtual environment active.\n"
            "Activate with: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate (Unix)"
        )
        return 1

    # Check 2: package installed
    location = get_package_location("antigravity-agents")
    if not location:
        print(
            "ERROR: antigravity-agents not installed in active venv.\n"
            "Install with: pip install -e '.[dev,llm,observability]'"
        )
        return 1

    # Check 3: package is editable
    if not is_package_editable("antigravity-agents"):
        print(
            f"ERROR: antigravity-agents is NOT installed in editable mode.\n"
            f"Current location: {location}\n"
            f"This causes tests to run against stale bytecode instead of current source.\n"
            f"\n"
            f"Fix: Reinstall as editable:\n"
            f"  pip uninstall -y antigravity-agents\n"
            f"  pip install -e '.[dev,llm,observability]'\n"
        )
        return 1

    # All checks passed
    return 0


if __name__ == "__main__":
    sys.exit(main())
