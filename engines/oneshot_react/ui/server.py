"""Tiny HTTP + JSON server for the web UI.

Pure-stdlib (no Flask/FastAPI dependency) so this engine can run with
``python -m engines.oneshot_react`` against a fresh interpreter.

The server is single-process and stores the game state in-memory.  This is
perfectly fine for "one human plays one engine" interactive use; multi-user
deployments are explicitly out of scope.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

from ..core.board import Board
from ..core.fen import STARTING_FEN
from ..core.move import Move
from ..core.notation import board_to_pgn, move_to_san
from ..core.pieces import Color, PieceType
from ..core.square import Square
from ..engine.search import Engine
from ..engine.strength import settings_for_elo


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class GameSession:
    """Holds the current board, engine, and bookkeeping for a single browser tab."""

    def __init__(self) -> None:
        self.board = Board(STARTING_FEN)
        self.engine = Engine(strength=settings_for_elo(1500))
        self.human_color: Color = Color.WHITE
        self.move_log: List[Dict[str, Any]] = []  # {san, uci, by}
        self.last_engine_info: Dict[str, Any] = {}
        self.lock = threading.Lock()

    def reset(self, fen: str = STARTING_FEN, human_color: Color = Color.WHITE) -> None:
        self.board = Board(fen)
        self.engine.reset()
        self.human_color = human_color
        self.move_log = []
        self.last_engine_info = {}

    def set_elo(self, elo: int) -> None:
        self.engine.set_elo(elo)

    def board_state(self) -> Dict[str, Any]:
        squares = []
        for r in range(8):
            row = []
            for c in range(8):
                p = self.board.squares[r][c]
                row.append(None if p is None else p.fen_char())
            squares.append(row)
        legal_by_from: Dict[str, List[str]] = {}
        for m in self.board.legal_moves():
            legal_by_from.setdefault(m.from_sq.algebraic(), []).append(m.uci())
        over, reason = self.board.is_game_over()
        return {
            "squares": squares,
            "turn": "w" if self.board.turn == Color.WHITE else "b",
            "human_color": "w" if self.human_color == Color.WHITE else "b",
            "fen": self.board.to_fen(),
            "legal_moves_by_from": legal_by_from,
            "in_check": self.board.is_in_check(self.board.turn),
            "game_over": over,
            "result_reason": reason,
            "result": self.board.result(),
            "move_log": self.move_log,
            "elo": self.engine.strength.elo,
            "last_engine": self.last_engine_info,
            "halfmove_clock": self.board.halfmove_clock,
            "fullmove_number": self.board.fullmove_number,
        }

    def play_human_move(self, uci_str: str) -> Dict[str, Any]:
        try:
            move = Move.from_uci(uci_str)
        except Exception:
            return {"ok": False, "error": "invalid move format"}
        if move not in self.board.legal_moves():
            return {"ok": False, "error": "illegal move"}
        san = move_to_san(self.board, move)
        self.board.make_move(move)
        self.move_log.append({"san": san, "uci": move.uci(), "by": "human"})
        return {"ok": True}

    def play_engine_move(self) -> Dict[str, Any]:
        if self.board.is_game_over()[0]:
            return {"ok": False, "error": "game over"}
        if self.board.turn == self.human_color:
            return {"ok": False, "error": "not engine's turn"}
        result = self.engine.search_and_choose(
            self.board,
            movetime_ms=self.engine.strength.movetime_ms,
            max_depth=self.engine.strength.max_depth,
            record_reasoning=True,
        )
        move = result.best_move
        if move is None:
            return {"ok": False, "error": "engine produced no move"}
        san = move_to_san(self.board, move)
        self.board.make_move(move)
        self.move_log.append({"san": san, "uci": move.uci(), "by": "engine"})
        top_pv = result.candidates[0][0] if result.candidates else None
        self.last_engine_info = {
            "best_uci": top_pv.uci() if top_pv else None,
            "played_uci": move.uci(),
            "score_cp": result.score_cp,
            "depth": result.depth_reached,
            "nodes": result.nodes,
            "elapsed_ms": result.elapsed_ms,
            "pv": [m.uci() for m in result.pv],
            "reasoning": result.reasoning.render() if result.reasoning else None,
        }
        return {"ok": True, "move": move.uci(), "san": san}

    def undo(self) -> bool:
        # Undo two plies so it's still the human's move
        a = self.board.unmake_move()
        if a is None:
            return False
        if self.move_log:
            self.move_log.pop()
        b = self.board.unmake_move()
        if b is not None and self.move_log:
            self.move_log.pop()
        return True

    def pgn(self) -> str:
        white = "Human" if self.human_color == Color.WHITE else "PointChess ReAct"
        black = "PointChess ReAct" if self.human_color == Color.WHITE else "Human"
        return board_to_pgn(self.board, headers={"White": white, "Black": black})


# ---------------------------------------------------------------------------


def _make_handler(session: GameSession):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return  # silence default access logs

        def _send_json(self, status: int, body: Dict[str, Any]) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_static(self, path: str) -> None:
            full = os.path.join(STATIC_DIR, path.lstrip("/"))
            if not os.path.exists(full) or os.path.isdir(full):
                self.send_response(404)
                self.end_headers()
                return
            ext = os.path.splitext(full)[1].lower()
            content_type = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".ico": "image/x-icon",
            }.get(ext, "application/octet-stream")
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self._send_static("index.html")
            elif self.path.startswith("/static/"):
                self._send_static(self.path[len("/static/") :])
            elif self.path == "/api/state":
                with session.lock:
                    self._send_json(200, session.board_state())
            elif self.path == "/api/pgn":
                with session.lock:
                    self._send_json(200, {"pgn": session.pgn()})
            elif self.path == "/api/elo_options":
                # Surface the strength brackets so the UI can show metadata.
                from ..engine.strength import MIN_ELO, MAX_ELO
                self._send_json(200, {"min": MIN_ELO, "max": MAX_ELO, "default": 1500})
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid JSON"})
                return

            if self.path == "/api/new_game":
                fen = payload.get("fen") or STARTING_FEN
                color_str = payload.get("human_color", "w")
                hc = Color.WHITE if color_str == "w" else Color.BLACK
                with session.lock:
                    try:
                        session.reset(fen=fen, human_color=hc)
                    except Exception as exc:
                        self._send_json(400, {"ok": False, "error": str(exc)})
                        return
                    self._send_json(200, session.board_state())
            elif self.path == "/api/move":
                uci_str = payload.get("uci", "")
                with session.lock:
                    res = session.play_human_move(uci_str)
                    if not res["ok"]:
                        self._send_json(400, res)
                        return
                    state = session.board_state()
                self._send_json(200, {"ok": True, "state": state})
            elif self.path == "/api/engine_move":
                with session.lock:
                    res = session.play_engine_move()
                    state = session.board_state()
                if not res["ok"]:
                    self._send_json(400, {"ok": False, "error": res["error"], "state": state})
                else:
                    self._send_json(200, {"ok": True, "state": state, "move": res["move"], "san": res["san"]})
            elif self.path == "/api/set_elo":
                try:
                    elo = int(payload.get("elo", 1500))
                except (TypeError, ValueError):
                    self._send_json(400, {"ok": False, "error": "elo must be int"})
                    return
                with session.lock:
                    session.set_elo(elo)
                    self._send_json(200, {"ok": True, "elo": session.engine.strength.elo})
            elif self.path == "/api/undo":
                with session.lock:
                    ok = session.undo()
                    state = session.board_state()
                self._send_json(200, {"ok": ok, "state": state})
            elif self.path == "/api/resign":
                with session.lock:
                    session.move_log.append({"san": "(resign)", "uci": "", "by": "human"})
                    state = session.board_state()
                    state["game_over"] = True
                    state["result_reason"] = "Human resigned"
                    state["result"] = "0-1" if session.human_color == Color.WHITE else "1-0"
                self._send_json(200, {"ok": True, "state": state})
            else:
                self._send_json(404, {"ok": False, "error": "not found"})

    return Handler


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    session = GameSession()
    handler = _make_handler(session)
    server = ThreadingHTTPServer((host, port), handler)
    server.session = session  # type: ignore[attr-defined]
    return server
