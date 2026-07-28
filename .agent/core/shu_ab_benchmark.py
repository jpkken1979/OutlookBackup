import csv
import json
import logging
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path

import numpy as np
from pydantic import BaseModel, field_validator
from scipy import stats

logger = logging.getLogger(__name__)


class ExecutionType(IntEnum):
    """Enum for A/B test execution types."""

    STRUCTURED_SHU = 1
    MANUAL_UNSTRUCTURED = 2


class BenchmarkData(BaseModel):
    """Data model for individual benchmark record.

    Attributes:
        type: Execution type (SHU or manual).
        goal: Goal description being executed.
        time_ms: Execution time in milliseconds.
        success: Whether execution succeeded.
        errors: Count of errors during execution.
        quality: Quality score (1-10 scale).
        timestamp: When benchmark was recorded.
    """

    type: ExecutionType
    goal: str
    time_ms: int
    success: bool
    errors: int
    quality: int
    timestamp: datetime

    @field_validator("time_ms")
    @classmethod
    def validate_time(cls, v: int) -> int:
        """Validate time_ms > 0."""
        if v <= 0:
            raise ValueError("time_ms must be > 0")
        return v

    @field_validator("errors")
    @classmethod
    def validate_errors(cls, v: int) -> int:
        """Validate errors >= 0."""
        if v < 0:
            raise ValueError("errors must be >= 0")
        return v

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: int) -> int:
        """Validate quality in [1, 10]."""
        if not (1 <= v <= 10):
            raise ValueError("quality must be in [1, 10]")
        return v

    def model_dump_json(self, **kwargs) -> str:
        """Override to ensure ISO format for timestamp."""
        d = self.model_dump(**kwargs)
        d["timestamp"] = self.timestamp.isoformat()
        return json.dumps(d)


class ShuABBenchmark:
    """A/B benchmark collector and analyzer for /shu vs manual queries.

    Manages recording benchmarks, statistical analysis, and CSV export.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize benchmark manager.

        Args:
            data_dir: Directory for storing benchmarks. Defaults to
                ~/.antigravity/shu/.
        """
        if data_dir is None:
            data_dir = Path.home() / ".antigravity" / "shu"
        self.data_dir = data_dir
        self.benchmarks_file = self.data_dir / "benchmarks.jsonl"

    def record_benchmark(
        self,
        execution_type: ExecutionType,
        goal: str,
        time_ms: int,
        success: bool,
        errors_count: int,
        quality_score: int,
    ) -> None:
        """Record a single benchmark execution.

        Args:
            execution_type: STRUCTURED_SHU or MANUAL_UNSTRUCTURED.
            goal: Goal description.
            time_ms: Execution time in milliseconds.
            success: Whether execution succeeded.
            errors_count: Number of errors encountered.
            quality_score: Quality score (1-10).

        Raises:
            ValueError: If validation fails.
        """
        data = BenchmarkData(
            type=execution_type,
            goal=goal,
            time_ms=time_ms,
            success=success,
            errors=errors_count,
            quality=quality_score,
            timestamp=datetime.utcnow(),
        )

        self.data_dir.mkdir(parents=True, exist_ok=True)

        with open(self.benchmarks_file, "a", encoding="utf-8") as f:
            f.write(data.model_dump_json() + "\n")

        logger.info(f"Benchmark recorded: {execution_type.name} {goal[:20]}... {time_ms}ms")

    def _load_benchmarks(self, days: int = 7) -> list[BenchmarkData]:
        """Load benchmarks from last N days.

        Args:
            days: Number of days to load.

        Returns:
            List of BenchmarkData objects.
        """
        if not self.benchmarks_file.exists():
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)
        benchmarks = []

        try:
            with open(self.benchmarks_file, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data_dict = json.loads(line)
                        data_dict["timestamp"] = datetime.fromisoformat(data_dict["timestamp"])
                        data = BenchmarkData(**data_dict)
                        if data.timestamp >= cutoff:
                            benchmarks.append(data)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Skipping malformed benchmark line: {e}")
                        continue
        except FileNotFoundError:
            return []

        return benchmarks

    def compare_metrics(self, days: int = 7) -> dict:
        """Compare metrics between SHU and manual execution.

        Args:
            days: Number of days to analyze.

        Returns:
            Dict with keys: shu_avg_time_ms, manual_avg_time_ms,
            shu_success_rate_pct, manual_success_rate_pct, shu_avg_quality,
            manual_avg_quality, shu_count, manual_count.
        """
        benchmarks = self._load_benchmarks(days)

        shu_data = [b for b in benchmarks if b.type == ExecutionType.STRUCTURED_SHU]
        manual_data = [b for b in benchmarks if b.type == ExecutionType.MANUAL_UNSTRUCTURED]

        result = {
            "shu_avg_time_ms": 0.0,
            "manual_avg_time_ms": 0.0,
            "shu_success_rate_pct": 0.0,
            "manual_success_rate_pct": 0.0,
            "shu_avg_quality": 0.0,
            "manual_avg_quality": 0.0,
            "shu_count": len(shu_data),
            "manual_count": len(manual_data),
        }

        if shu_data:
            result["shu_avg_time_ms"] = float(np.mean([b.time_ms for b in shu_data]))
            result["shu_success_rate_pct"] = float(np.mean([b.success for b in shu_data]) * 100)
            result["shu_avg_quality"] = float(np.mean([b.quality for b in shu_data]))

        if manual_data:
            result["manual_avg_time_ms"] = float(np.mean([b.time_ms for b in manual_data]))
            result["manual_success_rate_pct"] = float(
                np.mean([b.success for b in manual_data]) * 100
            )
            result["manual_avg_quality"] = float(np.mean([b.quality for b in manual_data]))

        return result

    def is_difference_significant(self, days: int = 7) -> bool:
        """Check if difference between SHU and manual is statistically significant.

        Uses independent two-sample T-test on execution times.

        Args:
            days: Number of days to analyze.

        Returns:
            True if p-value < 0.05, False otherwise.
        """
        benchmarks = self._load_benchmarks(days)

        shu_times = [b.time_ms for b in benchmarks if b.type == ExecutionType.STRUCTURED_SHU]
        manual_times = [
            b.time_ms for b in benchmarks if b.type == ExecutionType.MANUAL_UNSTRUCTURED
        ]

        if len(shu_times) < 2 or len(manual_times) < 2:
            return False

        t_stat, p_value = stats.ttest_ind(shu_times, manual_times)
        return bool(p_value < 0.05)

    def export_csv(self, output_path: Path) -> None:
        """Export all benchmarks to CSV.

        Args:
            output_path: Path to write CSV file.
        """
        benchmarks = self._load_benchmarks(days=999)  # All available

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "type", "goal", "time_ms", "success", "errors", "quality"],
            )
            writer.writeheader()
            for b in benchmarks:
                writer.writerow(
                    {
                        "timestamp": b.timestamp.isoformat(),
                        "type": b.type.name,
                        "goal": b.goal,
                        "time_ms": b.time_ms,
                        "success": b.success,
                        "errors": b.errors,
                        "quality": b.quality,
                    }
                )

        logger.info(f"Exported {len(benchmarks)} benchmarks to {output_path}")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="SHU A/B Benchmark CLI tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    summary_parser = subparsers.add_parser("summary", help="Export benchmark summary as JSON")
    summary_parser.add_argument(
        "--days", type=int, default=7, help="Number of days to analyze (default: 7)"
    )

    csv_parser = subparsers.add_parser("export-csv", help="Export benchmarks as CSV")
    csv_parser.add_argument("--output", type=str, required=True, help="Output CSV file path")

    args = parser.parse_args()

    if args.command == "summary":
        benchmark = ShuABBenchmark()
        metrics = benchmark.compare_metrics(days=args.days)
        is_sig = benchmark.is_difference_significant(days=args.days)

        # Calculate improvement percentage
        if metrics["manual_avg_time_ms"] > 0:
            improvement_pct = (
                (metrics["manual_avg_time_ms"] - metrics["shu_avg_time_ms"])
                / metrics["manual_avg_time_ms"]
                * 100
            )
        else:
            improvement_pct = 0.0

        output = {
            **metrics,
            "is_significant": is_sig,
            "shu_improvement_pct": improvement_pct,
        }
        print(json.dumps(output, indent=2))

    elif args.command == "export-csv":
        benchmark = ShuABBenchmark()
        benchmark.export_csv(Path(args.output))
        print(f"Exported to {args.output}")

    else:
        parser.print_help()
        sys.exit(1)
