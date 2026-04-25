"""Entry point for the LLM Ensemble chess engine.

Usage:
    python -m llm_ensemble              # start web UI (default port 8001)
    python -m llm_ensemble --uci        # run as UCI engine
    python -m llm_ensemble --host 0.0.0.0 --port 9000
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Allow running as a direct script (e.g. from VS Code) in addition to
# `python -m llm_ensemble`.  When executed directly, __package__ is None
# and relative imports fail, so we fix up sys.path and use absolute imports.
if __package__ is None or __package__ == "":
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    __package__ = "llm_ensemble"  # noqa: A001


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m llm_ensemble",
        description="PointChess Ensemble — five LLMs vote on every move",
    )
    parser.add_argument(
        "--uci",
        action="store_true",
        help="Run as a UCI engine (stdin/stdout)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the web UI server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for the web UI server (default: 8001)",
    )
    parser.add_argument(
        "--elo",
        type=int,
        default=1500,
        help="Initial ELO strength (400-2400, default: 1500)",
    )
    parser.add_argument(
        "--method",
        default="plurality",
        choices=["plurality", "score_weighted", "consensus"],
        help="Voting aggregation method (default: plurality)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.uci:
        _run_uci(args)
    else:
        _run_web(args)


def _run_uci(args: argparse.Namespace) -> None:
    """Start the UCI protocol loop on stdin/stdout."""
    from .uci.protocol import UCIProtocol
    from .ensemble.engine import EnsembleEngine

    engine = EnsembleEngine(elo=args.elo, voting_method=args.method)
    proto = UCIProtocol(engine=engine)
    proto.run_loop()


def _run_web(args: argparse.Namespace) -> None:
    """Start the web UI server."""
    from .ui.server import run_server
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
