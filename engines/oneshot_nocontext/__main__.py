"""Entry point for the PointChess engine.

Usage:
    python -m engine              # Start web UI (default)
    python -m engine --uci        # Start in UCI mode
    python -m engine --port 8080  # Web UI on custom port
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description='PointChess Engine')
    parser.add_argument('--uci', action='store_true', help='Run in UCI protocol mode')
    parser.add_argument('--port', type=int, default=8000, help='Web server port (default: 8000)')
    args = parser.parse_args()

    if args.uci:
        from engines.oneshot_nocontext.uci.protocol import UCIProtocol
        protocol = UCIProtocol()
        protocol.run()
    else:
        from engines.oneshot_nocontext.ui.server import start_server
        start_server(port=args.port)


if __name__ == '__main__':
    main()
