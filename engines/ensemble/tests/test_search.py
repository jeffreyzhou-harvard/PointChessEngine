from engine.board import Board
from engine.search import search, SearchLimits, MATE_THRESHOLD


def test_finds_mate_in_one():
    # White to play; Qxh7# (fool's mate-style construction).
    # Simpler: back-rank mate: black king on a8 boxed in by own pawns, white queen ready.
    fen = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"
    b = Board.from_fen(fen)
    res = search(b, SearchLimits(max_depth=3, time_ms=2000))
    assert res.best_move is not None
    assert res.best_move.uci() == "a1a8"
    assert res.score > MATE_THRESHOLD


def test_avoids_hanging_queen():
    # White queen attacked by pawn, must move it.
    fen = "4k3/8/8/8/3p4/4Q3/8/4K3 w - - 0 1"
    b = Board.from_fen(fen)
    res = search(b, SearchLimits(max_depth=3, time_ms=2000))
    assert res.best_move is not None
    # The queen must move to a safe square (not stay/be captured).
    # The chosen move's source should be e3.
    assert res.best_move.uci().startswith("e3")


def test_search_returns_legal_move():
    b = Board.initial()
    res = search(b, SearchLimits(max_depth=2, time_ms=1500))
    from engine.movegen import generate_legal
    legal_uci = {m.uci() for m in generate_legal(b)}
    assert res.best_move.uci() in legal_uci


def test_stalemate_detected():
    # K vs K+Q stalemate position: black king on a8, white queen on c7, white king nearby.
    fen = "k7/2Q5/1K6/8/8/8/8/8 b - - 0 1"
    b = Board.from_fen(fen)
    from engine.movegen import generate_legal
    assert generate_legal(b) == []
    assert not b.in_check()


def test_iterative_deepening_completes_one_depth():
    b = Board.initial()
    # very small budget but max_depth high -> should still complete depth 1 at least.
    res = search(b, SearchLimits(max_depth=4, time_ms=500))
    assert res.depth >= 1
    assert res.best_move is not None
