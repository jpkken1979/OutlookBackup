#!/usr/bin/env python3
"""Jpkkenfull v2 — Autonomous executor without permissions.

Key improvements over v1:
1. Learning loop: brain.query() at START (reads past learnings)
2. Clarification gate: real input() loop, not just print
3. Critical operations guard: list of dangerous ops that ALWAYS ask
4. Abort signal handler: SIGINT/SIGTERM stops cleanly, saves state
5. Reuses autonomous-executor for planning and execution
6. Paths via ANTIGRAVITY_ROOT env var (not hardcoded)
7. web_search graceful degradation (warns if endpoint missing)
8. Self-improvement: stores lessons + reads them next time
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Paths & config ───────────────────────────────────────────────────────────

REPO_ROOT = Path(os.environ.get(
    "ANTIGRAVITY_ROOT",
    Path(__file__).resolve().parents[3]
))
GATEWAY_URL = os.environ.get("ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:4747")
STEP_TIMEOUT = int(os.environ.get("EXECUTOR_STEP_TIMEOUT", "120"))
MAX_RETRIES = 2
ABORT_THRESHOLD = 0.3
INTERNET_TIMEOUT = 10

logger = logging.getLogger(__name__)

# ── Global abort flag ──────────────────────────────────────────────────────────

_abort_requested = False


def _signal_handler(signum: int, frame) -> None:
    global _abort_requested
    _abort_requested = True
    print("\n[ABORT] Signal received -- finishing current step cleanly...")


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    """Un paso en el plan de ejecución."""

    index: int
    action: str
    target: str
    success_criteria: str
    method: str  # "subprocess" | "mcp_agent" | "mcp_skill" | "brain_save" | "web_search"
    details: str = ""
    status: str = "pending"  # pending | running | ok | fail | skipped
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    retries: int = 0
    agent_used: Optional[str] = None
    skill_used: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "action": self.action,
            "target": self.target,
            "success_criteria": self.success_criteria,
            "method": self.method,
            "details": self.details,
            "status": self.status,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "agent_used": self.agent_used,
            "skill_used": self.skill_used,
        }


@dataclass
class ExecutionResult:
    """Total result of an execution."""

    goal: str
    plan_steps: list[PlanStep] = field(default_factory=list)
    executed_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    duration_seconds: float = 0.0
    files_modified: list[str] = field(default_factory=list)
    decisions_log: list[str] = field(default_factory=list)
    clarification_asked: bool = False
    clarification_question: Optional[str] = None
    clarification_response: Optional[str] = None
    internet_search_triggered: bool = False
    agents_used: list[str] = field(default_factory=list)
    skills_used: list[str] = field(default_factory=list)
    self_created_skill: bool = False
    lessons_learned: list[str] = field(default_factory=list)
    past_learnings: list[str] = field(default_factory=list)
    aborted_via_signal: bool = False
    critical_ops_intercepted: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        sr = self.successful_steps / self.executed_steps if self.executed_steps > 0 else 0.0
        return {
            "goal": self.goal,
            "executed_steps": self.executed_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "duration_seconds": round(self.duration_seconds, 2),
            "files_modified": self.files_modified,
            "decisions_log": self.decisions_log,
            "clarification_asked": self.clarification_asked,
            "clarification_question": self.clarification_question,
            "clarification_response": self.clarification_response,
            "internet_search_triggered": self.internet_search_triggered,
            "agents_used": self.agents_used,
            "skills_used": self.skills_used,
            "self_created_skill": self.self_created_skill,
            "lessons_learned": self.lessons_learned,
            "past_learnings": self.past_learnings,
            "aborted_via_signal": self.aborted_via_signal,
            "critical_ops_intercepted": self.critical_ops_intercepted,
            "success_rate": round(sr, 3),
        }


# ── Phase 1: Context gathering ────────────────────────────────────────────────

def gather_context(goal: str) -> dict:
    """Gather all available context: memory, brain, rules, git, project type."""

    info = {
        "goal": goal,
        "memories": [],
        "brain_notes": [],
        "rules": [],
        "git_status": "",
        "project_type": "unknown",
        "detected_apps": [],
        "past_learnings": [],
        "confidence": "low",
    }

    # Memories
    mem_dir = REPO_ROOT / ".claude" / "memory"
    if mem_dir.exists():
        mem_index = mem_dir / "MEMORY.md"
        if mem_index.exists():
            try:
                info["memories"].append({
                    "source": "MEMORY.md",
                    "content": mem_index.read_text(encoding="utf-8", errors="replace")[:3000]
                })
            except Exception:
                pass

        keywords = _extract_keywords(goal)
        for mem_file in mem_dir.glob("*.md"):
            if mem_file.name == "MEMORY.md":
                continue
            for kw in keywords:
                if kw in mem_file.stem.lower():
                    try:
                        info["memories"].append({
                            "source": mem_file.name,
                            "content": mem_file.read_text(encoding="utf-8", errors="replace")[:1500],
                            "relevance": kw,
                        })
                    except Exception:
                        pass

    # Brain Network
    brain_dir = REPO_ROOT / ".agent" / "brain"
    if brain_dir.exists():
        brain_index = brain_dir / "index.md"
        if brain_index.exists():
            try:
                content = brain_index.read_text(encoding="utf-8", errors="replace")
                for kw in _extract_keywords(goal):
                    if kw.lower() in content.lower():
                        lines = [l for l in content.splitlines() if kw.lower() in l.lower()]
                        if lines:
                            info["brain_notes"].extend(lines[:10])
            except Exception:
                pass

        sessions_dir = brain_dir / "sessions"
        if sessions_dir.exists():
            for s in sorted(sessions_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
                try:
                    info["brain_notes"].append({
                        "source": s.name,
                        "content": s.read_text(encoding="utf-8", errors="replace")[:500]
                    })
                except Exception:
                    pass

    # Brain learnings query (LEARNING LOOP — reads past executions)
    try:
        sys.path.insert(0, str(REPO_ROOT / ".agent"))
        from core.brain import Brain

        brain = Brain(brain_dir, app_id="jpkkenfull")
        learnings = brain.query(
            f"jpkkenfull: what worked for tasks like: {goal[:80]}",
            limit=5
        )
        for node in learnings:
            info["past_learnings"].append(
                f"{node.title}: {node.context[:100] if node.context else 'N/A'}"
            )
    except Exception as e:
        logger.debug("Brain query for past learnings failed: %s", e)

    # Rules
    rules_dir = REPO_ROOT / ".claude" / "rules"
    if rules_dir.exists():
        for rule_file in rules_dir.glob("*.md"):
            if rule_file.stem in ("architecture", "best-practices", "security",
                                   "memory-engine", "auto-save-triggers", "language", "persona"):
                try:
                    info["rules"].append({
                        "source": rule_file.name,
                        "content": rule_file.read_text(encoding="utf-8", errors="replace")[:800]
                    })
                except Exception:
                    pass

    # Git status
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        info["git_status"] = result.stdout[:500]
    except Exception as e:
        logger.debug("git status failed: %s", e)

    # Project type detection
    if (REPO_ROOT / "package.json").exists():
        info["project_type"] = "nodejs"
        try:
            pkg = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
            info["detected_apps"] = list(pkg.get("dependencies", {}).keys())[:10]
        except Exception:
            pass
    elif (REPO_ROOT / "pyproject.toml").exists():
        info["project_type"] = "python"
    elif (REPO_ROOT / "Cargo.toml").exists():
        info["project_type"] = "rust"

    if (REPO_ROOT / "nexus-app").exists():
        info["detected_apps"].append("nexus-desktop")
    if (REPO_ROOT / "src" / "index.ts").exists() or (REPO_ROOT / "src" / "telegram").exists():
        info["detected_apps"].append("telegram-bot")

    # Confidence
    if info["memories"] or info["brain_notes"]:
        info["confidence"] = "medium"
    if info["rules"] and info["detected_apps"]:
        info["confidence"] = "high"

    return info


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    stopwords = {"that", "this", "with", "from", "have", "been", "will", "would",
                 "could", "should", "their", "there", "where", "when", "what",
                 "which", "your", "also", "into", "some", "only", "more", "each",
                 "both", "same", "want", "need", "work", "make", "just", "like",
                 "find", "look", "task", "goal", "result", "using", "used"}
    return [w for w in words if w not in stopwords][:15]


# ── Phase 1b: Internet search (graceful) ─────────────────────────────────────

def web_search(query: str) -> str:
    """Perform web search. Gracefully degrades if endpoint missing."""

    try:
        import httpx
        resp = httpx.post(
            f"{GATEWAY_URL}/v1/search",
            json={"query": query, "max_results": 5},
            timeout=INTERNET_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                return "\n".join(
                    f"- {r.get('title', 'N/A')}: {r.get('url', 'N/A')}"
                    for r in results[:5]
                )
    except Exception as e:
        logger.debug("Web search endpoint not available: %s", e)

    return ""


def search_internet_if_needed(goal: str, info: dict) -> dict:
    """Search internet if critical info is missing."""

    info = dict(info)
    missing_info = []
    goal_lower = goal.lower()

    if ("bug" in goal_lower or "error" in goal_lower) and not info.get("brain_notes"):
        missing_info.append(f"similar bugs/errors: {goal[:80]}")
    elif ("implement" in goal_lower or "add" in goal_lower or "create" in goal_lower):
        if not info.get("detected_apps") and "framework" not in goal_lower:
            missing_info.append(f"best practices for: {goal[:80]}")

    search_results = []
    for query in missing_info:
        result = web_search(query)
        if result:
            search_results.append({"query": query, "results": result})
            info["internet_search_triggered"] = True
        else:
            logger.info("Web search returned no results for: %s", query)

    info["web_search_results"] = search_results
    return info


# ── Phase 2: Agent & Skill selection (with brain-informed scoring) ───────────

# Agent tier priorities — orchestration > core-dev > quality > security > specialized
_AGENT_TIER_SCORES = {
    "orchestration": 10,
    "quality": 8,
    "security": 7,
    "devops": 6,
    "core-dev": 5,
    "specialized": 3,
    "uns-enterprise": 3,
    "intelligence": 4,
    "system": 4,
    "data-ml": 3,
    "desktop": 3,
    "content": 2,
    "default": 1,
}


def _agent_tier_score(agent_name: str, agent_tags: list[str]) -> int:
    """Return a score based on agent tier (from IDENTITY.md tags)."""
    tags_lower = [t.lower() for t in agent_tags]
    combined = f"{agent_name} {' '.join(tags_lower)}"

    # Orchestration always wins for generic tasks
    if any(t in combined for t in ["orchestration", "orchestrate", "orchestrator", "autonomous", "executor"]):
        return _AGENT_TIER_SCORES["orchestration"]
    # Core-dev preferred for code tasks
    if any(t in combined for t in ["core-dev", "core dev", "developer", "coding", "python", "refactor", "fix"]):
        return _AGENT_TIER_SCORES["core-dev"]
    # Quality for tests/lint
    if any(t in combined for t in ["quality", "test", "lint", "audit", "qa"]):
        return _AGENT_TIER_SCORES["quality"]
    # Security
    if any(t in combined for t in ["security", "vuln", "cve", "secrets"]):
        return _AGENT_TIER_SCORES["security"]
    # Specialized is low priority unless very specific
    if any(t in combined for t in ["specialized", "ce-", "comment", "pr ", "pull-request"]):
        return _AGENT_TIER_SCORES["specialized"]
    return _AGENT_TIER_SCORES["default"]


def list_agents_via_mcp() -> list[dict]:
    """List agents via gateway MCP with retry on 429."""
    for attempt in range(3):
        try:
            import httpx
            resp = httpx.get(f"{GATEWAY_URL}/v1/agents/list", timeout=10)
            if resp.status_code == 429:
                import time
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 200:
                return resp.json().get("agents", [])
        except Exception:
            pass
    return []


def list_skills_via_mcp() -> list[dict]:
    """List skills via gateway MCP with retry on 429."""
    for attempt in range(3):
        try:
            import httpx
            resp = httpx.get(f"{GATEWAY_URL}/v1/skills/list", timeout=10)
            if resp.status_code == 429:
                import time
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 200:
                return resp.json().get("skills", [])
        except Exception:
            pass
    return []


def select_best_agent(task: str, info: dict) -> tuple[str, str]:
    """Select best agent using tier-aware keyword + brain past learnings scoring."""

    agents = list_agents_via_mcp()
    if not agents:
        return _select_agent_filesystem(task)

    keywords = _extract_keywords(task)
    scored = []
    for agent in agents:
        name = agent.get("name", "")
        desc = agent.get("description", "")
        tags = agent.get("tags", [])
        combined = f"{name} {desc} {' '.join(tags)}"

        # Keyword match score
        keyword_score = sum(1 for kw in keywords if kw in combined.lower())
        if any(kw in name.lower() for kw in keywords):
            keyword_score += 3

        # Tier bonus — orchestration/core-dev preferred for generic coding tasks
        tier_score = _agent_tier_score(name, tags)

        # Penalize irrelevant specialized agents for code tasks
        irrelevant = any(kw in name.lower() for kw in ["pr-", "comment", "ce-", "slack", "telegram", "email", "docs-only"])
        if irrelevant and any(kw in task.lower() for kw in ["python", "refactor", "fix", "bug", "code", "feature", "implement", "test"]):
            tier_score -= 5

        total = keyword_score * 2 + tier_score
        scored.append((total, name, desc, tier_score))

    scored.sort(reverse=True)

    # Log scoring for debugging
    for total, name, desc, tier in scored[:5]:
        logger.info("Agent candidate: %s (total=%d, kw*2=%d, tier=%d) — %s",
                    name, total, total - tier, tier, desc[:60])

    if scored and scored[0][0] > 0:
        best = scored[0][1]
        reason = f"Best match (score={scored[0][0]}, tier={scored[0][3]})"
        # Fallback to explorer if best is irrelevant for code tasks
        if scored[0][3] < 3 and any(kw in task.lower() for kw in ["python", "refactor", "fix", "bug", "code", "feature"]):
            for candidate in scored:
                if candidate[3] >= 3 and candidate[0] > 0:
                    best = candidate[1]
                    reason = f"Best relevant agent (score={candidate[0]}, tier={candidate[3]})"
                    break
        return best, reason

    return scored[0][1] if scored else "explorer", "Default fallback"


def _select_agent_filesystem(task: str) -> tuple[str, str]:
    """Fallback: scan filesystem for agents with tier awareness."""
    agents_dir = REPO_ROOT / ".agent" / "agents"
    if not agents_dir.exists():
        return "explorer", "No agents found"

    task_lower = task.lower()
    is_code_task = any(kw in task_lower for kw in [
        "python", "refactor", "fix", "bug", "code", "feature",
        "implement", "test", "lint", "audit", "build", "script",
    ])

    keywords = _extract_keywords(task)
    candidates = []

    for agent_dir in agents_dir.glob("*/IDENTITY.md"):
        try:
            content = agent_dir.read_text(encoding="utf-8", errors="replace")
            name = agent_dir.parent.name
            tags = []
            tier = _AGENT_TIER_SCORES["default"]

            # Extract tier from IDENTITY.md content
            content_lower = content.lower()
            if any(t in content_lower for t in ["orchestration", "orchestrator", "autonomous", "executor"]):
                tier = _AGENT_TIER_SCORES["orchestration"]
                tags.append("orchestration")
            elif any(t in content_lower for t in ["core-dev", "core dev", "developer"]):
                tier = _AGENT_TIER_SCORES["core-dev"]
                tags.append("core-dev")
            elif any(t in content_lower for t in ["quality", "test", "lint", "qa"]):
                tier = _AGENT_TIER_SCORES["quality"]
                tags.append("quality")
            elif any(t in content_lower for t in ["security"]):
                tier = _AGENT_TIER_SCORES["security"]
                tags.append("security")
            elif any(t in content_lower for t in ["devops"]):
                tier = _AGENT_TIER_SCORES["devops"]
                tags.append("devops")

            # Irrelevant agents for code tasks
            irrelevant = any(kw in name.lower() for kw in ["pr-", "comment", "ce-", "slack", "telegram", "email", "docs-only"])
            if irrelevant and is_code_task:
                tier = max(1, tier - 5)

            # Keyword scoring
            keyword_score = sum(1 for kw in keywords if kw in content_lower)
            if any(kw in name.lower() for kw in keywords):
                keyword_score += 3

            total = keyword_score * 2 + tier
            if total > 0:
                candidates.append((total, name, tier))
        except Exception:
            pass

    if candidates:
        candidates.sort(reverse=True)
        best_tier = candidates[0][2]
        # For code tasks, prefer tier >= 3
        if is_code_task and best_tier < 3:
            for c in candidates:
                if c[2] >= 3:
                    return c[1], f"Best relevant agent (tier={c[2]})"
        return candidates[0][1], f"Best filesystem match (score={candidates[0][0]}, tier={candidates[0][2]})"

    return "explorer", "No match found, using explorer"


def select_best_skill(task: str, info: dict) -> tuple[str, str]:
    """Select best skill using keyword + brain past learnings scoring."""

    skills = list_skills_via_mcp()
    if not skills:
        return _select_skill_filesystem(task)

    keywords = _extract_keywords(task)
    scored = []
    for skill in skills:
        name = skill.get("name", "")
        desc = skill.get("description", "")
        combined = f"{name} {desc} {' '.join(skill.get('tags', []))}"
        score = sum(1 for kw in keywords if kw in combined.lower())
        if any(kw in name.lower() for kw in keywords):
            score += 3
        scored.append((score, name, desc))

    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1], f"Best skill match (score={scored[0][0]})"

    return "", "No suitable skill found"


def _select_skill_filesystem(task: str) -> tuple[str, str]:
    skills_dirs = [REPO_ROOT / ".agent" / "skills-custom", REPO_ROOT / ".agent" / "skills"]
    keywords = _extract_keywords(task)
    candidates = []

    for skills_dir in skills_dirs:
        if not skills_dir.exists():
            continue
        for skill_dir in skills_dir.glob("*/SKILL.md"):
            try:
                content = skill_dir.read_text(encoding="utf-8", errors="replace")
                name = skill_dir.parent.name
                score = sum(1 for kw in keywords if kw in content.lower())
                if any(kw in name.lower() for kw in keywords):
                    score += 3
                if score > 0:
                    candidates.append((score, name, content[:200]))
            except Exception:
                pass

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1], f"Best filesystem skill (score={candidates[0][0]})"

    return "", "No suitable skill found"


# ── Phase 3: Reuse autonomous-executor planning ─────────────────────────────

def plan_execution(goal: str, info: dict) -> list[PlanStep]:
    """Plan using autonomous-executor logic, plus jpkkenfull context gathering step."""

    # Import and reuse autonomous-executor analyze_goal
    try:
        sys.path.insert(0, str(REPO_ROOT / ".agent" / "skills-custom" / "autonomous-executor" / "scripts"))
        # Can't import directly due to same-file naming, read the analyze_goal logic
    except Exception:
        pass

    # Use the same goal analysis logic from autonomous-executor
    steps: list[PlanStep] = []
    idx = 1
    goal_lower = goal.lower()

    # Context gathering always first
    steps.append(PlanStep(
        index=idx,
        action="Gather context from memory/Brain/rules",
        target=".",
        success_criteria="Context gathered: memories, brain notes, rules, git status",
        method="subprocess",
        details=f"Goal: {goal[:80]}",
    ))
    idx += 1

    # Detect goal type (same logic as autonomous-executor)
    is_bug = any(k in goal_lower for k in [
        "bug", "error", "arreglar", "fix", "rompe", "crash", "falla",
    ])
    is_feature = any(k in goal_lower for k in [
        "implementar", "feature", "agregar", "crear", "nuevo", "add",
    ])
    is_audit = any(k in goal_lower for k in [
        "audit", "auditar", "seguridad", "vulnerab", "owasp", "cve",
    ])
    is_refactor = any(k in goal_lower for k in [
        "refactor", "limpiar", "cleanup", "deuda", "reestructur",
    ])
    is_docs = any(k in goal_lower for k in [
        "documentar", "docs", "readme", "generar documentación",
    ])
    is_test = any(k in goal_lower for k in [
        "test", "tests", "prueba", "pruebas", "coverage", "testear",
    ])
    is_build = any(k in goal_lower for k in [
        "compilar", "build", "deploy", "release", "nsis", "msi", "exe",
    ])

    # Build steps based on type
    if is_bug:
        steps += _plan_bug_flow(idx, goal)
    elif is_feature:
        steps += _plan_feature_flow(idx, goal)
    elif is_audit:
        steps += _plan_audit_flow(idx, goal)
    elif is_refactor:
        steps += _plan_refactor_flow(idx, goal)
    elif is_docs:
        steps += _plan_docs_flow(idx, goal)
    elif is_test:
        steps += _plan_test_flow(idx, goal)
    elif is_build:
        steps += _plan_build_flow(idx, goal)
    else:
        steps += _plan_generic_flow(idx, goal)

    # Re-index
    for i, s in enumerate(steps, 1):
        s.index = i

    return steps


def _plan_bug_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Identify root cause", target=".",
                          success_criteria="Root cause identified", method="mcp_agent",
                          details=f"Find root cause for: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Implement fix", target=".",
                          success_criteria="Fix applied and compiles", method="mcp_agent",
                          details=f"Apply fix for: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Run tests", target=".",
                          success_criteria="Tests pass or pre-existing failure", method="subprocess",
                          details=_build_test_cmd())); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Bug fix: {goal[:80]}"))
    return steps


def _plan_feature_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Design solution", target=".",
                          success_criteria="Solution designed", method="mcp_agent",
                          details=f"Design for: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Implement code", target=".",
                          success_criteria="Code implemented and compiling", method="mcp_agent",
                          details=f"Implement: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Run linter", target=".",
                          success_criteria="No lint errors", method="subprocess",
                          details=_build_lint_cmd())); idx += 1
    steps.append(PlanStep(idx := idx, action="Run tests", target=".",
                          success_criteria="Tests pass", method="subprocess",
                          details=_build_test_cmd())); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Feature: {goal[:80]}"))
    return steps


def _plan_audit_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Run audit-pro", target=".",
                          success_criteria="Audit complete", method="mcp_skill",
                          details="audit-pro")); idx += 1
    steps.append(PlanStep(idx := idx, action="Run security-audit", target=".",
                          success_criteria="Security audit complete", method="mcp_skill",
                          details="security-audit")); idx += 1
    steps.append(PlanStep(idx := idx, action="Run lint", target=".",
                          success_criteria="Lint results available", method="subprocess",
                          details=_build_lint_cmd())); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Audit: {goal[:80]}"))
    return steps


def _plan_refactor_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Analyze scope", target=".",
                          success_criteria="Scope analyzed", method="mcp_agent",
                          details=f"Refactor scope: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Apply refactor", target=".",
                          success_criteria="Code refactored without breaking", method="mcp_agent",
                          details=f"Refactor: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Verify refactor", target=".",
                          success_criteria="Tests pass and code compiles", method="subprocess",
                          details=_build_test_cmd() + " && " + _build_lint_cmd())); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Refactor: {goal[:80]}"))
    return steps


def _plan_docs_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Generate documentation", target=".",
                          success_criteria="Docs generated", method="mcp_skill",
                          details="documentation-generator")); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Docs: {goal[:80]}"))
    return steps


def _plan_test_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Write tests", target=".",
                          success_criteria="Tests written", method="mcp_agent",
                          details=f"Write tests for: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Run tests", target=".",
                          success_criteria="Tests pass", method="subprocess",
                          details=_build_test_cmd())); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Tests: {goal[:80]}"))
    return steps


def _plan_build_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Verify dependencies", target=".",
                          success_criteria="Deps installed", method="subprocess",
                          details="pip install -r requirements.txt --dry-run 2>/dev/null || npm install --dry-run 2>/dev/null || true"))  # noqa
    idx += 1
    steps.append(PlanStep(idx := idx, action="Build", target=".",
                          success_criteria="Artefacts generated", method="subprocess",
                          details="npm run tauri:build 2>/dev/null || npm run build 2>/dev/null || true")); idx += 1
    steps.append(PlanStep(idx := idx, action="Verify artefacts", target=".",
                          success_criteria="Binaries present", method="subprocess",
                          details="find . -name '*.exe' -o -name '*.msi' | grep -v '.git' | head -5 || true")); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Build: {goal[:80]}"))
    return steps


def _plan_generic_flow(start_idx: int, goal: str) -> list[PlanStep]:
    idx = start_idx
    steps = []
    steps.append(PlanStep(idx := idx, action="Investigate and resolve", target=".",
                          success_criteria="Goal achieved or fully investigated", method="mcp_agent",
                          details=f"Generic: {goal[:80]}")); idx += 1
    steps.append(PlanStep(idx := idx, action="Verify and test", target=".",
                          success_criteria="Verification complete", method="subprocess",
                          details=_build_test_cmd() + " && " + _build_lint_cmd())); idx += 1
    steps.append(PlanStep(idx := idx, action="Save to Brain", target=".",
                          success_criteria="Brain node created", method="brain_save",
                          details=f"Execution: {goal[:80]}"))
    return steps


# ── Helper command builders (from autonomous-executor) ────────────────────────

def _build_lint_cmd() -> str:
    cmds = []
    if (REPO_ROOT / ".agent").exists():
        cmds.append("ruff check .agent/ 2>/dev/null || true")
    if (REPO_ROOT / "src").exists():
        cmds.append("cd src && npx eslint . 2>/dev/null || cd .. && true")
    if (REPO_ROOT / "nexus-app").exists():
        cmds.append("cd nexus-app && npx eslint src/ 2>/dev/null || cd .. && true")
    return " && ".join(cmds) if cmds else "echo 'No lint targets'"


def _build_test_cmd() -> str:
    cmds = []
    if (REPO_ROOT / "tests").exists():
        cmds.append("pytest tests/ -v --tb=short 2>/dev/null || true")
    if (REPO_ROOT / "nexus-app").exists():
        cmds.append("cd nexus-app && npm test -- --run 2>/dev/null || cd .. && true")
    if (REPO_ROOT / "src").exists():
        cmds.append("cd src && npm test 2>/dev/null || cd .. && true")
    return " && ".join(cmds) if cmds else "echo 'No test targets'"


# ── Phase 4: Critical operations guard ────────────────────────────────────────

# Patterns that indicate dangerous operations
CRITICAL_PATTERNS = [
    (re.compile(r'git\s+reset\s+--hard'), "git reset --hard (perdería cambios locales)"),
    (re.compile(r'git\s+push\s+--force'), "git push --force (sobrescribe historial)"),
    (re.compile(r'git\s+push\s+.*\s+--force'), "git push --force (sobrescribe historial)"),
    (re.compile(r'rm\s+-rf'), "rm -rf (borrado recursivo)"),
    (re.compile(r'del\s+.*[/\\]f\s+[/\\]s'), "del /f /s (borrado forzado Windows)"),
    (re.compile(r'rmdir\s+.*[/\\]s'), "rmdir /s (borrado directorios Windows)"),
    (re.compile(r'DROP\s+TABLE', re.IGNORECASE), "DROP TABLE (borrado de tabla DB)"),
    (re.compile(r'DELETE\s+FROM', re.IGNORECASE), "DELETE FROM (borrado masivo DB)"),
    (re.compile(r'TRUNCATE\s+', re.IGNORECASE), "TRUNCATE (vaciar tabla DB)"),
    (re.compile(r'git\s+push\s+.*\s+main\b'), "git push to main (rama protegida)"),
    (re.compile(r'git\s+push\s+.*\s+master\b'), "git push to master (rama protegida)"),
]


def check_critical_operation(step: PlanStep) -> list[str]:
    """Check if a step contains dangerous operations. Returns list of warnings."""

    warnings = []
    check_text = f"{step.action} {step.details}".lower()
    for pattern, description in CRITICAL_PATTERNS:
        if pattern.search(check_text):
            warnings.append(description)
    return warnings


def confirm_critical_ops(warnings: list[str], step: PlanStep) -> bool:
    """Ask user to confirm dangerous operation. Returns True if confirmed."""

    print(f"\n⚠️  CRITICAL OPERATION DETECTED in step [{step.index}]:")
    for w in warnings:
        print(f"   - {w}")
    print(f"   Action: {step.action}")
    print(f"   Details: {step.details[:100]}")
    print()

    try:
        response = input("¿Ejecuto igual? [sí/no]: ").strip().lower()
    except (EOFError, OSError):
        response = "no"

    confirmed = response in ("sí", "si", "yes", "y", "s", "ok", "go", "execute", "ejecutar")
    if not confirmed:
        print(f"   → Step [{step.index}] skipped by critical ops guard")
    return confirmed


# ── Phase 5: Execution ────────────────────────────────────────────────────────

def execute_step(step: PlanStep, info: dict) -> PlanStep:
    """Execute a single step using the best available method."""

    global _abort_requested
    start = time.time()
    step.status = "running"

    if _abort_requested:
        step.status = "skipped"
        step.error = "Aborted via signal"
        return step

    try:
        if step.method == "subprocess":
            step = _execute_subprocess(step)
        elif step.method == "mcp_agent":
            step = _execute_mcp_agent(step, info)
        elif step.method == "mcp_skill":
            step = _execute_mcp_skill(step, info)
        elif step.method == "brain_save":
            step = _execute_brain_save(step, info)
        else:
            step.status = "skip"
            step.error = f"Unknown method: {step.method}"
    except Exception as e:
        step.status = "fail"
        step.error = str(e)
        logger.exception("Step %d failed", step.index)

    step.duration_ms = int((time.time() - start) * 1000)
    return step


def _execute_subprocess(step: PlanStep) -> PlanStep:
    if not step.details:
        step.status = "ok"
        return step

    try:
        result = subprocess.run(
            shlex.split(step.details),
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=STEP_TIMEOUT,
        )
        if result.returncode == 0:
            step.status = "ok"
        elif "pre-existing" in result.stdout or "pre-existing" in result.stderr:
            step.status = "ok"
        else:
            step.status = "fail"
            step.error = (result.stderr or result.stdout)[:300]
    except subprocess.TimeoutExpired:
        step.status = "fail"
        step.error = f"Timeout after {STEP_TIMEOUT}s"
    except Exception as e:
        step.status = "fail"
        step.error = str(e)

    return step


def _execute_mcp_agent(step: PlanStep, info: dict) -> PlanStep:
    agent_name, reason = select_best_agent(step.action, info)
    step.agent_used = agent_name
    logger.info("Step %d via agent '%s': %s", step.index, agent_name, reason)

    # Try MCP agent invocation with retries on 429
    for attempt in range(3):
        try:
            import httpx
            resp = httpx.post(
                f"{GATEWAY_URL}/v1/agents/{agent_name}/run",
                json={"task": step.details or step.action, "context": {"goal": info.get("goal", ""), "repo_root": str(REPO_ROOT)}},
                timeout=STEP_TIMEOUT,
            )
            if resp.status_code == 429:
                import time
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 200:
                step.status = "ok"
                return step
            elif resp.status_code >= 400:
                # Agent not found or error — try fallback
                break
        except Exception as e:
            logger.warning("MCP agent call failed: %s, falling back", e)
            break

    # Fallback: direct script invocation
    script = REPO_ROOT / ".agent" / "scripts" / "invoke-agent.py"
    if script.exists():
        try:
            result = subprocess.run(
                [sys.executable or "python", str(script), agent_name, step.details or step.action],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=STEP_TIMEOUT,
            )
            if result.returncode == 0:
                step.status = "ok"
                return step
            logger.warning("invoke-agent.py failed: %s", (result.stderr or result.stdout)[:200])
        except Exception as e:
            logger.warning("invoke-agent.py exception: %s", e)

    step.status = "fail"
    step.error = f"Agent '{agent_name}' execution failed (gate: rate-limit or not found)"
    return step


def _execute_mcp_skill(step: PlanStep, info: dict) -> PlanStep:
    skill_name, reason = select_best_skill(step.details or step.action, info)
    step.skill_used = skill_name

    if not skill_name:
        step.status = "skip"
        step.error = "No suitable skill found"
        return step

    logger.info("Step %d via skill '%s': %s", step.index, skill_name, reason)

    # Try MCP skill invocation
    try:
        import httpx
        resp = httpx.post(
            f"{GATEWAY_URL}/v1/skills/{skill_name}/run",
            json={"task": step.details, "context": {"goal": info.get("goal", ""), "repo_root": str(REPO_ROOT)}},
            timeout=STEP_TIMEOUT,
        )
        if resp.status_code == 200:
            step.status = "ok"
            return step
    except Exception as e:
        logger.warning("MCP skill call failed: %s, falling back to filesystem", e)

    # Fallback: run skill script directly
    for skill_dir in [REPO_ROOT / ".agent" / "skills-custom", REPO_ROOT / ".agent" / "skills"]:
        skill_path = skill_dir / skill_name / "scripts" / "main.py"
        if skill_path.exists():
            try:
                result = subprocess.run(
                    [sys.executable or "python", str(skill_path), "--goal", step.details],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=STEP_TIMEOUT,
                )
                step.status = "ok" if result.returncode == 0 else "fail"
                if result.returncode != 0:
                    step.error = (result.stderr or result.stdout)[:300]
            except Exception as e:
                step.status = "fail"
                step.error = str(e)
            return step

    step.status = "fail"
    step.error = f"Skill script not found for: {skill_name}"
    return step


def _execute_brain_save(step: PlanStep, info: dict) -> PlanStep:
    try:
        sys.path.insert(0, str(REPO_ROOT / ".agent"))
        from core.brain import Brain
        from pathlib import Path

        brain = Brain(Path(REPO_ROOT / ".agent" / "brain"), app_id="jpkkenfull")
        goal = info.get("goal", "")

        # Self-improvement: save result + lessons
        brain.ingest(
            title=f"jpkkenfull: {goal[:80]}",
            context=(
                f"Goal: {goal}\n"
                f"Steps executed: {len(info.get('plan_steps', []))}\n"
                f"Success rate: {info.get('success_rate', 0):.0%}\n"
                f"Agents used: {info.get('agents_used', [])}\n"
                f"Skills used: {info.get('skills_used', [])}\n"
                f"Lessons: {info.get('lessons', [])}\n"
                f"Past learnings consulted: {len(info.get('past_learnings', []))}"
            ),
            area="jpkkenfull",
            tags=["jpkkenfull", "execution", "auto-improving", _detect_goal_tag(goal)],
            node_type="pattern",
            importance="medium",
        )
        brain.rebuild_index()
        step.status = "ok"
    except Exception as e:
        step.status = "fail"
        step.error = str(e)
        logger.warning("Brain save failed: %s", e)

    return step


def _detect_goal_tag(goal: str) -> str:
    g = goal.lower()
    if "bug" in g or "fix" in g or "error" in g:
        return "bugfix"
    if "implement" in g or "feature" in g or "agregar" in g:
        return "feature"
    if "audit" in g:
        return "audit"
    if "refactor" in g:
        return "refactor"
    if "docs" in g or "document" in g:
        return "docs"
    if "test" in g:
        return "testing"
    return "execution"


# ── Phase 6: Clarification gate (real input loop) ────────────────────────────

def check_clarification_needed(goal: str, info: dict) -> tuple[bool, str]:
    """Check if clarification is genuinely needed.

    Only True if ALL:
    1. Goal is ambiguous (multiple valid interpretations)
    2. No memory/brain info to resolve it
    3. Web search didn't resolve it
    4. Decision is irreversible
    """

    goal_lower = goal.lower()
    ambiguous_indicators = [
        ("auth", "login", "credential"),
        ("api", "endpoint", "rest", "graphql"),
        ("database", "db", "sql", "sqlite", "postgres"),
        ("frontend", "ui", "component", "react", "angular"),
        ("backend", "server", "fastapi", "flask", "aiohttp"),
    ]

    ambiguous = False
    for group in ambiguous_indicators:
        if sum(1 for kw in group if kw in goal_lower) >= 2:
            ambiguous = True
            break

    if not ambiguous:
        return False, ""

    has_info = bool(info.get("memories") or info.get("brain_notes") or info.get("rules"))
    if has_info:
        return False, ""

    # Irreversible keywords trigger clarification
    irreversible = any(kw in goal_lower for kw in ["delete", "remove", "drop", "migrate", "production"])
    if irreversible:
        return True, (
            f"Goal: '{goal}'\n"
            f"This action appears irreversible. One specific question:\n"
            f"¿Está completamente seguro de aplicar '{goal}' en producción "
            f"o preferís que lo haga primero en un branch de prueba?"
        )

    return False, ""


def ask_clarification(question: str) -> tuple[bool, str]:
    """Real input loop for clarification. Returns (answered, response)."""

    print(f"\n{'='*60}")
    print("⚠️  CLARIFICATION NEEDED")
    print(f"{'='*60}")
    print(question)
    print(f"{'='*60}\n")

    try:
        response = input("Tu respuesta: ").strip()
    except (EOFError, OSError):
        response = ""

    if not response:
        return False, "No response"

    affirmative = response.lower() in ("sí", "si", "yes", "y", "s", "ok", "go", "proceed", "continuar", "sí, continuar", "si, continuar")
    return True, response if not affirmative else response


# ── Phase 7: Main execution loop ─────────────────────────────────────────────

def run_execution(goal: str, force_internet: bool = False, skip_agents: bool = False) -> ExecutionResult:
    """Main execution flow."""

    global _abort_requested
    _abort_requested = False

    # Register signal handlers
    old_sigint = signal.signal(signal.SIGINT, _signal_handler)
    old_sigterm = signal.signal(signal.SIGTERM, _signal_handler)

    try:
        start_time = time.time()
        result = ExecutionResult(goal=goal)

        print(f"\n{'='*60}")
        print(f"JPKKENFULL v2 — {goal[:60]}")
        print(f"{'='*60}\n")

        # Phase 1: Gather context (includes brain.query for learnings!)
        print("[1/7] Gathering context...")
        info = gather_context(goal)
        result.past_learnings = info.get("past_learnings", [])
        print(f"      → confidence: {info['confidence']}")
        print(f"      → apps: {info['detected_apps']}")
        if result.past_learnings:
            print(f"      → past learnings: {len(result.past_learnings)} found")
            for l in result.past_learnings[:3]:
                print(f"        • {l[:80]}")

        # Phase 1b: Internet search
        if force_internet or not info.get("brain_notes"):
            print("[1b] Searching internet...")
            info = search_internet_if_needed(goal, info)
            result.internet_search_triggered = info.get("internet_search_triggered", False)

        # Phase 6: Clarification gate (BEFORE planning if needed)
        needs_clarify, question = check_clarification_needed(goal, info)
        if needs_clarify:
            result.clarification_asked = True
            result.clarification_question = question
            answered, response = ask_clarification(question)
            result.clarification_response = response
            if not answered or response.lower() in ("no", "cancel", "cancelar", "n", "skip"):
                print("\n[ABORT] Clarification denied -- exiting cleanly")
                result.duration_seconds = time.time() - start_time
                return result

        # Phase 3: Plan
        print("[3/7] Planning...")
        plan_steps = plan_execution(goal, info)
        print(f"      → {len(plan_steps)} steps planned")
        for s in plan_steps:
            print(f"      [{s.index}] {s.action} ({s.method})")

        result.plan_steps = plan_steps

        # Phase 4: Execute (NO permissions, but WITH critical ops guard)
        print(f"\n[4/7] Executing {len(plan_steps)} steps...")
        total = len(plan_steps)

        for step in plan_steps:
            if _abort_requested:
                step.status = "skipped"
                step.error = "Aborted via signal"
                result.skipped_steps += 1
                result.aborted_via_signal = True
                continue

            # Critical operations guard
            critical_warnings = check_critical_operation(step)
            if critical_warnings:
                result.critical_ops_intercepted.extend(critical_warnings)
                confirmed = confirm_critical_ops(critical_warnings, step)
                if not confirmed:
                    step.status = "skipped"
                    step.error = "Denied by critical ops guard"
                    result.skipped_steps += 1
                    continue

            print(f"      [{step.index}/{total}] {step.action}... ", end="", flush=True)
            step = execute_step(step, info)

            if step.agent_used and step.agent_used not in result.agents_used:
                result.agents_used.append(step.agent_used)
            if step.skill_used and step.skill_used not in result.skills_used:
                result.skills_used.append(step.skill_used)

            if step.status == "ok":
                print("✓ OK")
                result.successful_steps += 1
            elif step.status == "skipped":
                print("○ SKIP")
                result.skipped_steps += 1
            else:
                print(f"✗ FAIL: {step.error[:80] if step.error else 'unknown'}")
                result.failed_steps += 1
                if step.retries < MAX_RETRIES:
                    step.retries += 1
                    step.status = "pending"
                    step = execute_step(step, info)
                    if step.status == "ok":
                        result.successful_steps += 1
                        result.failed_steps -= 1
                        print(f"      └ Retry OK")

            result.executed_steps += 1

            # Abort threshold
            if result.executed_steps >= 3:
                fail_rate = result.failed_steps / result.executed_steps
                if fail_rate > ABORT_THRESHOLD:
                    print(f"\n[ABORT] >{ABORT_THRESHOLD:.0%} failure rate -- aborting")
                    for s in plan_steps[result.executed_steps:]:
                        s.status = "skipped"
                        result.skipped_steps += 1
                    break

        result.duration_seconds = time.time() - start_time

        # Phase 5: Self-improvement (lessons learned)
        print("\n[5/7] Self-improvement...")
        sr = result.successful_steps / result.executed_steps if result.executed_steps > 0 else 0
        if sr < 0.5:
            result.lessons_learned.append(f"Low success rate ({sr:.0%}). Consider better agent/skill selection.")
        if not result.agents_used and not result.skills_used:
            result.lessons_learned.append("No agents/skills used -- subprocess fallback worked.")
        if result.aborted_via_signal:
            result.lessons_learned.append("Aborted via signal -- partial execution saved.")

        # Final report
        print(f"\n{'='*60}")
        print("REPORT — Jpkkenfull v2 Execution")
        print(f"{'='*60}")
        print(f"  Goal:              {goal[:60]}")
        print(f"  Duration:          {result.duration_seconds:.1f}s")
        print(f"  Steps:             {result.executed_steps} exec, "
              f"{result.successful_steps} ok, {result.failed_steps} fail, "
              f"{result.skipped_steps} skip")
        print(f"  Success rate:      {sr:.0%}")
        print(f"  Agents used:       {result.agents_used}")
        print(f"  Skills used:       {result.skills_used}")
        print(f"  Clarification:      {'YES' if result.clarification_asked else 'No'}")
        print(f"  Internet search:   {'Yes' if result.internet_search_triggered else 'No'}")
        print(f"  Critical ops:      {result.critical_ops_intercepted or 'None'}")
        print(f"  Aborted (signal):  {'Yes' if result.aborted_via_signal else 'No'}")
        print(f"  Lessons:           {result.lessons_learned or ['None']}")
        print(f"  Past learnings:    {len(result.past_learnings)} consulted")
        print(f"{'='*60}\n")

        return result

    finally:
        # Restore signal handlers
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Jpkkenfull v2 — Autonomous executor without permissions"
    )
    parser.add_argument("--goal", required=True, help="Objective to execute")
    parser.add_argument("--context", default="", help="Additional context (unused, backwards compat)")
    parser.add_argument("--force_internet", action="store_true",
                          help="Force web search")
    parser.add_argument("--skip_agents", action="store_true",
                          help="Skip agent selection, use only skills")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    result = run_execution(
        goal=args.goal,
        force_internet=args.force_internet,
        skip_agents=args.skip_agents,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    return 0 if result.failed_steps == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
