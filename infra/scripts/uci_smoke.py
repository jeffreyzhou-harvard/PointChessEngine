#!/usr/bin/env python3
"""Run a small UCI smoke check for one registered engine."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chess

from arena.engines import REGISTRY, UCIClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=sorted(REGISTRY))
    parser.add_argument("--movetime-ms", type=int, default=75)
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    args = parser.parse_args()

    started = time.monotonic()
    client = UCIClient(REGISTRY[args.engine], startup_timeout=args.startup_timeout)
    try:
        bestmove, infos = client.go([], args.movetime_ms)
    finally:
        client.close()

    board = chess.Board()
    try:
        move = chess.Move.from_uci(bestmove)
    except ValueError:
        move = None

    legal = move in board.legal_moves if move is not None else False
    result = {
        "engine": args.engine,
        "bestmove": bestmove,
        "legal_from_startpos": legal,
        "info_count": len(infos),
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    print(json.dumps(result, sort_keys=True))
    if not legal:
        print(f"Illegal or malformed bestmove from start position: {bestmove}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
