"""ELO slider & strength scaling tests.

These tests cover two layers separately:

  1. **The pure mapping** (``config_from_elo``). Properties of the
     mapping itself: clamping, monotonicity, anchor values at the
     band boundaries, and the contract that ``MAX_ELO`` produces
     zero weakening (so the slider has a "play seriously" setting)
     while ``MIN_ELO`` produces strictly positive weakening (so the
     slider has a "weak" setting).

  2. **The wiring into :class:`Engine`.** That ``set_elo`` clamps,
     that the ELO config drives default depth/movetime, that
     explicit ``SearchLimits`` win over ELO defaults, that fixed
     seeds make weakening reproducible, that forced mate is never
     blundered, and that obvious tactics survive even at low ELO.

The cardinal invariant -- "the engine never returns an illegal
move regardless of ELO" -- gets its own parametrised test.
"""

from __future__ import annotations

import pytest

from chainofthought_engine.core.board import Board
from chainofthought_engine.core.fen import parse_fen
from chainofthought_engine.core.move import Move
from chainofthought_engine.search import (
    DEFAULT_ELO,
    Engine,
    EloConfig,
    MATE_SCORE,
    MAX_ELO,
    MIN_ELO,
    SearchLimits,
    config_from_elo,
)


# ---------------------------------------------------------------------------
# 1. mapping properties
# ---------------------------------------------------------------------------


class TestEloMappingShape:
    def test_returns_eloconfig(self):
        cfg = config_from_elo(1500)
        assert isinstance(cfg, EloConfig)

    def test_clamps_below_min(self):
        cfg = config_from_elo(MIN_ELO - 500)
        assert cfg.elo == MIN_ELO

    def test_clamps_above_max(self):
        cfg = config_from_elo(MAX_ELO + 500)
        assert cfg.elo == MAX_ELO

    def test_negative_elo_clamps(self):
        cfg = config_from_elo(-1000)
        assert cfg.elo == MIN_ELO

    def test_default_elo_is_in_range(self):
        assert MIN_ELO <= DEFAULT_ELO <= MAX_ELO


class TestEloMappingMonotonicity:
    """The cardinal user-facing guarantee: a stronger ELO must never
    play *worse* in any single dimension. We sweep the slider in
    100-point steps and check the four knobs.
    """

    @pytest.fixture
    def configs(self):
        return [config_from_elo(e) for e in range(MIN_ELO, MAX_ELO + 1, 100)]

    def test_max_depth_non_decreasing(self, configs):
        for a, b in zip(configs, configs[1:]):
            assert a.max_depth <= b.max_depth, (a.elo, b.elo)

    def test_movetime_non_decreasing(self, configs):
        for a, b in zip(configs, configs[1:]):
            assert a.movetime_ms <= b.movetime_ms, (a.elo, b.elo)

    def test_noise_non_increasing(self, configs):
        for a, b in zip(configs, configs[1:]):
            assert a.eval_noise_cp >= b.eval_noise_cp, (a.elo, b.elo)

    def test_blunder_non_increasing(self, configs):
        for a, b in zip(configs, configs[1:]):
            assert a.blunder_pct >= b.blunder_pct, (a.elo, b.elo)


class TestEloMappingAnchors:
    """Anchor values at slider extremes are part of the contract --
    the slider must have a 'no weakening' max and a 'visibly weak'
    min. These specific numbers are documented in elo.py and the
    README band table.
    """

    def test_max_elo_no_noise(self):
        cfg = config_from_elo(MAX_ELO)
        assert cfg.eval_noise_cp == 0
        assert cfg.blunder_pct == 0.0

    def test_max_elo_full_depth(self):
        cfg = config_from_elo(MAX_ELO)
        assert cfg.max_depth == 7

    def test_min_elo_has_weakening(self):
        cfg = config_from_elo(MIN_ELO)
        assert cfg.eval_noise_cp > 0
        assert cfg.blunder_pct > 0.0

    def test_min_elo_shallow_depth(self):
        cfg = config_from_elo(MIN_ELO)
        assert cfg.max_depth == 1

    @pytest.mark.parametrize(
        "elo,expected_depth",
        [
            (400, 1),
            (800, 2),
            (1200, 3),
            (1500, 4),
            (1800, 5),
            (2100, 6),
            (2400, 7),
        ],
    )
    def test_band_depths(self, elo, expected_depth):
        # Eyeball values for the README table. If you retune the
        # mapping, update both the table and these expectations.
        assert config_from_elo(elo).max_depth == expected_depth


# ---------------------------------------------------------------------------
# 2. Engine ELO API
# ---------------------------------------------------------------------------


class TestEngineEloAPI:
    def test_default_elo(self):
        assert Engine().elo == DEFAULT_ELO

    def test_construct_with_elo(self):
        assert Engine(elo=1800).elo == 1800

    def test_set_elo(self):
        e = Engine()
        e.set_elo(2000)
        assert e.elo == 2000

    def test_set_elo_clamps_high(self):
        e = Engine()
        e.set_elo(9999)
        assert e.elo == MAX_ELO

    def test_set_elo_clamps_low(self):
        e = Engine()
        e.set_elo(0)
        assert e.elo == MIN_ELO

    def test_construct_clamps(self):
        assert Engine(elo=10_000).elo == MAX_ELO
        assert Engine(elo=-100).elo == MIN_ELO

    def test_config_method(self):
        e = Engine(elo=2400)
        cfg = e.config()
        assert isinstance(cfg, EloConfig)
        assert cfg.elo == 2400

    def test_set_seed_replaces_rng(self):
        # Two engines, same seed => same first random draw.
        e1 = Engine(elo=400, seed=123)
        e2 = Engine(elo=400)
        e2.set_seed(123)
        assert e1._random.random() == e2._random.random()

    def test_new_game_resets_seed(self):
        e = Engine(elo=400, seed=7)
        before = e._random.random()
        e._random.random()  # consume one more
        e.new_game()
        after = e._random.random()
        assert before == after  # same seed => same first draw


# ---------------------------------------------------------------------------
# 3. limits interaction
# ---------------------------------------------------------------------------


class TestEloLimitsInteraction:
    """Caller's explicit limits override ELO defaults; otherwise the
    ELO config provides sensible defaults so callers that pass an
    empty SearchLimits still get a reasonable search.
    """

    def test_unbounded_uses_elo_max_depth(self):
        # Unbounded SearchLimits + low ELO => engine searches at most
        # cfg.max_depth (no runaway depth).
        engine = Engine(elo=400)  # max_depth = 1
        result = engine.search(Board.starting_position(), SearchLimits())
        assert result.depth == 1

    def test_unbounded_uses_elo_max_depth_high(self):
        engine = Engine(elo=MAX_ELO)  # max_depth = 7
        result = engine.search(
            Board.starting_position(), SearchLimits(movetime_ms=200)
        )
        # With a 200 ms budget we usually don't hit depth 7, but we
        # should NEVER exceed it because the ELO cap is respected
        # when no explicit depth was passed.
        assert 1 <= result.depth <= 7

    def test_explicit_depth_overrides_elo_cap(self):
        # User explicitly asks for depth 3 at low ELO; depth 3 is
        # honoured even though the ELO config caps default at 1.
        engine = Engine(elo=400)
        result = engine.search(
            Board.starting_position(), SearchLimits(depth=3)
        )
        assert result.depth == 3

    def test_explicit_movetime_overrides_elo_default(self):
        # ELO=2400 default movetime is 5s; we cap at 100ms explicitly.
        engine = Engine(elo=MAX_ELO)
        result = engine.search(
            Board.starting_position(), SearchLimits(movetime_ms=100)
        )
        assert result.best_move is not None
        # Allow generous slack for slow CI; the cap is "soft".
        assert result.time_ms < 1000


# ---------------------------------------------------------------------------
# 4. determinism under seeded weakening
# ---------------------------------------------------------------------------


class TestSeedDeterminism:
    """At MAX_ELO weakening is off and the search is deterministic
    by construction. At lower ELO the weakening RNG kicks in, so we
    verify (a) different engines with the same seed agree, and
    (b) different seeds can disagree."""

    def test_max_elo_is_deterministic_without_seed(self):
        # No noise + no blunder => RNG is never consulted, so seed
        # doesn't matter and two engines agree.
        b = Board.starting_position()
        r1 = Engine(elo=MAX_ELO).search(b, SearchLimits(depth=2))
        r2 = Engine(elo=MAX_ELO).search(b, SearchLimits(depth=2))
        assert r1.best_move == r2.best_move

    def test_low_elo_same_seed_same_move(self):
        b = Board.starting_position()
        r1 = Engine(elo=400, seed=42).search(b, SearchLimits(depth=2))
        r2 = Engine(elo=400, seed=42).search(b, SearchLimits(depth=2))
        assert r1.best_move == r2.best_move

    def test_low_elo_different_seeds_can_diverge(self):
        # NOT a guarantee of divergence (both seeds might happen to
        # pick the same move), but across many seeds at low ELO the
        # set of chosen moves should grow beyond a singleton.
        b = Board.starting_position()
        moves = set()
        for s in range(20):
            r = Engine(elo=400, seed=s).search(b, SearchLimits(depth=2))
            moves.add(r.best_move)
        assert len(moves) >= 2, (
            "Low-ELO engine should produce variety across seeds; "
            f"got only {moves}"
        )


# ---------------------------------------------------------------------------
# 5. weakening doesn't sabotage the engine
# ---------------------------------------------------------------------------


class TestEloDoesntBlunderMate:
    """The ELO weakening explicitly skips weakening when a forced
    mate is found. Even at MIN_ELO the engine plays the mating move
    every time."""

    def test_min_elo_finds_mate_in_one(self):
        # Same K+Q mate-in-1 used in stage 7's search tests.
        fen = "k7/8/1K6/8/8/8/8/7Q w - - 0 1"
        for seed in range(10):
            board = parse_fen(fen)
            engine = Engine(elo=MIN_ELO, seed=seed)
            # Force depth >= 2 so the engine actually sees the mate
            # (MIN_ELO's default cap is 1).
            result = engine.search(board, SearchLimits(depth=2))
            assert result.mate_in == 1, (
                f"seed {seed}: expected mate-in-1, got {result}"
            )
            board.make_move(result.best_move)
            assert board.is_checkmate(), f"seed {seed}: chosen move not mate"


class TestEloDoesntDropFreeMaterial:
    """A weak engine plays inaccurate moves but shouldn't drop a
    queen for nothing. With our noise cap (200 cp) and weighted
    blunder selection, capturing a free piece (worth ~900 cp) ranks
    so far above any alternative that the engine takes it most of
    the time even at MIN_ELO."""

    def test_low_elo_takes_free_queen_most_of_the_time(self):
        # Same 'free queen' position from stage 7.
        fen = "q3k3/8/8/8/8/8/4K3/R7 w - - 0 1"
        capture = Move.from_uci("a1a8")
        hits = 0
        for seed in range(20):
            board = parse_fen(fen)
            engine = Engine(elo=MIN_ELO, seed=seed)
            r = engine.search(board, SearchLimits(depth=2))
            if r.best_move == capture:
                hits += 1
        # The capture is weighted to win even when blunder fires.
        # 80% threshold over 20 seeds is comfortably above noise.
        assert hits >= 16, (
            f"MIN_ELO took the free queen only {hits}/20 times; "
            "weakening is too aggressive"
        )


# ---------------------------------------------------------------------------
# 6. legality is sacred
# ---------------------------------------------------------------------------


class TestEloAlwaysPlaysLegalMoves:
    @pytest.mark.parametrize("elo", [400, 800, 1200, 1500, 1800, 2100, 2400])
    def test_legal_at_every_elo(self, elo):
        # Mid-game position with many candidate moves.
        fen = (
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1"
        )
        for seed in range(5):
            board = parse_fen(fen)
            engine = Engine(elo=elo, seed=seed)
            result = engine.search(board, SearchLimits(depth=2))
            assert result.best_move is not None
            assert result.best_move in board.legal_moves(), (
                f"elo={elo} seed={seed} returned illegal move {result.best_move}"
            )


# ---------------------------------------------------------------------------
# 7. weakening reaches into the SearchResult
# ---------------------------------------------------------------------------


class TestSearchResultUnderWeakening:
    """When the engine blunders, the reported score_cp should reflect
    the move it actually plays (not the engine's true best). The PV
    should also start with the chosen move."""

    def test_pv_starts_with_chosen_move(self):
        # Mid-position with several reasonable moves.
        b = Board.starting_position()
        for seed in range(5):
            engine = Engine(elo=400, seed=seed)
            r = engine.search(b, SearchLimits(depth=2))
            if r.pv:
                assert r.pv[0] == r.best_move

    def test_score_present_for_normal_position(self):
        b = Board.starting_position()
        r = Engine(elo=MAX_ELO).search(b, SearchLimits(depth=2))
        assert r.score_cp is not None
        assert r.mate_in is None


# ---------------------------------------------------------------------------
# 8. mapping numeric values (lock-in for tuning regressions)
# ---------------------------------------------------------------------------


class TestMappingNumericLockIn:
    """If anyone retunes ``config_from_elo``, these values change.
    Failing here is a flag to update the README band table too."""

    def test_band_400(self):
        c = config_from_elo(400)
        assert c == EloConfig(
            elo=400, max_depth=1, movetime_ms=200,
            eval_noise_cp=200, blunder_pct=0.20,
        )

    def test_band_2400(self):
        c = config_from_elo(2400)
        assert c == EloConfig(
            elo=2400, max_depth=7, movetime_ms=5000,
            eval_noise_cp=0, blunder_pct=0.0,
        )

    def test_band_1500_default(self):
        c = config_from_elo(1500)
        # Linear interpolation: t = 1100/2000 = 0.55.
        # max_depth = 1 + round(6*0.55) = 1 + 3 = 4 (round half-even gives 3 for 3.3 -> 3, total 4)
        assert c.max_depth == 4
        # movetime_ms = 200 + round(4800*0.55) = 200 + 2640 = 2840
        assert c.movetime_ms == 2840
        # noise = round(200 * 0.45) = 90
        assert c.eval_noise_cp == 90
        # blunder = round(0.20 * 0.45, 4) = 0.09
        assert c.blunder_pct == 0.09
