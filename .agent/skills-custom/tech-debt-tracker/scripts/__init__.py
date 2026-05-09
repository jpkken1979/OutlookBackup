"""Tech Debt Tracker — skill package."""

import sys
from pathlib import Path

# Resolve skill root for absolute imports
_SKILL_ROOT = Path(__file__).parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from scripts.detectors import (
    ComplexityDetector,
    DuplicateDetector,
    NamingDetector,
    PythonTypeDetector,
    TodoDetector,
    UnusedDetector,
)
from scripts.main import DebtIssue, TechDebtReport, run_scan

__all__ = [
    "DebtIssue",
    "TechDebtReport",
    "run_scan",
    "PythonTypeDetector",
    "TodoDetector",
    "ComplexityDetector",
    "NamingDetector",
    "DuplicateDetector",
    "UnusedDetector",
]
