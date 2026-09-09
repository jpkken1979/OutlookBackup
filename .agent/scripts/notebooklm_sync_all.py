#!/usr/bin/env python3
"""Mass sync NotebookLM tooling and registry mappings across repos.

This script is designed to be called from a slash command (/notebooklmsyn)
and can run in two scopes:
- current repo only (default)
- root + first-level subrepos (--workspace)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPT = ROOT / ".agent" / "scripts" / "notebooklm_workflow.py"
BRIDGE_SCRIPT = ROOT / ".agent" / "scripts" / "notebooklm_bridge.py"


@dataclass
class RepoResult:
    """Result per repository.

    Attributes:
        repo: Repository directory name.
        path: Absolute repository path.
        inject_status: inject status string.
        associate_status: association status string.
        resync_status: resync status string.
        notebook_id: Associated notebook id if resolved.
        notebook_title: Associated notebook title if resolved.
        error: Error details when present.
    """

    repo: str
    path: str
    inject_status: str = "skipped"
    associate_status: str = "skipped"
    resync_status: str = "skipped"
    notebook_id: str = ""
    notebook_title: str = ""
    error: str = ""


def now_stamp() -> str:
    """Return UTC timestamp token for report filenames."""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run subprocess with UTF-8 text output.

    Args:
        cmd: Command as argv list.
        cwd: Working directory.

    Returns:
        Completed process object.
    """
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )


def discover_repos(workspace: bool) -> list[Path]:
    """Discover target repositories.

    Args:
        workspace: If True, include root + first-level children with .agent/.claude.

    Returns:
        List of repo paths.
    """
    if not workspace:
        return [ROOT]

    repos: list[Path] = [ROOT]
    for child in ROOT.iterdir():
        if not child.is_dir():
            continue
        has_agent = (child / ".agent").exists()
        has_claude = (child / ".claude").exists()
        if has_agent or has_claude:
            repos.append(child)
    return repos


def normalize(value: str) -> str:
    """Normalize text for fuzzy title matching."""
    lowered = value.lower().strip()
    return re.sub(r"[^a-z0-9]+", "", lowered)


def load_notebooks() -> list[dict[str, str]]:
    """Load notebook list from nlm CLI.

    Returns:
        List with keys id/title.

    Raises:
        RuntimeError: If notebooks cannot be listed.
    """
    proc = run_cmd(
        ["python", str(BRIDGE_SCRIPT), "nlm", "notebook", "list", "--json"],
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "nlm notebook list failed")

    payload = json.loads(proc.stdout)
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected notebook list format")

    notebooks: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        notebook_id = str(
            item.get("notebookId") or item.get("notebook_id") or item.get("id") or ""
        ).strip()
        title = str(item.get("title") or item.get("name") or "").strip()
        if notebook_id:
            notebooks.append({"id": notebook_id, "title": title})
    return notebooks


def match_notebook(repo_name: str, notebooks: list[dict[str, str]]) -> dict[str, str] | None:
    """Pick best notebook candidate for a repo by title similarity."""
    if not notebooks:
        return None

    repo_norm = normalize(repo_name)
    if not repo_norm:
        return None

    exact: list[dict[str, str]] = []
    contain: list[dict[str, str]] = []
    scored: list[tuple[int, dict[str, str]]] = []

    repo_tokens = {tok for tok in re.split(r"[^a-z0-9]+", repo_name.lower()) if tok}

    for nb in notebooks:
        title = nb.get("title", "")
        title_norm = normalize(title)
        if title_norm == repo_norm:
            exact.append(nb)
            continue
        if repo_norm in title_norm or title_norm in repo_norm:
            contain.append(nb)
            continue

        title_tokens = {tok for tok in re.split(r"[^a-z0-9]+", title.lower()) if tok}
        overlap = len(repo_tokens & title_tokens)
        if overlap > 0:
            scored.append((overlap, nb))

    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    if len(contain) == 1:
        return contain[0]
    if len(contain) > 1:
        return None
    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score = scored[0][0]
    best = [nb for score, nb in scored if score == best_score]
    if len(best) == 1:
        return best[0]
    return None


def existing_mapping(repo_path: Path) -> tuple[str, str]:
    """Read existing project mapping from local registry.

    Args:
        repo_path: Target repository path.

    Returns:
        Tuple (notebook_id, title). Empty strings when not mapped.
    """
    registry = repo_path / ".agent" / "notebooklm" / "projects.json"
    if not registry.exists():
        return "", ""

    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return "", ""

    if not isinstance(data, dict):
        return "", ""

    projects = data.get("projects", {})
    if not isinstance(projects, dict):
        return "", ""

    entry = projects.get(repo_path.name)
    if not isinstance(entry, dict):
        return "", ""

    notebook_id = str(entry.get("notebook_id") or "").strip()
    title = str(entry.get("title") or "").strip()
    return notebook_id, title


def inject_repo(repo_path: Path) -> tuple[bool, str]:
    """Run NotebookLM inject for target repo."""
    proc = run_cmd(
        ["python", str(WORKFLOW_SCRIPT), "inject", "--target", str(repo_path), "--json"],
        cwd=ROOT,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip() or "inject failed"
    return True, "ok"


def associate_repo(repo_path: Path, notebook: dict[str, str]) -> tuple[bool, str]:
    """Set project mapping in target repo registry."""
    workflow = repo_path / ".agent" / "scripts" / "notebooklm_workflow.py"
    if not workflow.exists():
        return False, "workflow script missing"

    repo_name = repo_path.name
    notebook_id = notebook["id"]
    title = notebook.get("title", repo_name) or repo_name
    proc = run_cmd(
        [
            "python",
            str(workflow),
            "project",
            "set",
            repo_name,
            notebook_id,
            "--title",
            title,
        ],
        cwd=repo_path,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip() or "project set failed"
    return True, "ok"


def resync_repo(repo_path: Path) -> tuple[bool, str]:
    """Run resync in target repo."""
    workflow = repo_path / ".agent" / "scripts" / "notebooklm_workflow.py"
    if not workflow.exists():
        return False, "workflow script missing"

    proc = run_cmd(["python", str(workflow), "resync"], cwd=repo_path)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip() or "resync failed"
    return True, "ok"


def write_reports(results: list[RepoResult]) -> tuple[Path, Path]:
    """Write JSON and CSV reports to root."""
    stamp = now_stamp()
    json_path = ROOT / f"notebooklmsyn_report_{stamp}.json"
    csv_path = ROOT / f"notebooklmsyn_report_{stamp}.csv"

    json_payload = [result.__dict__ for result in results]
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "repo",
                "path",
                "inject_status",
                "associate_status",
                "resync_status",
                "notebook_id",
                "notebook_title",
                "error",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(result.__dict__)

    return json_path, csv_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="NotebookLM sync helper across repos")
    parser.add_argument(
        "--workspace",
        action="store_true",
        help="Process root + first-level subrepos with .agent/.claude",
    )
    parser.add_argument(
        "--no-inject",
        action="store_true",
        help="Skip workflow/command injection step",
    )
    parser.add_argument(
        "--associate",
        action="store_true",
        help="Auto-map project -> notebook_id using notebook title matching",
    )
    parser.add_argument(
        "--resync",
        action="store_true",
        help="Run notebooklm_workflow.py resync in each repo",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print summary as JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    repos = discover_repos(workspace=args.workspace)

    notebooks: list[dict[str, str]] = []
    notebook_error = ""
    if args.associate:
        try:
            notebooks = load_notebooks()
        except Exception as exc:  # noqa: BLE001
            notebook_error = str(exc)

    results: list[RepoResult] = []

    for repo in repos:
        result = RepoResult(repo=repo.name, path=str(repo))

        if not args.no_inject:
            ok, msg = inject_repo(repo)
            result.inject_status = "ok" if ok else "error"
            if not ok:
                result.error = msg

        if args.associate:
            if notebook_error:
                result.associate_status = "error"
                result.error = (result.error + " | " if result.error else "") + notebook_error
            else:
                match = match_notebook(repo.name, notebooks)
                if match is None:
                    existing_id, existing_title = existing_mapping(repo)
                    if existing_id:
                        result.associate_status = "already_mapped"
                        result.notebook_id = existing_id
                        result.notebook_title = existing_title
                    else:
                        result.associate_status = "no_match"
                else:
                    ok, msg = associate_repo(repo, match)
                    result.associate_status = "ok" if ok else "error"
                    result.notebook_id = match.get("id", "")
                    result.notebook_title = match.get("title", "")
                    if not ok:
                        result.error = (result.error + " | " if result.error else "") + msg

        if args.resync:
            ok, msg = resync_repo(repo)
            result.resync_status = "ok" if ok else "error"
            if not ok:
                result.error = (result.error + " | " if result.error else "") + msg

        results.append(result)

    json_path, csv_path = write_reports(results)

    summary = {
        "total": len(results),
        "inject_ok": sum(1 for row in results if row.inject_status == "ok"),
        "associate_ok": sum(
            1 for row in results if row.associate_status in {"ok", "already_mapped"}
        ),
        "resync_ok": sum(1 for row in results if row.resync_status == "ok"),
        "errors": sum(
            1
            for row in results
            if row.inject_status == "error"
            or row.associate_status == "error"
            or row.resync_status == "error"
        ),
        "report_json": str(json_path),
        "report_csv": str(csv_path),
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("NotebookLMSyn summary")
        print(f"- total repos: {summary['total']}")
        print(f"- inject ok: {summary['inject_ok']}")
        print(f"- associate ok: {summary['associate_ok']}")
        print(f"- resync ok: {summary['resync_ok']}")
        print(f"- errors: {summary['errors']}")
        print(f"- report json: {summary['report_json']}")
        print(f"- report csv: {summary['report_csv']}")

    return 1 if summary["errors"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
