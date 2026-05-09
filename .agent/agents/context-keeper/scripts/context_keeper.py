#!/usr/bin/env python3
"""
Context Keeper Agent - Session Context Management

Capabilities:
- Track conversation context
- Maintain project state
- Provide context summaries
- Enable cross-session continuity
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """A piece of context information."""

    id: str
    category: str  # task, decision, file, error, insight
    content: str
    importance: int  # 1-5
    created_at: str
    expires_at: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SessionContext:
    """Current session context."""

    session_id: str
    project_path: str
    started_at: str
    current_task: str | None = None
    files_modified: list[str] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)
    errors_encountered: list[str] = field(default_factory=list)
    items: list[ContextItem] = field(default_factory=list)


@dataclass
class ContextReport:
    """Context analysis report."""

    project_path: str
    session_count: int = 0
    total_items: int = 0
    current_session: SessionContext | None = None
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "session_count": self.session_count,
            "total_items": self.total_items,
            "current_session": self.current_session.__dict__ if self.current_session else None,
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Context Status",
            "",
            f"**Project:** {self.project_path}",
            f"**Total Sessions:** {self.session_count}",
            f"**Context Items:** {self.total_items}",
            "",
        ]

        if self.current_session:
            session = self.current_session
            lines.extend(
                [
                    "## Current Session",
                    "",
                    f"**Session ID:** {session.session_id}",
                    f"**Started:** {session.started_at}",
                    f"**Current Task:** {session.current_task or 'None'}",
                    "",
                ]
            )

            if session.files_modified:
                lines.extend(["### Files Modified", ""])
                for f in session.files_modified[-10:]:
                    lines.append(f"- `{f}`")
                lines.append("")

            if session.decisions_made:
                lines.extend(["### Decisions Made", ""])
                for d in session.decisions_made[-5:]:
                    lines.append(f"- {d}")
                lines.append("")

            if session.items:
                lines.extend(["### Recent Context", ""])
                for item in sorted(session.items, key=lambda x: x.importance, reverse=True)[:5]:
                    lines.append(f"- **[{item.category}]** {item.content[:100]}...")
                lines.append("")

        if self.summary:
            lines.extend(["## Summary", "", self.summary])

        return "\n".join(lines)


class ContextKeeper:
    """Session and project context management agent."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.context_dir = self.project_path / ".agent" / "context"
        self.context_file = self.context_dir / "sessions.json"
        self._sessions: list[SessionContext] = []
        self._current_session: SessionContext | None = None
        self._load_context()

    def _load_context(self):
        """Load context from file."""
        if self.context_file.exists():
            try:
                data = json.loads(self.context_file.read_text())
                for session_data in data.get("sessions", []):
                    items = [ContextItem(**item) for item in session_data.pop("items", [])]
                    session = SessionContext(**session_data, items=items)
                    self._sessions.append(session)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Could not load context: {e}")

    def _save_context(self):
        """Save context to file."""
        self.context_dir.mkdir(parents=True, exist_ok=True)

        sessions_data = []
        for session in self._sessions[-10:]:  # Keep last 10 sessions
            session_dict = {
                "session_id": session.session_id,
                "project_path": session.project_path,
                "started_at": session.started_at,
                "current_task": session.current_task,
                "files_modified": session.files_modified,
                "decisions_made": session.decisions_made,
                "errors_encountered": session.errors_encountered,
                "items": [item.__dict__ for item in session.items],
            }
            sessions_data.append(session_dict)

        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "sessions": sessions_data,
        }
        self.context_file.write_text(json.dumps(data, indent=2))

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:8]

    async def start_session(self, task: str = None) -> SessionContext:
        """Start a new context session."""
        session = SessionContext(
            session_id=self._generate_session_id(),
            project_path=str(self.project_path),
            started_at=datetime.now().isoformat(),
            current_task=task,
        )
        self._sessions.append(session)
        self._current_session = session
        self._save_context()

        logger.info(f"Started session: {session.session_id}")
        return session

    async def get_current_session(self) -> SessionContext | None:
        """Get current session or start new one."""
        if not self._current_session:
            # Check for recent session (within last hour)
            if self._sessions:
                last = self._sessions[-1]
                try:
                    last_time = datetime.fromisoformat(last.started_at)
                    if (datetime.now() - last_time).seconds < 3600:
                        self._current_session = last
                        return self._current_session
                except Exception:
                    pass

            # Start new session
            await self.start_session()

        return self._current_session

    async def add_context(
        self, content: str, category: str = "insight", importance: int = 3, metadata: dict = None
    ) -> ContextItem:
        """Add context item to current session."""
        session = await self.get_current_session()

        item = ContextItem(
            id=hashlib.sha256(f"{content}{datetime.now()}".encode()).hexdigest()[:8],
            category=category,
            content=content,
            importance=importance,
            created_at=datetime.now().isoformat(),
            metadata=metadata or {},
        )

        session.items.append(item)

        # Also track specific categories
        if category == "file":
            if content not in session.files_modified:
                session.files_modified.append(content)
        elif category == "decision":
            session.decisions_made.append(content)
        elif category == "error":
            session.errors_encountered.append(content)

        self._save_context()
        return item

    async def set_current_task(self, task: str):
        """Set the current task being worked on."""
        session = await self.get_current_session()
        session.current_task = task
        self._save_context()

    async def track_file(self, file_path: str):
        """Track a modified file."""
        await self.add_context(file_path, category="file", importance=2)

    async def record_decision(self, decision: str, rationale: str = None):
        """Record a decision made during the session."""
        content = decision
        if rationale:
            content = f"{decision} (Rationale: {rationale})"
        await self.add_context(content, category="decision", importance=4)

    async def record_error(self, error: str, resolution: str = None):
        """Record an error encountered."""
        content = error
        if resolution:
            content = f"{error} -> Resolved: {resolution}"
        await self.add_context(content, category="error", importance=3)

    async def get_summary(self) -> str:
        """Get a summary of current context."""
        session = await self.get_current_session()

        parts = []

        if session.current_task:
            parts.append(f"**Current Task:** {session.current_task}")

        if session.files_modified:
            parts.append(f"**Files Modified:** {len(session.files_modified)}")
            for f in session.files_modified[-5:]:
                parts.append(f"  - {f}")

        if session.decisions_made:
            parts.append(f"**Decisions:** {len(session.decisions_made)}")
            for d in session.decisions_made[-3:]:
                parts.append(f"  - {d}")

        important_items = sorted(session.items, key=lambda x: x.importance, reverse=True)[:5]
        if important_items:
            parts.append("**Key Context:**")
            for item in important_items:
                parts.append(f"  - [{item.category}] {item.content[:50]}...")

        return "\n".join(parts) if parts else "No context recorded yet."

    async def get_status(self) -> ContextReport:
        """Get context status report."""
        session = await self.get_current_session()
        total_items = sum(len(s.items) for s in self._sessions)
        summary = await self.get_summary()

        return ContextReport(
            project_path=str(self.project_path),
            session_count=len(self._sessions),
            total_items=total_items,
            current_session=session,
            summary=summary,
        )

    async def get_relevant_context(self, query: str, limit: int = 5) -> list[ContextItem]:
        """Get context items relevant to a query."""
        query_lower = query.lower()
        results = []

        for session in self._sessions:
            for item in session.items:
                score = 0
                content_lower = item.content.lower()

                if query_lower in content_lower:
                    score += 10
                for word in query_lower.split():
                    if word in content_lower:
                        score += 2

                score += item.importance

                if score > 0:
                    results.append((score, item))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[:limit]]

    async def clear_session(self):
        """Clear current session context."""
        if self._current_session:
            self._current_session.items = []
            self._current_session.files_modified = []
            self._current_session.decisions_made = []
            self._current_session.errors_encountered = []
            self._save_context()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Context Keeper Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    subparsers = parser.add_subparsers(dest="command")

    # Add context command
    add_parser = subparsers.add_parser("add", help="Add context")
    add_parser.add_argument("content", help="Context content")
    add_parser.add_argument("--category", default="insight")
    add_parser.add_argument("--importance", type=int, default=3)

    # Set task command
    task_parser = subparsers.add_parser("task", help="Set current task")
    task_parser.add_argument("task", help="Task description")

    # Track file command
    file_parser = subparsers.add_parser("file", help="Track file")
    file_parser.add_argument("file_path", help="File path")

    # Decision command
    decision_parser = subparsers.add_parser("decision", help="Record decision")
    decision_parser.add_argument("decision", help="Decision")
    decision_parser.add_argument("--rationale", help="Rationale")

    # Summary command
    subparsers.add_parser("summary", help="Get summary")

    # Status command
    subparsers.add_parser("status", help="Get status")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search context")
    search_parser.add_argument("query", help="Search query")

    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = ContextKeeper(args.path)

    if args.command == "add":
        item = await agent.add_context(args.content, args.category, args.importance)
        print(f"Added: {item.id}")

    elif args.command == "task":
        await agent.set_current_task(args.task)
        print(f"Task set: {args.task}")

    elif args.command == "file":
        await agent.track_file(args.file_path)
        print(f"Tracked: {args.file_path}")

    elif args.command == "decision":
        await agent.record_decision(args.decision, args.rationale)
        print("Decision recorded")

    elif args.command == "summary":
        summary = await agent.get_summary()
        print(summary)

    elif args.command == "search":
        results = await agent.get_relevant_context(args.query)
        for item in results:
            print(f"[{item.category}] {item.content[:100]}...")

    else:
        status = await agent.get_status()
        if args.json:
            print(json.dumps(status.to_dict(), indent=2))
        else:
            print(status.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
