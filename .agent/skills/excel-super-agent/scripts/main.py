#!/usr/bin/env python3
"""Skill: excel-super-agent"""
import argparse
import json
import logging
import sys

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill: excel-super-agent")
    parser.add_argument(
        "--path",
        required=True,
        help="Absolute path to the .xlsx/.xlsm/.xls file to process",
    )
    parser.add_argument(
        "--hints",
        default="{}",
        help="JSON string with optional hints for the parser (default: {})",
    )
    args = parser.parse_args()

    logger.info("Skill %s invoked with path=%s", "excel-super-agent", args.path)

    # Validate path exists
    import os
    if not os.path.exists(args.path):
        print(json.dumps({"error": f"file not found: {args.path}"}))
        return 1

    # Parse hints (currently not forwarded to orchestrator — YAGNI)
    try:
        hints = json.loads(args.hints)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid --hints JSON: {e}"}))
        return 1

    # Delegate to orchestrator
    from orchestrator import process_excel
    result = process_excel(args.path, hints=hints)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
