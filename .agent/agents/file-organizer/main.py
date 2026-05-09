"""Wrapper para ejecución desde gateway (busca main.py en raíz del agente)."""

import subprocess
import sys
from pathlib import Path

script = Path(__file__).parent / "scripts" / "main.py"
sys.exit(subprocess.call([sys.executable, str(script)] + sys.argv[1:]))
