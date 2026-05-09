"""Entry point para plugin-eval-skill."""

import sys
from pathlib import Path

# Add agent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugin_eval.cli import app as cli_app

if __name__ == "__main__":
    cli_app()
