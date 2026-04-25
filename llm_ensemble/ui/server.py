"""HTTP server for the LLM Ensemble chess UI.

Serves a single-page app with a chess board and LLM voting panel.
The engine runs in a background thread for each position request.

API endpoints:
  GET  /            → index.html
  GET  /static/*    → static files
  POST /api/new     → new game
  GET  /api/state   → current board state (FEN, legal moves, status, history)
  POST /api/move    → human move; body: {"move": "e2e4"}
  POST /api/undo    → undo last two plies
  POST /api/resign  → human resigns
  GET  /api/engine  → trigger engine move; returns EnsembleResult JSON
  POST /api/option  → set engine option; body: {"elo": 1500, "method": "plurality"}
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ..ensemble.engine import EnsembleEngine, EnsembleResult
from ..config import DEFAULT_ELO, DEFAULT_VOTING_METHOD, VOTE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# ---------------------------------------------------------------------------
# Game state (single-game server)
# ---------------------------------------------------------------------------


class GameState:
    def __init__(self, elo: int = DEFAULT_ELO, voting_method: str = DEFAULT_VOTING_METHOD) -> None:
        from oneshot_react_engine.core.board import Board
        from oneshot_react_engine.core.fen import STARTING_FEN
        from oneshot_react_engine.core.notation import board_to_pgn
        self._Board = Board
        self._STARTING_FEN = STARTING_FEN
        self._pgn_fn = board_to_pgn

        self.board = Board(STARTING_FEN)
        self.human_color = "white"   # "white" or "black"
        self.elo = elo
        self.voting_method = voting_method

        self.engine = EnsembleEngine(
            elo=elo,
            voting_method=voting_method,
            vote_timeout=VOTE_TIMEOUT_SECONDS,
        )

        self.last_ensemble_result: Optional[EnsembleResult] = None
        self.move_history: list = []
        self.status = "ongoing"   # "ongoing" | "checkmate" | "stalemate" | "draw" | "resigned"
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self.board = self._Board(self._STARTING_FEN)
            self.last_ensemble_result = None
            self.move_history = []
            self.status = "ongoing"
            self.engine.reset()

    def set_elo(self, elo: int) -> None:
        with self._lock:
            self.elo = elo
            self.engine.set_elo(elo)

    def set_voting_method(self, method: str) -> None:
        with self._lock:
            self.voting_method = method
            self.engine._voting_method = method

    def _detect_status(self) -> str:
        legal = self.board.legal_moves()
        if not legal:
            if self.board.is_in_check():
                return "checkmate"
            return "stalemate"
        if self.board.halfmove_clock >= 100:
            return "draw"
        if self.board.is_threefold_repetition():
            return "draw"
        if self.board.is_insufficient_material():
            return "draw"
        return "ongoing"

    def apply_human_move(self, uci: str) -> dict:
        with self._lock:
            legal = self.board.legal_moves()
            move = next((m for m in legal if m.uci() == uci), None)
            if move is None:
                return {"ok": False, "error": "illegal move"}
            self.board._make_move_internal(move)
            self.move_history.append({"by": "human", "move": uci})
            self.status = self._detect_status()
            return {"ok": True}

    def apply_engine_move(self) -> dict:
        with self._lock:
            if self.status != "ongoing":
                return {"ok": False, "error": "game over"}
            try:
                result = self.engine.search_and_choose(self.board)
                self.last_ensemble_result = result
                legal = self.board.legal_moves()
                move = next((m for m in legal if m.uci() == result.chosen_move), None)
                if move is None:
                    return {"ok": False, "error": f"engine returned illegal move {result.chosen_move}"}
                self.board._make_move_internal(move)
                self.move_history.append({"by": "engine", "move": result.chosen_move})
                self.status = self._detect_status()
                return {"ok": True, "ensemble": self._ensemble_to_dict(result)}
            except Exception as exc:  # noqa: BLE001
                logger.exception("Engine error")
                return {"ok": False, "error": str(exc)}

    def undo(self) -> dict:
        with self._lock:
            # Undo two half-moves (engine + human)
            for _ in range(2):
                if self.board.move_history:
                    move, undo_state = self.board.move_history[-1]
                    self.board._unmake_move_internal(move, undo_state)
                    if self.move_history:
                        self.move_history.pop()
            self.status = self._detect_status()
            return {"ok": True}

    def resign(self) -> dict:
        with self._lock:
            self.status = "resigned"
            return {"ok": True}

    def state_dict(self) -> dict:
        with self._lock:
            legal = [m.uci() for m in self.board.legal_moves()]
            return {
                "fen": self.board.to_fen(),
                "turn": self.board.turn.name.lower(),
                "legal_moves": legal,
                "status": self.status,
                "move_history": list(self.move_history),
                "human_color": self.human_color,
                "elo": self.elo,
                "voting_method": self.voting_method,
                "in_check": self.board.is_in_check(),
                "fullmove": self.board.fullmove_number,
            }

    @staticmethod
    def _ensemble_to_dict(r: EnsembleResult) -> dict:
        votes_list = [
            {
                "llm": v.llm_name,
                "move": v.chosen_move,
                "success": v.success,
                "latency_ms": v.latency_ms,
                "explanation": v.explanation,
            }
            for v in r.voting_session.votes
        ]
        return {
            "chosen_move": r.chosen_move,
            "ab_best_move": r.ab_best_move,
            "ab_score_cp": r.ab_score_cp,
            "ab_depth": r.ab_depth,
            "ab_nodes": r.ab_nodes,
            "ab_elapsed_ms": r.ab_elapsed_ms,
            "candidates": r.candidates,
            "ab_scores": r.ab_scores,
            "votes": votes_list,
            "vote_counts": r.vote_tally.vote_counts,
            "weighted_scores": r.vote_tally.weighted_scores,
            "fallback_used": r.vote_tally.fallback_used,
            "fallback_reason": r.vote_tally.fallback_reason,
            "blunder_applied": r.blunder_applied,
            "elo": r.settings.elo,
            "voting_method": r.vote_tally.method,
        }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


_GAME: Optional[GameState] = None


def _get_game() -> GameState:
    global _GAME
    if _GAME is None:
        _GAME = GameState()
    return _GAME


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args) -> None:  # suppress default access log
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_file(os.path.join(_STATIC_DIR, "index.html"))
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]
            self._send_file(os.path.join(_STATIC_DIR, rel))
        elif path == "/api/state":
            self._send_json(_get_game().state_dict())
        elif path == "/api/engine":
            result = _get_game().apply_engine_move()
            self._send_json(result)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        game = _get_game()

        if path == "/api/new":
            body = self._read_body()
            game.reset()
            if "human_color" in body:
                game.human_color = body["human_color"]
            self._send_json({"ok": True})

        elif path == "/api/move":
            body = self._read_body()
            result = game.apply_human_move(body.get("move", ""))
            if result["ok"]:
                result["state"] = game.state_dict()
            self._send_json(result)

        elif path == "/api/undo":
            self._send_json(game.undo())

        elif path == "/api/resign":
            self._send_json(game.resign())

        elif path == "/api/option":
            body = self._read_body()
            if "elo" in body:
                game.set_elo(int(body["elo"]))
            if "method" in body:
                game.set_voting_method(body["method"])
            self._send_json({"ok": True})

        else:
            self.send_error(404)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_server(host: str = "127.0.0.1", port: int = 8001) -> None:
    """Start the HTTP server and open the browser."""
    global _GAME
    _GAME = GameState()

    server = HTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"PointChess Ensemble UI → {url}")
    print("Press Ctrl-C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
