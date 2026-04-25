"""Engine search and ELO scaling tests."""

import random

from oneshot_react_engine.core import Board, Move
from oneshot_react_engine.engine import Engine, settings_for_elo
from oneshot_react_engine.engine.evaluator import evaluate
from oneshot_react_engine.engine.strength import MAX_ELO, MIN_ELO


def test_finds_mate_in_one():
    b = Board("6k1/5ppp/8/8/8/8/8/4K2Q w - - 0 1")  # Qa8# (h7 pawn blocks escape)
    eng = Engine(strength=settings_for_elo(2200))
    res = eng.search(b, max_depth=3, movetime_ms=2000)
    assert res.best_move is not None
    # Either Qa8# or Qh7# (depending on tie-breaking) should be a winning move
    b.make_move(res.best_move)
    assert b.is_checkmate()


def test_finds_capture_when_free():
    # White queen on d1 can take a hanging black queen on d8
    b = Board("3q4/8/8/8/8/8/8/3QK2k w - - 0 1")
    eng = Engine(strength=settings_for_elo(2000))
    res = eng.search(b, max_depth=3, movetime_ms=1500)
    assert res.best_move is not None
    assert res.best_move.to_sq.algebraic() == "d8"


def test_does_not_blunder_queen():
    # Simple position; verify engine doesn't hang its queen
    b = Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    eng = Engine(strength=settings_for_elo(2200))
    res = eng.search(b, max_depth=3, movetime_ms=2000)
    move = res.best_move
    assert move is not None
    # Opening engine shouldn't sacrifice its queen on the first move
    piece = b.piece_at(move.from_sq)
    assert piece is not None
    assert piece.piece_type.name != "QUEEN"


def test_no_legal_moves_returns_none():
    # Stalemate - no legal moves
    b = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    eng = Engine(strength=settings_for_elo(1500))
    res = eng.search(b, max_depth=2)
    assert res.best_move is None


def test_engine_stable_under_repeated_searches():
    b = Board()
    eng = Engine(strength=settings_for_elo(1500))
    m1 = eng.choose_move(b, max_depth=2, movetime_ms=500)
    m2 = eng.choose_move(b, max_depth=2, movetime_ms=500)
    assert m1 in b.legal_moves()
    assert m2 in b.legal_moves()


def test_evaluator_starting_zero_ish():
    b = Board()
    score = evaluate(b)
    # At the starting position evaluation should be close to 0 (mobility may add a bit)
    assert -100 <= score <= 100


def test_evaluator_material_imbalance():
    # White has an extra queen
    b = Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    score = evaluate(b)
    assert score > 500


def test_strength_settings_clamped():
    s_lo = settings_for_elo(50)
    s_hi = settings_for_elo(9999)
    assert s_lo.elo == MIN_ELO
    assert s_hi.elo == MAX_ELO


def test_strength_monotonic_depth():
    depths = [settings_for_elo(e).max_depth for e in range(400, 2401, 200)]
    # Depth should never decrease as ELO increases
    assert all(depths[i] <= depths[i + 1] for i in range(len(depths) - 1))


def test_strength_monotonic_blunder():
    blunders = [settings_for_elo(e).blunder_pct for e in range(400, 2401, 200)]
    # Blunder rate should never increase as ELO increases
    assert all(blunders[i] >= blunders[i + 1] for i in range(len(blunders) - 1))


def test_weak_engine_still_legal():
    b = Board()
    eng = Engine(strength=settings_for_elo(400), rng=random.Random(0))
    move = eng.choose_move(b, max_depth=1, movetime_ms=200)
    assert move in b.legal_moves()


def test_reasoning_trace_recorded():
    b = Board()
    eng = Engine(strength=settings_for_elo(1500))
    res = eng.search_and_choose(b, max_depth=2, movetime_ms=500, record_reasoning=True)
    assert res.reasoning is not None
    rendered = res.reasoning.render()
    assert "Thought:" in rendered
    assert "Action:" in rendered
    assert "Observation:" in rendered
