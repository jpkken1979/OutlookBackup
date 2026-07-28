"""Build platform-specific, shell-independent portable runtime artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_PYINSTALLER_ERROR_TAIL = 12_000


def platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower().replace("amd64", "x86_64")
    return f"{system}-{machine}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_pyinstaller(
    *,
    repo_root: Path,
    output_root: Path,
    work_root: Path,
    name: str,
    entrypoint: Path,
    import_paths: list[Path],
    collect_submodules: tuple[str, ...] = (),
    collect_data: tuple[str, ...] = (),
    data_files: tuple[tuple[Path, str], ...] = (),
    exclude_modules: tuple[str, ...] = (),
) -> None:
    dist_root = work_root / "dist"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        name,
        "--distpath",
        str(dist_root),
        "--workpath",
        str(work_root / name),
        "--specpath",
        str(work_root / "specs"),
    ]
    for import_path in import_paths:
        command.extend(["--paths", str(import_path)])
    for package in collect_submodules:
        command.extend(["--collect-submodules", package])
    for package in collect_data:
        command.extend(["--collect-data", package])
    for package in exclude_modules:
        command.extend(["--exclude-module", package])
    for source, destination in data_files:
        command.extend(
            [
                "--add-data",
                f"{source}{os.pathsep}{destination}",
            ]
        )
    command.append(str(entrypoint))
    try:
        subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.CalledProcessError as exc:
        diagnostic = "\n".join(part for part in (exc.stdout, exc.stderr) if part).strip()
        if len(diagnostic) > _PYINSTALLER_ERROR_TAIL:
            diagnostic = diagnostic[-_PYINSTALLER_ERROR_TAIL:]
        raise RuntimeError(f"PyInstaller failed for {name}:\n{diagnostic}") from exc
    frozen_app = dist_root / name
    destination = output_root / name
    if destination.exists():
        raise FileExistsError(f"Portable output already exists: {destination}")
    shutil.copytree(frozen_app, destination)


def _prepare_gateway_source(repo_root: Path, work_root: Path) -> tuple[Path, Path]:
    """Stage the legacy gateway under a collision-free package name.

    Source mode historically calls the project package ``mcp``, the same name
    as the official SDK.  The runtime extends ``__path__`` and works in Python,
    but static freezer analysis cannot reliably merge those two packages.
    Renaming only the temporary build copy keeps source compatibility while the
    frozen gateway imports the official SDK as the unambiguous ``mcp`` package.
    """

    stage_root = work_root / "portable-source"
    gateway_package = stage_root / "antigravity_gateway"
    source_package = repo_root / ".agent" / "mcp"
    shutil.copytree(
        source_package,
        gateway_package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    source_core = repo_root / ".agent" / "core"
    if source_core.is_dir():
        shutil.copytree(
            source_core,
            stage_root / "core",
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                ".benchmarks",
            ),
        )
    daemon_worker = gateway_package / "daemon_worker.py"
    if daemon_worker.is_file():
        source = daemon_worker.read_text(encoding="utf-8")
        daemon_worker.write_text(
            source.replace(
                "from mcp.gateway_profiles import load_profile",
                "from antigravity_gateway.gateway_profiles import load_profile",
            ),
            encoding="utf-8",
        )
    entrypoint = stage_root / "antigravity_gateway_entrypoint.py"
    entrypoint.write_text(
        "\n".join(
            [
                '"""Frozen OpenAntigravity gateway entrypoint."""',
                "import os",
                'os.environ.setdefault("ANTIGRAVITY_PORTABLE_RUNTIME", "1")',
                "_portable_home = os.environ.get('ANTIGRAVITY_HOME')",
                "if _portable_home:",
                "    os.environ.setdefault('ANTIGRAVITY_ROOT', _portable_home)",
                "from core.portable_runtime import run_portable_script_cli",
                "_portable_exit_code = run_portable_script_cli()",
                "if _portable_exit_code is not None:",
                "    raise SystemExit(_portable_exit_code)",
                "from antigravity_gateway.gateway_main import main",
                "",
                'if __name__ == "__main__":',
                "    main()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return stage_root, entrypoint


def build_portable_runtime(
    repo_root: Path,
    output_root: Path,
    *,
    node_runtime: Path | None = None,
) -> dict[str, Any]:
    """Freeze broker, gateway and installer as isolated ``onedir`` apps."""

    repo_root = repo_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="antigravity-pyi-") as temporary:
        work_root = Path(temporary)
        staged_gateway_root, staged_gateway_entrypoint = _prepare_gateway_source(
            repo_root,
            work_root,
        )
        _run_pyinstaller(
            repo_root=repo_root,
            output_root=output_root,
            work_root=work_root,
            name="antigravity-mcp",
            entrypoint=repo_root / ".agent" / "mcp" / "antigravity_mcp.py",
            import_paths=[repo_root / ".agent"],
        )
        _run_pyinstaller(
            repo_root=repo_root,
            output_root=output_root,
            work_root=work_root,
            name="antigravity-gateway",
            entrypoint=staged_gateway_entrypoint,
            import_paths=[staged_gateway_root],
            collect_submodules=("mcp.server", "mcp.client", "mcp.shared"),
            collect_data=("mcp",),
            exclude_modules=(
                "chromadb",
                "cv2",
                "matplotlib",
                "mem0",
                "pandas",
                "PIL",
                "scipy",
                "sentence_transformers",
                "sklearn",
                "torch",
                "torchaudio",
                "torchvision",
                "transformers",
            ),
            data_files=(
                (
                    staged_gateway_root
                    / "antigravity_gateway"
                    / "broker"
                    / "connectors.json",
                    "antigravity_gateway/broker",
                ),
            ),
        )
        _run_pyinstaller(
            repo_root=repo_root,
            output_root=output_root,
            work_root=work_root,
            name="antigravity-installer",
            entrypoint=repo_root / ".agent" / "scripts" / "mcp_injector.py",
            import_paths=[repo_root / ".agent", repo_root / ".agent" / "scripts"],
        )

    if node_runtime is not None:
        node_runtime = node_runtime.resolve()
        if not node_runtime.is_dir():
            raise ValueError("node_runtime must be a directory")
        shutil.copytree(node_runtime, output_root / "node", dirs_exist_ok=True)

    files = {
        path.relative_to(output_root).as_posix(): _sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path.name != "runtime-manifest.json"
    }
    manifest = {
        "schema_version": 1,
        "platform": platform_tag(),
        "python": platform.python_version(),
        "build_mode": "pyinstaller-onedir",
        "node_included": node_runtime is not None,
        "files": files,
    }
    (output_root / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "platform": manifest["platform"],
        "file_count": len(files),
        "runtime_root": str(output_root),
        "node_included": manifest["node_included"],
    }
