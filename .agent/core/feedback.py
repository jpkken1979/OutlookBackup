#!/usr/bin/env python3
"""
Feedback Capture Pipeline.

Captures user feedback on agent outputs and feeds it into the learning system.

Features:
- Register executions for potential feedback
- Collect explicit ratings (1-5)
- Track implicit acceptance/rejection
- Process corrections
- Feed learnings to AutonomousLearningPipeline
"""

import asyncio
import inspect
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("antigravity.feedback")


class FeedbackRating(Enum):
    """Feedback rating levels."""

    TERRIBLE = 1
    POOR = 2
    OKAY = 3
    GOOD = 4
    EXCELLENT = 5


@dataclass
class ExecutionFeedback:
    """Feedback for an execution."""

    task_id: str
    rating: int | None = None
    accepted: bool = False
    corrections: str | None = None
    feedback_at: str | None = None
    implicit_signals: list[str] = field(default_factory=list)


@dataclass
class PendingExecution:
    """An execution awaiting feedback."""

    task_id: str
    execution_data: dict
    registered_at: str
    feedback: ExecutionFeedback | None = None
    expires_at: str | None = None


class FeedbackCollector:
    """
    Collect and process user feedback on agent outputs.

    Integrates with AutonomousLearningPipeline to:
    - Reinforce successful approaches
    - Mark failing approaches for improvement
    - Learn user preferences
    """

    def __init__(self, data_dir: str = ".agent/data/feedback", feedback_ttl_hours: int = 24):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.pending: dict[str, PendingExecution] = {}
        self.feedback_history: list[ExecutionFeedback] = []
        self.feedback_ttl = timedelta(hours=feedback_ttl_hours)

        # Learning pipeline reference (lazy loaded)
        self._learning_pipeline = None

        # Callbacks for feedback events
        self._on_feedback_callbacks: list[Callable] = []

        # Load persisted state
        self._load_state()

        logger.info(f"FeedbackCollector initialized at {self.data_dir}")

    @property
    def learning_pipeline(self):
        """Lazy load learning pipeline."""
        if self._learning_pipeline is None:
            try:
                from .autonomous_learning import get_learning_pipeline

                self._learning_pipeline = get_learning_pipeline()  # type: ignore[assignment]  # dep opcional: autonomous_learning
            except ImportError:
                logger.warning("AutonomousLearningPipeline not available")
        return self._learning_pipeline

    def _load_state(self):
        """Load persisted state."""
        state_file = self.data_dir / "feedback_state.json"
        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    state = json.load(f)
                    # Restore pending executions
                    for task_id, data in state.get("pending", {}).items():
                        self.pending[task_id] = PendingExecution(
                            task_id=task_id,
                            execution_data=data.get("execution_data", {}),
                            registered_at=data.get("registered_at", ""),
                            expires_at=data.get("expires_at"),
                        )
                    logger.info(f"Loaded {len(self.pending)} pending feedback requests")
            except Exception as e:
                logger.warning(f"Could not load feedback state: {e}")

    def _save_state(self):
        """Persist state."""
        state_file = self.data_dir / "feedback_state.json"
        try:
            state = {
                "pending": {
                    task_id: {
                        "execution_data": p.execution_data,
                        "registered_at": p.registered_at,
                        "expires_at": p.expires_at,
                    }
                    for task_id, p in self.pending.items()
                },
                "saved_at": datetime.now().isoformat(),
            }
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save feedback state: {e}")

    async def register_execution(self, task_id: str, execution_data: dict) -> str:
        """
        Register an execution for potential feedback.

        Args:
            task_id: Unique task identifier
            execution_data: Data about the execution

        Returns:
            Feedback URL/callback reference
        """
        now = datetime.now()
        expires = now + self.feedback_ttl

        self.pending[task_id] = PendingExecution(
            task_id=task_id,
            execution_data=execution_data,
            registered_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )

        self._save_state()
        self._cleanup_expired()

        logger.debug(f"Registered execution for feedback: {task_id}")
        return f"/feedback/{task_id}"

    async def submit_feedback(
        self,
        task_id: str,
        rating: int | None = None,
        accepted: bool = True,
        corrections: str | None = None,
    ) -> bool:
        """
        Submit user feedback for an execution.

        Args:
            task_id: Task to provide feedback for
            rating: Rating 1-5 (optional)
            accepted: Whether output was accepted
            corrections: Any corrections made (optional)

        Returns:
            True if feedback was processed
        """
        if task_id not in self.pending:
            logger.warning(f"No pending execution for task_id: {task_id}")
            return False

        execution = self.pending[task_id]

        # Create feedback record
        feedback = ExecutionFeedback(
            task_id=task_id,
            rating=rating,
            accepted=accepted,
            corrections=corrections,
            feedback_at=datetime.now().isoformat(),
        )

        execution.feedback = feedback
        self.feedback_history.append(feedback)

        # Process feedback for learning
        await self._process_feedback(execution, feedback)

        # Notify callbacks
        for callback in self._on_feedback_callbacks:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(feedback)
                else:
                    callback(feedback)
            except Exception as e:
                logger.warning(f"Feedback callback error: {e}")

        # Remove from pending
        del self.pending[task_id]
        self._save_state()

        logger.info(f"Feedback submitted for {task_id}: rating={rating}, accepted={accepted}")
        return True

    async def submit_implicit_signal(self, task_id: str, signal: str):
        """
        Submit an implicit feedback signal.

        Signals:
        - "used_output" - User used the output
        - "modified_output" - User modified the output
        - "discarded_output" - User discarded the output
        - "asked_revision" - User asked for revision
        - "time_viewing" - Time spent viewing (value: seconds)

        Args:
            task_id: Task to signal about
            signal: Signal type
        """
        if task_id not in self.pending:
            return

        execution = self.pending[task_id]

        if execution.feedback is None:
            execution.feedback = ExecutionFeedback(task_id=task_id)

        execution.feedback.implicit_signals.append(signal)

        # Interpret implicit signals
        if signal == "used_output":
            execution.feedback.accepted = True
        elif signal == "discarded_output" or signal == "asked_revision":
            execution.feedback.accepted = False

    async def _process_feedback(self, execution: PendingExecution, feedback: ExecutionFeedback):
        """Process feedback for learning."""
        if not self.learning_pipeline:
            return

        try:
            from .autonomous_learning import FeedbackType

            # Determine feedback type
            if feedback.rating:
                if feedback.rating >= 4:
                    feedback_type = FeedbackType.EXPLICIT_POSITIVE
                elif feedback.rating <= 2:
                    feedback_type = FeedbackType.EXPLICIT_NEGATIVE
                else:
                    feedback_type = (
                        FeedbackType.IMPLICIT_ACCEPTANCE
                        if feedback.accepted
                        else FeedbackType.IMPLICIT_REJECTION
                    )
            else:
                feedback_type = (
                    FeedbackType.IMPLICIT_ACCEPTANCE
                    if feedback.accepted
                    else FeedbackType.IMPLICIT_REJECTION
                )

            # If corrections provided, it's a correction type
            if feedback.corrections:
                feedback_type = FeedbackType.CORRECTION

            # Send to learning pipeline
            await self.learning_pipeline.process_feedback(
                feedback_type=feedback_type,
                context={
                    "task": execution.execution_data.get("task", ""),
                    "task_type": execution.execution_data.get("task_type", ""),
                    "agents": execution.execution_data.get("agents_used", []),
                    "rating": feedback.rating,
                    "accepted": feedback.accepted,
                },
                details=feedback.corrections,
            )

            # Learn user preferences from high ratings
            if feedback.rating and feedback.rating >= 4:
                task_type = execution.execution_data.get("task_type", "general")
                agents = execution.execution_data.get("agents_used", [])

                await self.learning_pipeline.learn_preference(
                    category="agent_selection",
                    key=task_type,
                    value=agents,
                    observation_strength=feedback.rating / 5.0,
                )

            logger.debug(f"Feedback processed for learning: {feedback_type.value}")

        except Exception as e:
            logger.error(f"Error processing feedback for learning: {e}")

    def on_feedback(self, callback: Callable):
        """Register a callback for feedback events."""
        self._on_feedback_callbacks.append(callback)

    def _cleanup_expired(self):
        """Remove expired pending executions."""
        now = datetime.now()
        expired = [
            task_id
            for task_id, execution in self.pending.items()
            if execution.expires_at and datetime.fromisoformat(execution.expires_at) < now
        ]

        for task_id in expired:
            # Treat expired without feedback as implicit rejection
            execution = self.pending[task_id]
            if execution.feedback is None:
                logger.debug(f"Expired without feedback: {task_id}")
            del self.pending[task_id]

        if expired:
            self._save_state()

    def get_pending_count(self) -> int:
        """Get count of pending feedback requests."""
        return len(self.pending)

    def get_stats(self) -> dict:
        """Get feedback statistics."""
        if not self.feedback_history:
            return {"total_feedback": 0, "average_rating": None, "acceptance_rate": None}

        rated = [f for f in self.feedback_history if f.rating]
        accepted = [f for f in self.feedback_history if f.accepted]

        return {
            "total_feedback": len(self.feedback_history),
            "average_rating": sum(f.rating for f in rated if f.rating is not None) / len(rated)
            if rated
            else None,
            "acceptance_rate": len(accepted) / len(self.feedback_history),
            "pending_count": len(self.pending),
            "with_corrections": sum(1 for f in self.feedback_history if f.corrections),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_collector: FeedbackCollector | None = None


def get_feedback_collector() -> FeedbackCollector:
    """Get the feedback collector instance."""
    global _collector
    if _collector is None:
        _collector = FeedbackCollector()
    return _collector


async def register_for_feedback(task_id: str, execution_data: dict) -> str:
    """Register an execution for feedback."""
    collector = get_feedback_collector()
    return await collector.register_execution(task_id, execution_data)


async def submit_user_feedback(
    task_id: str, rating: int | None = None, accepted: bool = True, corrections: str | None = None
) -> bool:
    """Submit user feedback."""
    collector = get_feedback_collector()
    return await collector.submit_feedback(task_id, rating, accepted, corrections)


# =============================================================================
# CLI
# =============================================================================


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Feedback Capture Pipeline")
    parser.add_argument("--stats", action="store_true", help="Show feedback statistics")
    parser.add_argument("--pending", action="store_true", help="Show pending feedback requests")
    parser.add_argument("--submit", type=str, help="Submit feedback for task ID")
    parser.add_argument("--rating", type=int, choices=[1, 2, 3, 4, 5], help="Rating (1-5)")
    parser.add_argument("--accepted", action="store_true", help="Mark as accepted")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    collector = get_feedback_collector()

    if args.stats:
        stats = collector.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("Feedback Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")

    elif args.pending:
        pending = list(collector.pending.keys())
        if args.json:
            print(json.dumps(pending, indent=2))
        else:
            print(f"Pending feedback requests ({len(pending)}):")
            for task_id in pending:
                print(f"  - {task_id}")

    elif args.submit:
        success = await collector.submit_feedback(
            task_id=args.submit, rating=args.rating, accepted=args.accepted
        )
        print(f"Feedback submitted: {success}")

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
