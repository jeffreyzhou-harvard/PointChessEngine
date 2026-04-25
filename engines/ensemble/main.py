"""Entry point for PyChess.

Usage:
    python main.py            # default: UCI on stdio
    python main.py --uci      # explicit
    python main.py --ui [--port 8080] [--host 127.0.0.1]
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pychess")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--uci", action="store_true", help="Run UCI on stdio (default)")
    mode.add_argument("--ui", action="store_true", help="Run local web UI")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args(argv)

    if args.ui:
        from ui.server import main as ui_main
        ui_main(args.host, args.port)
        return 0
    # default: UCI
    from engine.uci import run_uci
    run_uci()
    return 0


if __name__ == "__main__":
    sys.exit(main())
