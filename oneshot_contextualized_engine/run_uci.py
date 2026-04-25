#!/usr/bin/env python3
"""UCI entrypoint.

Run with: `python3 run_uci.py` and feed UCI commands on stdin.

Set as a UCI engine in any compatible GUI (CuteChess, Arena, Banksia,
Lichess BotLi, etc.) by pointing it at this script with `python3` as the
interpreter.
"""

import os
import sys

# Make sibling packages importable when invoked as a script.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from uci.protocol import UCIEngine

if __name__ == "__main__":
    UCIEngine().run()
