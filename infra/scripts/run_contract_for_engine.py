#!/usr/bin/env python3
"""Run the shared UCI contract suite for one registered engine."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, help="arena.engines registry id")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    env = os.environ.copy()
    env["POINTCHESS_ENGINE_FILTER"] = args.engine
    command = [sys.executable, "-m", "pytest", "-q", "tests/contract"]
    completed = subprocess.run(command, text=True, capture_output=True, env=env)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    result = {
        "tier": "contract",
        "engine": args.engine,
        "command": " ".join(command),
        "passed": completed.returncode == 0,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    print(json.dumps(result, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
