"""Agent Skill Manager - Manages skill loading for agents.

Provides:
- Skill discovery via SkillRegistry or filesystem fallback
- Skill script registration as tools
- Skill metadata loading

Version: 1.0.0
"""

import importlib
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_base import AntigravityAgent

logger = logging.getLogger("antigravity.skills")


def _import_sibling_module(module_name: str) -> Any:
    """Imports a sibling module without relying on relative imports."""
    base_module = __name__.rpartition(".")[0]
    candidates = [f"{base_module}.{module_name}"] if base_module else []
    candidates.append(module_name)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return importlib.import_module(candidate)
        except Exception as error:
            last_error = error

    if last_error is not None:
        raise last_error
    raise ImportError(f"Unable to import sibling module: {module_name}")


class AgentSkillManager:
    """Gestiona la carga de skills para agentes."""

    def __init__(self, agent_instance: "AntigravityAgent"):
        """Initialize skill manager with agent instance."""
        self.agent = agent_instance
        logger.debug(f"SkillManager initialized for {agent_instance.identity.name}")

    def load_skill(self, skill_name: str, skills_dir: Path | None = None) -> bool:
        """Load a skill and its associated tools.

        Uses centralized SkillRegistry (singleton) if available for O(1) lookup.
        Falls back to manual directory search if registry not available.

        Args:
            skill_name: Name of the skill to load
            skills_dir: Directory containing skills

        Returns:
            True if skill loaded successfully
        """
        # Try centralized registry first
        try:
            skill_registry_module = _import_sibling_module("skill_registry")
            SkillRegistry = skill_registry_module.SkillRegistry

            registry = SkillRegistry.instance()
            skill = registry.get(skill_name, lazy=True)
            if skill:
                skill_path = skill.path
            else:
                # Fallback to manual search
                skills_dir = skills_dir or Path(__file__).parent.parent / "skills"
                skill_path = skills_dir / skill_name
        except (ImportError, RuntimeError, AttributeError):
            # Registry not available, fallback to manual search
            skills_dir = skills_dir or Path(__file__).parent.parent / "skills"
            skill_path = skills_dir / skill_name

        if not skill_path.exists():
            logger.warning(f"Skill not found: {skill_name}")
            return False

        # Read skill metadata
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            logger.debug(f"Loading skill metadata from {skill_md}")

        # Load skill scripts as tools
        scripts_dir = skill_path / "scripts"
        if scripts_dir.exists():
            # Import at runtime to avoid circular dependency
            from agent_base import Tool

            for script in scripts_dir.glob("*.py"):
                tool_name = f"{skill_name}_{script.stem}"
                self.agent.register_tool(
                    Tool(
                        name=tool_name,
                        description=f"Script from {skill_name} skill",
                        func=lambda s=script: self._run_skill_script(s),
                    )
                )

        self.agent.skills_loaded.append(skill_name)
        logger.info(f"Loaded skill: {skill_name}")
        return True

    @staticmethod
    def _run_skill_script(script_path: Path) -> str:
        """Run a skill script and return output.

        Args:
            script_path: Path to the skill script

        Returns:
            Script output (stdout or stderr)
        """
        result = subprocess.run(
            ["python", str(script_path)], capture_output=True, text=True, timeout=120
        )

        return result.stdout or result.stderr
