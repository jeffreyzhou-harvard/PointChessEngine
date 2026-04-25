"""Entry point: --uci (default), --ui [--port N], or --both."""

from __future__ import annotations

import argparse
import sys
import threading
import time

from engine.core import EngineCore
from engine.uci import uci_loop


def run_uci(core: EngineCore) -> None:
    uci_loop(core)


def run_ui(core: EngineCore, host: str, port: int, foreground: bool = True) -> None:
    from ui.server import UIServer
    server = UIServer(core, host=host, port=port)
    server.start()
    print(f"UI server: {server.url}", file=sys.stderr)
    if foreground:
        try:
            # The core needs to keep draining commands; run it on this thread.
            core.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
            core.shutdown()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="councilengine")
    p.add_argument("--uci", action="store_true", help="UCI mode (default)")
    p.add_argument("--ui", action="store_true", help="HTTP UI mode")
    p.add_argument("--both", action="store_true", help="UCI + HTTP UI together")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args(argv)

    core = EngineCore()

    if args.both:
        from ui.server import UIServer
        server = UIServer(core, host=args.host, port=args.port)
        server.start()
        print(f"UI server: {server.url}", file=sys.stderr)
        try:
            uci_loop(core)
        finally:
            server.stop()
        return 0

    if args.ui:
        run_ui(core, args.host, args.port, foreground=True)
        return 0

    # default: UCI
    run_uci(core)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
