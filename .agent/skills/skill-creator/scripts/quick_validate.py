#!/usr/bin/env python3
"""
Skill Validator - Validates skill structure against official Claude Code spec.

Checks:
- SKILL.md exists with valid YAML frontmatter
- Required fields (name, description) present and valid
- All frontmatter fields are allowed per spec
- Name follows naming conventions (hyphen-case, max 64 chars, no reserved words)
- Description quality (length, third person, no angle brackets)
- Body length (warns if > 500 lines)
- Reference files are one level deep
- Scripts have no shell=True usage
- No hardcoded secrets patterns

Usage:
    python quick_validate.py <skill_directory>
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


ALLOWED_FRONTMATTER = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "disable-model-invocation",
    "user-invocable",
    "context",
    "agent",
    "model",
    "argument-hint",
    "hooks",
}

RESERVED_WORDS = {"anthropic", "claude"}

SECRET_PATTERNS = [
    re.compile(r'(?:api[_-]?key|secret|token|password)\s*[=:]\s*["\'][^"\']{8,}', re.IGNORECASE),
    re.compile(r"(?:sk-|ghp_|gho_|github_pat_)[a-zA-Z0-9]{20,}"),
]

MAX_BODY_LINES = 500
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024


def parse_frontmatter(content: str) -> tuple[dict | None, str, str | None]:
    """Parse YAML frontmatter from SKILL.md content.

    Args:
        content: Full file content.

    Returns:
        Tuple of (frontmatter_dict, body, error_message).
    """
    if not content.startswith("---"):
        return None, content, "No YAML frontmatter found (must start with ---)"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None, content, "Invalid frontmatter format (missing closing ---)"

    frontmatter_text = match.group(1)
    body = content[match.end() :]

    if yaml is not None:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                return None, body, "Frontmatter must be a YAML dictionary"
            return frontmatter, body, None
        except yaml.YAMLError as e:
            return None, body, f"Invalid YAML in frontmatter: {e}"
    else:
        # Fallback: basic parsing without yaml module
        frontmatter = {}
        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip()
        return frontmatter, body, None


def validate_skill(skill_path: str | Path) -> tuple[bool, str]:
    """Validate a skill directory against the official spec.

    Args:
        skill_path: Path to the skill directory.

    Returns:
        Tuple of (is_valid, message).
    """
    skill_path = Path(skill_path)
    errors: list[str] = []
    warnings: list[str] = []

    # Check SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    content = skill_md.read_text(encoding="utf-8")

    # Parse frontmatter
    frontmatter, body, parse_error = parse_frontmatter(content)
    if parse_error:
        return False, parse_error
    if frontmatter is None:
        return False, "Could not parse frontmatter"

    # Check for unexpected frontmatter fields
    unexpected = set(frontmatter.keys()) - ALLOWED_FRONTMATTER
    if unexpected:
        errors.append(
            f"Unexpected frontmatter field(s): {', '.join(sorted(unexpected))}. "
            f"Allowed: {', '.join(sorted(ALLOWED_FRONTMATTER))}"
        )

    # Validate name
    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        errors.append(f"'name' must be a string, got {type(name).__name__}")
    else:
        name = name.strip()
        if name:
            if not re.match(r"^[a-z0-9-]+$", name):
                errors.append(
                    f"Name '{name}' must be hyphen-case "
                    "(lowercase letters, digits, and hyphens only)"
                )
            if name.startswith("-") or name.endswith("-") or "--" in name:
                errors.append(
                    f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
                )
            if len(name) > MAX_NAME_LENGTH:
                errors.append(f"Name too long ({len(name)} chars). Maximum: {MAX_NAME_LENGTH}")
            for word in RESERVED_WORDS:
                if word in name:
                    errors.append(f"Name cannot contain reserved word '{word}'")

            # Check name matches directory
            if name != skill_path.name:
                warnings.append(f"Name '{name}' doesn't match directory '{skill_path.name}'")

    # Validate description
    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        errors.append(f"'description' must be a string, got {type(description).__name__}")
    else:
        description = description.strip()
        if not description:
            errors.append("Description is empty")
        elif "[TODO" in description:
            warnings.append("Description still contains TODO placeholder")
        else:
            if "<" in description or ">" in description:
                errors.append("Description cannot contain angle brackets (< or >)")
            if len(description) > MAX_DESCRIPTION_LENGTH:
                errors.append(
                    f"Description too long ({len(description)} chars). "
                    f"Maximum: {MAX_DESCRIPTION_LENGTH}"
                )
            # Check for first/second person
            desc_lower = description.lower()
            if desc_lower.startswith(("i ", "i can", "i will", "i help")):
                warnings.append(
                    "Description uses first person ('I...'). "
                    "Use third person instead ('Processes...', 'Analyzes...')"
                )
            if desc_lower.startswith(("you ", "you can", "you will")):
                warnings.append(
                    "Description uses second person ('You...'). Use third person instead"
                )
            # Check if description includes trigger info
            trigger_words = ["use when", "use for", "use this", "invoke when", "trigger"]
            if not any(w in desc_lower for w in trigger_words):
                warnings.append(
                    "Description doesn't include 'Use when...' trigger guidance. "
                    "Adding triggers improves activation from ~50% to ~90%"
                )

    # Validate invocation control consistency
    disable_model = frontmatter.get("disable-model-invocation", False)
    user_invocable = frontmatter.get("user-invocable", True)
    if disable_model and not user_invocable:
        errors.append(
            "Cannot set both disable-model-invocation: true AND user-invocable: false "
            "(skill would be unreachable)"
        )

    # Validate context/agent fields
    context = frontmatter.get("context")
    agent = frontmatter.get("agent")
    if context and context != "fork":
        errors.append(f"'context' must be 'fork', got '{context}'")
    if agent and not context:
        warnings.append("'agent' field has no effect without 'context: fork'")

    # Check body length
    body_lines = body.strip().split("\n")
    if len(body_lines) > MAX_BODY_LINES:
        warnings.append(
            f"Body has {len(body_lines)} lines (recommended max: {MAX_BODY_LINES}). "
            "Consider splitting into reference files"
        )

    # Check for secrets in all files
    for file_path in skill_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in {
            ".md",
            ".py",
            ".sh",
            ".yaml",
            ".yml",
            ".json",
        }:
            try:
                file_content = file_path.read_text(encoding="utf-8")
                for pattern in SECRET_PATTERNS:
                    if pattern.search(file_content):
                        errors.append(
                            f"Possible secret/credential in {file_path.relative_to(skill_path)}"
                        )
            except (UnicodeDecodeError, PermissionError):
                pass

    # Check scripts for actual shell=True in function calls (subprocess, etc.)
    # Pattern: shell=True preceded by ( or , indicating a function argument
    shell_call_pattern = re.compile(r"[,(]\s*shell\s*=\s*True")
    for script_path in (
        (skill_path / "scripts").rglob("*.py") if (skill_path / "scripts").exists() else []
    ):
        try:
            script_content = script_path.read_text(encoding="utf-8")
            for match in shell_call_pattern.finditer(script_content):
                line_num = script_content[: match.start()].count("\n") + 1
                errors.append(
                    f"Script {script_path.name}:{line_num} uses shell=True "
                    "(security risk, use shlex.split instead)"
                )
                break
        except (UnicodeDecodeError, PermissionError):
            pass

    # Check reference depth (should be one level)
    for ref_path in skill_path.rglob("*.md"):
        if ref_path == skill_md:
            continue
        relative = ref_path.relative_to(skill_path)
        if len(relative.parts) > 2:
            warnings.append(
                f"Reference '{relative}' is nested too deep. "
                "Keep references one level deep from SKILL.md"
            )

    # Build result
    if errors:
        msg = "Validation FAILED:\n"
        for e in errors:
            msg += f"  ERROR: {e}\n"
        for w in warnings:
            msg += f"  WARNING: {w}\n"
        return False, msg.strip()

    if warnings:
        msg = "Skill is valid (with warnings):\n"
        for w in warnings:
            msg += f"  WARNING: {w}\n"
        return True, msg.strip()

    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
