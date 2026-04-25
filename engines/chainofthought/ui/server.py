"""Browser UI HTTP server.

A tiny ``http.server`` wrapper that exposes :class:`~.session.Session`
over JSON and serves the static frontend in :mod:`engines.chainofthought.ui.static`.

API surface (all JSON unless noted):

  ============================  ====================================
  ``GET  /``                    serves ``index.html`` (text/html)
  ``GET  /static/<path>``       serves a file from ``ui/static/``
  ``GET  /api/state``           current :meth:`Session.state_dict`
  ``GET  /api/pgn``             ``text/plain`` PGN of current game
  ``POST /api/new``             body ``{color, elo}``; resets game
  ``POST /api/move``            body ``{uci}``; applies user move
  ``POST /api/engine_move``     engine searches & plays one move
  ``POST /api/resign``          user resigns
  ``POST /api/elo``             body ``{elo}``; updates strength
  ============================  ====================================

Errors are returned as JSON ``{"error": "..."}`` with an
appropriate 4xx status code; the loop never crashes on bad input.

Threading
---------

We use :class:`http.server.ThreadingHTTPServer` so a long-running
``/api/engine_move`` doesn't starve unrelated requests (state polls,
``/api/resign``). All session access is serialised by
``server.session_lock`` -- the session itself is not thread-safe.
That means while the engine is searching, other requests *queue*,
which is fine for a single-user UI.

Test surface
------------

:func:`make_server` builds an unstarted :class:`UIServer` so tests
can introspect the bound port and call handler methods directly. The
``UIServer`` instance carries ``session`` and ``session_lock``
attributes that handlers consult.
"""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

from .session import Session, _color_from_name


_STATIC_DIR: Path = Path(__file__).resolve().parent / "static"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


# ----------------------------------------------------------------------
# server class
# ----------------------------------------------------------------------


class UIServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with a :class:`Session` and a lock.

    The session and lock live on the server (not on the handler)
    because handlers are constructed per-request.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        session: Optional[Session] = None,
    ) -> None:
        super().__init__(address, _Handler)
        self.session: Session = session if session is not None else Session()
        self.session_lock = threading.Lock()


# ----------------------------------------------------------------------
# request handler
# ----------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    server_version = "ChainOfThoughtUI/0.1"

    # The ThreadingHTTPServer above will set its own ``server`` ref,
    # which is the UIServer instance; this annotation is just for IDE
    # help when reading.
    server: UIServer  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # logging: silence the default per-request stderr spam
    # ------------------------------------------------------------------

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    # ------------------------------------------------------------------
    # routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._serve_static_file("index.html")
        if path.startswith("/static/"):
            return self._serve_static_file(path[len("/static/") :])
        if path == "/api/state":
            return self._handle_get_state()
        if path == "/api/pgn":
            return self._handle_get_pgn()
        return self._send_error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json()
        except ValueError as exc:
            return self._send_error(400, f"bad JSON: {exc}")

        try:
            if path == "/api/new":
                return self._handle_new(body)
            if path == "/api/move":
                return self._handle_move(body)
            if path == "/api/engine_move":
                return self._handle_engine_move()
            if path == "/api/resign":
                return self._handle_resign()
            if path == "/api/elo":
                return self._handle_elo(body)
        except ValueError as exc:
            return self._send_error(400, str(exc))
        except Exception as exc:  # noqa: BLE001  (defensive)
            return self._send_error(500, f"internal error: {exc}")

        return self._send_error(404, "not found")

    # ------------------------------------------------------------------
    # API handlers
    # ------------------------------------------------------------------

    def _handle_get_state(self) -> None:
        with self.server.session_lock:
            state = self.server.session.state_dict()
        self._send_json(200, state)

    def _handle_get_pgn(self) -> None:
        with self.server.session_lock:
            pgn = self.server.session.pgn()
        self._send_text(200, pgn)

    def _handle_new(self, body: dict) -> None:
        color_name = body.get("color", "white")
        elo_raw = body.get("elo")
        with self.server.session_lock:
            color = _color_from_name(color_name)
            self.server.session.start_new_game(
                user_color=color,
                elo=int(elo_raw) if elo_raw is not None else None,
            )
            # If the user picked Black, the engine moves first.
            if self.server.session.is_engine_turn():
                self.server.session.play_engine_move()
            state = self.server.session.state_dict()
        self._send_json(200, state)

    def _handle_move(self, body: dict) -> None:
        uci = body.get("uci")
        if not isinstance(uci, str) or not uci:
            return self._send_error(400, "missing 'uci'")
        with self.server.session_lock:
            self.server.session.play_user_move(uci)
            state = self.server.session.state_dict()
        self._send_json(200, state)

    def _handle_engine_move(self) -> None:
        with self.server.session_lock:
            info = self.server.session.play_engine_move()
            state = self.server.session.state_dict()
        # Surface the most recent engine info on the response too --
        # state_dict always carries last_engine_info, but a separate
        # field makes "this response is the result of the engine just
        # moving" unambiguous.
        state["engine_move"] = info
        self._send_json(200, state)

    def _handle_resign(self) -> None:
        with self.server.session_lock:
            self.server.session.resign()
            state = self.server.session.state_dict()
        self._send_json(200, state)

    def _handle_elo(self, body: dict) -> None:
        elo_raw = body.get("elo")
        if elo_raw is None:
            return self._send_error(400, "missing 'elo'")
        with self.server.session_lock:
            self.server.session.set_elo(int(elo_raw))
            state = self.server.session.state_dict()
        self._send_json(200, state)

    # ------------------------------------------------------------------
    # static files
    # ------------------------------------------------------------------

    def _serve_static_file(self, relative: str) -> None:
        # Defence in depth: refuse anything that escapes the static dir.
        try:
            target = (_STATIC_DIR / relative).resolve()
            target.relative_to(_STATIC_DIR.resolve())
        except (ValueError, RuntimeError):
            return self._send_error(404, "not found")
        if not target.is_file():
            return self._send_error(404, "not found")

        ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    # IO helpers
    # ------------------------------------------------------------------

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(str(exc)) from exc
        if not isinstance(decoded, dict):
            raise ValueError("expected a JSON object")
        return decoded

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ----------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------


def make_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    session: Optional[Session] = None,
) -> UIServer:
    """Construct (but do not start) a :class:`UIServer`.

    Pass ``port=0`` to let the OS pick a free port; tests use this.
    """
    return UIServer((host, port), session=session)


def serve(port: int = 8000, host: str = "127.0.0.1") -> None:
    """Run the UI on ``http://<host>:<port>`` until interrupted."""
    server = make_server(host=host, port=port)
    bound_host, bound_port = server.server_address[:2]
    print(
        f"Chain-of-Thought UI ready at http://{bound_host}:{bound_port}/",
        flush=True,
    )
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down...", flush=True)
    finally:
        server.shutdown()
        server.server_close()
