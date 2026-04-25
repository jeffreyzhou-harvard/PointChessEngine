"""Scripted UCI engine used by arena tests.

Plays moves from the ``--moves`` CLI flag in order, one per ``go``.
Use a separate spec per side so each engine has its own script (env
vars are inherited by all child processes, which would make both
sides play the same line).

CLI:
  --moves a,b,c   comma-separated UCI moves (default: white opening line)
  --delay 0.5     seconds to sleep before each bestmove (default 0)
  --name NAME     `id name` string (default "FakeUCI")
"""
from __future__ import annotations

import argparse
import sys
import time


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--moves", default="e2e4,d2d4,g1f3,b1c3,f1e2,e1g1")
    p.add_argument("--delay", type=float, default=0.0)
    p.add_argument("--name", default="FakeUCI")
    args = p.parse_args(argv)
    moves = [m for m in args.moves.split(",") if m]
    delay = args.delay
    name = args.name
    move_idx = 0
    while True:
        line = sys.stdin.readline()
        if not line:
            return 0
        parts = line.strip().split()
        if not parts:
            continue
        cmd = parts[0]
        if cmd == "uci":
            print(f"id name {name}")
            print("id author arena-tests")
            print("option name UCI_Elo type spin default 1500 min 400 max 2400")
            print("uciok")
        elif cmd == "isready":
            print("readyok")
        elif cmd == "ucinewgame":
            move_idx = 0
        elif cmd == "go":
            if delay:
                time.sleep(delay)
            mv = moves[move_idx] if move_idx < len(moves) else "0000"
            move_idx += 1
            print(f"info depth 4 nodes 1234 time 50 nps 24680 score cp 25 pv {mv}")
            print(f"bestmove {mv}")
        elif cmd == "quit":
            return 0
        sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
