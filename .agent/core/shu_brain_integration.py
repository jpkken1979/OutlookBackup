from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_BRAIN_DIR_RELATIVE = ".agent/brain"
_APP_ID = "nexus-mother"


def _resolve_brain_dir() -> Path:
    root_env = os.environ.get("ANTIGRAVITY_ROOT", "")
    if root_env:
        return Path(root_env) / _DEFAULT_BRAIN_DIR_RELATIVE
    return Path(__file__).parent.parent.parent / _DEFAULT_BRAIN_DIR_RELATIVE


class ShuBrainIntegrator:
    def __init__(self, brain_dir=None, app_id=_APP_ID):
        self._brain_dir = Path(brain_dir) if brain_dir is not None else _resolve_brain_dir()
        self._app_id = app_id
        self._brain: Any = None

    def _get_brain(self) -> Any:
        if self._brain is None:
            import sys

            agent_path = str(self._brain_dir.parent.parent)
            if agent_path not in sys.path:
                sys.path.insert(0, agent_path)
            from core.brain.core import Brain

            self._brain = Brain(self._brain_dir, app_id=self._app_id)
        return self._brain

    def ingest_execution(
        self, goal: str, category: str, responses: list[str], result: str, execution_time_ms: float
    ) -> str:
        if not goal or not goal.strip():
            raise ValueError("goal no puede estar vacio")
        importance = "high" if result == "error" else "medium"
        title = f"[SHU] {category} - {goal[:50]}"
        context_data = {
            "goal": goal,
            "category": category,
            "result": result,
            "execution_time_ms": execution_time_ms,
            "responses": responses,
        }
        context = json.dumps(context_data, ensure_ascii=False, indent=2)
        tags: list[str] = []
        seen: set[str] = set()
        for t in ["shu", category, result]:
            if t not in seen:
                seen.add(t)
                tags.append(t)
        brain = self._get_brain()
        node = brain.ingest(
            title=title,
            context=context,
            area="intelligence",
            tags=tags,
            node_type="session",
            importance=importance,
        )
        logger.info("[INFO] SHU -> Brain: nodo creado %s", node.slug)
        return node.slug

    def ingest_improvement(self, suggestions: dict[str, Any], affected_templates: list[str]) -> str:
        timestamp = datetime.now(UTC).isoformat()
        title = f"[SHU Auto-Improve] {timestamp}"
        context_data = {
            "timestamp": timestamp,
            "suggestions": suggestions,
            "affected_templates": affected_templates,
        }
        context = json.dumps(context_data, ensure_ascii=False, indent=2)
        brain = self._get_brain()
        node = brain.ingest(
            title=title,
            context=context,
            area="intelligence",
            tags=["shu", "auto-improvement", "quality"],
            node_type="pattern",
            importance="high",
        )
        logger.info("[INFO] SHU -> Brain: mejora ingestada %s", node.slug)
        return node.slug

    def query_similar_goals(self, goal: str, limit: int = 5) -> list[dict[str, Any]]:
        if not goal or not goal.strip():
            return []
        try:
            brain = self._get_brain()
            nodes = brain.query(f"SHU {goal}", limit=limit * 2)
        except Exception as exc:
            logger.debug("[DEBUG] query_similar_goals fallo: %s", exc)
            return []
        results: list[dict[str, Any]] = []
        for node in nodes:
            if "shu" not in (node.tags or []):
                continue
            try:
                data = json.loads(node.context or "{}")
            except (json.JSONDecodeError, AttributeError):
                continue
            if "goal" not in data:
                continue
            results.append(
                {
                    "goal": data.get("goal", ""),
                    "category": data.get("category", ""),
                    "result": data.get("result", ""),
                    "execution_time_ms": data.get("execution_time_ms", 0.0),
                }
            )
            if len(results) >= limit:
                break
        return results

    def get_improvement_history(self, limit: int = 10) -> list[dict[str, Any]]:
        try:
            brain = self._get_brain()
            nodes = brain.query("SHU Auto-Improve", limit=limit * 2)
        except Exception as exc:
            logger.debug("[DEBUG] get_improvement_history fallo: %s", exc)
            return []
        results: list[dict[str, Any]] = []
        for node in nodes:
            if "auto-improvement" not in (node.tags or []):
                continue
            try:
                data = json.loads(node.context or "{}")
            except (json.JSONDecodeError, AttributeError):
                continue
            suggestions = data.get("suggestions", {})
            affected = data.get("affected_templates", [])
            results.append(
                {
                    "timestamp": data.get("timestamp", ""),
                    "suggestions_count": len(suggestions),
                    "templates_affected": affected,
                }
            )
            if len(results) >= limit:
                break
        return results
