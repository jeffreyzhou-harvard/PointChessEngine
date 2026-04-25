#!/usr/bin/env python3
"""Champion tournament gate placeholder for FastChess/Stockfish runs."""

from __future__ import annotations

import argparse
import json
import shutil
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="")
    parser.add_argument("--require-fastchess", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    fastchess = shutil.which("fastchess")
    stockfish = shutil.which("stockfish")
    skipped = fastchess is None
    result = {
        "tier": "tournament",
        "engine": args.engine,
        "fastchess": fastchess,
        "stockfish": stockfish,
        "skipped": skipped,
        "passed": not args.require_fastchess or fastchess is not None,
        "duration_seconds": round(time.monotonic() - started, 3),
        "note": "Manual/scheduled gate. Install FastChess to run real round robin and calibration.",
    }
    print(json.dumps(result, sort_keys=True))
    return 1 if args.require_fastchess and fastchess is None else 0


if __name__ == "__main__":
    raise SystemExit(main())
