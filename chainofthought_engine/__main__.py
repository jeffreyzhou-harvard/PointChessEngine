"""Entry point.

Usage::

    python -m chainofthought_engine            # launch the UI (default)
    python -m chainofthought_engine --uci      # speak UCI on stdin/stdout
    python -m chainofthought_engine --ui       # explicit UI launch
    python -m chainofthought_engine --port N   # UI port (default 8000)

Both adapters are still scaffolding at this stage and will raise
NotImplementedError when invoked. Wiring them here so later stages can
fill them in without changing how the user launches the program.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chainofthought_engine")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--uci", action="store_true", help="run as a UCI engine")
    mode.add_argument("--ui", action="store_true", help="run the web UI (default)")
    parser.add_argument("--port", type=int, default=8000, help="UI port")
    args = parser.parse_args(argv)

    if args.uci:
        from .uci.protocol import UCIProtocol

        UCIProtocol().run()
        return 0

    from .ui.server import serve

    serve(port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
