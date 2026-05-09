#!/usr/bin/env python3
"""
ML Engineer Agent - Machine Learning pipeline analysis and optimization.

Usage:
    python ml_engineer.py <project_path> [--json]
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
class MLIssue:
    """ML engineering issue."""

    id: str
    category: str  # reproducibility, performance, quality, deployment
    severity: str
    title: str
    location: str
    description: str
    fix: str


@dataclass
class MLReport:
    """ML project analysis report."""

    project_path: str
    timestamp: str
    framework: str
    issues: list = field(default_factory=list)
    pipeline_stages: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


class MLEngineer:
    """ML engineering analysis agent."""

    ML_ANTI_PATTERNS = {
        "no_random_seed": {
            "pattern": r"(train_test_split|RandomForest|shuffle=True)",
            "anti_pattern": r"random_state\s*=",
            "title": "Missing random seed",
            "description": "Random operations without seed harm reproducibility.",
            "severity": "high",
            "fix": "Add random_state parameter to all random operations",
        },
        "hardcoded_hyperparameters": {
            "pattern": r"(learning_rate|lr)\s*=\s*\d+\.\d+",
            "anti_pattern": r"(config|params|hparams)\[",
            "title": "Hardcoded hyperparameters",
            "description": "Hyperparameters should be in config files, not code.",
            "severity": "medium",
            "fix": "Move hyperparameters to config file or use hydra/omegaconf",
        },
        "no_experiment_logging": {
            "keywords": ["fit(", "train(", "model.train"],
            "anti_keywords": ["mlflow", "wandb", "neptune", "tensorboard"],
            "title": "No experiment tracking",
            "description": "Training without logging makes experiments hard to reproduce.",
            "severity": "high",
            "fix": "Add MLflow, Weights & Biases, or similar experiment tracking",
        },
        "data_leakage": {
            "pattern": r"(fit_transform|fit)\([^)]*X[^)]*\)[^#]*train_test_split",
            "title": "Potential data leakage",
            "description": "Fitting on full data before split causes data leakage.",
            "severity": "critical",
            "fix": "Split data first, then fit only on training data",
        },
        "notebook_in_prod": {
            "pattern": r"\.ipynb$",
            "title": "Notebook in production code",
            "description": "Jupyter notebooks shouldn't be used for production ML.",
            "severity": "medium",
            "fix": "Convert notebooks to Python modules with proper structure",
        },
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issue_counter = 0

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"ML-{self.issue_counter:03d}"

    def _detect_framework(self) -> str:
        """Detect ML framework from imports."""
        frameworks = {
            "tensorflow": ["tensorflow", "keras", "tf."],
            "pytorch": ["torch", "pytorch"],
            "sklearn": ["sklearn", "scikit-learn"],
            "xgboost": ["xgboost"],
            "lightgbm": ["lightgbm"],
            "huggingface": ["transformers", "huggingface"],
        }

        all_content = ""
        for file_path in self.project_path.rglob("*.py"):
            with contextlib.suppress(Exception):
                all_content += file_path.read_text()

        detected = []
        for name, keywords in frameworks.items():
            if any(kw in all_content for kw in keywords):
                detected.append(name)

        return ", ".join(detected) if detected else "unknown"

    def _detect_pipeline_stages(self) -> list[str]:
        """Detect ML pipeline stages present in the project."""
        stages = []

        stage_patterns = {
            "data_loading": ["pd.read", "load_data", "DataLoader", "Dataset"],
            "preprocessing": ["preprocess", "transform", "normalize", "StandardScaler"],
            "feature_engineering": ["feature", "FeatureExtractor", "get_features"],
            "model_training": ["fit(", "train(", "model.train"],
            "evaluation": ["evaluate", "score", "metrics", "accuracy"],
            "prediction": ["predict", "inference"],
            "model_saving": ["save_model", "torch.save", "joblib.dump"],
        }

        all_content = ""
        for file_path in self.project_path.rglob("*.py"):
            with contextlib.suppress(Exception):
                all_content += file_path.read_text()

        for stage, patterns in stage_patterns.items():
            if any(p in all_content for p in patterns):
                stages.append(stage)

        return stages

    def analyze_code(self) -> list[MLIssue]:
        """Analyze code for ML anti-patterns."""
        issues = []

        all_files_content = {}
        for file_path in self.project_path.rglob("*.py"):
            if any(
                skip in str(file_path) for skip in ["venv", ".git", "__pycache__", "site-packages"]
            ):
                continue
            with contextlib.suppress(Exception):
                all_files_content[str(file_path)] = file_path.read_text()

        # Check for notebooks in production
        notebook_count = len(list(self.project_path.rglob("*.ipynb")))
        if notebook_count > 0:
            issues.append(
                MLIssue(
                    id=self._generate_issue_id(),
                    category="deployment",
                    severity="medium",
                    title=f"{notebook_count} Jupyter notebooks found",
                    location=str(self.project_path),
                    description="Notebooks found that may need conversion for production.",
                    fix="Convert notebooks to Python modules using nbconvert or manual refactoring",
                )
            )

        # Analyze Python files
        for file_path, content in all_files_content.items():
            # Check for missing random seeds
            if re.search(r"train_test_split|RandomForest|shuffle=True", content):
                if not re.search(r"random_state\s*=", content):
                    issues.append(
                        MLIssue(
                            id=self._generate_issue_id(),
                            category="reproducibility",
                            severity="high",
                            title="Missing random seed",
                            location=file_path,
                            description="Random operations without seed harm reproducibility.",
                            fix="Add random_state parameter to all random operations",
                        )
                    )

            # Check for experiment tracking
            has_training = any(kw in content for kw in ["fit(", ".train(", "trainer.train"])
            has_logging = any(
                kw in content for kw in ["mlflow", "wandb", "neptune", "tensorboard", "logging"]
            )

            if has_training and not has_logging:
                issues.append(
                    MLIssue(
                        id=self._generate_issue_id(),
                        category="reproducibility",
                        severity="high",
                        title="No experiment tracking",
                        location=file_path,
                        description="Training code without experiment logging.",
                        fix="Add MLflow or Weights & Biases for experiment tracking",
                    )
                )

            # Check for hardcoded paths
            if re.search(r'["\'][/\\][^"\']*\.(csv|pkl|pt|h5|json)["\']', content):
                issues.append(
                    MLIssue(
                        id=self._generate_issue_id(),
                        category="reproducibility",
                        severity="low",
                        title="Hardcoded file paths",
                        location=file_path,
                        description="Hardcoded paths reduce portability.",
                        fix="Use Path objects and config files for paths",
                    )
                )

            # Check for model saving
            if re.search(r"model\.(fit|train)", content):
                if not re.search(r"(save|dump|torch\.save|pickle)", content):
                    issues.append(
                        MLIssue(
                            id=self._generate_issue_id(),
                            category="deployment",
                            severity="medium",
                            title="Model not saved after training",
                            location=file_path,
                            description="Trained model may not be persisted.",
                            fix="Add model saving after training (joblib, torch.save, etc.)",
                        )
                    )

        return issues

    def check_mlops_practices(self) -> dict:
        """Check for MLOps best practices."""
        practices = {
            "experiment_tracking": False,
            "model_versioning": False,
            "data_versioning": False,
            "ci_cd": False,
            "monitoring": False,
            "config_management": False,
        }

        # Check for config files
        config_files = list(self.project_path.rglob("config*.yaml")) + list(
            self.project_path.rglob("*.yml")
        )
        practices["config_management"] = len(config_files) > 0

        # Check for MLflow/W&B
        requirements = list(self.project_path.rglob("requirements*.txt"))
        for req in requirements:
            try:
                content = req.read_text().lower()
                if any(t in content for t in ["mlflow", "wandb", "neptune"]):
                    practices["experiment_tracking"] = True
                if "dvc" in content:
                    practices["data_versioning"] = True
            except Exception:
                pass

        # Check for DVC
        if (self.project_path / ".dvc").exists() or list(self.project_path.rglob("*.dvc")):
            practices["data_versioning"] = True

        # Check for CI/CD
        if any(
            [
                (self.project_path / ".github" / "workflows").exists(),
                (self.project_path / ".gitlab-ci.yml").exists(),
                (self.project_path / "Jenkinsfile").exists(),
            ]
        ):
            practices["ci_cd"] = True

        return practices

    def generate_report(self) -> MLReport:
        """Generate comprehensive ML analysis report."""
        logger.info(f"Analyzing ML project: {self.project_path}")

        framework = self._detect_framework()
        stages = self._detect_pipeline_stages()
        issues = self.analyze_code()
        practices = self.check_mlops_practices()

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        # Generate recommendations
        recommendations = []

        if severity_counts["critical"] > 0:
            recommendations.append("Fix critical issues (data leakage) immediately")

        if not practices["experiment_tracking"]:
            recommendations.append("Add experiment tracking with MLflow or Weights & Biases")

        if not practices["data_versioning"]:
            recommendations.append("Implement data versioning with DVC")

        if not practices["config_management"]:
            recommendations.append("Use Hydra or OmegaConf for configuration management")

        if "model_saving" not in stages and "model_training" in stages:
            recommendations.append("Add model serialization after training")

        recommendations.extend(
            [
                "Add model validation tests",
                "Implement data validation with Great Expectations",
                "Set up model monitoring for production",
            ]
        )

        return MLReport(
            project_path=str(self.project_path),
            timestamp=datetime.now().isoformat(),
            framework=framework,
            issues=[asdict(i) for i in issues],
            pipeline_stages=stages,
            recommendations=recommendations,
            metrics={
                "python_files": len(list(self.project_path.rglob("*.py"))),
                "notebook_files": len(list(self.project_path.rglob("*.ipynb"))),
                "mlops_practices": practices,
            },
            summary={
                "total_issues": len(issues),
                "by_severity": severity_counts,
                "pipeline_stages": len(stages),
                "framework": framework,
            },
        )


def format_report_markdown(report: MLReport) -> str:
    """Format report as markdown."""
    lines = [
        "# ML Engineering Analysis Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Framework:** {report.framework}",
        f"**Date:** {report.timestamp}",
        "",
        "## Pipeline Stages Detected",
        "",
    ]

    for stage in report.pipeline_stages:
        lines.append(f"- ✅ {stage.replace('_', ' ').title()}")

    lines.extend(["", "## Issues by Severity", ""])

    for severity, count in report.summary.get("by_severity", {}).items():
        if count > 0:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                severity, "⚪"
            )
            lines.append(f"- {emoji} {severity.upper()}: {count}")

    lines.extend(["", "## MLOps Practices", ""])
    practices = report.metrics.get("mlops_practices", {})
    for practice, status in practices.items():
        emoji = "✅" if status else "❌"
        lines.append(f"- {emoji} {practice.replace('_', ' ').title()}")

    lines.extend(["", "## Issues", ""])

    for issue in report.issues:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            issue.get("severity", ""), "⚪"
        )
        lines.extend(
            [
                f"### {severity_emoji} {issue.get('id', '')}: {issue.get('title', '')}",
                "",
                f"**Category:** {issue.get('category', '')}",
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
    parser = argparse.ArgumentParser(description="ML Engineer Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    engineer = MLEngineer(args.project)
    report = engineer.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
