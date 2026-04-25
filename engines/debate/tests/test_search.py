"""Search tests."""

import threading

from engine.board import Board, move_uci
from engine.search import (
    iterative_deepening, alphabeta, quiescence,
    SearchContext, select_strength_move, MATE,
)
from engine.tt import TranspositionTable
from engine.strength import configure


def test_finds_mate_in_one():
    # White to move and mate in one: Qh5xf7# style
    # Use simple "back-rank mate": Black king on a8, white rook on h1, black rook on b8 covering, white queen on h7 mates
    # Easier classic: 4k3/4Q3/4K3/8/8/8/8/8 w - - 0 1  (white queen on e7, white king on e6, mate is Qe7-e8?)
    # Actually e7 queen + e6 king already mates black king on e8? No, black king on e8 has no moves -> mate
    # Let's set up clear M1: Black king on h8, white queen on g6, white king on f7. Qg7# is mate.
    fen = "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"
    b = Board.from_fen(fen)
    move, score, _ = iterative_deepening(b, time_limit_ms=2000, max_depth=3)
    assert move is not None
    # The move should be a mating move (Qg6-g7)
    b.make_move(move)
    from engine.movegen import generate_legal_moves, in_check
    legal = generate_legal_moves(b, b.side_to_move)
    assert in_check(b, b.side_to_move) and len(legal) == 0


def test_avoids_hanging_queen():
    # White queen on d4, black queen on h4 attacking it; with simple defense None.
    # White to move should not lose the queen (move it, capture, or defend).
    fen = "4k3/8/8/8/3Q3q/8/8/4K3 w - - 0 1"
    b = Board.from_fen(fen)
    move, score, _ = iterative_deepening(b, time_limit_ms=1000, max_depth=4)
    assert move is not None
    # The move's score should be >= roughly 0 (we shouldn't blunder the queen)
    # Queen exchange would be 0; moving the queen safely or capturing the black queen would be fine.
    assert score > -500


def test_stop_event_aborts_search():
    b = Board.starting_position()
    stop = threading.Event()
    stop.set()  # immediately stop
    move, score, _ = iterative_deepening(b, time_limit_ms=10_000, max_depth=20, stop_event=stop)
    # Either returns a move from depth 1 (if completed) or None; must not hang.
    # Test passes by virtue of returning at all.


def test_iterative_deepening_returns_move_starting_position():
    b = Board.starting_position()
    move, score, results = iterative_deepening(b, time_limit_ms=1000, max_depth=3)
    assert move is not None
    assert len(results) == 20


def test_strength_top1_deterministic():
    """Strength top_k==1 returns deterministic best move."""
    b = Board.starting_position()
    cfg = configure(2400)
    move, score, results = iterative_deepening(b, time_limit_ms=2000,
                                               max_depth=cfg.max_depth, config=cfg)
    chosen = select_strength_move(b, results, cfg)
    assert chosen == results[0][0]


def test_strength_low_elo_samples_within_topk():
    """At low ELO, chosen move is within the candidate window."""
    import random as _r
    b = Board.starting_position()
    cfg = configure(600)
    _, _, results = iterative_deepening(b, time_limit_ms=500, max_depth=cfg.max_depth, config=cfg)
    rng = _r.Random(123)
    chosen = select_strength_move(b, results, cfg, rng=rng)
    topk_moves = [m for m, _ in results[: cfg.top_k]]
    assert chosen in topk_moves


def test_strength_plays_mate_unconditionally():
    # Same M1 position; even with low ELO it must play the mate.
    fen = "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"
    b = Board.from_fen(fen)
    cfg = configure(400)
    _, _, results = iterative_deepening(b, time_limit_ms=2000,
                                        max_depth=max(2, cfg.max_depth), config=cfg)
    chosen = select_strength_move(b, results, cfg)
    assert chosen is not None
    b.make_move(chosen)
    from engine.movegen import generate_legal_moves, in_check
    assert in_check(b, b.side_to_move) and len(generate_legal_moves(b, b.side_to_move)) == 0
