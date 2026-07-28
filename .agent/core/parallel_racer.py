#!/usr/bin/env python3
"""
Parallel Racing Engine — Multi-Agent Competitive Execution.

Dispatches the same task to multiple agents simultaneously, collects
responses, scores them with composite evaluation, and returns the best
result.  Supports four racing tiers from fast (3 agents, first viable
wins) to ultra (all available agents, exhaustive scoring).

Features:
- Tier-based agent selection (FAST, STANDARD, THOROUGH, ULTRA)
- Composite scoring across 4 dimensions (substance, directness,
  completeness, accuracy)
- Per-agent cumulative rankings from race history
- Graceful degradation when agents fail or timeout

Usage:
    from .agent.core.parallel_racer import ParallelRacer, RacingTier

    racer = ParallelRacer()
    result = await racer.race(
        "Implement a retry decorator with exponential backoff",
        tier=RacingTier.STANDARD,
    )

    print(f"Winner: {result.winner.agent_name}")
    print(f"Score: {result.winner.score.overall:.2f}")
    print(f"Improvement: {result.improvement_over_first:.1f}%")
"""

import asyncio
import hashlib
import logging
import random
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.core.parallel_racer")

__all__ = [
    "ParallelRacer",
    "RacingTier",
    "RaceEntry",
    "RaceResult",
    "CompositeScore",
]


# ---------------------------------------------------------------------------
# Enums & data structures
# ---------------------------------------------------------------------------


class RacingTier(str, Enum):
    """Racing tier controlling how many agents participate."""

    FAST = "fast"  # 3 agents, first viable response wins
    STANDARD = "standard"  # 5 agents, scored selection
    THOROUGH = "thorough"  # 10 agents, full composite scoring
    ULTRA = "ultra"  # all available agents, exhaustive


_TIER_AGENT_COUNTS: dict[RacingTier, int] = {
    RacingTier.FAST: 3,
    RacingTier.STANDARD: 5,
    RacingTier.THOROUGH: 10,
    RacingTier.ULTRA: 20,
}


@dataclass
class CompositeScore:
    """Multi-dimensional quality score for a race response.

    Attributes:
        substance: Relevance to the task (0-1).
        directness: Clarity without hedging (0-1).
        completeness: Coverage of all task aspects (0-1).
        accuracy: Technical correctness indicators (0-1).
        overall: Weighted combination of all dimensions.
    """

    substance: float
    directness: float
    completeness: float
    accuracy: float
    overall: float

    def to_dict(self) -> dict[str, float]:
        """Serialize score to a plain dictionary.

        Returns:
            Dictionary with all score dimensions.
        """
        return asdict(self)


@dataclass
class RaceEntry:
    """A single agent's race participation record.

    Attributes:
        agent_name: Name of the participating agent.
        response: The agent's response text.
        score: Composite quality score.
        latency_ms: Execution time in milliseconds.
        status: Outcome status (completed, failed, timeout).
        error: Error message if the agent failed.
    """

    agent_name: str
    response: str
    score: CompositeScore
    latency_ms: int
    status: str  # "completed", "failed", "timeout"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize entry to a plain dictionary.

        Returns:
            Dictionary representation of this entry.
        """
        d = asdict(self)
        d["score"] = self.score.to_dict()
        return d


@dataclass
class RaceResult:
    """Outcome of a parallel race.

    Attributes:
        task: The task that was raced.
        tier: The racing tier used.
        winner: The entry with the highest composite score.
        all_entries: Every entry, sorted by score descending.
        total_time_ms: Wall-clock time for the entire race.
        agents_participated: Total agents dispatched.
        agents_completed: Agents that finished successfully.
        agents_failed: Agents that failed or timed out.
        improvement_over_first: Percentage improvement of winner
            over the first response received.
    """

    task: str
    tier: RacingTier
    winner: RaceEntry
    all_entries: list[RaceEntry]
    total_time_ms: int
    agents_participated: int
    agents_completed: int
    agents_failed: int
    improvement_over_first: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a plain dictionary.

        Returns:
            Dictionary representation of the race result.
        """
        return {
            "task": self.task,
            "tier": self.tier.value,
            "winner": self.winner.to_dict(),
            "all_entries": [e.to_dict() for e in self.all_entries],
            "total_time_ms": self.total_time_ms,
            "agents_participated": self.agents_participated,
            "agents_completed": self.agents_completed,
            "agents_failed": self.agents_failed,
            "improvement_over_first": round(self.improvement_over_first, 2),
        }


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_WEIGHT_SUBSTANCE: float = 0.30
_WEIGHT_DIRECTNESS: float = 0.25
_WEIGHT_COMPLETENESS: float = 0.25
_WEIGHT_ACCURACY: float = 0.20

_HEDGING_WORDS: list[str] = [
    "maybe",
    "perhaps",
    "possibly",
    "it depends",
    "might",
    "could be",
    "not sure",
    "i think",
    "arguably",
    "debatable",
    "it's hard to say",
    "in some cases",
    "potentially",
]

_ASSERTIVE_MARKERS: list[str] = [
    "specifically",
    "precisely",
    "exactly",
    "clearly",
    "definitely",
    "certainly",
    "directly",
    "the solution is",
    "here is",
    "you should",
    "the answer is",
    "to accomplish this",
]

_CODE_SYNTAX_MARKERS: list[str] = [
    "def ",
    "class ",
    "import ",
    "function ",
    "const ",
    "let ",
    "return ",
    "if ",
    "for ",
    "while ",
    "async ",
    "await ",
    "```",
    "=>",
    "->",
]

_MAX_RACE_HISTORY = 50
_MAX_AGENT_HISTORY = 200


# ---------------------------------------------------------------------------
# Agent capability hints (for simulated execution)
# ---------------------------------------------------------------------------

_AGENT_CAPABILITY_HINTS: dict[str, list[str]] = {
    "planner": ["planning", "decomposition", "roadmap", "strategy"],
    "architect": ["architecture", "design", "system", "patterns"],
    "backend": ["api", "server", "database", "python", "node"],
    "frontend": ["ui", "react", "css", "component", "design"],
    "debugger": ["debug", "error", "fix", "trace", "log"],
    "security": ["security", "auth", "vulnerability", "encryption"],
    "devops": ["deploy", "ci", "docker", "kubernetes", "infra"],
    "testing": ["test", "coverage", "assertion", "mock", "spec"],
    "documentation": ["docs", "readme", "guide", "reference"],
    "performance": ["optimize", "benchmark", "profiling", "cache"],
    "code-reviewer": ["review", "quality", "refactor", "clean"],
    "database": ["sql", "schema", "migration", "query", "index"],
}


# ---------------------------------------------------------------------------
# ParallelRacer
# ---------------------------------------------------------------------------


class ParallelRacer:
    """Multi-agent parallel racing engine.

    Dispatches the same task to multiple agents simultaneously,
    collects responses, scores them with composite evaluation,
    and returns the best result.

    Attributes:
        agents_dir: Path to the agents directory.
        timeout: Default per-agent timeout in seconds.
        race_history: Deque of recent race results (capped).
        agent_stats: Per-agent cumulative statistics.
    """

    def __init__(
        self,
        agents_dir: str | Path | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize with agents directory and default timeout.

        Args:
            agents_dir: Path to the agents directory. Defaults to
                ``.agent/agents/`` relative to this module.
            timeout: Default per-agent timeout in seconds.
        """
        if agents_dir is not None:
            self.agents_dir = Path(agents_dir)
        else:
            self.agents_dir = Path(__file__).parent.parent / "agents"

        self.timeout = timeout
        self.race_history: deque[dict[str, Any]] = deque(maxlen=_MAX_RACE_HISTORY)
        self.agent_stats: dict[str, dict[str, Any]] = {}
        self._available_agents: list[str] | None = None

        logger.info(
            "ParallelRacer initialized — agents_dir=%s timeout=%ds",
            self.agents_dir,
            self.timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def race(
        self,
        task: str,
        tier: RacingTier = RacingTier.STANDARD,
        agents: list[str] | None = None,
    ) -> RaceResult:
        """Run a parallel race with the specified tier.

        Selects agents based on the tier (or uses the explicit list),
        dispatches the task to all of them in parallel, scores every
        response, and returns a ``RaceResult`` with the winner.

        Args:
            task: The task description to send to all agents.
            tier: Racing tier controlling agent count and selection.
            agents: Optional explicit list of agent names. Overrides
                tier-based selection when provided.

        Returns:
            A ``RaceResult`` with the winning entry and all entries.

        Raises:
            ValueError: If no agents are available for the race.
        """
        race_start = time.monotonic()

        # Select agents
        if agents is not None:
            selected = agents
        else:
            selected = self._select_agents(task, tier)

        if not selected:
            raise ValueError(f"No agents available for racing. Check agents_dir: {self.agents_dir}")

        logger.info(
            "Race started — tier=%s agents=%d task=%.80s",
            tier.value,
            len(selected),
            task,
        )

        # Dispatch all agents in parallel
        tasks = [self._execute_agent(agent_name, task) for agent_name in selected]
        entries: list[RaceEntry] = await asyncio.gather(*tasks, return_exceptions=True)  # type: ignore[assignment]

        # Convert exceptions to failed entries
        resolved: list[RaceEntry] = []
        for i, entry in enumerate(entries):
            if isinstance(entry, BaseException):
                resolved.append(
                    RaceEntry(
                        agent_name=selected[i],
                        response="",
                        score=CompositeScore(0.0, 0.0, 0.0, 0.0, 0.0),
                        latency_ms=0,
                        status="failed",
                        error=str(entry),
                    )
                )
            else:
                resolved.append(entry)

        # Separate completed from failed
        completed = [e for e in resolved if e.status == "completed"]
        failed = [e for e in resolved if e.status != "completed"]

        # Sort completed by score descending
        completed.sort(key=lambda e: e.score.overall, reverse=True)
        all_entries = completed + failed

        # Determine winner
        if completed:
            winner = completed[0]
        elif resolved:
            # All failed — pick the one with the least bad status
            winner = resolved[0]
        else:
            # Should not happen due to guard above, but be safe
            winner = RaceEntry(
                agent_name="none",
                response="",
                score=CompositeScore(0.0, 0.0, 0.0, 0.0, 0.0),
                latency_ms=0,
                status="failed",
                error="No agents participated",
            )

        # Calculate improvement over first response (by arrival time / latency)
        improvement = 0.0
        if len(completed) >= 2:
            # "First response" = lowest latency among completed
            first_by_time = min(completed, key=lambda e: e.latency_ms)
            if first_by_time.score.overall > 0:
                improvement = (
                    (winner.score.overall - first_by_time.score.overall)
                    / first_by_time.score.overall
                    * 100.0
                )

        total_time_ms = int((time.monotonic() - race_start) * 1000)

        result = RaceResult(
            task=task,
            tier=tier,
            winner=winner,
            all_entries=all_entries,
            total_time_ms=total_time_ms,
            agents_participated=len(selected),
            agents_completed=len(completed),
            agents_failed=len(failed),
            improvement_over_first=improvement,
        )

        # Record history and update stats
        self._record_race(result)

        logger.info(
            "Race finished — winner=%s score=%.3f completed=%d/%d time=%dms",
            winner.agent_name,
            winner.score.overall,
            len(completed),
            len(selected),
            total_time_ms,
        )

        return result

    async def _execute_agent(self, agent_name: str, task: str) -> RaceEntry:
        """Execute a single agent and return its entry.

        Uses simulated execution: generates a response based on the
        agent's capability hints and the task content.  Real agent
        execution depends on external systems and can be plugged in
        by subclassing.

        Args:
            agent_name: Name of the agent to execute.
            task: The task description.

        Returns:
            A ``RaceEntry`` with the agent's response and score.
        """
        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self._simulate_agent(agent_name, task),
                timeout=self.timeout,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            score = self._score_response(task, response)
            return RaceEntry(
                agent_name=agent_name,
                response=response,
                score=score,
                latency_ms=latency_ms,
                status="completed",
            )
        except TimeoutError:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning("Agent %s timed out after %dms", agent_name, latency_ms)
            return RaceEntry(
                agent_name=agent_name,
                response="",
                score=CompositeScore(0.0, 0.0, 0.0, 0.0, 0.0),
                latency_ms=latency_ms,
                status="timeout",
                error=f"Timeout after {self.timeout}s",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning("Agent %s failed: %s", agent_name, exc)
            return RaceEntry(
                agent_name=agent_name,
                response="",
                score=CompositeScore(0.0, 0.0, 0.0, 0.0, 0.0),
                latency_ms=latency_ms,
                status="failed",
                error=str(exc),
            )

    def _score_response(self, task: str, response: str) -> CompositeScore:
        """Score a response using composite evaluation.

        Evaluates four dimensions and produces a weighted overall score.

        Args:
            task: The original task description.
            response: The agent's response text.

        Returns:
            A ``CompositeScore`` with per-dimension and overall scores.
        """
        substance = self._score_substance(task, response)
        directness = self._score_directness(response)
        completeness = self._score_completeness(task, response)
        accuracy = self._score_accuracy(response)

        overall = (
            _WEIGHT_SUBSTANCE * substance
            + _WEIGHT_DIRECTNESS * directness
            + _WEIGHT_COMPLETENESS * completeness
            + _WEIGHT_ACCURACY * accuracy
        )

        return CompositeScore(
            substance=round(substance, 4),
            directness=round(directness, 4),
            completeness=round(completeness, 4),
            accuracy=round(accuracy, 4),
            overall=round(overall, 4),
        )

    def _select_agents(self, task: str, tier: RacingTier) -> list[str]:
        """Select agents for the race based on tier and task affinity.

        Uses historical performance data when available, otherwise
        selects randomly from discovered agents.

        Args:
            task: The task description (used for affinity matching).
            tier: The racing tier controlling how many agents to pick.

        Returns:
            List of agent names to participate in the race.
        """
        available = self._discover_available_agents()
        if not available:
            return []

        max_agents = _TIER_AGENT_COUNTS[tier]

        # If we have fewer agents than the tier wants, use all
        if len(available) <= max_agents:
            return list(available)

        # Rank agents by historical performance + task affinity
        ranked = self._rank_agents_for_task(available, task)

        # For diversity, mix top performers with some random picks
        top_count = max(1, max_agents * 2 // 3)
        random_count = max_agents - top_count

        top_picks = ranked[:top_count]
        remaining = [a for a in ranked[top_count:] if a not in top_picks]

        if remaining and random_count > 0:
            random_picks = random.sample(remaining, min(random_count, len(remaining)))
        else:
            random_picks = []

        selected = top_picks + random_picks
        return selected[:max_agents]

    def get_race_history(self) -> list[dict[str, Any]]:
        """Return history of past races with statistics.

        Returns:
            List of race summary dictionaries, most recent first.
        """
        return list(reversed(self.race_history))

    def get_agent_rankings(self) -> list[dict[str, Any]]:
        """Return cumulative agent rankings from all races.

        Rankings are sorted by win rate descending, then by average
        score descending.

        Returns:
            List of agent ranking dictionaries.
        """
        rankings: list[dict[str, Any]] = []
        for agent_name, stats in self.agent_stats.items():
            total = stats.get("total_races", 0)
            wins = stats.get("wins", 0)
            win_rate = wins / total if total > 0 else 0.0
            avg_score = stats.get("total_score", 0.0) / total if total > 0 else 0.0
            avg_latency = stats.get("total_latency_ms", 0) / total if total > 0 else 0

            rankings.append(
                {
                    "agent_name": agent_name,
                    "total_races": total,
                    "wins": wins,
                    "win_rate": round(win_rate, 4),
                    "average_score": round(avg_score, 4),
                    "average_latency_ms": int(avg_latency),
                    "failures": stats.get("failures", 0),
                }
            )

        rankings.sort(key=lambda r: (r["win_rate"], r["average_score"]), reverse=True)
        return rankings

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_substance(task: str, response: str) -> float:
        """Score substance: relevance to the task.

        Checks for task-relevant keywords, adequate length, and
        on-topic content.

        Args:
            task: The original task.
            response: The agent's response.

        Returns:
            Score between 0.0 and 1.0.
        """
        if not response.strip():
            return 0.0

        score = 0.0

        # Length adequacy (longer responses tend to have more substance,
        # up to a reasonable threshold)
        word_count = len(response.split())
        if word_count >= 200:
            score += 0.35
        elif word_count >= 100:
            score += 0.25
        elif word_count >= 50:
            score += 0.15
        elif word_count >= 20:
            score += 0.08

        # Task-relevant keyword overlap
        task_words = set(re.findall(r"\b\w{4,}\b", task.lower()))
        response_words = set(re.findall(r"\b\w{4,}\b", response.lower()))
        if task_words:
            overlap = len(task_words & response_words) / len(task_words)
            score += 0.35 * min(overlap, 1.0)

        # Structural indicators (headings, lists, code blocks)
        if re.search(r"^#{1,3}\s", response, re.MULTILINE):
            score += 0.10
        if re.search(r"^[-*]\s", response, re.MULTILINE):
            score += 0.10
        if "```" in response:
            score += 0.10

        return min(score, 1.0)

    @staticmethod
    def _score_directness(response: str) -> float:
        """Score directness: clarity without hedging.

        Penalizes hedging words and rewards assertive language.

        Args:
            response: The agent's response.

        Returns:
            Score between 0.0 and 1.0.
        """
        if not response.strip():
            return 0.0

        response_lower = response.lower()
        # Start with a base score
        score = 0.7

        # Penalize hedging words (proportional to frequency)
        hedge_count = sum(1 for word in _HEDGING_WORDS if word in response_lower)
        hedge_penalty = min(hedge_count * 0.06, 0.40)
        score -= hedge_penalty

        # Reward assertive markers
        assertive_count = sum(1 for marker in _ASSERTIVE_MARKERS if marker in response_lower)
        assertive_bonus = min(assertive_count * 0.05, 0.30)
        score += assertive_bonus

        return max(0.0, min(score, 1.0))

    @staticmethod
    def _score_completeness(task: str, response: str) -> float:
        """Score completeness: coverage of all task aspects.

        Checks for multiple sections, code examples when appropriate,
        and coverage of task sub-topics.

        Args:
            task: The original task.
            response: The agent's response.

        Returns:
            Score between 0.0 and 1.0.
        """
        if not response.strip():
            return 0.0

        score = 0.0

        # Multiple sections / paragraphs
        paragraphs = [p.strip() for p in response.split("\n\n") if p.strip()]
        if len(paragraphs) >= 5:
            score += 0.30
        elif len(paragraphs) >= 3:
            score += 0.20
        elif len(paragraphs) >= 2:
            score += 0.10

        # Code examples when the task looks code-related
        task_lower = task.lower()
        is_code_task = any(
            kw in task_lower
            for kw in [
                "implement",
                "code",
                "function",
                "class",
                "script",
                "program",
                "algorithm",
                "api",
                "write",
                "create",
                "build",
                "develop",
                "decorator",
                "module",
            ]
        )
        if is_code_task and "```" in response:
            score += 0.25
        elif not is_code_task:
            score += 0.10  # Non-code tasks get a base completeness bonus

        # Coverage of task aspects via keyword presence
        task_words = set(re.findall(r"\b\w{4,}\b", task.lower()))
        response_lower = response.lower()
        covered = sum(1 for w in task_words if w in response_lower)
        if task_words:
            coverage_ratio = covered / len(task_words)
            score += 0.25 * min(coverage_ratio, 1.0)

        # Presence of summary / conclusion indicators
        if re.search(
            r"\b(?:in\s+summary|conclusion|to\s+summarize|overall|in\s+short)\b",
            response_lower,
        ):
            score += 0.10

        return min(score, 1.0)

    @staticmethod
    def _score_accuracy(response: str) -> float:
        """Score accuracy: technical correctness indicators.

        Checks for valid code syntax patterns, logical consistency,
        and factual indicators.

        Args:
            response: The agent's response.

        Returns:
            Score between 0.0 and 1.0.
        """
        if not response.strip():
            return 0.0

        score = 0.5  # Base: assume moderately accurate

        # Code syntax validity indicators
        code_marker_count = sum(1 for m in _CODE_SYNTAX_MARKERS if m in response)
        if code_marker_count >= 4:
            score += 0.20
        elif code_marker_count >= 2:
            score += 0.10

        # Balanced brackets/parens in code blocks
        code_blocks = re.findall(r"```[\s\S]*?```", response)
        if code_blocks:
            for block in code_blocks:
                opens = block.count("(") + block.count("[") + block.count("{")
                closes = block.count(")") + block.count("]") + block.count("}")
                if opens > 0 and opens == closes:
                    score += 0.10
                    break  # One balanced block is enough

        # Logical consistency: numbered steps or ordered reasoning
        if re.search(r"(?:^|\n)\s*\d+\.\s", response):
            score += 0.10

        # Specific technical references (URLs, file paths, version numbers)
        if re.search(r"(?:https?://|/\w+/\w+|\d+\.\d+\.\d+)", response):
            score += 0.10

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Agent discovery & ranking
    # ------------------------------------------------------------------

    def _discover_available_agents(self) -> list[str]:
        """Discover available agents from the agents directory.

        Caches results after first scan. Agents are identified by
        directories containing an ``IDENTITY.md`` file.

        Returns:
            List of agent directory names.
        """
        if self._available_agents is not None:
            return self._available_agents

        agents: list[str] = []
        if not self.agents_dir.exists():
            logger.warning("Agents directory not found: %s", self.agents_dir)
            self._available_agents = agents
            return agents

        for entry in sorted(self.agents_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue
            identity = entry / "IDENTITY.md"
            if identity.exists():
                agents.append(entry.name)

        logger.info("Discovered %d agents in %s", len(agents), self.agents_dir)
        self._available_agents = agents
        return agents

    def _rank_agents_for_task(self, agents: list[str], task: str) -> list[str]:
        """Rank agents by historical performance and task affinity.

        Combines win rate, average score, and keyword affinity into
        a single ranking score.

        Args:
            agents: Available agent names.
            task: The task description for affinity matching.

        Returns:
            Agents sorted by ranking score descending.
        """
        task_lower = task.lower()

        def rank_key(agent: str) -> float:
            rank_score = 0.0

            # Historical performance (60% weight)
            stats = self.agent_stats.get(agent, {})
            total = stats.get("total_races", 0)
            if total > 0:
                win_rate = stats.get("wins", 0) / total
                avg_score = stats.get("total_score", 0.0) / total
                rank_score += 0.60 * (0.5 * win_rate + 0.5 * avg_score)

            # Task affinity via capability hints (40% weight)
            hints = _AGENT_CAPABILITY_HINTS.get(agent, [])
            if hints:
                affinity = sum(1 for h in hints if h in task_lower)
                rank_score += 0.40 * min(affinity / max(len(hints), 1), 1.0)

            return rank_score

        return sorted(agents, key=rank_key, reverse=True)

    # ------------------------------------------------------------------
    # Simulated execution
    # ------------------------------------------------------------------

    async def _simulate_agent(self, agent_name: str, task: str) -> str:
        """Simulate an agent's response to a task.

        Generates a deterministic but varied response based on the
        agent's name and the task content. This simulates what a real
        agent execution would produce without requiring external LLM
        calls.

        Args:
            agent_name: Name of the agent.
            task: The task description.

        Returns:
            Simulated response text.
        """
        # Simulate variable latency (50-500ms)
        seed = int(
            hashlib.md5(f"{agent_name}:{task}".encode(), usedforsecurity=False).hexdigest()[:8], 16
        )
        latency = 0.05 + (seed % 450) / 1000.0
        await asyncio.sleep(latency)

        # Build response based on agent capabilities
        hints = _AGENT_CAPABILITY_HINTS.get(agent_name, ["general"])
        capability_text = ", ".join(hints)

        # Deterministic variation per agent
        rng = random.Random(seed)
        rng.randint(2, 5)
        detail_level = rng.choice(["concise", "detailed", "comprehensive"])

        response_parts: list[str] = [
            f"# Analysis by {agent_name}",
            "",
            "## Task Understanding",
            f"The task requires: {task}",
            f"This falls within my expertise areas: {capability_text}.",
            "",
        ]

        # Add approach section
        response_parts.extend(
            [
                "## Approach",
                f"Here is a {detail_level} approach to solving this task:",
                "",
            ]
        )

        # Add numbered steps
        step_count = rng.randint(3, 6)
        for i in range(1, step_count + 1):
            response_parts.append(
                f"{i}. Step {i}: Address the {hints[i % len(hints)] if hints else 'core'} aspects"
            )
        response_parts.append("")

        # Conditionally add code block for code-related tasks
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["implement", "code", "function", "class", "write"]):
            response_parts.extend(
                [
                    "## Implementation",
                    "",
                    "```python",
                    f"# Implementation by {agent_name}",
                    f"def solve_{agent_name.replace('-', '_')}(task: str) -> str:",
                    '    """Solve the given task."""',
                    f"    # Core logic for: {task[:60]}",
                    "    result = process(task)",
                    "    return result",
                    "```",
                    "",
                ]
            )

        # Add summary
        response_parts.extend(
            [
                "## Summary",
                "",
                f"This {detail_level} analysis covers the key aspects of the task "
                f"from a {capability_text} perspective. The solution addresses "
                f"all {step_count} identified requirements.",
            ]
        )

        return "\n".join(response_parts)

    # ------------------------------------------------------------------
    # History & statistics
    # ------------------------------------------------------------------

    def _record_race(self, result: RaceResult) -> None:
        """Record a race result in history and update agent stats.

        Args:
            result: The completed race result.
        """
        # Add to history
        self.race_history.append(
            {
                "task": result.task[:200],
                "tier": result.tier.value,
                "winner": result.winner.agent_name,
                "winner_score": result.winner.score.overall,
                "agents_participated": result.agents_participated,
                "agents_completed": result.agents_completed,
                "total_time_ms": result.total_time_ms,
                "improvement_over_first": round(result.improvement_over_first, 2),
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Update per-agent stats
        for entry in result.all_entries:
            name = entry.agent_name
            if name not in self.agent_stats:
                self.agent_stats[name] = {
                    "total_races": 0,
                    "wins": 0,
                    "total_score": 0.0,
                    "total_latency_ms": 0,
                    "failures": 0,
                }

            stats = self.agent_stats[name]
            stats["total_races"] += 1

            if entry.status == "completed":
                stats["total_score"] += entry.score.overall
                stats["total_latency_ms"] += entry.latency_ms
            else:
                stats["failures"] += 1

            if entry.agent_name == result.winner.agent_name:
                stats["wins"] += 1
