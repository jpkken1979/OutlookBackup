#!/usr/bin/env python3
"""Audit vendored external skill snapshots against upstream sources.

Este flujo NO actualiza snapshots. Solo:
- compara snapshot local vs upstream
- genera reportes y diffs revisables
- deja la decisión de actualización para una revisión humana posterior
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("update_vendored_external_skills")

DEFAULT_TIMEOUT_SECONDS = 90
SKIP_NAMES = {".git", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class RepoSnapshot:
    name: str
    vendor_subpath: str
    upstream_repo_url: str
    upstream_page_url: str
    kind: str = "repo"


@dataclass(frozen=True)
class FileSnapshot:
    name: str
    vendor_subpath: str
    upstream_source_url: str
    upstream_page_url: str
    kind: str = "file"


SnapshotSpec = RepoSnapshot | FileSnapshot


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_vendor_root(repo_root: Path | None = None) -> Path:
    root = repo_root or get_repo_root()
    return (root / ".agent" / "vendor" / "external-skills").resolve()


def get_review_root(repo_root: Path | None = None) -> Path:
    root = repo_root or get_repo_root()
    return (root / ".antigravity" / "vendor-audits" / "external-skills").resolve()


def get_snapshot_specs() -> dict[str, SnapshotSpec]:
    return {
        "superpowers": RepoSnapshot(
            name="superpowers",
            vendor_subpath="superpowers",
            upstream_repo_url="https://github.com/obra/superpowers.git",
            upstream_page_url="https://github.com/obra/superpowers",
        ),
        "brainstorming-planning": FileSnapshot(
            name="brainstorming-planning",
            vendor_subpath="brainstorming-planning/SKILL.md",
            upstream_source_url=(
                "https://raw.githubusercontent.com/gakonst/dotfiles/"
                "49d5f5f80dafdd2e6e97998961fc51322c5aebd7/.codex/skills/brainstorm/SKILL.md"
            ),
            upstream_page_url="https://mcpmarket.com/es/tools/skills/brainstorming-planning",
        ),
        "oh-my-claudecode": RepoSnapshot(
            name="oh-my-claudecode",
            vendor_subpath="oh-my-claudecode",
            upstream_repo_url="https://github.com/Yeachan-Heo/oh-my-claudecode.git",
            upstream_page_url="https://github.com/Yeachan-Heo/oh-my-claudecode",
        ),
    }


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_directory_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_NAMES for part in path.parts):
            continue
        if path.is_file():
            hashes[str(path.relative_to(root)).replace("\\", "/")] = sha256_file(path)
    return hashes


def summarize_hash_differences(
    local_hashes: dict[str, str],
    upstream_hashes: dict[str, str],
) -> dict[str, Any]:
    local_paths = set(local_hashes)
    upstream_paths = set(upstream_hashes)
    added = sorted(upstream_paths - local_paths)
    removed = sorted(local_paths - upstream_paths)
    changed = sorted(
        path for path in local_paths & upstream_paths if local_hashes[path] != upstream_hashes[path]
    )
    unchanged = sorted(
        path for path in local_paths & upstream_paths if local_hashes[path] == upstream_hashes[path]
    )
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchangedCount": len(unchanged),
        "hasDiff": bool(added or removed or changed),
    }


def render_directory_stat(diff_summary: dict[str, Any]) -> str:
    return (
        f"added={len(diff_summary['added'])} "
        f"removed={len(diff_summary['removed'])} "
        f"changed={len(diff_summary['changed'])} "
        f"unchanged={diff_summary['unchangedCount']}"
    )


def create_git_no_index_diff(local_path: Path, upstream_path: Path) -> tuple[str, str]:
    git_path = shutil.which("git")
    if git_path is None:
        return ("git no disponible", "git no disponible para generar diff detallado")

    stat_result = _run(
        [
            git_path,
            "--no-pager",
            "diff",
            "--no-index",
            "--stat",
            "--",
            str(local_path),
            str(upstream_path),
        ]
    )
    patch_result = _run(
        [git_path, "--no-pager", "diff", "--no-index", "--", str(local_path), str(upstream_path)]
    )

    stat_output = (stat_result.stdout or stat_result.stderr).strip()
    patch_output = (patch_result.stdout or patch_result.stderr).strip()
    return (stat_output, patch_output)


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Antigravity-Vendor-Audit"})
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:  # noqa: S310
        return response.read().decode("utf-8")


def clone_repo_snapshot(repo_url: str, destination: Path) -> str:
    git_path = shutil.which("git")
    if git_path is None:
        raise RuntimeError("git no está disponible en PATH")

    clone_result = _run([git_path, "clone", "--depth", "1", repo_url, str(destination)])
    if clone_result.returncode != 0:
        raise RuntimeError(
            clone_result.stderr.strip() or clone_result.stdout.strip() or "git clone falló"
        )

    head_result = _run([git_path, "-C", str(destination), "rev-parse", "HEAD"])
    if head_result.returncode != 0:
        return "unknown"
    return (head_result.stdout or "unknown").strip()


def write_review_files(
    report_dir: Path,
    package_name: str,
    *,
    summary: dict[str, Any],
    stat_output: str,
    patch_output: str,
) -> dict[str, str]:
    package_dir = report_dir / package_name
    package_dir.mkdir(parents=True, exist_ok=True)

    summary_path = package_dir / "summary.json"
    stat_path = package_dir / "diff.stat.txt"
    patch_path = package_dir / "diff.patch"

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    stat_path.write_text(stat_output, encoding="utf-8")
    patch_path.write_text(patch_output, encoding="utf-8")

    return {
        "summary": str(summary_path),
        "stat": str(stat_path),
        "patch": str(patch_path),
    }


def audit_repo_snapshot(spec: RepoSnapshot, vendor_root: Path, report_dir: Path) -> dict[str, Any]:
    local_path = vendor_root / spec.vendor_subpath
    if not local_path.exists():
        raise RuntimeError(f"snapshot local no encontrado: {local_path}")

    with tempfile.TemporaryDirectory(prefix=f"antigravity-{spec.name}-") as temp_dir:
        upstream_path = Path(temp_dir) / spec.name
        upstream_commit = clone_repo_snapshot(spec.upstream_repo_url, upstream_path)
        local_hashes = collect_directory_hashes(local_path)
        upstream_hashes = collect_directory_hashes(upstream_path)
        diff_summary = summarize_hash_differences(local_hashes, upstream_hashes)
        stat_output, patch_output = create_git_no_index_diff(local_path, upstream_path)

    summary = {
        "package": spec.name,
        "kind": spec.kind,
        "source": spec.upstream_page_url,
        "upstreamRepo": spec.upstream_repo_url,
        "upstreamCommit": upstream_commit,
        "vendorPath": str(local_path),
        "diff": diff_summary,
        "statSummary": render_directory_stat(diff_summary),
        "reviewRequired": diff_summary["hasDiff"],
    }
    files = write_review_files(
        report_dir,
        spec.name,
        summary=summary,
        stat_output=stat_output or summary["statSummary"],
        patch_output=patch_output or "Sin cambios detectados.",
    )
    summary["reviewFiles"] = files
    return summary


def audit_file_snapshot(spec: FileSnapshot, vendor_root: Path, report_dir: Path) -> dict[str, Any]:
    local_path = vendor_root / spec.vendor_subpath
    if not local_path.exists():
        raise RuntimeError(f"snapshot local no encontrado: {local_path}")

    local_text = local_path.read_text(encoding="utf-8")
    upstream_text = fetch_text(spec.upstream_source_url)

    has_diff = local_text != upstream_text
    patch_output = "".join(
        difflib.unified_diff(
            local_text.splitlines(keepends=True),
            upstream_text.splitlines(keepends=True),
            fromfile=str(local_path),
            tofile=spec.upstream_source_url,
        )
    )
    stat_output = "changed=1 unchanged=0" if has_diff else "changed=0 unchanged=1"

    summary = {
        "package": spec.name,
        "kind": spec.kind,
        "source": spec.upstream_page_url,
        "upstreamSource": spec.upstream_source_url,
        "vendorPath": str(local_path),
        "diff": {
            "added": [],
            "removed": [],
            "changed": [local_path.name] if has_diff else [],
            "unchangedCount": 0 if has_diff else 1,
            "hasDiff": has_diff,
        },
        "statSummary": stat_output,
        "reviewRequired": has_diff,
    }
    files = write_review_files(
        report_dir,
        spec.name,
        summary=summary,
        stat_output=stat_output,
        patch_output=patch_output or "Sin cambios detectados.",
    )
    summary["reviewFiles"] = files
    return summary


def audit_vendor_snapshots(
    repo_root: Path | None = None,
    *,
    package_names: list[str] | None = None,
) -> dict[str, Any]:
    root = repo_root or get_repo_root()
    vendor_root = get_vendor_root(root)
    review_root = get_review_root(root)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir = review_root / timestamp
    report_dir.mkdir(parents=True, exist_ok=True)

    specs = get_snapshot_specs()
    selected_names = package_names or list(specs.keys())

    results: dict[str, Any] = {}
    failures: dict[str, str] = {}
    for name in selected_names:
        spec = specs.get(name)
        if spec is None:
            failures[name] = "paquete no soportado"
            continue
        try:
            if spec.kind == "repo":
                results[name] = audit_repo_snapshot(spec, vendor_root, report_dir)
            else:
                results[name] = audit_file_snapshot(spec, vendor_root, report_dir)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)

    has_diffs = any(result.get("reviewRequired") for result in results.values())
    summary = {
        "reportDir": str(report_dir),
        "packagesRequested": selected_names,
        "packagesAudited": list(results.keys()),
        "packagesFailed": failures,
        "hasDiffs": has_diffs,
        "reviewRequiredCount": sum(
            1 for result in results.values() if result.get("reviewRequired")
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
    }

    index_path = report_dir / "index.json"
    index_path.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "summary": summary,
        "results": results,
        "index": str(index_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit vendored external skills without updating snapshots"
    )
    parser.add_argument(
        "--package",
        action="append",
        dest="packages",
        help="Audit only a specific package (repeatable).",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    result = audit_vendor_snapshots(package_names=args.packages)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    logger.info("✅ [Vendor Audit] Auditoría completada")
    logger.info(f"   reportDir: {result['summary']['reportDir']}")
    logger.info(f"   index: {result['index']}")
    logger.info(f"   hasDiffs: {result['summary']['hasDiffs']}")
    if result["summary"]["packagesFailed"]:
        logger.warning(f"   failures: {result['summary']['packagesFailed']}")


if __name__ == "__main__":
    main()
