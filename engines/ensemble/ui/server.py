"""Local-only HTTP server hosting the web UI."""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from engine.board import WHITE, BLACK
from engine.core import Engine, GoParams


HERE = os.path.dirname(__file__)
STATIC_DIR = os.path.join(HERE, "static")


class UIState:
    def __init__(self, engine: Engine, human_color: str = "w") -> None:
        self.engine = engine
        self.human_color = human_color  # "w" or "b"
        self.thinking = False
        self.lock = threading.Lock()

    def is_engine_turn(self) -> bool:
        stm = "w" if self.engine.board.side_to_move == WHITE else "b"
        return stm != self.human_color

    def maybe_engine_move(self) -> None:
        if self.thinking:
            return
        if self.engine.game_status() != "ongoing":
            return
        if not self.is_engine_turn():
            return
        self.thinking = True

        def on_best(mv, res):
            if mv is not None:
                with self.lock:
                    try:
                        self.engine.board.make_move(mv)
                    except Exception:
                        pass
            self.thinking = False

        self.engine.go(GoParams(), on_bestmove=on_best)


def _make_handler(ui: UIState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # silence default logging

        def _send_json(self, code: int, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_file(self, path: str, mime: str) -> None:
            try:
                with open(path, "rb") as f:
                    body = f.read()
            except FileNotFoundError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
                return
            if self.path.startswith("/static/"):
                rel = self.path[len("/static/"):]
                rel = rel.split("?")[0]
                # prevent path traversal
                safe = os.path.normpath(rel).replace("\\", "/")
                if safe.startswith(".."):
                    self.send_error(403); return
                full = os.path.join(STATIC_DIR, safe)
                mime = "text/javascript" if full.endswith(".js") else (
                       "text/css" if full.endswith(".css") else (
                       "text/html" if full.endswith(".html") else "application/octet-stream"))
                self._send_file(full, mime)
                return
            if self.path == "/state":
                with ui.lock:
                    fen = ui.engine.fen()
                    legal = ui.engine.legal_uci_moves()
                    status = ui.engine.game_status()
                stm = "w" if ui.engine.board.side_to_move == WHITE else "b"
                self._send_json(200, {
                    "fen": fen,
                    "legal_moves": legal,
                    "status": status,
                    "side_to_move": stm,
                    "human_color": ui.human_color,
                    "thinking": ui.thinking,
                    "elo": ui.engine.elo,
                })
                # If engine's turn, kick it off (after responding).
                ui.maybe_engine_move()
                return
            self.send_error(404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw.decode()) if raw else {}
            except json.JSONDecodeError:
                data = {}

            if self.path == "/move":
                mv = data.get("move")
                if not isinstance(mv, str):
                    self._send_json(400, {"error": "missing move"}); return
                with ui.lock:
                    try:
                        ui.engine.push_uci(mv)
                    except ValueError as e:
                        self._send_json(400, {"error": str(e)}); return
                self._send_json(200, {"ok": True})
                ui.maybe_engine_move()
                return
            if self.path == "/new":
                elo = int(data.get("elo", 1500))
                human = data.get("human_color", "w")
                with ui.lock:
                    ui.engine.stop()
                    ui.engine.new_game()
                    ui.engine.set_elo(elo)
                    ui.human_color = "b" if human == "b" else "w"
                    ui.thinking = False
                self._send_json(200, {"ok": True})
                ui.maybe_engine_move()
                return
            if self.path == "/stop":
                ui.engine.stop()
                ui.thinking = False
                self._send_json(200, {"ok": True})
                return
            self.send_error(404)
    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080,
          engine: Optional[Engine] = None,
          human_color: str = "w") -> ThreadingHTTPServer:
    if engine is None:
        engine = Engine()
    ui = UIState(engine, human_color=human_color)
    server = ThreadingHTTPServer((host, port), _make_handler(ui))
    return server


def main(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = serve(host, port)
    print(f"PyChess UI on http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
