"""
Log Analyzer skill for Antigravity ecosystem.
Detects error patterns in log files and generates actionable reports.

Usage as module:
    from agent.skills_custom.log_analyzer.scripts.analyzer import run_analysis
    from agent.skills_custom.log_analyzer.scripts.patterns import PATTERNS
"""

from .analyzer import AnalysisResult, run_analysis
from .patterns import PATTERNS

__all__ = ["AnalysisResult", "run_analysis", "PATTERNS"]
