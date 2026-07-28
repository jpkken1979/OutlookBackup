#!/usr/bin/env python3
"""
Antigravity Ecosystem Validator v1.0

Validates ecosystem structure BEFORE commits to catch errors early.
Can be used as pre-commit hook or standalone.

Usage:
    python .agent/scripts/validate_ecosystem.py
    python .agent/scripts/validate_ecosystem.py --fix  # Auto-fix issues
"""

import sys
from pathlib import Path

# Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agent" / "agents"
SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"


def validate_agents() -> list[str]:
    """Validate all agents have required files."""
    errors = []

    if not AGENTS_DIR.exists():
        return ["Agents directory not found"]

    for agent_dir in AGENTS_DIR.iterdir():
        if not agent_dir.is_dir():
            continue

        name = agent_dir.name

        # Skip special directories
        if name.startswith("_") or name.startswith("."):
            continue

        # Check required files
        identity = agent_dir / "IDENTITY.md"
        prompt = agent_dir / "SYSTEM_PROMPT.md"

        if not identity.exists():
            errors.append(f"Agent '{name}' missing IDENTITY.md")

        if not prompt.exists():
            errors.append(f"Agent '{name}' missing SYSTEM_PROMPT.md")

    return errors


def validate_skills() -> list[str]:
    """Validate all skills have SKILL.md."""
    errors = []

    if not SKILLS_DIR.exists():
        return ["Skills directory not found"]

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue

        name = skill_dir.name

        # Skip special directories
        if name.startswith(".") or name.startswith("_") or name == "community":
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"Skill '{name}' missing SKILL.md")

    return errors


def auto_fix_agents() -> int:
    """Create missing SYSTEM_PROMPT.md files."""
    fixed = 0

    for agent_dir in AGENTS_DIR.iterdir():
        if not agent_dir.is_dir():
            continue

        name = agent_dir.name
        if name.startswith("_") or name.startswith("."):
            continue

        identity = agent_dir / "IDENTITY.md"
        prompt = agent_dir / "SYSTEM_PROMPT.md"

        if identity.exists() and not prompt.exists():
            # Create basic SYSTEM_PROMPT.md
            agent_name = name.replace("-", " ").title()
            content = f"""# {agent_name} - System Prompt

You are {agent_name}, a specialized agent in the Antigravity ecosystem.

## Core Behavior

1. Read your IDENTITY.md for detailed capabilities and responsibilities
2. Follow the rules in .antigravity/rules.md
3. Use structured logging for all operations
4. Coordinate with other agents when needed

## Activation

This agent activates when tasks match its specialty as defined in IDENTITY.md.

## Output Format

- Use clear, structured responses
- Include reasoning for decisions
- Provide actionable recommendations
"""
            prompt.write_text(content)
            print(f"{GREEN}[FIXED]{RESET} Created {prompt}")
            fixed += 1

    return fixed


def main():
    print(f"\n{CYAN}{'=' * 60}{RESET}")
    print(f"{CYAN}  ANTIGRAVITY ECOSYSTEM VALIDATOR v1.0{RESET}")
    print(f"{CYAN}{'=' * 60}{RESET}\n")

    auto_fix = "--fix" in sys.argv

    # Validate agents
    print(f"{CYAN}[1/2]{RESET} Validating agents...")
    agent_errors = validate_agents()

    # Validate skills
    print(f"{CYAN}[2/2]{RESET} Validating skills...")
    skill_errors = validate_skills()

    all_errors = agent_errors + skill_errors

    if all_errors:
        print(f"\n{RED}{'=' * 60}{RESET}")
        print(f"{RED}  VALIDATION FAILED - {len(all_errors)} errors{RESET}")
        print(f"{RED}{'=' * 60}{RESET}\n")

        for error in all_errors:
            print(f"{RED}  [ERROR]{RESET} {error}")

        if auto_fix:
            print(f"\n{YELLOW}Attempting auto-fix...{RESET}\n")
            fixed = auto_fix_agents()
            if fixed:
                print(f"\n{GREEN}Fixed {fixed} issues. Run again to verify.{RESET}")
                return 0
        else:
            print(f"\n{YELLOW}Tip: Run with --fix to auto-create missing files{RESET}")

        return 1

    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}  VALIDATION PASSED{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}\n")

    # Stats
    agent_count = len(
        [d for d in AGENTS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")]
    )
    skill_count = len(
        [d for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    )

    print(f"  Agents validated: {agent_count}")
    print(f"  Skills validated: {skill_count}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
