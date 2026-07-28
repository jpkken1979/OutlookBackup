"""Transactional CLI for portable bundle v2 operations.

The historical injector remains available while clients migrate. This module
is intentionally small so Nexus and future shells (Tauri, Electron or CLI) call
the same source of truth.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Sequence

from .bundle_v2 import (
    analyze_source_install,
    build_tar_zst,
    install_from_archive,
    install_from_source,
    repair_from_source,
    rollback,
)
from .portable_build import build_portable_runtime

BUNDLE_COMMANDS = frozenset({"analyze", "install", "repair", "update", "rollback", "build"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp_injector.py")
    parser.add_argument(
        "--root",
        help="OpenAntigravity source root. Defaults to this injector's repository.",
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    for operation in ("analyze", "install", "repair", "update", "rollback"):
        command = subparsers.add_parser(operation)
        command.add_argument("target", type=Path)
        if operation in {"install", "update"}:
            command.add_argument(
                "--client",
                action="append",
                default=[],
                help="Configured client name; repeat for multiple clients.",
            )
            command.add_argument("--bundle", type=Path)
            command.add_argument("--signature", type=Path)
            command.add_argument("--trusted-public-key")

    build = subparsers.add_parser("build")
    build.add_argument("output", type=Path)
    build.add_argument("--node-runtime", type=Path)
    build.add_argument(
        "--source-only",
        action="store_true",
        help="Skip executable freezing; intended only for development.",
    )
    return parser


def is_bundle_command(argv: Sequence[str]) -> bool:
    if not argv:
        return False
    if argv[0] in BUNDLE_COMMANDS:
        return True
    # Global argparse options may precede the subcommand, as used by Nexus.
    if len(argv) >= 3 and argv[0] == "--root":
        return argv[2] in BUNDLE_COMMANDS
    return False


def run(argv: Sequence[str], *, default_repo_root: Path) -> int:
    args = _parser().parse_args(list(argv))
    repo_root = Path(args.root).resolve() if args.root else default_repo_root.resolve()

    if args.operation == "analyze":
        result = analyze_source_install(repo_root, args.target.resolve())
    elif args.operation in {"install", "update"}:
        if args.bundle:
            if not args.signature:
                raise SystemExit("--signature is required with --bundle")
            result = install_from_archive(
                args.bundle,
                args.signature,
                args.target.resolve(),
                trusted_public_key_b64=args.trusted_public_key,
                clients=args.client,
            )
        else:
            result = install_from_source(
                repo_root,
                args.target.resolve(),
                clients=args.client,
            )
    elif args.operation == "repair":
        result = repair_from_source(repo_root, args.target.resolve())
    elif args.operation == "rollback":
        result = rollback(args.target.resolve())
    else:
        if args.source_only:
            result = build_tar_zst(repo_root, args.output.resolve())
        else:
            with tempfile.TemporaryDirectory(prefix="antigravity-runtime-") as temporary:
                runtime_root = Path(temporary) / "runtime"
                runtime = build_portable_runtime(
                    repo_root,
                    runtime_root,
                    node_runtime=args.node_runtime,
                )
                result = {
                    **build_tar_zst(
                        repo_root,
                        args.output.resolve(),
                        runtime_root=runtime_root,
                    ),
                    "runtime": runtime,
                }

    print(json.dumps({"success": True, "operation": args.operation, **result}, ensure_ascii=True))
    return 0
