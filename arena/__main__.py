"""Run with: python -m arena   (default port 8765)."""
from __future__ import annotations

import argparse

from arena.server import serve


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m arena")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
