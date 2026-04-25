#!/usr/bin/env python3
"""Web UI entrypoint. Serves a click-to-move human-vs-engine page at /."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from web.server import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the chess web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    main(host=args.host, port=args.port)
