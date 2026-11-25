"""Entry point: python3 team.py <command>  (Windows: python team.py <command>)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
