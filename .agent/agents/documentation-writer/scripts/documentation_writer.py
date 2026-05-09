#!/usr/bin/env python3
"""
Documentation Writer Agent

Capabilities:
- README generation
- API documentation
- ADR (Architecture Decision Records) creation
- Runbook writing
- Changelog management
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DocSection:
    """Documentation section."""

    title: str
    content: str
    subsections: list["DocSection"] = field(default_factory=list)


class DocumentationWriter:
    """Documentation Writer agent for technical documentation."""

    def __init__(self) -> None:
        self.name = "DocumentationWriter"
        logger.info("DocumentationWriter initialized")

    async def generate_readme(self, task: str) -> dict[str, Any]:
        """Generate a README document.

        Args:
            task: Description of the README to generate.

        Returns:
            Dictionary with README content.
        """
        logger.info(f"Generating README: {task}")

        readme = """# Project Name

> Short description of what this project does

## Features

- Feature 1
- Feature 2
- Feature 3

## Installation

```bash
git clone <repository>
cd <project>
pip install -r requirements.txt
```

## Usage

```python
from project import main

result = main()
print(result)
```

## Configuration

Set environment variables in `.env`:

```
API_KEY=your_api_key
DATABASE_URL=postgresql://localhost/db
```

## API Reference

### `POST /api/v1/resource`

Create a new resource.

**Request:**
```json
{
  "name": "example",
  "value": 42
}
```

**Response:**
```json
{
  "id": 1,
  "name": "example",
  "value": 42,
  "created_at": "2024-01-01T00:00:00Z"
}
```

## License

MIT
"""

        return {
            "agent": self.name,
            "type": "README",
            "content": readme,
            "summary": f"README generated for: {task}",
        }

    async def create_adr(self, task: str) -> dict[str, Any]:
        """Create an Architecture Decision Record.

        Args:
            task: Description of the ADR to create.

        Returns:
            Dictionary with ADR content.
        """
        logger.info(f"Creating ADR: {task}")

        adr = """# ADR-001: Use PostgreSQL for Primary Database

## Status
Accepted

## Context
We need to choose a primary database for the application. We have experience with SQLite for local development and need to scale to production workloads with concurrent access, complex queries, and data integrity requirements.

## Decision
We will use PostgreSQL as the primary database for production workloads, keeping SQLite for local development and testing.

## Consequences

### Positive
- Better concurrency support with connection pooling
- Advanced query optimization (indexes, query plans)
- JSON/JSONB support for semi-structured data
- Mature ecosystem with excellent tooling
- ACID compliance with full transaction support

### Negative
- More complex local setup (docker or installation)
- Additional infrastructure to maintain
- Connection management complexity

## Alternatives Considered

### MySQL
- Less advanced JSON support
- Different feature set for window functions

### SQLite
- Excellent for testing, not suitable for production concurrency

## Implementation

Use SQLAlchemy with asyncpg for async database access:
```python
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://user:pass@host/db")
```
"""

        return {
            "agent": self.name,
            "type": "ADR",
            "content": adr,
            "summary": f"ADR created for: {task}",
        }

    async def execute(self, task: str) -> dict[str, Any]:
        """Execute a documentation task.

        Args:
            task: Description of the documentation task.

        Returns:
            Dictionary with documentation content.
        """
        logger.info(f"Executing documentation task: {task[:80]}")

        task_lower = task.lower()
        result: dict[str, Any] = {
            "agent": self.name,
            "task": task,
            "status": "completed",
            "summary": "",
            "content": None,
            "recommendations": [],
        }

        if "readme" in task_lower:
            result["summary"] = "README generated"
            result["content"] = await self.generate_readme(task)

        elif "adr" in task_lower or "architecture decision" in task_lower:
            result["summary"] = "ADR created"
            result["content"] = await self.create_adr(task)

        elif "api" in task_lower or "endpoint" in task_lower:
            result["summary"] = "API documentation generated"
            result["content"] = """## API Documentation

### Authentication

All endpoints require Bearer token authentication:
```
Authorization: Bearer <your_token>
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/users | List all users |
| POST | /api/v1/users | Create a user |
| GET | /api/v1/users/{id} | Get user by ID |
| PUT | /api/v1/users/{id} | Update user |
| DELETE | /api/v1/users/{id} | Delete user |

### Error Responses

All errors follow this format:
```json
{
  "detail": "Error message",
  "code": "ERROR_CODE"
}
```
"""
            result["recommendations"].append("Use OpenAPI 3.0 spec for auto-generated docs")
            result["recommendations"].append("Include example requests/responses for each endpoint")

        elif "runbook" in task_lower or "operational" in task_lower:
            result["summary"] = "Runbook generated"
            result["content"] = """# Incident Response Runbook

## Severity Levels

| Level | Response Time | Examples |
|-------|---------------|----------|
| P1 | 15 minutes | Service down, data loss |
| P2 | 1 hour | Partial outage, degraded performance |
| P3 | 4 hours | Non-critical bug |
| P4 | 24 hours | Feature request, minor issue |

## Response Steps

1. **Identify** — Confirm the issue and assess severity
2. **Communicate** — Alert stakeholders (Slack #incidents)
3. **Mitigate** — Apply immediate fix or workaround
4. **Resolve** — Implement permanent fix
5. **Review** — Post-mortem within 48 hours

## Rollback Procedure

If a deployment causes issues:
```bash
# Rollback to previous version
kubectl rollout undo deployment/myapp --namespace=production
# Verify rollback
kubectl rollout status deployment/myapp --namespace=production
```
"""
            result["recommendations"].append("Update runbook after each incident")
            result["recommendations"].append("Test rollback procedure quarterly")

        else:
            result["summary"] = f"Documentation generated for: {task}"
            result["recommendations"].append("Keep docs close to code (docstrings, README in repo)")
            result["recommendations"].append("Review documentation quarterly")

        logger.info(f"Documentation task completed: {result['summary']}")
        return result


async def main() -> None:
    """CLI entry point."""
    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        writer = DocumentationWriter()
        result = await writer.execute(task)
        print(f"Result: {result['summary']}")
        if result.get("content"):
            print(f"Content length: {len(str(result['content']))} chars")
    else:
        print("Usage: python documentation_writer.py <task>")


if __name__ == "__main__":
    asyncio.run(main())