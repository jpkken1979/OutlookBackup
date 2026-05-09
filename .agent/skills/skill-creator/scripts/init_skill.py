#!/usr/bin/env python3
"""
Skill Initializer - Creates a new skill from template with full frontmatter support.

Usage:
    init_skill.py <skill-name> --path <path> [options]

Options:
    --type <standard|task|reference>  Skill type (default: standard)
    --subagent                        Add context: fork with agent selection
    --allowed-tools "Tool1, Tool2"    Restrict tool access
    --description "..."               Pre-fill the description

Examples:
    init_skill.py my-new-skill --path .agent/skills
    init_skill.py deploy-app --path .claude/skills --type task
    init_skill.py code-conventions --path .agent/skills --type reference
    init_skill.py deep-research --path .claude/skills --subagent
    init_skill.py safe-reader --path .claude/skills --allowed-tools "Read, Grep, Glob"
"""

import argparse
import re
import sys
from pathlib import Path


SKILL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
SKILL_NAME_MAX_LENGTH = 64
RESERVED_WORDS = {"anthropic", "claude"}


def validate_skill_name(skill_name: str) -> str | None:
    """Valida el nombre del skill segun las reglas oficiales.

    Args:
        skill_name: Nombre del skill a validar.

    Returns:
        Mensaje de error si es invalido, None si es valido.
    """
    if not skill_name:
        return "El nombre del skill no puede estar vacio"

    if len(skill_name) > SKILL_NAME_MAX_LENGTH:
        return (
            f"El nombre '{skill_name}' excede {SKILL_NAME_MAX_LENGTH} caracteres "
            f"(tiene {len(skill_name)})"
        )

    if not SKILL_NAME_PATTERN.match(skill_name):
        return (
            f"El nombre '{skill_name}' no es valido. "
            "Debe usar hyphen-case con solo letras minusculas, digitos y guiones "
            "(e.g., 'data-analyzer', 'processing-pdfs')"
        )

    for word in RESERVED_WORDS:
        if word in skill_name:
            return f"El nombre no puede contener la palabra reservada '{word}'"

    return None


def title_case_skill_name(skill_name: str) -> str:
    """Convert hyphenated skill name to Title Case for display."""
    return " ".join(word.capitalize() for word in skill_name.split("-"))


def build_frontmatter(
    skill_name: str,
    skill_type: str = "standard",
    subagent: bool = False,
    allowed_tools: str | None = None,
    description: str | None = None,
) -> str:
    """Genera el frontmatter YAML segun el tipo de skill.

    Args:
        skill_name: Nombre del skill.
        skill_type: Tipo: standard, task, reference.
        subagent: Si debe ejecutarse en subagente.
        allowed_tools: Herramientas permitidas.
        description: Descripcion pre-llenada.

    Returns:
        Frontmatter YAML como string.
    """
    lines = ["---"]
    lines.append(f"name: {skill_name}")

    desc = description or (
        "[TODO: Write a specific, 'pushy' description in THIRD PERSON. "
        "Include what the skill does AND when to use it. "
        "Include all trigger keywords users might say. Max 1024 chars.]"
    )
    lines.append("description: >-")
    lines.append(f"  {desc}")

    if skill_type == "task":
        lines.append("disable-model-invocation: true")
    elif skill_type == "reference":
        lines.append("user-invocable: false")

    if allowed_tools:
        lines.append(f"allowed-tools: {allowed_tools}")

    if subagent:
        lines.append("context: fork")
        lines.append("agent: general-purpose  # Options: Explore, Plan, general-purpose, or custom")

    lines.append("---")
    return "\n".join(lines)


def build_body(skill_name: str, skill_title: str, skill_type: str, subagent: bool) -> str:
    """Genera el cuerpo del SKILL.md.

    Args:
        skill_name: Nombre del skill.
        skill_title: Titulo en Title Case.
        skill_type: Tipo de skill.
        subagent: Si usa subagente.

    Returns:
        Cuerpo markdown como string.
    """
    sections = [f"\n# {skill_title}\n"]

    if skill_type == "task":
        sections.append(
            "[TODO: Write step-by-step task instructions. "
            f"This skill is invoked manually with /{skill_name}, so include explicit actions.]\n"
        )
        sections.append("## Steps\n")
        sections.append("1. [TODO: First step]")
        sections.append("2. [TODO: Second step]")
        sections.append("3. [TODO: Verify output]\n")
        if subagent:
            sections.append(
                "**Note:** This skill runs in an isolated subagent. "
                "It has no access to conversation history.\n"
            )
    elif skill_type == "reference":
        sections.append(
            "[TODO: Write reference knowledge that Claude applies to ongoing work. "
            "This skill is loaded automatically when relevant — users cannot invoke it directly.]\n"
        )
        sections.append("## Guidelines\n")
        sections.append("- [TODO: Guideline 1]")
        sections.append("- [TODO: Guideline 2]\n")
        sections.append("## Patterns\n")
        sections.append("[TODO: Add code patterns, conventions, or domain knowledge]\n")
    else:
        sections.append("[TODO: 1-2 sentences explaining what this skill enables]\n")
        sections.append("## Quick Start\n")
        sections.append("[TODO: Show the simplest usage with a concise example]\n")
        sections.append("## Detailed Usage\n")
        sections.append(
            "[TODO: Add detailed instructions. Choose a structure:\n"
            "- **Workflow-Based**: Step-by-step procedures\n"
            "- **Task-Based**: Different operations/capabilities\n"
            "- **Reference**: Standards or specifications\n"
            "- **Capabilities-Based**: Interrelated features]\n"
        )

    sections.append("## Resources\n")
    sections.append(
        "- **scripts/**: Executable code — run without loading into context\n"
        "- **references/**: Documentation — loaded on-demand by Claude\n"
        "- **assets/**: Templates/files — used in output, not loaded into context\n"
    )
    sections.append("Delete unused resource directories.\n")

    return "\n".join(sections)


EXAMPLE_SCRIPT = '''#!/usr/bin/env python3
"""
Example helper script for {skill_name}.

Replace with actual implementation or delete if not needed.
Scripts are executed without loading into context — only output consumes tokens.
"""

from pathlib import Path


def main() -> None:
    """Punto de entrada principal."""
    print("This is an example script for {skill_name}")
    # TODO: Implement actual logic


if __name__ == "__main__":
    main()
'''

EXAMPLE_REFERENCE = """# Reference Documentation for {skill_title}

## Contents
- [Section 1]
- [Section 2]

---

[TODO: Replace with actual reference content. Keep this file focused on one domain.
For files > 100 lines, include a table of contents (like above) so Claude can
see the full scope when previewing.]

Reference docs are ideal for:
- API documentation and schemas
- Detailed workflow guides
- Domain-specific knowledge
- Information too lengthy for SKILL.md
"""


def init_skill(
    skill_name: str,
    path: str,
    skill_type: str = "standard",
    subagent: bool = False,
    allowed_tools: str | None = None,
    description: str | None = None,
) -> Path | None:
    """Initialize a new skill directory with template SKILL.md.

    Args:
        skill_name: Name of the skill.
        path: Path where the skill directory should be created.
        skill_type: Type of skill (standard, task, reference).
        subagent: Whether to add context: fork.
        allowed_tools: Tools to allow without permission.
        description: Pre-filled description.

    Returns:
        Path to created skill directory, or None if error.
    """
    validation_error = validate_skill_name(skill_name)
    if validation_error:
        print(f"Error: {validation_error}")
        return None

    skill_dir = Path(path).resolve() / skill_name

    if skill_dir.exists():
        print(f"Error: Skill directory already exists: {skill_dir}")
        return None

    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
        print(f"Created skill directory: {skill_dir}")
    except Exception as e:
        print(f"Error creating directory: {e}")
        return None

    # Build SKILL.md
    skill_title = title_case_skill_name(skill_name)
    frontmatter = build_frontmatter(skill_name, skill_type, subagent, allowed_tools, description)
    body = build_body(skill_name, skill_title, skill_type, subagent)
    skill_content = frontmatter + body

    skill_md_path = skill_dir / "SKILL.md"
    try:
        skill_md_path.write_text(skill_content, encoding="utf-8")
        print("Created SKILL.md")
    except Exception as e:
        print(f"Error creating SKILL.md: {e}")
        return None

    # Create resource directories with examples
    try:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        example_script = scripts_dir / "example.py"
        example_script.write_text(EXAMPLE_SCRIPT.format(skill_name=skill_name), encoding="utf-8")
        example_script.chmod(0o755)
        print("Created scripts/example.py")

        references_dir = skill_dir / "references"
        references_dir.mkdir(exist_ok=True)
        example_reference = references_dir / "reference.md"
        example_reference.write_text(
            EXAMPLE_REFERENCE.format(skill_title=skill_title), encoding="utf-8"
        )
        print("Created references/reference.md")

        assets_dir = skill_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        (assets_dir / ".gitkeep").write_text("", encoding="utf-8")
        print("Created assets/")
    except Exception as e:
        print(f"Error creating resource directories: {e}")
        return None

    # Print summary
    type_label = {
        "standard": "Standard (user + Claude can invoke)",
        "task": "Task (user-only, disable-model-invocation: true)",
        "reference": "Reference (Claude-only, user-invocable: false)",
    }
    print(f"\nSkill '{skill_name}' initialized successfully")
    print(f"  Type: {type_label.get(skill_type, skill_type)}")
    if subagent:
        print("  Execution: Subagent (context: fork)")
    if allowed_tools:
        print(f"  Allowed tools: {allowed_tools}")
    print(f"  Location: {skill_dir}")
    print("\nNext steps:")
    print("1. Edit SKILL.md — complete the TODO items and write a pushy description")
    print("2. Customize or delete example files in scripts/, references/, assets/")
    print("3. Validate: python scripts/quick_validate.py", skill_dir)
    print("4. Score:    python scripts/score_skill.py", skill_dir)

    return skill_dir


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize a new skill from template",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s my-skill --path .agent/skills\n"
            "  %(prog)s deploy-app --path .claude/skills --type task\n"
            "  %(prog)s conventions --path .agent/skills --type reference\n"
            "  %(prog)s research --path .claude/skills --subagent\n"
        ),
    )
    parser.add_argument("skill_name", help="Skill name (hyphen-case, e.g., 'data-analyzer')")
    parser.add_argument("--path", required=True, help="Output directory for the skill")
    parser.add_argument(
        "--type",
        choices=["standard", "task", "reference"],
        default="standard",
        help="Skill type: standard (default), task (user-only), reference (Claude-only)",
    )
    parser.add_argument(
        "--subagent",
        action="store_true",
        help="Run in isolated subagent (adds context: fork)",
    )
    parser.add_argument(
        "--allowed-tools",
        help='Restrict tool access (e.g., "Read, Grep, Glob")',
    )
    parser.add_argument("--description", help="Pre-fill the skill description")

    args = parser.parse_args()

    print(f"Initializing skill: {args.skill_name}")
    print(f"  Location: {args.path}")
    print(f"  Type: {args.type}")
    print()

    result = init_skill(
        args.skill_name,
        args.path,
        skill_type=args.type,
        subagent=args.subagent,
        allowed_tools=args.allowed_tools,
        description=args.description,
    )

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
