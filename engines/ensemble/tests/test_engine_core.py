import time

from engine.core import Engine, GoParams


def test_set_position_startpos():
    e = Engine()
    e.set_position("startpos")
    assert "rnbqkbnr" in e.fen()


def test_set_position_with_moves():
    e = Engine()
    e.set_position("startpos", ["e2e4", "e7e5"])
    fen = e.fen()
    assert "e4" not in fen  # no algebraic in fen, but e4 occupied
    assert e.board.piece_at(__import__("engine.squares", fromlist=["algebraic_to_120"]).algebraic_to_120("e4")) != 0


def test_set_elo_clamps():
    e = Engine()
    e.set_elo(800)
    assert e.elo == 800
    try:
        e.set_elo(100)
        assert False
    except ValueError:
        pass


def test_engine_go_sync_returns_move():
    e = Engine()
    e.set_elo(2400)  # deterministic
    res = e.go(GoParams(depth=2, movetime=1000), sync=True)
    assert res is not None
    assert res.best_move is not None


def test_engine_legal_moves_initial():
    e = Engine()
    moves = e.legal_uci_moves()
    assert len(moves) == 20


def test_engine_status_checkmate():
    e = Engine()
    # Fool's mate
    e.set_position("startpos", ["f2f3", "e7e5", "g2g4", "d8h4"])
    assert e.game_status() == "checkmate"
