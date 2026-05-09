#!/usr/bin/env python3
"""
Skill Orchestration for Antigravity Ecosystem.

Automatic detection and invocation of skills based on task classification.
Integrates Vercel Agent Skills with the Antigravity orchestrator.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.skill_orchestration")


@dataclass
class SkillMatch:
    """Match between a task and a skill."""

    skill_name: str
    skill_path: Path
    confidence: float  # 0.0 - 1.0
    reason: str


class SkillOrchestrator:
    """Orchestrates skill selection and invocation based on task analysis."""

    def __init__(self, skills_dir: Path):
        """
        Initialize skill orchestrator.

        Args:
            skills_dir: Path to .agent/skills directory
        """
        self.skills_dir = Path(skills_dir)
        self.skill_patterns: dict[str, list[str]] = {}
        self._skill_paths: dict[str, Path] = {}
        self._load_skill_patterns()

    def _load_skill_patterns(self):
        """Load trigger patterns for each skill.

        Loads hardcoded patterns for known skills, then dynamically discovers
        additional patterns from SKILL.md frontmatter across all skill directories.
        """
        logger.info(f"Loading skill patterns from {self.skills_dir}")

        # Define patterns for vercel-agent-skills-best-practices
        self.skill_patterns["vercel-agent-skills-best-practices"] = [
            r"\bcrea(?:r|ndo) (?:una |un )?skill\b",
            r"\bvalidar skill\b",
            r"\bnueva? skill\b",
            r"\bagent skill\b",
            r"\bskill package\b",
            r"\bcreate (?:a |an )?skill\b",
            r"\bvalidate skill\b",
            r"\bnew skill\b",
            r"\bskill best practice",
            r"\bvercel skill",
        ]

        # Dynamically load patterns from SKILL.md metadata for all skills
        self._load_patterns_from_skill_metadata(self.skills_dir)

        # Also load from skills-custom directory (sibling to skills)
        skills_custom_dir = self.skills_dir.parent / "skills-custom"
        if skills_custom_dir.is_dir():
            self._load_patterns_from_skill_metadata(skills_custom_dir)

        logger.info(f"Loaded patterns for {len(self.skill_patterns)} skills")

    def _load_patterns_from_skill_metadata(self, directory: Path):
        """Scan a directory for SKILL.md files and extract trigger patterns.

        Reads YAML frontmatter from each SKILL.md, parses the 'Triggers:' section
        from the description field, and converts triggers into regex patterns.

        Args:
            directory: Directory containing skill subdirectories with SKILL.md files
        """
        if not directory.is_dir():
            return

        for skill_dir in sorted(directory.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            skill_name = skill_dir.name

            # Skip skills that already have hardcoded patterns
            if skill_name in self.skill_patterns:
                continue

            triggers = self._extract_triggers_from_skill_md(skill_md)
            if triggers:
                patterns = [re.escape(t) if not self._is_regex(t) else t for t in triggers]
                self.skill_patterns[skill_name] = patterns
                self._skill_paths[skill_name] = skill_dir
                logger.debug(f"Loaded {len(patterns)} trigger patterns for '{skill_name}'")

    @staticmethod
    def _extract_triggers_from_skill_md(skill_md_path: Path) -> list[str]:
        """Extract trigger keywords from a SKILL.md file's YAML frontmatter.

        Parses the YAML frontmatter and looks for a 'Triggers:' section at the
        end of the description field. Triggers are comma-separated keywords/phrases.

        Falls back to regex-based extraction when YAML parsing fails (common when
        descriptions contain unquoted colons like ``Triggers: foo, bar``).

        Args:
            skill_md_path: Path to a SKILL.md file

        Returns:
            List of trigger strings, or empty list if none found
        """
        try:
            content = skill_md_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read {skill_md_path}: {e}")
            return []

        # Extract YAML frontmatter between --- markers
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            return []

        frontmatter_text = fm_match.group(1)
        description = None

        # Try YAML parsing first
        try:
            metadata = yaml.safe_load(frontmatter_text)
            if isinstance(metadata, dict):
                desc_val = metadata.get("description", "")
                if isinstance(desc_val, str):
                    description = desc_val
        except yaml.YAMLError:
            # YAML fails when description has unquoted colons (e.g. "Triggers: foo").
            # Fall back to regex extraction from raw frontmatter text.
            pass

        # Fallback: extract description via regex from raw frontmatter
        if description is None:
            desc_match = re.search(
                r'^description:\s*"?(.+?)"?\s*$',
                frontmatter_text,
                re.MULTILINE,
            )
            if desc_match:
                description = desc_match.group(1)

        if not description:
            return []

        # Look for "Triggers:" section in description
        triggers_match = re.search(r"Triggers:\s*(.+)", description, re.IGNORECASE)
        if not triggers_match:
            return []

        triggers_str = triggers_match.group(1).rstrip(".")
        # Split by comma, strip whitespace and quotes
        triggers = []
        for trigger in triggers_str.split(","):
            cleaned = trigger.strip().strip('"').strip("'").strip()
            if cleaned:
                triggers.append(cleaned.lower())

        return triggers

    @staticmethod
    def _is_regex(pattern: str) -> bool:
        """Check if a string looks like a regex pattern (contains regex metacharacters).

        Args:
            pattern: String to check

        Returns:
            True if the string contains regex metacharacters
        """
        return bool(re.search(r"[\\()\[\]{}|+*?^$]", pattern))

    def _resolve_skill_path(self, skill_name: str) -> Path | None:
        """Resolve the filesystem path for a skill by name.

        Checks the cached path from dynamic loading first, then falls back to
        looking in the main skills directory.

        Args:
            skill_name: Name of the skill

        Returns:
            Path to skill directory, or None if not found
        """
        # Check if we have a cached path from dynamic loading
        if skill_name in self._skill_paths:
            return self._skill_paths[skill_name]

        # Fall back to main skills directory
        candidate = self.skills_dir / skill_name
        if candidate.exists():
            return candidate

        # Check skills-custom as last resort
        custom = self.skills_dir.parent / "skills-custom" / skill_name
        if custom.exists():
            return custom

        return None

    def classify_task(self, task: str) -> SkillMatch | None:
        """
        Classify task and find matching skill.

        Args:
            task: User task description

        Returns:
            SkillMatch if a skill matches, None otherwise
        """
        task_lower = task.lower()

        for skill_name, patterns in self.skill_patterns.items():
            for pattern in patterns:
                if re.search(pattern, task_lower):
                    skill_path = self._resolve_skill_path(skill_name)

                    if skill_path is not None and skill_path.exists():
                        match = SkillMatch(
                            skill_name=skill_name,
                            skill_path=skill_path,
                            confidence=0.9,  # High confidence for pattern match
                            reason=f"Pattern match: '{pattern}'",
                        )

                        logger.info(
                            f"Task matched skill '{skill_name}' "
                            f"(confidence: {match.confidence:.2f})"
                        )

                        return match

        logger.debug("No skill match found for task")
        return None

    def should_invoke_skill(self, task: str) -> bool:
        """
        Determine if a skill should be invoked for this task.

        Args:
            task: User task description

        Returns:
            True if a skill matches and should be invoked
        """
        match = self.classify_task(task)
        return match is not None and match.confidence >= 0.5

    def get_skill_recommendation(self, task: str) -> str | None:
        """
        Get skill recommendation for a task.

        Args:
            task: User task description

        Returns:
            Skill invocation command if recommended, None otherwise
        """
        match = self.classify_task(task)

        if not match:
            return None

        # Return command to invoke skill
        return f"Use skill: {match.skill_name}\nReason: {match.reason}"


# =============================================================================
# Integration with Orchestrator
# =============================================================================


def integrate_with_orchestrator():
    """
    Integration function to be called by orchestrator.

    This can be imported and used in orchestrator.py:

    from .skill_orchestration import integrate_with_orchestrator, SkillOrchestrator

    # In orchestrator initialization:
    skill_orch = SkillOrchestrator(SKILLS_DIR)

    # Before executing task:
    if skill_orch.should_invoke_skill(task_description):
        skill_match = skill_orch.classify_task(task_description)
        # Load and execute skill
    """
    pass


def load_skill_content(skill_path: Path) -> str | None:
    """
    Load skill content from SKILL.md.

    Args:
        skill_path: Path to skill directory

    Returns:
        Skill content (markdown) or None if not found
    """
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        logger.warning(f"SKILL.md not found at {skill_path}")
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
        logger.info(f"Loaded skill content from {skill_md}")
        return content
    except Exception as e:
        logger.error(f"Error loading skill: {e}")
        return None


def execute_skill_script(skill_path: Path, script_name: str, *args) -> int | None:
    """
    Execute a skill script.

    Args:
        skill_path: Path to skill directory
        script_name: Name of script to execute
        *args: Arguments to pass to script

    Returns:
        Exit code or None if script not found
    """
    import subprocess

    script_path = skill_path / "scripts" / script_name

    if not script_path.exists():
        logger.warning(f"Script not found: {script_path}")
        return None

    try:
        cmd = ["python", str(script_path)] + list(args)
        logger.info(f"Executing: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )

        logger.info(f"Script exited with code {result.returncode}")

        if result.stdout:
            logger.info(f"STDOUT:\n{result.stdout}")

        if result.stderr:
            logger.error(f"STDERR:\n{result.stderr}")

        return result.returncode

    except subprocess.TimeoutExpired:
        logger.error("Script execution timed out")
        return -1
    except Exception as e:
        logger.error(f"Error executing script: {e}")
        return -1


# =============================================================================
# CLI for Testing
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python skill_orchestration.py <task>")
        sys.exit(1)

    task = " ".join(sys.argv[1:])

    # Initialize
    skills_dir = Path(__file__).parent.parent / "skills"
    orchestrator = SkillOrchestrator(skills_dir)

    # Classify
    match = orchestrator.classify_task(task)

    if match:
        print("\n[OK] Skill Match Found:")
        print(f"  Skill: {match.skill_name}")
        print(f"  Confidence: {match.confidence:.2f}")
        print(f"  Reason: {match.reason}")
        print("\nRecommendation:")
        print(f"  {orchestrator.get_skill_recommendation(task)}")

        # Load skill content
        content = load_skill_content(match.skill_path)
        if content:
            print(f"\n[INFO] Skill loaded ({len(content)} chars)")
    else:
        print("\n[FAIL] No skill match found")
        print("Task will be executed by regular agent orchestration")
