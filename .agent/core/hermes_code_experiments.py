"""Isolated code experiments for review-only Hermes learning proposals."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hermes_learning import (
    HermesLearningEngine,
    learning_text_contains_secret,
    redact_learning_text,
)


_PROPOSAL_ID = re.compile(r"hlp_[0-9]{14}_[a-f0-9]{6}")
_BLOCKED_PATH_PARTS = {
    ".env",
    "credentials",
    "secrets",
    "auth.json",
    "id_rsa",
    "id_ed25519",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    pending.replace(path)


def _git_executable() -> str:
    discovered = shutil.which("git")
    if discovered:
        return discovered
    for candidate in (
        Path("C:/Program Files/Git/cmd/git.exe"),
        Path("C:/Program Files/Git/bin/git.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("Git is required for Hermes code experiments")


class HermesCodeExperimentManager:
    """Prepare and evaluate patches in detached worktrees only."""

    def __init__(
        self,
        engine: HermesLearningEngine,
        repo_root: Path,
        *,
        git_executable: str | None = None,
        gate_commands: Sequence[Sequence[str]] | None = None,
        timeout_seconds: int = 900,
    ) -> None:
        self.engine = engine
        self.repo_root = Path(repo_root).resolve()
        self.git = git_executable or _git_executable()
        self.timeout_seconds = max(30, min(int(timeout_seconds), 3600))
        self.root = (engine.state_dir / "experiments").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        python = str(Path(sys.executable).resolve())
        self.gate_commands = [list(command) for command in (gate_commands or ())]
        if not self.gate_commands:
            self.gate_commands = [
                [python, "-m", "ruff", "check", ".agent", "mcp-server"],
                [python, "-m", "mypy", ".agent/core"],
            ]
        self._git("rev-parse", "--show-toplevel", cwd=self.repo_root)

    def _git(
        self, *args: str, cwd: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [self.git, *args],
            cwd=str(cwd or self.repo_root),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout_seconds,
        )
        if check and completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[-1000:]
            raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
        return completed

    def _paths(self, proposal_id: str) -> tuple[Path, Path, Path]:
        if not _PROPOSAL_ID.fullmatch(proposal_id):
            raise ValueError("Invalid Hermes proposal ID")
        experiment = (self.root / proposal_id).resolve()
        if experiment.parent != self.root:
            raise ValueError("Experiment escaped the learning state directory")
        return experiment, experiment / "worktree", experiment / "manifest.json"

    def _proposal(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.engine.get_proposal(proposal_id)
        if proposal["kind"] != "code" or proposal["risk"] != "high":
            raise ValueError("Only high-risk review-only code proposals can create experiments")
        return proposal

    def _run_gates(self, worktree: Path) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for command in self.gate_commands:
            started = time.monotonic()
            try:
                completed = subprocess.run(
                    list(command),
                    cwd=str(worktree),
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    env={**os.environ, "PYTHONUTF8": "1"},
                )
                output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
                results.append(
                    {
                        "command": list(command),
                        "returncode": completed.returncode,
                        "passed": completed.returncode == 0,
                        "duration_ms": round((time.monotonic() - started) * 1000, 1),
                        "output_tail": redact_learning_text(output[-2000:]),
                    }
                )
            except subprocess.TimeoutExpired:
                results.append(
                    {
                        "command": list(command),
                        "returncode": 124,
                        "passed": False,
                        "duration_ms": round((time.monotonic() - started) * 1000, 1),
                        "output_tail": "Gate timed out",
                    }
                )
        return results

    def stage(self, proposal_id: str) -> dict[str, Any]:
        """Create a detached worktree and capture baseline gates."""

        proposal = self._proposal(proposal_id)
        experiment, worktree, manifest_path = self._paths(proposal_id)
        if manifest_path.is_file():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        experiment.mkdir(parents=True, exist_ok=True)
        if worktree.exists():
            raise RuntimeError(f"Unmanaged experiment path already exists: {worktree}")
        base_commit = self._git("rev-parse", "HEAD", cwd=self.repo_root).stdout.strip()
        self._git("worktree", "add", "--detach", str(worktree), base_commit, cwd=self.repo_root)
        baseline = self._run_gates(worktree)
        manifest = {
            "proposal_id": proposal_id,
            "status": "staged",
            "repo_root": str(self.repo_root),
            "worktree": str(worktree),
            "base_commit": base_commit,
            "proposal_hash": proposal["content_hash"],
            "baseline_gates": baseline,
            "candidate_gates": [],
            "changed_paths": [],
            "patch": None,
            "patch_sha256": None,
            "created_at": _now(),
            "evaluated_at": None,
            "archived_at": None,
        }
        _atomic_json(manifest_path, manifest)
        return manifest

    def _changed_paths(self, worktree: Path) -> list[str]:
        tracked = self._git(
            "diff", "--name-only", "--no-renames", "-z", "HEAD", cwd=worktree
        ).stdout
        untracked = self._git(
            "ls-files", "--others", "--exclude-standard", "-z", cwd=worktree
        ).stdout
        return sorted(
            {Path(raw).as_posix() for raw in (*tracked.split("\0"), *untracked.split("\0")) if raw}
        )

    def _validate_changed_paths(self, worktree: Path, changed_paths: list[str]) -> None:
        for relative in changed_paths:
            path = (worktree / relative).resolve()
            try:
                path.relative_to(worktree)
            except ValueError as exc:
                raise ValueError(f"Changed path escaped the experiment: {relative}") from exc
            lowered = {part.casefold() for part in Path(relative).parts}
            if lowered & _BLOCKED_PATH_PARTS:
                raise ValueError(f"Sensitive path cannot enter a learning patch: {relative}")
            if path.exists() and path.is_symlink():
                raise ValueError(f"Symlink cannot enter a learning patch: {relative}")

    def _capture_patch(
        self, proposal_id: str, worktree: Path, changed_paths: list[str]
    ) -> tuple[Path, str]:
        untracked = [
            path
            for path in changed_paths
            if self._git(
                "ls-files", "--error-unmatch", "--", path, cwd=worktree, check=False
            ).returncode
            != 0
        ]
        if untracked:
            self._git("add", "--intent-to-add", "--", *untracked, cwd=worktree)
        patch_bytes = subprocess.run(
            [self.git, "diff", "--binary", "--no-ext-diff", "--"],
            cwd=str(worktree),
            check=True,
            capture_output=True,
            timeout=self.timeout_seconds,
        ).stdout
        if not patch_bytes:
            raise RuntimeError("Experiment has no patch content")
        patch_text = patch_bytes.decode("utf-8", errors="replace")
        if learning_text_contains_secret(patch_text):
            raise ValueError("Credential-shaped data cannot enter a learning patch")
        experiment, _, _ = self._paths(proposal_id)
        patch_path = experiment / f"{proposal_id}.patch"
        pending = patch_path.with_suffix(".patch.pending")
        pending.write_bytes(patch_bytes)
        pending.replace(patch_path)
        return patch_path, hashlib.sha256(patch_bytes).hexdigest()

    def evaluate(self, proposal_id: str) -> dict[str, Any]:
        """Generate a patch and compare candidate gates without applying it."""

        self._proposal(proposal_id)
        _, worktree, manifest_path = self._paths(proposal_id)
        if not manifest_path.is_file() or not worktree.is_dir():
            raise RuntimeError("Stage the code experiment before evaluation")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed_paths = self._changed_paths(worktree)
        if not changed_paths:
            raise RuntimeError("The isolated worktree has no changes to evaluate")
        self._validate_changed_paths(worktree, changed_paths)
        diff_check = self._git("diff", "--check", cwd=worktree, check=False)
        candidate = self._run_gates(worktree)
        patch_path, patch_hash = self._capture_patch(proposal_id, worktree, changed_paths)
        baseline_passed = all(item["passed"] for item in manifest["baseline_gates"])
        candidate_passed = diff_check.returncode == 0 and all(item["passed"] for item in candidate)
        manifest.update(
            {
                "status": "evaluated" if candidate_passed else "failed",
                "changed_paths": changed_paths,
                "candidate_gates": candidate,
                "baseline_passed": baseline_passed,
                "candidate_passed": candidate_passed,
                "diff_check_passed": diff_check.returncode == 0,
                "diff_check_output": redact_learning_text(
                    (diff_check.stdout + diff_check.stderr)[-2000:]
                ),
                "patch": str(patch_path),
                "patch_sha256": patch_hash,
                "evaluated_at": _now(),
            }
        )
        _atomic_json(manifest_path, manifest)
        return manifest

    def archive(self, proposal_id: str) -> dict[str, Any]:
        """Preserve a patch, then remove only the exact detached worktree."""

        self._proposal(proposal_id)
        _, worktree, manifest_path = self._paths(proposal_id)
        if not manifest_path.is_file():
            raise RuntimeError("Unknown code experiment")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if worktree.is_dir():
            changed_paths = self._changed_paths(worktree)
            if changed_paths and not manifest.get("patch"):
                self._validate_changed_paths(worktree, changed_paths)
                patch_path, patch_hash = self._capture_patch(proposal_id, worktree, changed_paths)
                manifest["patch"] = str(patch_path)
                manifest["patch_sha256"] = patch_hash
                manifest["changed_paths"] = changed_paths
            registered = self._registered_worktrees()
            if worktree.resolve() not in registered:
                raise RuntimeError(
                    f"Refusing to remove an unregistered experiment path: {worktree}"
                )
            self._git("worktree", "remove", "--force", str(worktree), cwd=self.repo_root)
        manifest["status"] = "archived"
        manifest["archived_at"] = _now()
        _atomic_json(manifest_path, manifest)
        return manifest

    def _registered_worktrees(self) -> set[Path]:
        output = self._git("worktree", "list", "--porcelain", cwd=self.repo_root).stdout
        registered: set[Path] = set()
        for line in output.splitlines():
            if line.startswith("worktree "):
                registered.add(Path(line[len("worktree ") :]).resolve())
        return registered

    def list(self) -> list[dict[str, Any]]:
        manifests: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*/manifest.json"), reverse=True):
            try:
                manifests.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return manifests


__all__ = ["HermesCodeExperimentManager"]
