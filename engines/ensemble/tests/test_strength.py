import random

from engine.strength import params_for_elo, select_move, StrengthParams


class FakeMove:
    def __init__(self, name): self.name = name
    def __repr__(self): return f"M({self.name})"
    def __eq__(self, other): return isinstance(other, FakeMove) and self.name == other.name
    def __hash__(self): return hash(self.name)


def test_anchor_values():
    p = params_for_elo(400)
    assert p.max_depth == 1 and p.top_k == 8 and p.blunder_prob == 0.20
    p = params_for_elo(2400)
    assert p.max_depth == 7 and p.top_k == 1 and p.temperature == 0.0


def test_interpolation_monotonic():
    last_depth = 0
    for elo in range(400, 2401, 100):
        p = params_for_elo(elo)
        assert p.max_depth >= last_depth
        last_depth = p.max_depth


def test_select_argmax_top_k_one():
    moves = [(FakeMove("a"), 100), (FakeMove("b"), 50)]
    p = params_for_elo(2400)
    assert select_move(moves, p, random.Random(1)).name == "a"


def test_select_distribution_low_elo():
    """At low ELO with high temp + top_k=8, selection should not always be argmax."""
    moves = [(FakeMove(c), s) for c, s in zip("abcdefgh", [100, 95, 90, 80, 70, 60, 50, 40])]
    p = params_for_elo(400)
    rng = random.Random(42)
    picks = set()
    for _ in range(50):
        picks.add(select_move(moves, p, rng).name)
    assert len(picks) > 1, "expected diverse picks at low elo"


def test_blunder_excludes_disasters():
    """Blunder picks must avoid moves losing >300cp vs best."""
    moves = [(FakeMove("a"), 100), (FakeMove("b"), 90), (FakeMove("c"), -500)]
    p = StrengthParams(max_depth=1, time_ms=50, top_k=3, temperature=2.0, blunder_prob=1.0)
    rng = random.Random(0)
    seen = set()
    for _ in range(100):
        seen.add(select_move(moves, p, rng).name)
    assert "c" not in seen
