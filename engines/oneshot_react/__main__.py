"""Entry point: ``python -m engines.oneshot_react`` launches the web UI by default;
``--uci`` flips into UCI mode so it can be loaded into a chess GUI.
"""

from __future__ import annotations

import argparse
import sys

from .ui.server import create_server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="engines.oneshot_react")
    parser.add_argument(
        "--uci",
        action="store_true",
        help="run in UCI mode (read commands from stdin)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="host for the web UI server (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="port for the web UI server (default: 8000)"
    )
    args = parser.parse_args(argv)

    if args.uci:
        # Defer import so UCI mode doesn't pay the cost of starting an HTTP server.
        from .uci.protocol import run_uci

        run_uci()
        return 0

    server = create_server(host=args.host, port=args.port)
    print(f"PointChess ReAct UI listening on http://{args.host}:{args.port}", flush=True)
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
