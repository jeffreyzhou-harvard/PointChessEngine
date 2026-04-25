#!/usr/bin/env python3
"""Run the current perft gate used by Champion mode."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERFT_TARGET = "tests/classical/test_c2_legal_move_generation.py::TestC2_7PerftHooks"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="", help="Engine id being gated; current perft gate is canonical-classical")
    args = parser.parse_args()

    started = time.monotonic()
    command = [sys.executable, "-m", "pytest", "-q", PERFT_TARGET]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    print(
        json.dumps(
            {
                "tier": "perft",
                "engine": args.engine,
                "perft_target": PERFT_TARGET,
                "passed": completed.returncode == 0,
                "duration_seconds": round(time.monotonic() - started, 3),
                "note": "Current perft gate uses canonical classical tests; per-engine UCI perft needs a debug/perft command.",
            },
            sort_keys=True,
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
