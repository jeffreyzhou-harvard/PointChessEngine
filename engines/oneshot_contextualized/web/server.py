"""Flask web server: human-vs-engine UI.

Endpoints:
    GET  /                  the page
    POST /api/new_game      body: {"side": "white"|"black", "elo": int}
    GET  /api/state         {fen, turn, status, result, last_move, history}
    GET  /api/legal_moves   {moves: ["e2e4", ...]}
    POST /api/move          body: {"uci": "e2e4"}; returns updated state +
                            engine_move (if engine then made one)
    POST /api/engine_move   ask engine to move now
    POST /api/resign        end the game by resignation
    GET  /api/pgn           download PGN

State is per-server-process (single-game, single-user). For a multi-user
deployment, key the game on a session id.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory, render_template

import chess

# Make sibling packages importable.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.engine import Engine
from engine.game import Game


app = Flask(
    __name__,
    static_folder=os.path.join(HERE, "static"),
    template_folder=os.path.join(HERE, "templates"),
)


class _State:
    def __init__(self) -> None:
        self.engine = Engine()
        self.engine.set_limit_strength(True)
        self.engine.set_elo(1500)
        self.game = Game()
        self.human_color: chess.Color = chess.WHITE
        self.resigned: bool = False
        self.elo: int = 1500
        self.last_engine_uci: Optional[str] = None
        self.last_engine_san: Optional[str] = None


STATE = _State()


def _state_payload() -> dict:
    g = STATE.game
    return {
        "fen": g.fen,
        "turn": "white" if g.turn == chess.WHITE else "black",
        "human_color": "white" if STATE.human_color == chess.WHITE else "black",
        "status": "Resigned. Engine wins." if STATE.resigned else g.status_text(),
        "is_over": STATE.resigned or g.is_over,
        "result": ("0-1" if STATE.resigned and STATE.human_color == chess.WHITE
                   else "1-0" if STATE.resigned and STATE.human_color == chess.BLACK
                   else g.result if g.is_over else "*"),
        "history_san": list(g.san_history),
        "last_move_uci": (g.move_history[-1].uci()
                          if g.move_history else None),
        "last_engine_uci": STATE.last_engine_uci,
        "last_engine_san": STATE.last_engine_san,
        "elo": STATE.elo,
        "in_check": g.board.is_check() and not STATE.resigned and not g.is_over,
    }


def _engine_move() -> Optional[str]:
    if STATE.resigned or STATE.game.is_over:
        return None
    info = STATE.engine.choose_move(STATE.game.board)
    if info.best_move is None:
        return None
    san = STATE.game.board.san(info.best_move)
    STATE.game.push(info.best_move)
    STATE.last_engine_uci = info.best_move.uci()
    STATE.last_engine_san = san
    return info.best_move.uci()


# ---- routes ----------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/new_game", methods=["POST"])
def new_game():
    data = request.get_json(silent=True) or {}
    side = (data.get("side") or "white").lower()
    elo = int(data.get("elo", 1500))
    STATE.human_color = chess.WHITE if side == "white" else chess.BLACK
    STATE.elo = max(400, min(2400, elo))
    STATE.resigned = False
    STATE.last_engine_uci = None
    STATE.last_engine_san = None
    STATE.engine.new_game()
    STATE.engine.set_elo(STATE.elo)
    STATE.engine.set_limit_strength(True)
    STATE.game.reset()

    # If the engine plays white, let it move first.
    if STATE.human_color == chess.BLACK:
        _engine_move()

    return jsonify(_state_payload())


@app.route("/api/state", methods=["GET"])
def state():
    return jsonify(_state_payload())


@app.route("/api/legal_moves", methods=["GET"])
def legal_moves():
    src = request.args.get("from")  # e.g., "e2"
    moves = []
    for m in STATE.game.board.legal_moves:
        u = m.uci()
        if src is None or u.startswith(src):
            moves.append(u)
    return jsonify({"moves": moves})


@app.route("/api/move", methods=["POST"])
def move():
    if STATE.resigned or STATE.game.is_over:
        return jsonify({"error": "game is over", **_state_payload()}), 400
    if STATE.game.turn != STATE.human_color:
        return jsonify({"error": "not your turn", **_state_payload()}), 400

    data = request.get_json(silent=True) or {}
    uci = data.get("uci")
    if not uci:
        return jsonify({"error": "missing uci", **_state_payload()}), 400

    try:
        STATE.game.push_uci(uci)
    except ValueError as e:
        return jsonify({"error": str(e), **_state_payload()}), 400

    # If the game's not over, let the engine reply.
    if not STATE.game.is_over:
        _engine_move()

    return jsonify(_state_payload())


@app.route("/api/engine_move", methods=["POST"])
def engine_move():
    if STATE.resigned or STATE.game.is_over:
        return jsonify({"error": "game is over", **_state_payload()}), 400
    if STATE.game.turn == STATE.human_color:
        return jsonify({"error": "human's turn", **_state_payload()}), 400
    _engine_move()
    return jsonify(_state_payload())


@app.route("/api/resign", methods=["POST"])
def resign():
    STATE.resigned = True
    return jsonify(_state_payload())


@app.route("/api/pgn", methods=["GET"])
def pgn():
    body = STATE.game.to_pgn()
    return (body, 200, {
        "Content-Type": "application/x-chess-pgn",
        "Content-Disposition": 'attachment; filename="game.pgn"',
    })


def main(host: str = "127.0.0.1", port: int = 5000) -> None:
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
