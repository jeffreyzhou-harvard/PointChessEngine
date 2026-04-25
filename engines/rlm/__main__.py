"""Command-line entry point for the RLM-inspired engine."""

from __future__ import annotations

import argparse
import sys

from .uci import run_uci


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pointchess-rlm")
    parser.add_argument("--uci", action="store_true", help="Run the engine in UCI mode")
    parser.parse_args(argv)
    run_uci()
    return 0


if __name__ == "__main__":
    sys.exit(main())
