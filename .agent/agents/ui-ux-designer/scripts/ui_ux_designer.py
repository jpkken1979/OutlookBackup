"""Backward-compatibility shim — delega a main.py (plugin architecture)."""
import asyncio
from main import DesignReport, UIUXDesigner  # noqa: F401 — re-exportados

__all__ = ["UIUXDesigner", "DesignReport"]

async def main() -> "DesignReport":
    """CLI entry point for ui-ux-designer agent."""
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    designer = UIUXDesigner()
    return await designer.analyze_project(project)


if __name__ == "__main__":
    report = asyncio.run(main())
    print(f"Score: {report.score_global}/10 | Aprobado: {report.approved}")
    print(f"Tokens extraídos: {len(report.tokens)}")
    print(f"Violaciones a11y: {len(report.a11y_violations)}")
    if report.nielsen_report:
        print(f"Nielsen global: {report.nielsen_report.global_score}/10")


def main_wrapper():
    """main_wrapper-compatible entry point for ui-ux-designer agent."""
    return asyncio.run(main())
