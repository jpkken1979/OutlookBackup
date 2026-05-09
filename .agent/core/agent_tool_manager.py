"""Agent Tool Manager - Manages tools available to agents.

Provides:
- Tool registration and execution
- Default tools (read_file, write_file, search_codebase, execute_command)
- Tool execution with error handling and timing
- Permission-based access control

Version: 1.0.0
"""

import inspect
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_base import AntigravityAgent, Tool, ToolResult

logger = logging.getLogger("antigravity.tools")

# WRITABLE_ROOTS: comma-separated list of directories allowed for write_file
# Falls back to project root if not set.
def _get_writable_roots() -> list[Path]:
    """Parse WRITABLE_ROOTS env var into a list of resolved Path objects."""
    env_val = os.environ.get("WRITABLE_ROOTS", "").strip()
    if not env_val:
        # Fallback: use the repo root
        repo_root = Path(__file__).resolve().parent.parent.parent
        return [repo_root]
    roots = []
    for part in env_val.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            roots.append(Path(part).resolve())
        except (ValueError, OSError):
            logger.warning("WRITABLE_ROOTS: invalid path ignored: %s", part)
    return roots


def _is_path_in_writable_roots(path: Path, writable_roots: list[Path]) -> bool:
    """Check if resolved path is contained in any of the writable_roots."""
    try:
        resolved = path.resolve()
    except (ValueError, OSError):
        return False
    for root in writable_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


# Security utilities (importadas aqui para evitar circular imports con agent_base)
try:
    from .security_utils import is_within_root
except ImportError:
    from security_utils import is_within_root


class AgentToolManager:
    """Gestiona herramientas disponibles para agentes."""

    def __init__(self, agent_instance: "AntigravityAgent"):
        """Initialize tool manager with agent instance."""
        self.agent = agent_instance
        self.tools: dict[str, Tool] = {}
        logger.debug(f"ToolManager initialized for {agent_instance.identity.name}")

    def register_tool(self, tool: "Tool") -> None:
        """Register a tool for this agent to use."""
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def setup_default_tools(self) -> None:
        """Setup default tools available to all agents."""
        # Import at runtime to avoid circular dependency
        from agent_base import Tool

        self.register_tool(
            Tool(name="read_file", description="Read contents of a file", func=self._tool_read_file)
        )

        self.register_tool(
            Tool(
                name="write_file",
                description="Write contents to a file",
                func=self._tool_write_file,
            )
        )

        self.register_tool(
            Tool(
                name="search_codebase",
                description="Search for patterns in the codebase",
                func=self._tool_search_codebase,
            )
        )

        self.register_tool(
            Tool(
                name="execute_command",
                description="Execute a shell command",
                func=self._tool_execute_command,
            )
        )

    async def use_tool(self, tool_name: str, **kwargs) -> "ToolResult":
        """
        Execute a registered tool.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments for the tool

        Returns:
            ToolResult with output or error
        """
        # Import at runtime to avoid circular dependency
        from agent_base import ToolResult

        if tool_name not in self.tools:
            return ToolResult(success=False, output=None, error=f"Tool not found: {tool_name}")

        tool = self.tools[tool_name]
        start_time = datetime.now()

        try:
            if inspect.iscoroutinefunction(tool.func):
                output = await tool.func(**kwargs)
            else:
                output = tool.func(**kwargs)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.debug(
                f"Tool {tool_name} executed in {execution_time:.1f}ms by {self.agent.identity.name}"
            )

            return ToolResult(success=True, output=output, execution_time_ms=execution_time)

        except Exception as e:
            logger.error(f"Tool {tool_name} failed for {self.agent.identity.name}: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    # =========================================================================
    # DEFAULT TOOL IMPLEMENTATIONS
    # =========================================================================

    def _tool_read_file(self, path: str) -> str:
        """Read a file's contents."""
        if not self.agent.capabilities.can_access_files:
            raise PermissionError("File access not allowed")

        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return file_path.read_text(encoding="utf-8")

    def _tool_write_file(self, path: str, content: str) -> str:
        """Write content to a file.

        Security:
        - Validates path against WRITABLE_ROOTS (env var, comma-separated).
          If not set, defaults to the repo root.
        - Blocks directory traversal attempts.
        - Path must resolve inside one of the allowed roots.
        """
        if not self.agent.capabilities.can_access_files:
            raise PermissionError("File access not allowed")

        writable_roots = _get_writable_roots()
        file_path = Path(path).resolve()

        if not _is_path_in_writable_roots(file_path, writable_roots):
            roots_str = ", ".join(str(r) for r in writable_roots)
            raise PermissionError(
                f"Path outside WRITABLE_ROOTS: {path!r} "
                f"(allowed: {roots_str})"
            )

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"

    def _tool_search_codebase(self, pattern: str, path: str = ".") -> list[dict]:
        """Search for a pattern in the codebase.

        Security:
        - pattern: se valida compilando como regex (previene ReDoS)
        - path: se valida con is_within_root para prevenir path traversal
        """
        # Validar regex del pattern (previene ReDoS)
        try:
            re.compile(pattern)
        except re.error as e:
            logger.warning("Pattern invalido como regex: %s", e)
            raise ValueError(f"Pattern invalido: {e}") from e

        # Validar path contra cwd (previene path traversal)
        root = Path.cwd()
        try:
            is_within_root(str(root), path)
        except (OSError, ValueError) as e:
            logger.warning("Path traversal bloqueado en search_codebase: %s", path)
            raise PermissionError(f"Path fuera del directorio permitido: {path}") from e

        try:
            result = subprocess.run(
                ["grep", "-rn", pattern, path], capture_output=True, text=True, timeout=30
            )
            output = result.stdout
        except FileNotFoundError:
            raw_matches: list[str] = []
            regex = re.compile(pattern)
            root = Path(path)

            for file_path in root.rglob("*"):
                if not file_path.is_file():
                    continue

                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                for line_number, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        raw_matches.append(f"{file_path}:{line_number}:{line}")
                        if len(raw_matches) >= 50:
                            break

                if len(raw_matches) >= 50:
                    break

            output = "\n".join(raw_matches)

        # grep output format: "filepath:linenum:content"
        # On Windows, absolute paths start with a drive letter "C:/..." so the
        # regex anchors on a digit-only line number between two colons.
        _grep_re = re.compile(r"^(.*?):(\d+):(.*)$")
        matches: list[dict[str, Any]] = []
        for line in output.split("\n"):
            if line:
                m = _grep_re.match(line)
                if m:
                    matches.append(
                        {"file": m.group(1), "line": int(m.group(2)), "content": m.group(3)}
                    )

        return matches[:50]  # Limit results

    def _tool_execute_command(self, command: str) -> dict:
        """Execute a shell command safely."""
        if not self.agent.capabilities.can_execute_code:
            raise PermissionError("Code execution not allowed")

        import os
        import shlex

        # SECURITY: Validate command doesn't contain dangerous patterns
        dangerous_patterns = ["rm -rf /", "mkfs", ":(){:|:&};:", "> /dev/sd", "dd if="]
        for pattern in dangerous_patterns:
            if pattern in command:
                raise ValueError(f"Dangerous command pattern detected: {pattern}")

        # SECURITY: Use shlex.split for safe command parsing instead of shell=True
        try:
            cmd_parts = shlex.split(command)
        except ValueError as e:
            raise ValueError(f"Invalid command format: {e}") from e

        if os.name == "nt":
            execution_args = ["cmd", "/c"] + cmd_parts  # SECURITY: args as list, not raw string
        else:
            execution_args = cmd_parts

        result = subprocess.run(
            execution_args,
            shell=False,  # SECURITY: Never use shell=True with user input
            capture_output=True,
            text=True,
            timeout=60,
        )

        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
