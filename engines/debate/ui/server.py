"""HTTP UI server. Vanilla stdlib http.server (ThreadingHTTPServer).

Endpoints:
- GET /                          -> index.html
- GET /static/<path>             -> static asset
- GET /api/state                 -> JSON snapshot
- POST /api/newgame              -> start a new game
- POST /api/move {"uci": "..."}  -> apply human move
- POST /api/go    {"movetime":N} -> trigger engine search
- POST /api/stop                 -> stop search
- POST /api/elo  {"elo": N, "limit": bool} -> set strength
- POST /api/position {"fen": "...", "moves": [...]} -> set position
"""

from __future__ import annotations

import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from engine.core import (
    EngineCore, CmdNewGame, CmdPosition, CmdGo, CmdStop,
    CmdSetElo, CmdSetLimitStrength, CmdMakeUserMove,
)


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png":  "image/png",
    ".svg":  "image/svg+xml",
}


def make_handler(core: EngineCore):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # silence
            return

        # --- helpers ----
        def _send_json(self, status, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_file(self, path):
            if not os.path.isfile(path):
                self.send_error(404, "not found")
                return
            ext = os.path.splitext(path)[1].lower()
            mime = _MIME.get(ext, "application/octet-stream")
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        # --- routing ----
        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            path = url.path
            if path == "/":
                self._send_file(os.path.join(STATIC_DIR, "index.html"))
                return
            if path.startswith("/static/"):
                rel = path[len("/static/"):]
                # avoid path traversal
                safe = os.path.normpath(rel).lstrip(os.sep)
                if ".." in safe.split(os.sep):
                    self.send_error(403, "forbidden")
                    return
                self._send_file(os.path.join(STATIC_DIR, safe))
                return
            if path == "/api/state":
                self._send_json(200, core.snapshot())
                return
            self.send_error(404, "not found")

        def do_POST(self):
            url = urllib.parse.urlparse(self.path)
            path = url.path
            body = self._read_json()

            if path == "/api/newgame":
                core.submit(CmdNewGame())
                self._send_json(200, {"ok": True})
                return
            if path == "/api/move":
                uci = body.get("uci", "")
                if uci:
                    core.submit(CmdMakeUserMove(uci))
                self._send_json(200, {"ok": True})
                return
            if path == "/api/go":
                cmd = CmdGo()
                if "movetime" in body:
                    cmd.movetime = int(body["movetime"])
                if "depth" in body:
                    cmd.depth = int(body["depth"])
                core.submit(cmd)
                self._send_json(200, {"ok": True})
                return
            if path == "/api/stop":
                core.submit(CmdStop())
                self._send_json(200, {"ok": True})
                return
            if path == "/api/elo":
                if "limit" in body:
                    core.submit(CmdSetLimitStrength(bool(body["limit"])))
                if "elo" in body:
                    core.submit(CmdSetElo(int(body["elo"])))
                self._send_json(200, {"ok": True})
                return
            if path == "/api/position":
                fen = body.get("fen") or ""
                moves = body.get("moves") or []
                core.submit(CmdPosition(fen=fen, moves=list(moves)))
                self._send_json(200, {"ok": True})
                return

            self.send_error(404, "not found")

    return Handler


class UIServer:
    def __init__(self, core: EngineCore, host: str = "127.0.0.1", port: int = 8080):
        self.core = core
        self.host = host
        self.port = port
        self.httpd: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        handler = make_handler(self.core)
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=3.0)
        self.httpd = None
        self.thread = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"
