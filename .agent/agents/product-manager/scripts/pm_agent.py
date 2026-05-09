#!/usr/bin/env python3
"""
Product Manager Agent

Capabilities:
- Product roadmap planning
- User story creation
- Feature prioritization (MoSCoW, RICE, ICE)
- PRD document generation
- KPI definition
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserStory:
    """User story."""

    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    priority: str = ""
    story_points: int = 0
    acceptance_criteria: list[str] = field(default_factory=list)


class ProductManager:
    """Product Manager agent for product planning and requirements."""

    def __init__(self) -> None:
        self.name = "ProductManager"
        logger.info("ProductManager initialized")

    async def execute(self, task: str) -> dict[str, Any]:
        """Execute a product management task.

        Args:
            task: Description of the product task.

        Returns:
            Dictionary with user stories, roadmap, or PRD content.
        """
        logger.info(f"Executing product task: {task[:80]}")

        result: dict[str, Any] = {
            "agent": self.name,
            "task": task,
            "status": "completed",
            "summary": "",
            "user_stories": [],
            "roadmap": None,
            "prd": None,
            "recommendations": [],
        }

        task_lower = task.lower()

        if "user story" in task_lower or "stories" in task_lower or "login" in task_lower:
            result["summary"] = "User stories generated for the feature"
            result["user_stories"] = [
                {
                    "id": "US-001",
                    "title": "User login with email and password",
                    "as_a": "registered user",
                    "i_want": "login with email and password",
                    "so_that": "I can access my account and personal data",
                    "priority": "Must have",
                    "story_points": 5,
                    "acceptance_criteria": [
                        "Given user has valid credentials, when they submit login form, then they are redirected to dashboard",
                        "Given user has invalid credentials, when they submit, then error message 'Invalid email or password' is shown",
                        "Given user has not confirmed email, when they login, then they are redirected to resend confirmation page",
                    ],
                },
                {
                    "id": "US-002",
                    "title": "Password reset via email",
                    "as_a": "user who forgot password",
                    "i_want": "receive a password reset email",
                    "so_that": "I can regain access to my account",
                    "priority": "Should have",
                    "story_points": 3,
                    "acceptance_criteria": [
                        "Given user enters valid email, when they click 'forgot password', then email is sent within 30 seconds",
                        "Given user enters non-existent email, when they click 'forgot password', then generic success message is shown (security)",
                    ],
                },
            ]
            result["recommendations"].append("Consider OAuth2 social login as future enhancement")
            result["recommendations"].append("Add rate limiting to prevent brute force attacks")

        elif "roadmap" in task_lower or "prioritize" in task_lower:
            result["summary"] = "Feature prioritization and roadmap provided"
            result["roadmap"] = {
                "Q1": ["User authentication (Must)", "Dashboard v1 (Must)", "User profile (Should)"],
                "Q2": ["Notifications (Should)", "Team collaboration (Could)", "Analytics (Won't - next phase)"],
                "Q3": ["API integrations (Must)", "Mobile app (Should)", "Advanced reporting (Could)"],
            }
            result["recommendations"].append("Use MoSCoW for initial prioritization, RICE for refinement")
            result["recommendations"].append("Review roadmap quarterly with stakeholder input")

        elif "prd" in task_lower or "requirements" in task_lower or "document" in task_lower:
            result["summary"] = "PRD document generated"
            result["prd"] = {
                "title": "User Authentication System",
                "problem_statement": "Users cannot access the platform without a secure authentication mechanism, leading to potential data breaches and poor user experience.",
                "goals": [
                    "Provide secure login for registered users",
                    "Enable password recovery",
                    "Support social login (Google, GitHub)",
                ],
                "scope": {
                    "in": ["Login form", "Password reset", "Email verification", "Session management"],
                    "out": ["User registration (separate epic)", "Admin user management", "SSO integration (v2)"],
                },
                "success_metrics": [
                    "Login success rate > 95%",
                    "Average login time < 2 seconds",
                    "Password reset completion rate > 70%",
                ],
                "constraints": ["GDPR compliance", "OWASP security standards", "WCAG 2.1 AA accessibility"],
            }
            result["recommendations"].append("Include security review in definition of Done")
            result["recommendations"].append("Plan for MFA in v2 of the system")

        elif "kpi" in task_lower or "metric" in task_lower:
            result["summary"] = "KPI definitions provided"
            result["recommendations"].append("Track login conversion rate (attempts to successful)")
            result["recommendations"].append("Monitor password reset completion rate")
            result["recommendations"].append("Measure session duration and return rate")

        else:
            result["summary"] = f"Product manager analyzed: {task}"
            result["recommendations"].append("Start with user stories to define scope")
            result["recommendations"].append("Use MoSCoW to prioritize: Must > Should > Could > Won't")

        logger.info(f"Product task completed: {result['summary']}")
        return result


async def main() -> None:
    """CLI entry point."""
    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        pm = ProductManager()
        result = await pm.execute(task)
        print(f"Result: {result['summary']}")
        if result.get("user_stories"):
            for us in result["user_stories"]:
                print(f"  [{us['id']}] {us['title']} ({us['priority']})")
    else:
        print("Usage: python pm_agent.py <task>")


if __name__ == "__main__":
    asyncio.run(main())