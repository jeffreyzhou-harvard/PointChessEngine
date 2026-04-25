"""Command-line entry point for the GEPA-RLM engine artifact."""

from __future__ import annotations

import sys

from .main import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
