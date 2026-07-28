"""SuperAgentBackend — delegates parse_smart to the excel-super-agent skill.

The skill lives at .agent/skills/excel-super-agent/scripts/main.py and is
invoked via subprocess (shell=False) with the file path as argument. The
skill is expected to print a JSON document to stdout describing the parsed
content; non-zero exit codes or invalid JSON raise SuperAgentInvocationError.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SuperAgentInvocationError(RuntimeError):
    """Raised when invoking the excel-super-agent skill fails."""


def _project_root() -> Path:
    """Locate the repo root by climbing from this file."""
    return Path(__file__).resolve().parents[4]


class SuperAgentBackend:
    """Backend that shells out to the excel-super-agent skill for parsing."""

    SKILL_REL_PATH = ".agent/skills/excel-super-agent/scripts/main.py"
    TIMEOUT_SECONDS = 60

    def parse_smart(
        self,
        path: str,
        hints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke the skill and return parsed content as dict.

        Args:
            path: absolute path to the .xlsx/.xlsm/.xls file.
            hints: optional dict passed via JSON to the skill.

        Raises:
            FileNotFoundError: if path doesn't exist.
            SuperAgentInvocationError: if skill exits non-zero or returns
                non-JSON stdout.
        """
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"file not found: {path}")

        skill_path = _project_root() / self.SKILL_REL_PATH
        if not skill_path.exists():
            raise SuperAgentInvocationError(f"skill script not found at {skill_path}")

        cmd: list[str] = [sys.executable, str(skill_path), "--path", str(target)]
        if hints:
            cmd.extend(["--hints", json.dumps(hints, ensure_ascii=False)])

        logger.info("[super-agent] invoking %s", shlex.join(cmd))

        try:
            result = subprocess.run(
                cmd,
                shell=False,  # Security: regla security.md del repo
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_SECONDS,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired as e:
            raise SuperAgentInvocationError(
                f"super-agent timed out after {self.TIMEOUT_SECONDS}s"
            ) from e

        if result.returncode != 0:
            raise SuperAgentInvocationError(
                f"super-agent exit={result.returncode} stderr={result.stderr!r}"
            )

        try:
            return json.loads(result.stdout)  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            raise SuperAgentInvocationError(
                f"super-agent returned non-JSON stdout: {result.stdout[:200]!r}"
            ) from e
