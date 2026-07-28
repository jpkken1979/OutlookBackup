#!/usr/bin/env python3
"""
Antigravity Plugin CLI - Command-line interface for plugin management.

Usage:
    python .agent/scripts/plugin-cli.py list
    python .agent/scripts/plugin-cli.py search "data engineering"
    python .agent/scripts/plugin-cli.py activate conductor
    python .agent/scripts/plugin-cli.py deactivate conductor
    python .agent/scripts/plugin-cli.py info conductor
    python .agent/scripts/plugin-cli.py stats
    python .agent/scripts/plugin-cli.py reload conductor
    python .agent/scripts/plugin-cli.py reload --all
    python .agent/scripts/plugin-cli.py install /path/to/plugin
    python .agent/scripts/plugin-cli.py uninstall plugin-name
    python .agent/scripts/plugin-cli.py index build
    python .agent/scripts/plugin-cli.py index export registry.json
    python .agent/scripts/plugin-cli.py deps conductor
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure core modules are importable
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / ".agent"))
sys.path.insert(0, str(_project_root))

from core.plugin_manager import PluginManager, PluginState  # noqa: E402
from core.plugin_registry import PluginRegistry  # noqa: E402

logger = logging.getLogger("antigravity.plugin_cli")


# =============================================================================
# FORMATTING HELPERS
# =============================================================================

# Try to use the actual module path at import time
_AGENT_DIR = Path(__file__).resolve().parent.parent


def _get_manager() -> PluginManager:
    """Create and initialize a PluginManager."""
    manager = PluginManager(plugins_dir=_AGENT_DIR / "plugins")
    manager.discover()
    return manager


def _get_registry() -> PluginRegistry:
    """Create and initialize a PluginRegistry."""
    return PluginRegistry(plugins_dir=_AGENT_DIR / "plugins")


STATE_COLORS = {
    "active": "\033[32m",  # green
    "inactive": "\033[33m",  # yellow
    "discovered": "\033[36m",  # cyan
    "installed": "\033[34m",  # blue
    "error": "\033[31m",  # red
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def _colorize(text: str, color: str) -> str:
    """Apply ANSI color to text."""
    return f"{color}{text}{RESET}"


def _state_badge(state: str) -> str:
    """Create a colored state badge."""
    color = STATE_COLORS.get(state, "")
    return _colorize(f"[{state.upper()}]", color)


# =============================================================================
# COMMANDS
# =============================================================================


def cmd_list(args: argparse.Namespace) -> None:
    """List all plugins."""
    manager = _get_manager()

    state_filter = None
    if args.state:
        try:
            state_filter = PluginState(args.state)
        except ValueError:
            print(f"Invalid state: {args.state}")
            print(f"Valid states: {', '.join(s.value for s in PluginState)}")
            sys.exit(1)

    plugins = manager.list_plugins(state=state_filter)

    if not plugins:
        print("No plugins found.")
        return

    if args.json:
        data = [
            {
                "name": p.metadata.name,
                "version": p.metadata.version,
                "state": p.state.value,
                "skills": p.skills_count,
                "agents": p.agents_count,
                "description": p.metadata.description[:80],
            }
            for p in plugins
        ]
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    # Table output
    print(f"\n{BOLD}Antigravity Plugins ({len(plugins)}){RESET}\n")
    print(f"  {'PLUGIN':<35} {'VERSION':<10} {'STATE':<15} {'SKILLS':<8} {'AGENTS':<8}")
    print(f"  {'─' * 35} {'─' * 10} {'─' * 15} {'─' * 8} {'─' * 8}")

    for p in sorted(plugins, key=lambda x: x.metadata.name):
        badge = _state_badge(p.state.value)
        print(
            f"  {p.metadata.name:<35} {p.metadata.version:<10} {badge:<24} "
            f"{p.skills_count:<8} {p.agents_count:<8}"
        )

    stats = manager.get_stats()
    print(
        f"\n  {DIM}Total: {stats['total_plugins']} plugins | "
        f"{stats['total_skills']} skills | "
        f"{stats['total_agents']} agents{RESET}\n"
    )


def cmd_search(args: argparse.Namespace) -> None:
    """Search plugins."""
    registry = _get_registry()
    registry.build_index()

    results = registry.search(
        args.query,
        category=args.category,
        tag=args.tag,
        limit=args.limit,
    )

    if not results:
        print(f"No results for: {args.query}")
        return

    if args.json:
        data = [
            {
                "name": r.entry.name,
                "score": round(r.score, 1),
                "description": r.entry.description[:100],
                "skills": r.entry.skills,
                "match_reasons": r.match_reasons,
            }
            for r in results
        ]
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print(f"\n{BOLD}Search results for '{args.query}' ({len(results)} found){RESET}\n")

    for i, r in enumerate(results, 1):
        score_bar = ">" * min(int(r.score / 2), 20)
        print(f"  {i}. {BOLD}{r.entry.name}{RESET} v{r.entry.version}")
        print(f"     {DIM}{r.entry.description[:80]}{RESET}")
        print(f"     Skills: {', '.join(r.entry.skills[:5]) or 'none'}")
        print(f"     Score: {_colorize(score_bar, STATE_COLORS['active'])} ({r.score:.1f})")
        print()


def cmd_activate(args: argparse.Namespace) -> None:
    """Activate a plugin."""
    manager = _get_manager()

    async def _run() -> None:
        try:
            info = await manager.activate(args.name)
            if args.json:
                print(json.dumps(info.model_dump(), indent=2, ensure_ascii=False))
                return
            print(f"Activated: {info.metadata.name} (skills={info.skills_count})")
        except KeyError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)

    asyncio.run(_run())


def cmd_deactivate(args: argparse.Namespace) -> None:
    """Deactivate a plugin."""
    manager = _get_manager()

    async def _run() -> None:
        try:
            info = await manager.deactivate(args.name)
            if args.json:
                print(json.dumps(info.model_dump(), indent=2, ensure_ascii=False))
                return
            print(f"Deactivated: {info.metadata.name}")
        except KeyError as e:
            print(f"Error: {e}")
            sys.exit(1)

    asyncio.run(_run())


def cmd_info(args: argparse.Namespace) -> None:
    """Show detailed plugin info."""
    manager = _get_manager()
    info = manager.get(args.name)

    if info is None:
        print(f"Plugin not found: {args.name}")
        sys.exit(1)

    if args.json:
        print(json.dumps(info.model_dump(), indent=2, ensure_ascii=False))
        return

    m = info.metadata
    print(f"\n{BOLD}{m.name}{RESET} v{m.version}")
    print(f"{'─' * 50}")
    print(f"  State:       {_state_badge(info.state.value)}")
    print(f"  Description: {m.description[:80] or 'N/A'}")
    print(f"  Author:      {m.author.name}")
    print(f"  License:     {m.license or 'N/A'}")
    print(f"  Category:    {m.category or 'N/A'}")
    print(f"  Tags:        {', '.join(m.tags) or 'none'}")
    print(f"  Skills:      {info.skills_count}")
    print(f"  Agents:      {info.agents_count}")
    print(f"  Commands:    {info.commands_count}")
    print(f"  Path:        {info.path}")
    if m.dependencies:
        print(f"  Dependencies: {', '.join(m.dependencies)}")
    if info.activated_at:
        print(f"  Activated:   {info.activated_at}")
    if info.error_message:
        print(f"  Error:       {_colorize(info.error_message, STATE_COLORS['error'])}")
    print()


def cmd_stats(args: argparse.Namespace) -> None:
    """Show plugin statistics."""
    manager = _get_manager()
    stats = manager.get_stats()

    registry = _get_registry()
    registry.build_index()
    reg_stats = registry.get_stats()

    if args.json:
        print(json.dumps({**stats, **reg_stats}, indent=2))
        return

    print(f"\n{BOLD}Plugin Ecosystem Statistics{RESET}\n")
    print(f"  Total Plugins:  {stats['total_plugins']}")
    print(f"  Total Skills:   {stats['total_skills']}")
    print(f"  Total Agents:   {stats['total_agents']}")
    print(f"  Total Commands: {stats['total_commands']}")
    print()

    print(f"  {BOLD}By State:{RESET}")
    for state, count in sorted(stats["by_state"].items()):
        print(f"    {_state_badge(state)} {count}")
    print()

    if reg_stats.get("top_categories"):
        print(f"  {BOLD}Top Categories:{RESET}")
        for cat, count in list(reg_stats["top_categories"].items())[:8]:
            bar = "=" * min(count * 2, 30)
            print(f"    {cat:<20} {_colorize(bar, STATE_COLORS['active'])} {count}")
    print()


def cmd_reload(args: argparse.Namespace) -> None:
    """Hot-reload plugin(s)."""
    manager = _get_manager()

    async def _run() -> None:
        if args.all:
            reloaded = await manager.reload_all()
            print(f"Reloaded {len(reloaded)} plugins")
        else:
            try:
                info = await manager.reload(args.name)
                print(f"Reloaded: {info.metadata.name} (skills={info.skills_count})")
            except KeyError as e:
                print(f"Error: {e}")
                sys.exit(1)

    asyncio.run(_run())


def cmd_install(args: argparse.Namespace) -> None:
    """Install a plugin from a directory."""
    manager = _get_manager()
    source = Path(args.source)

    async def _run() -> None:
        try:
            info = await manager.install(source, name=args.name)
            print(f"Installed: {info.metadata.name}")
            if args.activate:
                await manager.activate(info.metadata.name)
                print(f"Activated: {info.metadata.name}")
        except (FileNotFoundError, FileExistsError) as e:
            print(f"Error: {e}")
            sys.exit(1)

    asyncio.run(_run())


def cmd_uninstall(args: argparse.Namespace) -> None:
    """Uninstall a plugin."""
    manager = _get_manager()

    async def _run() -> None:
        try:
            if not args.force:
                confirm = input(f"Uninstall {args.name}? (y/N): ").strip().lower()
                if confirm != "y":
                    print("Cancelled.")
                    return
            await manager.uninstall(args.name, keep_data=args.keep_data)
            print(f"Uninstalled: {args.name}")
        except KeyError as e:
            print(f"Error: {e}")
            sys.exit(1)

    asyncio.run(_run())


def cmd_index(args: argparse.Namespace) -> None:
    """Registry index operations."""
    registry = _get_registry()

    if args.action == "build":
        index = registry.build_index()
        print(f"Index built: {index.total_plugins} plugins, {index.total_skills} skills")

    elif args.action == "export":
        registry.load_index()
        path = registry.export_index(args.output or "registry-export.json")
        print(f"Exported to: {path}")

    elif args.action == "import":
        if not args.input:
            print("Error: --input required for import")
            sys.exit(1)
        registry.load_index()
        index = registry.import_index(args.input)
        print(f"Imported. Total: {index.total_plugins} plugins")

    elif args.action == "stats":
        registry.load_index()
        stats = registry.get_stats()
        print(json.dumps(stats, indent=2))


def cmd_deps(args: argparse.Namespace) -> None:
    """Show dependency tree for a plugin."""
    registry = _get_registry()
    registry.build_index()

    try:
        deps = registry.resolve_dependencies(args.name)
        if len(deps) <= 1:
            print(f"{args.name}: no dependencies")
        else:
            print(f"\n{BOLD}Dependency tree for {args.name}:{RESET}\n")
            for i, dep in enumerate(deps):
                prefix = "  └─ " if i == len(deps) - 1 else "  ├─ "
                marker = " (target)" if dep == args.name else ""
                print(f"{prefix}{dep}{marker}")
            print()
    except KeyError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Antigravity Plugin Manager CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  plugin-cli.py list                     List all plugins
  plugin-cli.py list --state active      List only active plugins
  plugin-cli.py search "api testing"     Search plugins
  plugin-cli.py activate conductor       Activate a plugin
  plugin-cli.py reload --all             Hot-reload all plugins
  plugin-cli.py stats                    Show ecosystem statistics
        """,
    )
    parser.add_argument("--json", action="store_true", default=False, help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    p_list = subparsers.add_parser("list", aliases=["ls"], help="List plugins")
    p_list.add_argument("--state", "-s", help="Filter by state")
    p_list.add_argument("--json", action="store_true", default=False)

    # search
    p_search = subparsers.add_parser("search", aliases=["find"], help="Search plugins")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--category", "-c", help="Filter by category")
    p_search.add_argument("--tag", "-t", help="Filter by tag")
    p_search.add_argument("--limit", "-l", type=int, default=20)
    p_search.add_argument("--json", action="store_true", default=False)

    # activate
    p_activate = subparsers.add_parser("activate", aliases=["on"], help="Activate plugin")
    p_activate.add_argument("name", help="Plugin name")
    p_activate.add_argument("--json", action="store_true", default=False)

    # deactivate
    p_deactivate = subparsers.add_parser("deactivate", aliases=["off"], help="Deactivate plugin")
    p_deactivate.add_argument("name", help="Plugin name")
    p_deactivate.add_argument("--json", action="store_true", default=False)

    # info
    p_info = subparsers.add_parser("info", aliases=["show"], help="Show plugin details")
    p_info.add_argument("name", help="Plugin name")
    p_info.add_argument("--json", action="store_true", default=False)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show ecosystem statistics")
    p_stats.add_argument("--json", action="store_true", default=False)

    # reload
    p_reload = subparsers.add_parser("reload", help="Hot-reload plugin(s)")
    p_reload.add_argument("name", nargs="?", help="Plugin name")
    p_reload.add_argument("--all", "-a", action="store_true", help="Reload all")

    # install
    p_install = subparsers.add_parser("install", help="Install plugin from directory")
    p_install.add_argument("source", help="Source directory path")
    p_install.add_argument("--name", "-n", help="Override plugin name")
    p_install.add_argument("--activate", "-a", action="store_true", help="Activate after install")

    # uninstall
    p_uninstall = subparsers.add_parser("uninstall", aliases=["remove"], help="Uninstall plugin")
    p_uninstall.add_argument("name", help="Plugin name")
    p_uninstall.add_argument("--force", "-f", action="store_true")
    p_uninstall.add_argument("--keep-data", action="store_true")

    # index
    p_index = subparsers.add_parser("index", help="Registry index operations")
    p_index.add_argument("action", choices=["build", "export", "import", "stats"])
    p_index.add_argument("--output", "-o", help="Output file for export")
    p_index.add_argument("--input", "-i", help="Input file for import")

    # deps
    p_deps = subparsers.add_parser("deps", help="Show dependency tree")
    p_deps.add_argument("name", help="Plugin name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s] %(message)s",
    )

    commands = {
        "list": cmd_list,
        "ls": cmd_list,
        "search": cmd_search,
        "find": cmd_search,
        "activate": cmd_activate,
        "on": cmd_activate,
        "deactivate": cmd_deactivate,
        "off": cmd_deactivate,
        "info": cmd_info,
        "show": cmd_info,
        "stats": cmd_stats,
        "reload": cmd_reload,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "remove": cmd_uninstall,
        "index": cmd_index,
        "deps": cmd_deps,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
