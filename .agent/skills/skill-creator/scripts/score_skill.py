#!/usr/bin/env python3
"""
Skill Quality Scorer - Evaluates skill quality on a 0-100 scale.

Scores across 5 dimensions:
- Frontmatter (25 pts): name, description quality, invocation control
- Content (25 pts): body length, structure, progressive disclosure
- Resources (20 pts): scripts, references, assets organization
- Quality (20 pts): examples, feedback loops, checklists
- Security (10 pts): no secrets, no shell=True, safe patterns

Usage:
    python score_skill.py <skill_directory>
    python score_skill.py <skill_directory> --verbose
    python score_skill.py <skill_directory> --json
"""

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter, return (dict, body)."""
    if not content.startswith("---"):
        return {}, content

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}, content

    text = match.group(1)
    body = content[match.end() :]

    if yaml is not None:
        try:
            fm = yaml.safe_load(text)
            return fm if isinstance(fm, dict) else {}, body
        except yaml.YAMLError:
            return {}, body

    fm = {}
    for line in text.split("\n"):
        if ":" in line and not line.startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def score_skill(skill_path: str | Path, verbose: bool = False) -> dict:
    """Score a skill directory on multiple dimensions.

    Args:
        skill_path: Path to the skill directory.
        verbose: Whether to include detailed breakdown.

    Returns:
        Dictionary with scores and breakdown.
    """
    skill_path = Path(skill_path)
    breakdown: dict[str, list[str]] = {
        "frontmatter": [],
        "content": [],
        "resources": [],
        "quality": [],
        "security": [],
    }
    scores = {
        "frontmatter": 0,  # /25
        "content": 0,  # /25
        "resources": 0,  # /20
        "quality": 0,  # /20
        "security": 0,  # /10
    }

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {"total": 0, "scores": scores, "breakdown": breakdown, "grade": "F"}

    content = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    # ===== FRONTMATTER (25 pts) =====
    # Name present and valid (5 pts)
    name = fm.get("name", "")
    if isinstance(name, str) and name.strip():
        name = name.strip()
        if re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", name) and len(name) <= 64:
            scores["frontmatter"] += 5
            breakdown["frontmatter"].append("+5 Name is valid")
        else:
            scores["frontmatter"] += 2
            breakdown["frontmatter"].append("+2 Name exists but has issues")
    else:
        breakdown["frontmatter"].append("+0 Missing or invalid name")

    # Description present (5 pts)
    desc = fm.get("description", "")
    if isinstance(desc, str):
        desc = desc.strip()
    else:
        desc = ""

    if desc and "[TODO" not in desc:
        scores["frontmatter"] += 5
        breakdown["frontmatter"].append("+5 Description present")
    elif desc:
        scores["frontmatter"] += 1
        breakdown["frontmatter"].append("+1 Description is TODO placeholder")
    else:
        breakdown["frontmatter"].append("+0 Missing description")

    # Description quality (10 pts)
    if desc and "[TODO" not in desc:
        desc_lower = desc.lower()
        quality = 0

        # Length check (2 pts)
        if 50 <= len(desc) <= 1024:
            quality += 2
            breakdown["frontmatter"].append("+2 Description length is good")
        elif len(desc) > 20:
            quality += 1
            breakdown["frontmatter"].append("+1 Description is short")

        # Third person (2 pts)
        if not desc_lower.startswith(("i ", "i can", "you ", "you can")):
            quality += 2
            breakdown["frontmatter"].append("+2 Uses third person")
        else:
            breakdown["frontmatter"].append("+0 Uses first/second person")

        # Trigger keywords (3 pts)
        if any(w in desc_lower for w in ["use when", "use for", "invoke when", "trigger"]):
            quality += 3
            breakdown["frontmatter"].append("+3 Includes trigger guidance")
        else:
            breakdown["frontmatter"].append("+0 Missing trigger guidance")

        # Multiple trigger scenarios (3 pts)
        trigger_indicators = desc.count(",") + desc.count(";") + desc.count("(")
        if trigger_indicators >= 3:
            quality += 3
            breakdown["frontmatter"].append("+3 Rich trigger keywords")
        elif trigger_indicators >= 1:
            quality += 1
            breakdown["frontmatter"].append("+1 Some trigger keywords")
        else:
            breakdown["frontmatter"].append("+0 Few trigger keywords")

        scores["frontmatter"] += min(quality, 10)

    # Invocation control configured (5 pts)
    has_invocation_control = (
        "disable-model-invocation" in fm
        or "user-invocable" in fm
        or "context" in fm
        or "allowed-tools" in fm
    )
    if has_invocation_control:
        scores["frontmatter"] += 5
        breakdown["frontmatter"].append("+5 Invocation control configured")
    else:
        scores["frontmatter"] += 2
        breakdown["frontmatter"].append("+2 Using defaults (consider explicit control)")

    # ===== CONTENT (25 pts) =====
    body_lines = [l for l in body.strip().split("\n") if l.strip()]

    # Body exists and has substance (5 pts)
    if len(body_lines) > 5:
        scores["content"] += 5
        breakdown["content"].append("+5 Body has substantial content")
    elif len(body_lines) > 0:
        scores["content"] += 2
        breakdown["content"].append("+2 Body is minimal")
    else:
        breakdown["content"].append("+0 Body is empty")

    # Under 500 lines (5 pts)
    if len(body_lines) <= 500:
        scores["content"] += 5
        breakdown["content"].append("+5 Under 500-line limit")
    else:
        scores["content"] += 1
        breakdown["content"].append(f"+1 Over limit ({len(body_lines)} lines)")

    # Has headings structure (5 pts)
    headings = [l for l in body_lines if l.startswith("#")]
    if len(headings) >= 3:
        scores["content"] += 5
        breakdown["content"].append(f"+5 Well-structured ({len(headings)} headings)")
    elif len(headings) >= 1:
        scores["content"] += 3
        breakdown["content"].append(f"+3 Some structure ({len(headings)} headings)")
    else:
        breakdown["content"].append("+0 No headings")

    # Has code examples (5 pts)
    code_blocks = body.count("```")
    if code_blocks >= 4:
        scores["content"] += 5
        breakdown["content"].append("+5 Multiple code examples")
    elif code_blocks >= 2:
        scores["content"] += 3
        breakdown["content"].append("+3 Some code examples")
    else:
        breakdown["content"].append("+0 No code examples")

    # No TODO placeholders (5 pts)
    todo_count = body.count("[TODO")
    if todo_count == 0:
        scores["content"] += 5
        breakdown["content"].append("+5 No TODO placeholders")
    else:
        breakdown["content"].append(f"+0 Has {todo_count} TODO placeholders")

    # ===== RESOURCES (20 pts) =====
    has_scripts = (
        (skill_path / "scripts").exists() and any((skill_path / "scripts").iterdir())
        if (skill_path / "scripts").exists()
        else False
    )
    has_references = (
        (skill_path / "references").exists() and any((skill_path / "references").iterdir())
        if (skill_path / "references").exists()
        else False
    )
    has_assets = (
        (skill_path / "assets").exists()
        and any(f.name != ".gitkeep" for f in (skill_path / "assets").iterdir())
        if (skill_path / "assets").exists()
        else False
    )

    # Scripts (8 pts)
    if has_scripts:
        real_scripts = [
            f for f in (skill_path / "scripts").iterdir() if f.is_file() and f.name != "example.py"
        ]
        if real_scripts:
            scores["resources"] += 8
            breakdown["resources"].append(f"+8 Has {len(real_scripts)} real scripts")
        else:
            scores["resources"] += 3
            breakdown["resources"].append("+3 Has example script only")
    else:
        breakdown["resources"].append("+0 No scripts")

    # References (8 pts)
    if has_references:
        ref_files = [f for f in (skill_path / "references").iterdir() if f.is_file()]
        if ref_files:
            scores["resources"] += 8
            breakdown["resources"].append(f"+8 Has {len(ref_files)} reference files")

            # Check for table of contents in long files
            for rf in ref_files:
                try:
                    rc = rf.read_text(encoding="utf-8")
                    if rc.count("\n") > 100 and "## Contents" not in rc and "## Table of" not in rc:
                        breakdown["resources"].append(
                            f"  WARN: {rf.name} is >100 lines without ToC"
                        )
                except (UnicodeDecodeError, PermissionError):
                    pass
        else:
            scores["resources"] += 2
            breakdown["resources"].append("+2 Empty references directory")
    else:
        breakdown["resources"].append("+0 No references")

    # Assets (4 pts)
    if has_assets:
        scores["resources"] += 4
        breakdown["resources"].append("+4 Has assets")
    else:
        scores["resources"] += 2
        breakdown["resources"].append("+2 No assets (often not needed)")

    # ===== QUALITY (20 pts) =====
    body_lower = body.lower()

    # Has concrete examples (5 pts)
    if "example" in body_lower and code_blocks >= 2:
        scores["quality"] += 5
        breakdown["quality"].append("+5 Has concrete examples with code")
    elif "example" in body_lower:
        scores["quality"] += 2
        breakdown["quality"].append("+2 Mentions examples")
    else:
        breakdown["quality"].append("+0 No examples")

    # Has feedback loops or validation (5 pts)
    feedback_words = ["validate", "verify", "check", "if validation fails", "run validator"]
    if any(w in body_lower for w in feedback_words):
        scores["quality"] += 5
        breakdown["quality"].append("+5 Has validation/feedback loops")
    else:
        breakdown["quality"].append("+0 No feedback loops")

    # Has checklists or step-by-step (5 pts)
    has_steps = bool(re.search(r"^\d+\.", body, re.MULTILINE))
    has_checklist = "- [ ]" in body or "- [x]" in body
    if has_checklist:
        scores["quality"] += 5
        breakdown["quality"].append("+5 Has checklists")
    elif has_steps:
        scores["quality"] += 3
        breakdown["quality"].append("+3 Has numbered steps")
    else:
        breakdown["quality"].append("+0 No structured steps")

    # References bundled files from SKILL.md (5 pts)
    has_file_refs = bool(re.search(r"\[.*?\]\(.*?\.md\)", body))
    if has_file_refs:
        scores["quality"] += 5
        breakdown["quality"].append("+5 References bundled files")
    else:
        if has_references:
            breakdown["quality"].append("+0 Has references but doesn't link them from SKILL.md")
        else:
            scores["quality"] += 2
            breakdown["quality"].append("+2 No references to link")

    # ===== SECURITY (10 pts) =====
    security_score = 10

    # Check for secrets
    secret_patterns = [
        re.compile(r'(?:api[_-]?key|secret|token|password)\s*[=:]\s*["\'][^"\']{8,}', re.I),
        re.compile(r"(?:sk-|ghp_|gho_|github_pat_)[a-zA-Z0-9]{20,}"),
    ]
    for fp in skill_path.rglob("*"):
        if fp.is_file() and fp.suffix in {".md", ".py", ".sh", ".yaml", ".yml", ".json"}:
            try:
                fc = fp.read_text(encoding="utf-8")
                for pat in secret_patterns:
                    if pat.search(fc):
                        security_score -= 5
                        breakdown["security"].append(
                            f"-5 Possible secret in {fp.relative_to(skill_path)}"
                        )
                        break
                # Check for shell=True in function calls (subprocess, etc.)
                if fp.suffix == ".py":
                    shell_call_re = re.compile(r"[,(]\s*shell\s*=\s*True")
                    if shell_call_re.search(fc):
                        security_score -= 3
                        breakdown["security"].append(
                            f"-3 shell=True in {fp.relative_to(skill_path)}"
                        )
            except (UnicodeDecodeError, PermissionError):
                pass

    scores["security"] = max(0, security_score)
    if security_score == 10:
        breakdown["security"].append("+10 No security issues found")

    # ===== TOTAL =====
    total = sum(scores.values())
    grade = (
        "A+"
        if total >= 95
        else "A"
        if total >= 90
        else "B+"
        if total >= 85
        else "B"
        if total >= 80
        else "C+"
        if total >= 75
        else "C"
        if total >= 70
        else "D"
        if total >= 60
        else "F"
    )

    return {
        "total": total,
        "grade": grade,
        "scores": scores,
        "breakdown": breakdown,
    }


def format_report(result: dict, skill_name: str) -> str:
    """Format the score result as a human-readable report.

    Args:
        result: Score result dictionary.
        skill_name: Name of the skill.

    Returns:
        Formatted report string.
    """
    lines = [
        f"Skill Quality Report: {skill_name}",
        "=" * 50,
        f"Total Score: {result['total']}/100 (Grade: {result['grade']})",
        "",
    ]

    dimension_labels = {
        "frontmatter": "Frontmatter",
        "content": "Content",
        "resources": "Resources",
        "quality": "Quality",
        "security": "Security",
    }
    dimension_max = {
        "frontmatter": 25,
        "content": 25,
        "resources": 20,
        "quality": 20,
        "security": 10,
    }

    for key, label in dimension_labels.items():
        score = result["scores"][key]
        max_score = dimension_max[key]
        bar_filled = int((score / max_score) * 20)
        bar = "#" * bar_filled + "." * (20 - bar_filled)
        lines.append(f"  {label:12s} [{bar}] {score:2d}/{max_score}")

    lines.append("")
    lines.append("Breakdown:")

    for key, label in dimension_labels.items():
        items = result["breakdown"][key]
        if items:
            lines.append(f"  {label}:")
            for item in items:
                lines.append(f"    {item}")

    return "\n".join(lines)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python score_skill.py <skill_directory> [--verbose] [--json]")
        sys.exit(1)

    skill_path = Path(sys.argv[1])
    verbose = "--verbose" in sys.argv
    as_json = "--json" in sys.argv

    if not skill_path.exists():
        print(f"Error: Path not found: {skill_path}")
        sys.exit(1)

    result = score_skill(skill_path, verbose=verbose)

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result, skill_path.name))


if __name__ == "__main__":
    main()
