"""git-analyst — Analiza historial git, actividad y tendencias del proyecto."""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timedelta, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (
    llm_summarize,
    main_wrapper,
    run_command,
)

AGENT_NAME = "git-analyst"


def _git(args: list[str], root: Path, timeout: int = 30) -> str:
    """Run a git command and return stdout."""
    result = run_command(["git", *args], cwd=root, timeout=timeout)
    return result["stdout"] if result["ok"] else ""


def _parse_date(date_str: str) -> datetime | None:
    """Parse git date format (ISO-ish)."""
    try:
        # Format: 2026-03-22 10:30:00 +0900
        clean = date_str.strip()
        if not clean:
            return None
        # Try ISO format
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _count_commits_since(root: Path, days: int) -> int:
    """Count commits in the last N days."""
    since = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    output = _git(["rev-list", "--count", f"--since={since}", "HEAD"], root)
    try:
        return int(output.strip())
    except ValueError:
        return 0


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    # Check if git repo
    if not (root / ".git").exists():
        return {
            "status": "error",
            "summary": "No es un repositorio git.",
            "raw": {},
            "llm_used": "none",
        }

    # Recent commits
    recent_commits = _git(["log", "--oneline", "-30"], root)

    # Contributor stats
    contributors = _git(["shortlog", "-sn", "--no-merges", "HEAD"], root)
    # Take top 10
    contrib_lines = contributors.strip().splitlines()[:10]

    # Recent change scope
    diff_stat = _git(["diff", "--stat", "HEAD~10..HEAD"], root)

    # Project age (first commit date)
    first_date_str = _git(["log", "--format=%ai", "--reverse"], root)
    first_date = None
    if first_date_str:
        first_line = first_date_str.strip().splitlines()[0] if first_date_str.strip() else ""
        first_date = _parse_date(first_line)

    last_date_str = _git(["log", "-1", "--format=%ai"], root)
    last_date = _parse_date(last_date_str.strip()) if last_date_str else None

    project_age_days = 0
    if first_date and last_date:
        project_age_days = (last_date - first_date).days

    # Commit counts by period
    commits_7d = _count_commits_since(root, 7)
    commits_30d = _count_commits_since(root, 30)
    commits_90d = _count_commits_since(root, 90)

    # Total commits
    total_output = _git(["rev-list", "--count", "HEAD"], root)
    total_commits = int(total_output.strip()) if total_output.strip().isdigit() else 0

    # Most changed files (top 15)
    name_only = _git(["log", "--name-only", "--pretty=format:", "-100"], root)
    file_counter: Counter[str] = Counter()
    if name_only:
        for line in name_only.strip().splitlines():
            line = line.strip()
            if line:
                file_counter[line] += 1
    hot_files = file_counter.most_common(15)

    # Current branch
    branch = _git(["branch", "--show-current"], root).strip()

    raw = {
        "branch": branch,
        "total_commits": total_commits,
        "project_age_days": project_age_days,
        "first_commit": first_date.isoformat() if first_date else None,
        "last_commit": last_date.isoformat() if last_date else None,
        "commits_7d": commits_7d,
        "commits_30d": commits_30d,
        "commits_90d": commits_90d,
        "contributors": [line.strip() for line in contrib_lines],
        "hot_files": [{"file": f, "changes": c} for f, c in hot_files],
        "recent_commits_sample": recent_commits.strip().splitlines()[:15],
    }

    # Velocity
    weekly_avg = round(commits_30d / 4.3, 1) if commits_30d else 0

    # LLM summary
    data_for_llm = (
        f"Repositorio: {root.name}\n"
        f"Branch: {branch}\n"
        f"Total commits: {total_commits}\n"
        f"Edad: {project_age_days} dias\n"
        f"Commits ultimos 7d: {commits_7d}, 30d: {commits_30d}, 90d: {commits_90d}\n"
        f"Promedio semanal: {weekly_avg}\n\n"
        f"Contribuidores (top 10):\n{contributors.strip()}\n\n"
        f"Archivos mas modificados (ultimos 100 commits):\n"
    )
    for fname, count in hot_files:
        data_for_llm += f"  {count}x {fname}\n"

    data_for_llm += f"\nCommits recientes:\n{recent_commits.strip()}\n"

    if diff_stat:
        data_for_llm += f"\nCambios recientes (HEAD~10..HEAD):\n{diff_stat[:2000]}\n"

    prompt = (
        "Analiza la actividad de este repositorio git. "
        "Comenta sobre: velocidad del proyecto, areas activas (hot spots), "
        "tendencias (acelerando/desacelerando), distribucion de contribuidores "
        "y cualquier patron notable. Responde en español, conciso."
    )

    summary = llm_summarize(data_for_llm, prompt)
    llm_used = "auto"

    if not summary:
        llm_used = "none"
        summary = (
            f"Repositorio: {root.name} (branch: {branch})\n"
            f"Total commits: {total_commits} | Edad: {project_age_days} dias\n"
            f"Actividad: {commits_7d} (7d), {commits_30d} (30d), {commits_90d} (90d)\n"
            f"Promedio semanal: {weekly_avg} commits\n\n"
            f"Top contribuidores:\n"
        )
        for line in contrib_lines[:5]:
            summary += f"  {line.strip()}\n"
        summary += "\nArchivos mas modificados:\n"
        for fname, count in hot_files[:10]:
            summary += f"  {count}x {fname}\n"

    return {
        "status": "success",
        "summary": summary,
        "raw": raw,
        "llm_used": llm_used,
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)
