"""ce-demo-reel — scripts entry point wrapper."""
import json
import sys
from pathlib import Path

# Allow imports from parent agent directory
_agent_root = Path(__file__).parent.parent
sys.path.insert(0, str(_agent_root))

from main import run  # type: ignore[attr-defined]


def main() -> dict:
    """CLI entry point for ce-demo-reel agent."""
    input_data = sys.argv[1] if len(sys.argv) > 1 else ""
    return run(input_data)


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))


def main_wrapper():
    """main_wrapper-compatible entry point for ce-demo-reel agent."""
    return main()
