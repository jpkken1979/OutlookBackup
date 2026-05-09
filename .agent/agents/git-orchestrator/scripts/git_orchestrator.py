#!/usr/bin/env python3
"""
Git Orchestrator Agent - Orquestacion completa de operaciones Git

Coordina commits, PRs, releases, y mantiene el flujo de versionado automatico.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class CommitType(Enum):
    """Tipos de commit segun Conventional Commits."""

    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    PERF = "perf"
    TEST = "test"
    BUILD = "build"
    CI = "ci"
    CHORE = "chore"
    REVERT = "revert"


@dataclass
class FileChange:
    """Representa un cambio en un archivo."""

    path: str
    status: str  # M, A, D, R, etc.
    additions: int = 0
    deletions: int = 0


@dataclass
class CommitPlan:
    """Plan para un commit."""

    files: list[FileChange]
    commit_type: CommitType
    scope: str | None
    description: str
    body: str | None = None
    breaking: bool = False


@dataclass
class GitOrchestratorResult:
    """Resultado de operacion del orquestador."""

    success: bool
    operation: str
    message: str
    details: dict = field(default_factory=dict)


class GitOrchestrator:
    """Orquestador de operaciones Git."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Carga configuracion del orquestador."""
        self.repo_path / ".agent" / "config" / "git_orchestrator.yaml"
        default_config = {
            "commit_style": "conventional",
            "branch_strategy": "github-flow",
            "auto_changelog": True,
            "protected_branches": ["main", "master", "production"],
            "pr_template": ".github/PULL_REQUEST_TEMPLATE.md",
        }
        # En produccion: cargar desde archivo YAML
        return default_config

    def _run_git(self, *args: str) -> tuple[bool, str]:
        """Ejecuta comando git."""
        try:
            result = subprocess.run(
                ["git", *args], cwd=self.repo_path, capture_output=True, text=True
            )
            return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def get_status(self) -> list[FileChange]:
        """Obtiene estado actual del repositorio."""
        success, output = self._run_git("status", "--porcelain")
        if not success:
            return []

        changes = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            status = line[:2].strip()
            path = line[3:].strip()
            changes.append(FileChange(path=path, status=status))

        return changes

    def analyze_changes(self, changes: list[FileChange]) -> CommitType:
        """Analiza cambios y sugiere tipo de commit."""
        paths = [c.path for c in changes]

        # Analizar patrones en paths
        if any("test" in p.lower() for p in paths):
            return CommitType.TEST
        if any(p.endswith(".md") for p in paths):
            return CommitType.DOCS
        if any("config" in p.lower() or ".yaml" in p or ".json" in p for p in paths):
            return CommitType.CHORE
        if any(".github" in p or "ci" in p.lower() for p in paths):
            return CommitType.CI

        # Default: inferir del diff
        return CommitType.FEAT

    def detect_scope(self, changes: list[FileChange]) -> str | None:
        """Detecta scope del commit basado en archivos."""
        paths = [c.path for c in changes]

        # Buscar directorio comun
        if len(paths) == 1:
            parts = paths[0].split("/")
            if len(parts) > 1:
                return parts[0]

        # Buscar patron comun
        common_parts = set(paths[0].split("/"))
        for path in paths[1:]:
            common_parts &= set(path.split("/"))

        if common_parts:
            return list(common_parts)[0]

        return None

    def generate_commit_message(
        self,
        commit_type: CommitType,
        description: str,
        scope: str | None = None,
        body: str | None = None,
        breaking: bool = False,
    ) -> str:
        """Genera mensaje de commit siguiendo Conventional Commits."""
        # Header
        header = commit_type.value
        if scope:
            header += f"({scope})"
        if breaking:
            header += "!"
        header += f": {description}"

        message = header

        if body:
            message += f"\n\n{body}"

        if breaking:
            message += "\n\nBREAKING CHANGE: " + description

        return message

    def create_commit(
        self, files: list[str], message: str, amend: bool = False
    ) -> GitOrchestratorResult:
        """Crea un commit con los archivos especificados."""
        # Stage files
        for f in files:
            success, _ = self._run_git("add", f)
            if not success:
                return GitOrchestratorResult(
                    success=False, operation="commit", message=f"Failed to stage {f}"
                )

        # Commit
        cmd = ["commit", "-m", message]
        if amend:
            cmd.append("--amend")

        success, output = self._run_git(*cmd)

        return GitOrchestratorResult(
            success=success,
            operation="commit",
            message=output,
            details={"files": files, "message": message},
        )

    def auto_commit(self, description: str | None = None) -> GitOrchestratorResult:
        """Commit automatico con mensaje generado."""
        changes = self.get_status()
        if not changes:
            return GitOrchestratorResult(
                success=False, operation="auto_commit", message="No changes to commit"
            )

        commit_type = self.analyze_changes(changes)
        scope = self.detect_scope(changes)

        if not description:
            # Generar descripcion basada en cambios
            if len(changes) == 1:
                description = f"update {changes[0].path}"
            else:
                description = f"update {len(changes)} files"

        message = self.generate_commit_message(
            commit_type=commit_type, description=description, scope=scope
        )

        files = [c.path for c in changes]
        return self.create_commit(files, message)

    def create_pr(
        self, title: str, body: str | None = None, base: str = "main", draft: bool = False
    ) -> GitOrchestratorResult:
        """Crea un Pull Request usando gh CLI."""
        # Verificar que estamos en un branch diferente a base
        success, current_branch = self._run_git("branch", "--show-current")
        if not success or current_branch == base:
            return GitOrchestratorResult(
                success=False,
                operation="create_pr",
                message=f"Must be on a branch different from {base}",
            )

        # Push branch
        success, _ = self._run_git("push", "-u", "origin", current_branch)
        if not success:
            return GitOrchestratorResult(
                success=False, operation="create_pr", message="Failed to push branch"
            )

        # Crear PR con gh
        cmd = ["gh", "pr", "create", "--title", title, "--base", base]
        if body:
            cmd.extend(["--body", body])
        if draft:
            cmd.append("--draft")

        try:
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            success = result.returncode == 0
            output = result.stdout.strip() or result.stderr.strip()
        except Exception as e:
            success = False
            output = str(e)

        return GitOrchestratorResult(
            success=success,
            operation="create_pr",
            message=output,
            details={"title": title, "base": base, "branch": current_branch},
        )

    def generate_changelog(self, from_tag: str | None = None, to_ref: str = "HEAD") -> str:
        """Genera changelog desde commits."""
        # Obtener commits
        cmd = ["log", "--pretty=format:%s|%h|%an|%ai"]
        if from_tag:
            cmd.append(f"{from_tag}..{to_ref}")
        else:
            cmd.extend(["-n", "50"])  # Ultimos 50 commits

        success, output = self._run_git(*cmd)
        if not success:
            return ""

        # Parsear y agrupar por tipo
        groups: dict[str, list[str]] = {
            "Features": [],
            "Bug Fixes": [],
            "Documentation": [],
            "Other": [],
        }

        for line in output.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue

            msg = parts[0]
            hash_short = parts[1]

            # Clasificar
            if msg.startswith("feat"):
                groups["Features"].append(f"- {msg} ({hash_short})")
            elif msg.startswith("fix"):
                groups["Bug Fixes"].append(f"- {msg} ({hash_short})")
            elif msg.startswith("docs"):
                groups["Documentation"].append(f"- {msg} ({hash_short})")
            else:
                groups["Other"].append(f"- {msg} ({hash_short})")

        # Generar changelog
        changelog = f"# Changelog\n\n## {datetime.now().strftime('%Y-%m-%d')}\n\n"

        for section, items in groups.items():
            if items:
                changelog += f"### {section}\n\n"
                changelog += "\n".join(items)
                changelog += "\n\n"

        return changelog

    def execute(self, task: str) -> GitOrchestratorResult:
        """Ejecuta tarea del orquestador."""
        task_lower = task.lower()

        if "commit" in task_lower:
            # Extraer descripcion si existe
            match = re.search(r'["\'](.+?)["\']', task)
            description = match.group(1) if match else None
            return self.auto_commit(description)

        elif "pr" in task_lower or "pull request" in task_lower:
            # Extraer titulo
            match = re.search(r'["\'](.+?)["\']', task)
            title = match.group(1) if match else "Update"
            return self.create_pr(title)

        elif "changelog" in task_lower:
            changelog = self.generate_changelog()
            return GitOrchestratorResult(
                success=True,
                operation="changelog",
                message="Changelog generated",
                details={"changelog": changelog},
            )

        elif "status" in task_lower:
            changes = self.get_status()
            return GitOrchestratorResult(
                success=True,
                operation="status",
                message=f"Found {len(changes)} changes",
                details={"changes": [{"path": c.path, "status": c.status} for c in changes]},
            )

        else:
            return GitOrchestratorResult(
                success=False, operation="unknown", message=f"Unknown task: {task}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Git Orchestrator - Orquestacion automatica de Git"
    )
    parser.add_argument(
        "task", nargs="?", default="status", help="Tarea a ejecutar (commit, pr, changelog, status)"
    )
    parser.add_argument("--repo", default=".", help="Path al repositorio")
    parser.add_argument("--json", action="store_true", help="Output en formato JSON")

    args = parser.parse_args()

    orchestrator = GitOrchestrator(args.repo)
    result = orchestrator.execute(args.task)

    if args.json:
        print(
            json.dumps(
                {
                    "success": result.success,
                    "operation": result.operation,
                    "message": result.message,
                    "details": result.details,
                },
                indent=2,
            )
        )
    else:
        status = "✓" if result.success else "✗"
        print(f"[{status}] {result.operation}: {result.message}")
        if result.details:
            for key, value in result.details.items():
                if isinstance(value, list):
                    print(f"  {key}:")
                    for item in value[:10]:  # Limitar output
                        print(f"    - {item}")
                elif isinstance(value, str) and len(value) > 100:
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
