"""Run the ttcap CLI from a source tree on PYTHONPATH (no install on the Pi)."""

import sys

from ttcap.cli import main

if __name__ == "__main__":
    sys.exit(main())
