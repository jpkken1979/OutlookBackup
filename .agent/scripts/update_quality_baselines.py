#!/usr/bin/env python3
"""
Update quality baselines after successful CI runs.

This script is intended to run AFTER a merge to main, updating baselines
with current metrics if there's a significant improvement.

Usage:
    python .agent/scripts/update_quality_baselines.py [--force]

Options:
    --force    Update baselines without confirmation (CI only)
    --help     Show this help
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def load_coverage_metrics() -> dict | None:
    """Load coverage metrics from coverage.json."""
    try:
        with open("coverage.json") as f:
            data = json.load(f)
            return {
                "percent_covered": data.get("totals", {}).get("percent_covered", 0),
                "covered_lines": data.get("totals", {}).get("covered_lines", 0),
                "missing_lines": data.get("totals", {}).get("missing_lines", 0),
                "num_statements": data.get("totals", {}).get("num_statements", 0),
            }
    except Exception as e:
        print(f"❌ Could not load coverage.json: {e}")
        return None


def load_mutation_metrics() -> dict | None:
    """Load mutation metrics from baseline or HTML report."""
    try:
        if Path(".mutmut-baseline.json").exists():
            with open(".mutmut-baseline.json") as f:
                data = json.load(f)
                return {
                    "total_mutation_points": data.get("summary", {}).get(
                        "total_mutation_points", 0
                    ),
                    "estimated_total_mutants": data.get("summary", {}).get(
                        "estimated_total_mutants", ""
                    ),
                    "timestamp": data.get("analysis_timestamp", ""),
                }
    except Exception as e:
        print(f"⚠️ Could not load mutation baseline: {e}")
        return None
    return None


def load_previous_baseline() -> dict:
    """Load previous baseline from governance/quality-baseline.json."""
    baseline_path = Path("governance/quality-baseline.json")
    if baseline_path.exists():
        try:
            with open(baseline_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "coverage_percent": 0,
        "covered_lines": 0,
        "mutation_points": 0,
        "timestamp": None,
    }


def compute_improvement(prev: dict, current: dict) -> dict:
    """Compute improvement metrics."""
    improvement = {}

    # Coverage improvement
    if current.get("coverage_percent"):
        improvement["coverage_delta"] = current["coverage_percent"] - prev.get(
            "coverage_percent", 0
        )
        improvement["coverage_improvement"] = improvement["coverage_delta"] > 0

    # Line coverage improvement
    if current.get("covered_lines"):
        improvement["lines_delta"] = current["covered_lines"] - prev.get("covered_lines", 0)

    return improvement


def update_baseline(force: bool = False) -> int:
    """Update baselines if improvements detected."""
    print("\n📊 Checking quality metrics...\n")

    # Load current metrics
    coverage = load_coverage_metrics()
    mutation = load_mutation_metrics()

    if not coverage:
        print(
            "❌ No coverage metrics found. Run: pytest --cov=.agent/core --cov-report=json:coverage.json"
        )
        return 1

    # Load previous baseline
    prev_baseline = load_previous_baseline()

    # Compute improvements
    improvement = compute_improvement(prev_baseline, coverage or {})

    # Display summary
    print("Current metrics:")
    if coverage:
        print(f"  Coverage: {coverage['percent_covered']:.1f}% ({coverage['covered_lines']} lines)")
    if mutation:
        print(f"  Mutation points: {mutation['total_mutation_points']}")

    print("\nPrevious baseline:")
    print(f"  Coverage: {prev_baseline.get('coverage_percent', 0):.1f}%")
    print(f"  Covered lines: {prev_baseline.get('covered_lines', 0)}")

    if improvement:
        print("\nImprovement detected:")
        if improvement.get("coverage_improvement"):
            delta = improvement["coverage_delta"]
            print(f"  Coverage: +{delta:.2f}% 📈")
        if improvement.get("lines_delta", 0) > 0:
            print(f"  Lines: +{improvement['lines_delta']} 📈")

    # Decide whether to update
    should_update = (
        improvement.get("coverage_improvement", False)
        and improvement.get("coverage_delta", 0) >= 0.5  # At least 0.5% improvement
    )

    if not should_update and not force:
        print("\n⏭️ No significant improvement detected. Baseline unchanged.")
        return 0

    if not force:
        response = input("\n🤔 Update baseline? (y/n): ").strip().lower()
        if response != "y":
            print("Cancelled.")
            return 0

    # Update baseline
    new_baseline = {
        "coverage_percent": coverage["percent_covered"],
        "covered_lines": coverage["covered_lines"],
        "missing_lines": coverage["missing_lines"],
        "num_statements": coverage["num_statements"],
        "mutation_points": mutation.get("total_mutation_points", 0) if mutation else 0,
        "timestamp": datetime.now().isoformat(),
        "note": "Updated by update_quality_baselines.py after successful CI run",
    }

    # Create governance directory if needed
    gov_dir = Path("governance")
    gov_dir.mkdir(exist_ok=True)

    # Write updated baseline
    baseline_path = gov_dir / "quality-baseline.json"
    with open(baseline_path, "w") as f:
        json.dump(new_baseline, f, indent=2)

    print(f"\n✅ Baseline updated: {baseline_path}")
    print(json.dumps(new_baseline, indent=2))

    return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Update quality baselines after successful CI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--force", action="store_true", help="Update without confirmation (for CI)")

    args = parser.parse_args()

    return update_baseline(force=args.force)


if __name__ == "__main__":
    sys.exit(main())
