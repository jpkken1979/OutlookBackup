#!/usr/bin/env python3
"""
Game Developer Agent - Game development analysis and optimization.

Usage:
    python game_developer.py <project_path> [--engine auto|unity|godot|unreal] [--json]
"""

import argparse
import contextlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class GameIssue:
    """Game development issue."""

    id: str
    category: str  # performance, architecture, design, optimization
    severity: str
    title: str
    location: str
    description: str
    fix: str


@dataclass
class PerformanceMetrics:
    """Game performance metrics."""

    estimated_frame_budget: str
    potential_bottlenecks: list = field(default_factory=list)
    optimization_opportunities: list = field(default_factory=list)


@dataclass
class GameReport:
    """Game project analysis report."""

    project_path: str
    engine: str
    timestamp: str
    issues: list = field(default_factory=list)
    architecture: dict = field(default_factory=dict)
    performance: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class GameDeveloper:
    """Game development analysis agent."""

    UNITY_PATTERNS = {
        "find_in_update": {
            "pattern": r"void\s+Update\s*\([^)]*\)[^}]*Find\s*[<(]",
            "title": "Find() called in Update()",
            "description": "Calling Find() in Update() is expensive. Cache references in Start().",
            "severity": "high",
            "fix": "Cache the reference in Start() or Awake()",
        },
        "getcomponent_in_update": {
            "pattern": r"void\s+Update\s*\([^)]*\)[^}]*GetComponent\s*[<(]",
            "title": "GetComponent() in Update()",
            "description": "GetComponent() in Update() causes GC allocation. Cache in Start().",
            "severity": "high",
            "fix": "Cache component reference in Start() or use [SerializeField]",
        },
        "string_concatenation": {
            "pattern": r"Debug\.Log\s*\([^)]*\+[^)]*\)",
            "title": "String concatenation in Debug.Log",
            "description": "String concatenation allocates memory. Use string interpolation.",
            "severity": "low",
            "fix": 'Use $"text {variable}" or remove debug logs in production',
        },
        "instantiate_in_update": {
            "pattern": r"void\s+Update\s*\([^)]*\)[^}]*Instantiate\s*\(",
            "title": "Instantiate() in Update()",
            "description": "Frequent instantiation causes GC spikes. Use object pooling.",
            "severity": "high",
            "fix": "Implement object pooling pattern",
        },
    }

    GODOT_PATTERNS = {
        "get_node_in_process": {
            "pattern": r"func\s+_process\s*\([^)]*\)[^:]*:[^}]*get_node\s*\(",
            "title": "get_node() in _process()",
            "description": "get_node() in _process() is slow. Use @onready instead.",
            "severity": "high",
            "fix": "Use @onready var node = $NodePath",
        },
        "load_in_process": {
            "pattern": r"func\s+_process\s*\([^)]*\)[^:]*:[^}]*(load|preload)\s*\(",
            "title": "load() in _process()",
            "description": "Loading resources in _process() causes stuttering.",
            "severity": "critical",
            "fix": "Preload resources or use ResourceLoader.load_threaded()",
        },
        "missing_static_typing": {
            "pattern": r"var\s+\w+\s*=(?!\s*:)",
            "title": "Missing static typing",
            "description": "GDScript runs faster with static typing.",
            "severity": "low",
            "fix": "Add type hints: var name: Type = value",
        },
    }

    GENERAL_PATTERNS = {
        "no_object_pooling": {
            "keywords": ["Instantiate", "new ", "create", "spawn"],
            "anti_keywords": ["pool", "Pool", "reuse", "Reuse"],
            "title": "Consider object pooling",
            "description": "Frequent object creation detected without pooling.",
            "severity": "medium",
            "fix": "Implement object pooling for frequently spawned objects",
        },
    }

    def __init__(self, project_path: str, engine: str = "auto"):
        self.project_path = Path(project_path)
        self.engine = self._detect_engine() if engine == "auto" else engine
        self.issue_counter = 0

    def _detect_engine(self) -> str:
        """Detect game engine from project files."""
        # Unity
        if (self.project_path / "Assets").exists() or any(self.project_path.rglob("*.unity")):
            return "unity"
        # Godot
        if (self.project_path / "project.godot").exists() or any(self.project_path.rglob("*.gd")):
            return "godot"
        # Unreal
        if any(self.project_path.rglob("*.uproject")):
            return "unreal"
        # Phaser/Web
        if any(self.project_path.rglob("phaser*.js")):
            return "phaser"
        return "unknown"

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"GAME-{self.issue_counter:03d}"

    def analyze_unity(self) -> list[GameIssue]:
        """Analyze Unity project."""
        issues = []

        for file_path in self.project_path.rglob("*.cs"):
            if "Library" in str(file_path) or "Packages" in str(file_path):
                continue

            try:
                content = file_path.read_text()

                for _pattern_name, pattern_info in self.UNITY_PATTERNS.items():
                    if re.search(pattern_info["pattern"], content, re.MULTILINE | re.DOTALL):
                        issues.append(
                            GameIssue(
                                id=self._generate_issue_id(),
                                category="performance",
                                severity=pattern_info["severity"],
                                title=pattern_info["title"],
                                location=str(file_path.relative_to(self.project_path)),
                                description=pattern_info["description"],
                                fix=pattern_info["fix"],
                            )
                        )
            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

        return issues

    def analyze_godot(self) -> list[GameIssue]:
        """Analyze Godot project."""
        issues = []

        for file_path in self.project_path.rglob("*.gd"):
            if ".godot" in str(file_path):
                continue

            try:
                content = file_path.read_text()

                for _pattern_name, pattern_info in self.GODOT_PATTERNS.items():
                    if re.search(pattern_info["pattern"], content, re.MULTILINE | re.DOTALL):
                        issues.append(
                            GameIssue(
                                id=self._generate_issue_id(),
                                category="performance",
                                severity=pattern_info["severity"],
                                title=pattern_info["title"],
                                location=str(file_path.relative_to(self.project_path)),
                                description=pattern_info["description"],
                                fix=pattern_info["fix"],
                            )
                        )
            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

        return issues

    def analyze_architecture(self) -> dict:
        """Analyze game architecture."""
        architecture = {
            "engine": self.engine,
            "patterns_detected": [],
            "scene_count": 0,
            "script_count": 0,
            "has_state_machine": False,
            "has_event_system": False,
            "has_object_pooling": False,
        }

        # Count files
        if self.engine == "unity":
            architecture["scene_count"] = len(list(self.project_path.rglob("*.unity")))
            architecture["script_count"] = len(list(self.project_path.rglob("*.cs")))
        elif self.engine == "godot":
            architecture["scene_count"] = len(list(self.project_path.rglob("*.tscn")))
            architecture["script_count"] = len(list(self.project_path.rglob("*.gd")))

        # Detect patterns
        all_content = ""
        for ext in [".cs", ".gd", ".cpp", ".js"]:
            for file_path in self.project_path.rglob(f"*{ext}"):
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text()

        # State machine
        if re.search(r"(StateMachine|state_machine|FSM|currentState|CurrentState)", all_content):
            architecture["has_state_machine"] = True
            architecture["patterns_detected"].append("State Machine")

        # Event system
        if re.search(r"(EventManager|event_manager|Signal|UnityEvent|EventBus)", all_content):
            architecture["has_event_system"] = True
            architecture["patterns_detected"].append("Event System")

        # Object pooling
        if re.search(r"(ObjectPool|object_pool|Pool\.|pooling)", all_content, re.IGNORECASE):
            architecture["has_object_pooling"] = True
            architecture["patterns_detected"].append("Object Pooling")

        # ECS
        if re.search(r"(Entity|Component|System|ECS|DOTS)", all_content):
            architecture["patterns_detected"].append("ECS Pattern")

        return architecture

    def analyze_performance(self) -> dict:
        """Analyze performance characteristics."""
        performance = {
            "estimated_complexity": "unknown",
            "bottleneck_risks": [],
            "optimization_tips": [],
        }

        all_content = ""
        for ext in [".cs", ".gd", ".cpp"]:
            for file_path in self.project_path.rglob(f"*{ext}"):
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text()

        # Check for physics heavy
        if re.search(r"(Rigidbody|RigidBody|Physics\.|CollisionShape)", all_content):
            performance["bottleneck_risks"].append("Physics calculations")
            performance["optimization_tips"].append("Use physics layers to reduce collision checks")

        # Check for AI/Pathfinding
        if re.search(r"(NavMesh|NavigationAgent|AStar|Pathfind)", all_content):
            performance["bottleneck_risks"].append("Pathfinding")
            performance["optimization_tips"].append("Cache paths and update less frequently")

        # Check for particle systems
        if re.search(r"(ParticleSystem|GPUParticles|emit)", all_content):
            performance["bottleneck_risks"].append("Particle systems")
            performance["optimization_tips"].append("Limit particle count, use GPU particles")

        # Check for networking
        if re.search(r"(NetworkManager|MultiplayerAPI|Mirror|Photon)", all_content):
            performance["bottleneck_risks"].append("Network synchronization")
            performance["optimization_tips"].append("Use delta compression and interpolation")

        return performance

    def generate_report(self) -> GameReport:
        """Generate comprehensive game analysis report."""
        logger.info(f"Analyzing game project: {self.project_path}")
        logger.info(f"Detected engine: {self.engine}")

        issues = []

        if self.engine == "unity":
            issues.extend(self.analyze_unity())
        elif self.engine == "godot":
            issues.extend(self.analyze_godot())

        architecture = self.analyze_architecture()
        performance = self.analyze_performance()

        # Generate recommendations
        recommendations = []

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        if severity_counts["critical"] > 0:
            recommendations.append("Fix critical performance issues immediately")
        if not architecture.get("has_object_pooling") and architecture.get("script_count", 0) > 5:
            recommendations.append("Implement object pooling for frequently spawned objects")
        if not architecture.get("has_state_machine") and architecture.get("script_count", 0) > 10:
            recommendations.append("Consider state machine pattern for character/game states")

        recommendations.extend(
            [
                "Profile on target platform before optimizing",
                "Test on lowest spec target device",
                "Monitor frame time, not just FPS",
            ]
        )

        return GameReport(
            project_path=str(self.project_path),
            engine=self.engine,
            timestamp=datetime.now().isoformat(),
            issues=[asdict(i) for i in issues],
            architecture=architecture,
            performance=performance,
            recommendations=recommendations,
            summary={
                "total_issues": len(issues),
                "by_severity": severity_counts,
                "scene_count": architecture.get("scene_count", 0),
                "script_count": architecture.get("script_count", 0),
                "patterns_used": architecture.get("patterns_detected", []),
            },
        )


def format_report_markdown(report: GameReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Game Development Analysis Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Engine:** {report.engine.title()}",
        f"**Date:** {report.timestamp}",
        "",
        "## Summary",
        "",
        f"- **Scenes:** {report.summary.get('scene_count', 0)}",
        f"- **Scripts:** {report.summary.get('script_count', 0)}",
        f"- **Issues Found:** {report.summary.get('total_issues', 0)}",
        f"- **Patterns Used:** {', '.join(report.summary.get('patterns_used', [])) or 'None detected'}",
        "",
        "## Issues by Severity",
        "",
    ]

    for severity, count in report.summary.get("by_severity", {}).items():
        if count > 0:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                severity, "⚪"
            )
            lines.append(f"- {emoji} {severity.upper()}: {count}")

    lines.extend(["", "## Performance Risks", ""])
    for risk in report.performance.get("bottleneck_risks", []):
        lines.append(f"- ⚠️ {risk}")

    lines.extend(["", "## Issues", ""])

    for issue in report.issues:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            issue.get("severity", ""), "⚪"
        )
        lines.extend(
            [
                f"### {severity_emoji} {issue.get('id', '')}: {issue.get('title', '')}",
                "",
                f"**Location:** `{issue.get('location', '')}`",
                "",
                issue.get("description", ""),
                "",
                f"**Fix:** {issue.get('fix', '')}",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["", "## Recommendations", ""])
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Game Developer Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "unity", "godot", "unreal", "phaser"],
        help="Game engine",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    analyzer = GameDeveloper(args.project, args.engine)
    report = analyzer.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
