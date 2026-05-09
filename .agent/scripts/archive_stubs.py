#!/usr/bin/env python3
"""Archive 18 stub agents (have agent.json + IDENTITY but no Python code)."""
import shutil
from pathlib import Path

stubs = [
    "backend-specialist", "coder", "database-architect", "debugger",
    "devops-engineer", "docs-specialist", "documentation-writer",
    "frontend-specialist", "haken-document-specialist", "haken-system-architect",
    "inteligente-shain-agent", "performance-optimizer", "product-manager",
    "qa-automation-engineer", "security-auditor", "super-orchestrator",
    "test-engineer", "uns-hr-specialist",
]

agents = Path(__file__).parent.parent / "agents"
archive = agents / "_archive_stubs"
archive.mkdir(exist_ok=True)

for name in stubs:
    src = agents / name
    dst = archive / name
    if src.exists():
        shutil.move(str(src), str(dst))
        print(f"ARCHIVED: {name}/ -> _archive_stubs/")
    else:
        print(f"SKIP (already gone): {name}/")
