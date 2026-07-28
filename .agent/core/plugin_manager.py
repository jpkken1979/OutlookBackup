#!/usr/bin/env python3
"""
Antigravity Plugin Manager - Lifecycle management for plugins.

Provides:
- Plugin discovery and validation
- Lifecycle management (install, activate, deactivate, uninstall)
- Hot-loading without restart
- Event hooks for plugin state changes
- Integration with existing plugin directory structure

Usage:
    from core.plugin_manager import PluginManager

    manager = PluginManager()
    manager.discover()
    manager.activate("conductor")
    manager.deactivate("conductor")
"""

import json
import logging
import shutil
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

logger = logging.getLogger("antigravity.plugin_manager")

if TYPE_CHECKING:
    from sdk.validators import ValidationResult

_validate_skill_fn: Callable[[Path], "ValidationResult"] | None
try:
    from sdk.validators import validate_skill as _validate_skill_fn
except Exception:  # pragma: no cover - optional validation dependency in runtime contexts
    _validate_skill_fn = None


# =============================================================================
# MODELS
# =============================================================================


class PluginState(str, Enum):
    """Plugin lifecycle states."""

    DISCOVERED = "discovered"
    INSTALLED = "installed"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class PluginAuthor(BaseModel):
    """Plugin author information."""

    name: str = "Unknown"
    email: str = ""


class PluginMetadata(BaseModel):
    """Normalized plugin metadata from plugin.json."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: PluginAuthor = Field(default_factory=PluginAuthor)
    license: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    tier: int = 0
    priority: str = "normal"
    dependencies: list[str] = Field(default_factory=list)


class PluginInfo(BaseModel):
    """Complete plugin information with state."""

    metadata: PluginMetadata
    state: PluginState = PluginState.DISCOVERED
    path: str = ""
    skills_count: int = 0
    agents_count: int = 0
    commands_count: int = 0
    activated_at: str | None = None
    deactivated_at: str | None = None
    error_message: str | None = None


class PluginEvent(BaseModel):
    """Event emitted during plugin lifecycle transitions."""

    plugin_name: str
    event_type: str
    old_state: PluginState | None = None
    new_state: PluginState
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    details: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# HOOK SYSTEM
# =============================================================================


class PluginHook:
    """Hook registration for plugin lifecycle events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Any]] = {}

    def on(self, event_type: str, handler: Any) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Any) -> None:
        """Remove a handler for an event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    async def emit(self, event: PluginEvent) -> None:
        """Emit an event to all registered handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                import inspect

                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error("Hook handler error for %s: %s", event.event_type, e)


# =============================================================================
# PLUGIN MANAGER
# =============================================================================


class PluginManager:
    """
    Manages plugin lifecycle: discovery, activation, deactivation, and removal.

    Works with the existing .agent/plugins/ directory structure:
        plugin-name/
        ├── .claude-plugin/plugin.json   (metadata, optional)
        ├── plugin.json                  (metadata, alternative location)
        ├── skills/                      (embedded skills)
        ├── agents/                      (embedded agents)
        ├── commands/                    (slash commands)
        └── ANTIGRAVITY_INTEGRATION.md   (integration docs)
    """

    def __init__(
        self,
        plugins_dir: Path | None = None,
        state_file: Path | None = None,
        orchestrator: Any | None = None,
    ) -> None:
        self._plugins_dir = plugins_dir or Path(__file__).parent.parent / "plugins"
        self._state_file = state_file or self._plugins_dir / ".plugin-state.json"
        self._plugins: dict[str, PluginInfo] = {}
        self._hooks = PluginHook()
        self._loaded = False
        self._orchestrator: Any | None = orchestrator  # AntigravityOrchestrator opcional

        self._load_state()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def hooks(self) -> PluginHook:
        """Access hook system for registering event handlers."""
        return self._hooks

    @property
    def plugins(self) -> dict[str, PluginInfo]:
        """All known plugins."""
        return dict(self._plugins)

    @property
    def active_plugins(self) -> dict[str, PluginInfo]:
        """Only active plugins."""
        return {
            name: info for name, info in self._plugins.items() if info.state == PluginState.ACTIVE
        }

    @property
    def plugins_dir(self) -> Path:
        """Plugins directory path."""
        return self._plugins_dir

    # -------------------------------------------------------------------------
    # State Persistence
    # -------------------------------------------------------------------------

    def _load_state(self) -> None:
        """Load persisted plugin states from disk."""
        if not self._state_file.exists():
            return

        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            for name, state_str in raw.get("states", {}).items():
                if name in self._plugins:
                    try:
                        self._plugins[name].state = PluginState(state_str)
                    except ValueError:
                        pass
            self._loaded = True
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load plugin state: %s", e)

    def _save_state(self) -> None:
        """Persist current plugin states to disk."""
        state_data = {
            "version": "1.0.0",
            "updated_at": datetime.now().isoformat(),
            "states": {name: info.state.value for name, info in self._plugins.items()},
        }
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(state_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # -------------------------------------------------------------------------
    # Discovery
    # -------------------------------------------------------------------------

    def _read_plugin_metadata(self, plugin_dir: Path) -> PluginMetadata | None:
        """Read and parse plugin metadata from directory."""
        # Try .claude-plugin/plugin.json first, then root plugin.json
        candidates = [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / "plugin.json",
        ]

        for candidate in candidates:
            if candidate.exists():
                try:
                    raw = json.loads(candidate.read_text(encoding="utf-8"))
                    # Normalize author field
                    author = raw.get("author", {})
                    if isinstance(author, str):
                        author = {"name": author, "email": ""}
                    raw["author"] = author
                    # Set name from directory if not in metadata
                    if "name" not in raw:
                        raw["name"] = plugin_dir.name
                    return PluginMetadata(**raw)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning("Failed to parse metadata for %s: %s", plugin_dir.name, e)
                    return None

        # No metadata file found - create minimal metadata from directory name
        return PluginMetadata(name=plugin_dir.name)

    def _count_contents(self, plugin_dir: Path) -> tuple[int, int, int]:
        """Count skills, agents, and commands in a plugin directory."""
        skills_count = 0
        agents_count = 0
        commands_count = 0

        skills_dir = plugin_dir / "skills"
        if skills_dir.exists():
            skills_count = sum(
                1 for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
            )

        agents_dir = plugin_dir / "agents"
        if agents_dir.exists():
            agents_count = sum(
                1 for d in agents_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
            )

        commands_dir = plugin_dir / "commands"
        if commands_dir.exists():
            commands_count = sum(
                1 for f in commands_dir.iterdir() if f.is_file() and not f.name.startswith(".")
            )

        return skills_count, agents_count, commands_count

    def discover(self) -> list[str]:
        """
        Scan plugins directory and discover all available plugins.

        Returns:
            List of newly discovered plugin names.
        """
        if not self._plugins_dir.exists():
            logger.warning("Plugins directory not found: %s", self._plugins_dir)
            return []

        discovered: list[str] = []
        preserved_states: dict[str, PluginState] = {
            name: info.state for name, info in self._plugins.items()
        }

        for entry in sorted(self._plugins_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue

            metadata = self._read_plugin_metadata(entry)
            if metadata is None:
                continue

            skills_count, agents_count, commands_count = self._count_contents(entry)

            # Preserve previous state if it existed
            previous_state = preserved_states.get(metadata.name, PluginState.DISCOVERED)

            self._plugins[metadata.name] = PluginInfo(
                metadata=metadata,
                state=previous_state,
                path=str(entry),
                skills_count=skills_count,
                agents_count=agents_count,
                commands_count=commands_count,
            )

            if metadata.name not in preserved_states:
                discovered.append(metadata.name)

        # Load persisted states after discovery
        self._load_state()
        self._loaded = True

        logger.info("Discovered %d plugins (%d new)", len(self._plugins), len(discovered))
        return discovered

    # -------------------------------------------------------------------------
    # Lifecycle Operations
    # -------------------------------------------------------------------------

    async def activate(self, name: str) -> PluginInfo:
        """
        Activate a plugin, making its skills and agents available.

        Args:
            name: Plugin name to activate.

        Returns:
            Updated PluginInfo.

        Raises:
            KeyError: If plugin not found.
            RuntimeError: If plugin is in error state.
        """
        info = self._get_plugin_or_raise(name)

        if info.state == PluginState.ACTIVE:
            logger.info("Plugin %s is already active", name)
            return info

        if info.state == PluginState.ERROR:
            raise RuntimeError(f"Plugin {name} is in error state: {info.error_message}")

        # Check dependencies
        missing_deps = self._check_dependencies(info)
        if missing_deps:
            raise RuntimeError(f"Plugin {name} has unmet dependencies: {', '.join(missing_deps)}")

        # Validate embedded skills before activation.
        self._validate_plugin_before_activate(info)

        old_state = info.state
        info.state = PluginState.ACTIVE
        info.activated_at = datetime.now().isoformat()
        info.error_message = None

        self._save_state()

        event = PluginEvent(
            plugin_name=name,
            event_type="activated",
            old_state=old_state,
            new_state=PluginState.ACTIVE,
            details={
                "skills": info.skills_count,
                "agents": info.agents_count,
            },
        )
        await self._hooks.emit(event)

        # Notificar al orchestrator para registrar skills en el pool
        if self._orchestrator is not None:
            plugin_skills = self._get_plugin_skill_names(info)
            self._orchestrator.register_plugin_skills(name, plugin_skills)

        logger.info("Activated plugin: %s (skills=%d)", name, info.skills_count)
        return info

    async def deactivate(self, name: str) -> PluginInfo:
        """
        Deactivate a plugin, removing its skills and agents from availability.

        Args:
            name: Plugin name to deactivate.

        Returns:
            Updated PluginInfo.

        Raises:
            KeyError: If plugin not found.
        """
        info = self._get_plugin_or_raise(name)

        if info.state == PluginState.INACTIVE:
            logger.info("Plugin %s is already inactive", name)
            return info

        # Check if other active plugins depend on this one
        dependents = self._find_dependents(name)
        if dependents:
            logger.warning(
                "Deactivating %s which is depended on by: %s",
                name,
                ", ".join(dependents),
            )

        old_state = info.state
        info.state = PluginState.INACTIVE
        info.deactivated_at = datetime.now().isoformat()

        self._save_state()

        event = PluginEvent(
            plugin_name=name,
            event_type="deactivated",
            old_state=old_state,
            new_state=PluginState.INACTIVE,
        )
        await self._hooks.emit(event)

        # Notificar al orchestrator para eliminar skills del pool
        if self._orchestrator is not None:
            self._orchestrator.unregister_plugin_skills(name)

        logger.info("Deactivated plugin: %s", name)
        return info

    async def install(self, source_path: Path, name: str | None = None) -> PluginInfo:
        """
        Install a plugin from a source directory.

        Copies the plugin directory into the plugins directory.

        Args:
            source_path: Path to the plugin source directory.
            name: Override name (defaults to directory name).

        Returns:
            PluginInfo for the installed plugin.

        Raises:
            FileNotFoundError: If source path doesn't exist.
            FileExistsError: If plugin already installed.
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Plugin source not found: {source_path}")

        plugin_name = name or source_path.name
        target_dir = self._plugins_dir / plugin_name

        if target_dir.exists():
            raise FileExistsError(f"Plugin {plugin_name} already exists at {target_dir}")

        # Copy plugin directory
        shutil.copytree(source_path, target_dir)
        logger.info("Copied plugin from %s to %s", source_path, target_dir)

        # Discover the new plugin
        metadata = self._read_plugin_metadata(target_dir)
        if metadata is None:
            metadata = PluginMetadata(name=plugin_name)

        skills_count, agents_count, commands_count = self._count_contents(target_dir)

        info = PluginInfo(
            metadata=metadata,
            state=PluginState.INSTALLED,
            path=str(target_dir),
            skills_count=skills_count,
            agents_count=agents_count,
            commands_count=commands_count,
        )
        self._plugins[plugin_name] = info
        self._save_state()

        event = PluginEvent(
            plugin_name=plugin_name,
            event_type="installed",
            old_state=None,
            new_state=PluginState.INSTALLED,
            details={"source": str(source_path)},
        )
        await self._hooks.emit(event)

        logger.info("Installed plugin: %s", plugin_name)
        return info

    async def uninstall(self, name: str, keep_data: bool = False) -> None:
        """
        Uninstall a plugin.

        Args:
            name: Plugin name to uninstall.
            keep_data: If True, only deactivate without deleting files.

        Raises:
            KeyError: If plugin not found.
            RuntimeError: If plugin is active (must deactivate first).
        """
        info = self._get_plugin_or_raise(name)

        if info.state == PluginState.ACTIVE:
            await self.deactivate(name)

        if not keep_data:
            plugin_path = Path(info.path)
            if plugin_path.exists():
                # Create backup before deletion
                backup_dir = self._plugins_dir / ".backups"
                backup_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                backup_path = backup_dir / f"{name}.{timestamp}"
                shutil.copytree(plugin_path, backup_path)
                logger.info("Backup created at %s", backup_path)

                shutil.rmtree(plugin_path)
                logger.info("Removed plugin directory: %s", plugin_path)

        event = PluginEvent(
            plugin_name=name,
            event_type="uninstalled",
            old_state=info.state,
            new_state=PluginState.DISCOVERED,
            details={"kept_data": keep_data},
        )
        await self._hooks.emit(event)

        del self._plugins[name]
        self._save_state()

        logger.info("Uninstalled plugin: %s (kept_data=%s)", name, keep_data)

    # -------------------------------------------------------------------------
    # Hot-Loading
    # -------------------------------------------------------------------------

    async def reload(self, name: str) -> PluginInfo:
        """
        Hot-reload a plugin: re-read metadata and contents without restart.

        Preserves activation state. Useful after editing plugin files.

        Args:
            name: Plugin name to reload.

        Returns:
            Updated PluginInfo.

        Raises:
            KeyError: If plugin not found.
        """
        info = self._get_plugin_or_raise(name)
        plugin_path = Path(info.path)

        if not plugin_path.exists():
            info.state = PluginState.ERROR
            info.error_message = f"Plugin directory not found: {plugin_path}"
            self._save_state()
            raise FileNotFoundError(info.error_message)

        previous_state = info.state

        # Re-read metadata
        metadata = self._read_plugin_metadata(plugin_path)
        if metadata is None:
            metadata = PluginMetadata(name=name)

        skills_count, agents_count, commands_count = self._count_contents(plugin_path)

        # Update plugin info preserving state
        info.metadata = metadata
        info.skills_count = skills_count
        info.agents_count = agents_count
        info.commands_count = commands_count

        self._save_state()

        event = PluginEvent(
            plugin_name=name,
            event_type="reloaded",
            old_state=previous_state,
            new_state=previous_state,
            details={
                "skills": skills_count,
                "agents": agents_count,
            },
        )
        await self._hooks.emit(event)

        logger.info("Reloaded plugin: %s (state preserved: %s)", name, previous_state)
        return info

    async def reload_all(self) -> list[str]:
        """
        Hot-reload all plugins: re-discover and update without losing state.

        Returns:
            List of plugin names that were reloaded.
        """
        self.discover()
        reloaded = []
        for name in list(self._plugins.keys()):
            try:
                await self.reload(name)
                reloaded.append(name)
            except Exception as e:
                logger.error("Failed to reload plugin %s: %s", name, e)

        return reloaded

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def get(self, name: str) -> PluginInfo | None:
        """Get plugin info by name, or None if not found."""
        return self._plugins.get(name)

    def list_plugins(
        self,
        state: PluginState | None = None,
        tag: str | None = None,
        category: str | None = None,
    ) -> list[PluginInfo]:
        """
        List plugins with optional filtering.

        Args:
            state: Filter by state.
            tag: Filter by tag.
            category: Filter by category.

        Returns:
            List of matching PluginInfo objects.
        """
        results = list(self._plugins.values())

        if state is not None:
            results = [p for p in results if p.state == state]

        if tag is not None:
            tag_lower = tag.lower()
            results = [p for p in results if tag_lower in [t.lower() for t in p.metadata.tags]]

        if category is not None:
            cat_lower = category.lower()
            results = [p for p in results if p.metadata.category.lower() == cat_lower]

        return results

    def search(self, query: str) -> list[PluginInfo]:
        """
        Search plugins by name, description, or tags.

        Args:
            query: Search query string.

        Returns:
            List of matching PluginInfo objects sorted by relevance.
        """
        query_lower = query.lower()
        scored: list[tuple[float, PluginInfo]] = []

        for info in self._plugins.values():
            score = self._score_plugin(query_lower, info)
            if score > 0:
                scored.append((score, info))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [info for _, info in scored]

    @staticmethod
    def _score_plugin(query_lower: str, info: PluginInfo) -> float:
        """Calcula el score de relevancia de un plugin para una query.

        Args:
            query_lower: Query ya en minúsculas.
            info: PluginInfo a puntuar.

        Returns:
            Score acumulado (name > description > tag > category/capability).
        """
        score = 0.0
        name = info.metadata.name.lower()

        # Name match (highest weight)
        if query_lower in name:
            score += 10.0
        if name == query_lower:
            score += 20.0

        # Description match
        if query_lower in info.metadata.description.lower():
            score += 5.0

        # Tag match
        score += sum(3.0 for tag in info.metadata.tags if query_lower in tag.lower())

        # Category match
        if query_lower in info.metadata.category.lower():
            score += 2.0

        # Capability match
        score += sum(2.0 for cap in info.metadata.capabilities if query_lower in cap.lower())

        return score

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about plugins."""
        total = len(self._plugins)
        by_state: dict[str, int] = {}
        total_skills = 0
        total_agents = 0
        total_commands = 0

        for info in self._plugins.values():
            state_name = info.state.value
            by_state[state_name] = by_state.get(state_name, 0) + 1
            total_skills += info.skills_count
            total_agents += info.agents_count
            total_commands += info.commands_count

        return {
            "total_plugins": total,
            "by_state": by_state,
            "total_skills": total_skills,
            "total_agents": total_agents,
            "total_commands": total_commands,
        }

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    async def activate_all(self) -> list[str]:
        """Activate all discovered/installed/inactive plugins."""
        activated = []
        for name, info in self._plugins.items():
            if info.state in (
                PluginState.DISCOVERED,
                PluginState.INSTALLED,
                PluginState.INACTIVE,
            ):
                try:
                    await self.activate(name)
                    activated.append(name)
                except Exception as e:
                    logger.error("Failed to activate %s: %s", name, e)
        return activated

    async def deactivate_all(self) -> list[str]:
        """Deactivate all active plugins."""
        deactivated = []
        for name, info in list(self._plugins.items()):
            if info.state == PluginState.ACTIVE:
                try:
                    await self.deactivate(name)
                    deactivated.append(name)
                except Exception as e:
                    logger.error("Failed to deactivate %s: %s", name, e)
        return deactivated

    # -------------------------------------------------------------------------
    # Dependency Checks
    # -------------------------------------------------------------------------

    def _check_dependencies(self, info: PluginInfo) -> list[str]:
        """Check if all plugin dependencies are satisfied."""
        missing = []
        for dep in info.metadata.dependencies:
            dep_info = self._plugins.get(dep)
            if dep_info is None or dep_info.state != PluginState.ACTIVE:
                missing.append(dep)
        return missing

    def _find_dependents(self, name: str) -> list[str]:
        """Find active plugins that depend on the given plugin."""
        dependents = []
        for other_name, other_info in self._plugins.items():
            if other_info.state == PluginState.ACTIVE:
                if name in other_info.metadata.dependencies:
                    dependents.append(other_name)
        return dependents

    # -------------------------------------------------------------------------
    # Orchestrator Integration
    # -------------------------------------------------------------------------

    @property
    def orchestrator(self) -> Any | None:
        """Orquestador registrado para notificaciones de skills."""
        return self._orchestrator

    @orchestrator.setter
    def orchestrator(self, value: Any | None) -> None:
        """Asigna un orquestador para recibir notificaciones de skills.

        Args:
            value: Instancia de AntigravityOrchestrator o None.
        """
        self._orchestrator = value
        if value is not None:
            logger.info("Orchestrator registered in PluginManager")

    def _get_plugin_skill_names(self, info: PluginInfo) -> list[str]:
        """Obtiene los nombres de skills de un plugin desde su directorio.

        Lee el directorio skills/ del plugin y retorna los nombres de skills.

        Args:
            info: Información del plugin.

        Returns:
            Lista de nombres de skills del plugin.
        """
        skills: list[str] = []
        skills_dir = Path(info.path) / "skills"
        if skills_dir.is_dir():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skills.append(skill_dir.name)
        return list(set(skills))

    def _validate_plugin_before_activate(self, info: PluginInfo) -> None:
        """Validate plugin assets before activation.

        For now we validate embedded skills using sdk.validators.validate_skill.
        Warnings are logged and do not block activation.
        Errors block activation with RuntimeError.
        """
        if _validate_skill_fn is None:
            logger.debug("Skill validator not available; skipping plugin validation")
            return

        plugin_path = Path(info.path)
        skills_dir = plugin_path / "skills"
        if not skills_dir.exists() or not skills_dir.is_dir():
            return

        validation_errors: list[str] = []
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue

            result = _validate_skill_fn(skill_dir)
            for warning in result.warnings:
                logger.warning(
                    "Plugin '%s' skill '%s' warning: %s",
                    info.metadata.name,
                    skill_dir.name,
                    warning,
                )
            if not result.valid:
                for error in result.errors:
                    validation_errors.append(f"{skill_dir.name}: {error}")

        if validation_errors:
            raise RuntimeError(
                f"Plugin {info.metadata.name} validation failed: "
                + "; ".join(validation_errors[:20])
            )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_plugin_or_raise(self, name: str) -> PluginInfo:
        """Get plugin by name or raise KeyError."""
        info = self._plugins.get(name)
        if info is None:
            available = ", ".join(sorted(self._plugins.keys())[:10])
            raise KeyError(f"Plugin '{name}' not found. Available: {available}...")
        return info

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Export all plugin data as dictionary."""
        return {
            "plugins_dir": str(self._plugins_dir),
            "stats": self.get_stats(),
            "plugins": {name: info.model_dump() for name, info in self._plugins.items()},
        }
