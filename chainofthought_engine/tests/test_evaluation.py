"""Stage 6: static evaluation sanity tests.

The evaluator returns a centipawn score from the SIDE TO MOVE's
perspective. To make positions easier to reason about, every test
sets up so that it is White to move; the side-to-move score then
equals the white-perspective score.

Each test isolates one term as much as possible by holding the rest
of the position symmetrical or empty. Where a term cannot be tested
in pure isolation (because a legal chess position requires both
kings and the king PST swamps small differences), we use roughly
mirror-image positions and assert the SIGN of the score, not exact
values.
"""

from __future__ import annotations

import pytest

from chainofthought_engine.core import Board
from chainofthought_engine.search import (
    DEFAULT_WEIGHTS,
    MATE_SCORE,
    Weights,
    evaluate,
)
from chainofthought_engine.search.evaluation import (
    KNIGHT_PST,
    PAWN_PST,
    _material_term,
    _pst_term,
    _mobility_term,
    _king_safety_term,
    _pawn_structure_term,
    _center_control_term,
)


# ---------------------------------------------------------------------------
# game-end short-circuits
# ---------------------------------------------------------------------------


class TestEvaluationGameEnd:
    def test_checkmate_returns_negative_mate_score(self):
        # Fool's mate: white is to move and is checkmated.
        b = Board.from_fen(
            "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        )
        assert evaluate(b) == -MATE_SCORE

    def test_stalemate_is_zero(self):
        # Black to move; no legal moves; not in check.
        b = Board.from_fen("7k/8/5KQ1/8/8/8/8/8 b - - 0 1")
        assert evaluate(b) == 0

    def test_insufficient_material_is_zero(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/3BK3 w - - 0 1")
        assert evaluate(b) == 0


# ---------------------------------------------------------------------------
# material
# ---------------------------------------------------------------------------


class TestMaterialTerm:
    def test_starting_position_material_is_zero(self):
        b = Board.starting_position()
        assert _material_term(b, DEFAULT_WEIGHTS) == 0

    def test_white_up_a_queen(self):
        # White has an extra queen on d1; otherwise mirrored kings only.
        b = Board.from_fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        assert _material_term(b, DEFAULT_WEIGHTS) == DEFAULT_WEIGHTS.queen_value

    def test_black_up_a_knight(self):
        b = Board.from_fen("4k3/3n4/8/8/8/8/8/4K3 w - - 0 1")
        assert _material_term(b, DEFAULT_WEIGHTS) == -DEFAULT_WEIGHTS.knight_value

    def test_full_evaluate_prefers_side_with_extra_queen(self):
        b = Board.from_fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        # Side to move (white) is way better.
        assert evaluate(b) > 800

    def test_full_evaluate_negates_when_black_to_move(self):
        # Same material edge for white, but it's black to move now ->
        # eval (from black's POV) should be very negative.
        b = Board.from_fen("4k3/8/8/8/8/8/8/3QK3 b - - 0 1")
        assert evaluate(b) < -800


# ---------------------------------------------------------------------------
# piece-square tables
# ---------------------------------------------------------------------------


class TestPSTTerm:
    def test_centralized_knight_better_than_corner_knight(self):
        # Compare via the PST term directly, because K+N vs K is
        # insufficient material and ``evaluate`` short-circuits to 0
        # in both cases. Position-symmetric: same king squares, same
        # extra knight, just placed differently.
        center = Board.from_fen("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
        corner = Board.from_fen("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
        assert _pst_term(center, DEFAULT_WEIGHTS) > _pst_term(
            corner, DEFAULT_WEIGHTS
        )

    def test_advanced_pawn_better_than_back_pawn(self):
        # White pawn on a7 vs white pawn on a2; PST should favour a7.
        advanced = Board.from_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        back = Board.from_fen("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")
        assert _pst_term(advanced, DEFAULT_WEIGHTS) > _pst_term(
            back, DEFAULT_WEIGHTS
        )

    def test_pst_is_symmetric_under_color_flip(self):
        # The PST term should be sign-symmetric for mirror-image
        # positions. d4 (sq 27) mirrors to d5 (sq 35) via ``sq ^ 56``.
        white_knight_d4 = Board.from_fen("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
        black_knight_d5 = Board.from_fen("4k3/8/8/3n4/8/8/8/4K3 w - - 0 1")
        assert _pst_term(white_knight_d4, DEFAULT_WEIGHTS) == -_pst_term(
            black_knight_d5, DEFAULT_WEIGHTS
        )

    def test_full_eval_prefers_centralized_knight(self):
        # Same idea as the PST-only test, but using full ``evaluate``.
        # We add a pawn to both sides so K+N+P vs K+P is NOT
        # insufficient material; the pawn placement is identical, so
        # the only differentiator is the knight's PST + mobility.
        center = Board.from_fen("4k3/p7/8/8/3N4/8/P7/4K3 w - - 0 1")
        corner = Board.from_fen("4k3/p7/8/8/8/8/P7/N3K3 w - - 0 1")
        assert evaluate(center) > evaluate(corner)

    def test_knight_pst_internal_consistency(self):
        # Sanity: the knight PST has a clear central peak. d4 (sq 27)
        # should beat a1 (sq 0) by a wide margin.
        assert KNIGHT_PST[27] > KNIGHT_PST[0] + 50

    def test_pawn_pst_promotes_advancement(self):
        # 7th-rank pawn (sq a7=48) should beat 2nd-rank pawn (sq a2=8).
        assert PAWN_PST[48] > PAWN_PST[8]


# ---------------------------------------------------------------------------
# mobility
# ---------------------------------------------------------------------------


class TestMobilityTerm:
    def test_starting_position_mobility_is_zero(self):
        # Mirror-image starting position: equal mobility for both sides.
        b = Board.starting_position()
        assert _mobility_term(b, DEFAULT_WEIGHTS) == 0

    def test_extra_piece_increases_mobility(self):
        # Same kings, but white has an extra knight on d4 -> white has
        # more pseudo-legal moves than black.
        with_knight = Board.from_fen("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
        kings_only = Board.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        assert _mobility_term(with_knight, DEFAULT_WEIGHTS) > _mobility_term(
            kings_only, DEFAULT_WEIGHTS
        )

    def test_mobility_uses_weight(self):
        b = Board.from_fen("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
        small = Weights(mobility_per_move=1)
        large = Weights(mobility_per_move=10)
        # Same sign; magnitude scales with the weight.
        s_small = _mobility_term(b, small)
        s_large = _mobility_term(b, large)
        assert s_large == 10 * s_small


# ---------------------------------------------------------------------------
# king safety
# ---------------------------------------------------------------------------


class TestKingSafetyTerm:
    def test_castled_king_with_pawn_shield_better_than_exposed(self):
        # Both sides have just kings + 3 pawns. White king is "castled"
        # on g1 with shield on f2/g2/h2; black king is in the centre on
        # e5 with the pawns parked on the back rank (no shield).
        # White's king-safety contribution should be HIGHER than black's,
        # i.e. the white-perspective term is positive.
        castled_white = Board.from_fen(
            "8/8/8/4k3/8/8/PPP2PPP/3R2K1 w - - 0 1"
        )
        # Sanity: shield + corner king -> positive for white from
        # the white-king-only contribution; the black king on e5 has
        # no shield AND sits in the open. Net white-perspective term
        # should be positive.
        score = _king_safety_term(castled_white, DEFAULT_WEIGHTS)
        assert score > 0

    def test_king_zone_under_attack_is_penalised(self):
        # Two near-mirror positions; in one of them a black rook on
        # h-file is breathing down the white king's neck (attacks
        # squares in the king zone).
        safe = Board.from_fen("4k3/8/8/8/8/8/PPPPPPPP/4K3 w - - 0 1")
        attacked = Board.from_fen("4k3/8/8/8/8/8/PPPPPPPP/4K2r w - - 0 1")
        # White king on e1; black rook on h1 attacks f1, g1, h1
        # (king-zone squares for the e1 king).
        assert _king_safety_term(attacked, DEFAULT_WEIGHTS) < _king_safety_term(
            safe, DEFAULT_WEIGHTS
        )

    def test_open_file_in_front_of_king_is_penalised(self):
        # White king on e1 with NO pawn on e-file vs same setup with
        # a pawn on e2.
        open_file = Board.from_fen("4k3/8/8/8/8/8/PPPP1PPP/4K3 w - - 0 1")
        closed_file = Board.from_fen("4k3/8/8/8/8/8/PPPPPPPP/4K3 w - - 0 1")
        assert _king_safety_term(
            open_file, DEFAULT_WEIGHTS
        ) < _king_safety_term(closed_file, DEFAULT_WEIGHTS)


# ---------------------------------------------------------------------------
# pawn structure
# ---------------------------------------------------------------------------


class TestPawnStructureTerm:
    def test_doubled_pawns_penalised(self):
        # White doubled on the e-file (e2 and e3) vs no doubled.
        doubled = Board.from_fen("4k3/8/8/8/8/4P3/4P3/4K3 w - - 0 1")
        single = Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        # Doubled gives two pawns total = +200 material; single = +100.
        # The pawn-structure term alone should still penalise doubled.
        assert _pawn_structure_term(
            doubled, DEFAULT_WEIGHTS
        ) < _pawn_structure_term(single, DEFAULT_WEIGHTS)

    def test_isolated_pawn_penalised(self):
        # Single pawn on a2 has no friendly neighbours -> isolated.
        # With pawns on a2 AND b2, neither is isolated.
        isolated = Board.from_fen("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")
        connected = Board.from_fen("4k3/8/8/8/8/8/PP6/4K3 w - - 0 1")
        # Both compared at the structure-term level (so material doesn't
        # dominate the comparison).
        assert _pawn_structure_term(
            isolated, DEFAULT_WEIGHTS
        ) < _pawn_structure_term(connected, DEFAULT_WEIGHTS)

    def test_passed_pawn_bonus(self):
        # White pawn on a5 with no enemy pawn ahead on the a/b files:
        # passed pawn. Compare to a position where a black pawn on
        # b6 blocks the passer.
        passed = Board.from_fen("4k3/8/8/P7/8/8/8/4K3 w - - 0 1")
        blocked = Board.from_fen("4k3/8/1p6/P7/8/8/8/4K3 w - - 0 1")
        a = _pawn_structure_term(passed, DEFAULT_WEIGHTS)
        b = _pawn_structure_term(blocked, DEFAULT_WEIGHTS)
        # `passed` includes the passed-pawn bonus; `blocked` doesn't.
        # `blocked` ALSO has an isolated black b-pawn (penalty for
        # black = bonus for white from white's perspective), so the
        # pure-passed-pawn comparison would be muddied. Compare the
        # passed-pawn bonus contribution directly:
        assert a > 0
        assert (a - b) >= DEFAULT_WEIGHTS.passed_pawn - abs(
            DEFAULT_WEIGHTS.isolated_pawn
        )


# ---------------------------------------------------------------------------
# center control
# ---------------------------------------------------------------------------


class TestCenterControlTerm:
    def test_central_pawn_attackers_beat_no_attackers(self):
        # White pawns on d4 and e4 attack c5/d5/e5/f5 (covers d5, e5).
        # Black has no central attackers.
        white_center = Board.from_fen("4k3/8/8/8/3PP3/8/8/4K3 w - - 0 1")
        empty = Board.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        assert _center_control_term(
            white_center, DEFAULT_WEIGHTS
        ) > _center_control_term(empty, DEFAULT_WEIGHTS)

    def test_symmetric_central_attacks_cancel(self):
        # White pawns d4/e4 attack d5/e5; black pawns d5/e5 attack
        # d4/e4 in return -- not exactly mirror because pawns block
        # their own forward movement, but the center attack term
        # counts attacks only, and by construction both sides attack
        # all four central squares (each side attacks the two it
        # doesn't occupy and... actually: d4 pawn attacks c5/e5;
        # e4 pawn attacks d5/f5; d5 pawn attacks c4/e4; e5 pawn
        # attacks d4/f4). So white attacks {c5, d5, e5, f5} and
        # black attacks {c4, d4, e4, f4}. Among CENTER_SQUARES
        # {d4, e4, d5, e5}, white attacks d5 and e5; black attacks
        # d4 and e4. Symmetric -> cancels.
        b = Board.from_fen("4k3/8/8/3pp3/3PP3/8/8/4K3 w - - 0 1")
        assert _center_control_term(b, DEFAULT_WEIGHTS) == 0


# ---------------------------------------------------------------------------
# tempo + total evaluation
# ---------------------------------------------------------------------------


class TestEvaluateTotal:
    def test_starting_position_eval_is_small(self):
        # Symmetric position: only the tempo term should contribute.
        b = Board.starting_position()
        assert evaluate(b) == DEFAULT_WEIGHTS.tempo

    def test_color_symmetry(self):
        # Mirror-image positions should give equal scores from the
        # side-to-move perspective.
        white_to_move = Board.from_fen(
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        )
        # Construct a black-mirror: the same shape with colors swapped
        # and ranks flipped, with white to move.
        black_to_move_mirror = Board.from_fen(
            "rnbqkbnr/pppp1ppp/8/4p3/8/8/PPPPPPPP/RNBQKBNR w KQkq e6 0 1"
        )
        # Both are "side that just played e-pawn two squares is now
        # waiting; opponent to move". By symmetry of the eval terms,
        # the score from each side's POV should be equal.
        assert evaluate(white_to_move) == evaluate(black_to_move_mirror)

    def test_obviously_better_winning_endgame(self):
        # K + Q vs K with white queen far from blunder: white winning.
        b = Board.from_fen("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1")
        # Queen value (~900) plus PST bonuses; should be a huge plus.
        assert evaluate(b) > 800

    def test_obviously_better_losing_position(self):
        # Same setup but it's black to move and white has the queen.
        # Black is losing, so eval (from black's POV) is very negative.
        b = Board.from_fen("4k3/8/8/8/8/8/4Q3/4K3 b - - 0 1")
        assert evaluate(b) < -800

    def test_custom_weights_change_score(self):
        # Doubling material weights should roughly double the material
        # contribution. We don't assert exact equality (PST/mobility/
        # king-safety/etc. depend on counts not values), only that the
        # magnitude grows.
        b = Board.from_fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        s1 = evaluate(b, DEFAULT_WEIGHTS)
        s2 = evaluate(
            b,
            Weights(
                pawn_value=200,
                knight_value=640,
                bishop_value=660,
                rook_value=1000,
                queen_value=1800,
            ),
        )
        assert s2 > s1

    def test_weights_dataclass_is_frozen(self):
        # Tunability via construction; mutation must be rejected so
        # callers can safely share a singleton.
        with pytest.raises(Exception):
            DEFAULT_WEIGHTS.pawn_value = 1234  # type: ignore[misc]

    def test_evaluate_is_deterministic(self):
        b = Board.from_fen(
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        )
        a = evaluate(b)
        for _ in range(5):
            assert evaluate(b) == a
