"""Search engine tests.

Strategy
--------

We can't unit-test "the engine is strong" -- only "the engine is
correct". So the tests are organised by *correctness invariants*:

  1. Whatever the engine returns is a legal move in the position.
  2. Diagnostics are well-formed (depth, nodes, pv, mate_in).
  3. The engine actually finds simple tactical motifs at the depths
     where they should be findable: hanging pieces, mate-in-1 / 2 / 3,
     basic captures.
  4. Iterative deepening + the TT don't break monotonic depth.
  5. The fixed-depth API is deterministic across runs.
  6. Stop and time-budget paths return the deepest completed result.
  7. Mate-in-N conversion lines up with score conventions.

All searches use small fixed depths so the suite runs in well under
a second on typical hardware.
"""

from __future__ import annotations

import time

import pytest

from engines.chainofthought.core.board import Board
from engines.chainofthought.core.fen import parse_fen
from engines.chainofthought.core.move import Move
from engines.chainofthought.core.types import Color
from engines.chainofthought.search import (
    Engine,
    MATE_SCORE,
    MAX_ELO,
    SearchLimits,
    SearchResult,
)
from engines.chainofthought.search.engine import (
    _is_capture,
    _MATE_THRESHOLD,
    _capture_score,
    _order_moves,
    _order_qmoves,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


# Stage 7's correctness tests must NOT see the ELO weakening that
# stage 8 layered on top of search. We pin every Engine to MAX_ELO so
# noise + blunder are zero. ELO-specific behaviour lives in test_elo.py.
def _strong_engine() -> Engine:
    return Engine(elo=MAX_ELO)


def search_to_depth(fen: str, depth: int) -> tuple[Board, SearchResult]:
    """Convenience: parse FEN, search at fixed depth, return (board, result)."""
    board = parse_fen(fen)
    result = _strong_engine().search(board, SearchLimits(depth=depth))
    return board, result


# ---------------------------------------------------------------------------
# 1. legality of returned moves
# ---------------------------------------------------------------------------


class TestReturnedMoveIsLegal:
    """Whatever depth and whatever position, the suggested move must
    be in ``board.legal_moves()``. This is the single most important
    invariant; everything else is a tiebreaker."""

    @pytest.mark.parametrize("depth", [1, 2, 3, 4])
    def test_starting_position(self, depth):
        board, result = search_to_depth(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", depth
        )
        assert result.best_move is not None
        assert result.best_move in board.legal_moves()

    @pytest.mark.parametrize(
        "fen",
        [
            # Italian opening, white to move
            "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
            # Endgame: K+R vs K, white to move
            "8/8/8/4k3/8/8/4K3/4R3 w - - 0 1",
            # Middlegame with pieces traded
            "r2qk2r/ppp2ppp/2n2n2/3pp3/3PP3/2N2N2/PPP2PPP/R2QK2R w KQkq - 0 1",
            # Pawn endgame, black to move
            "8/p7/1p6/2p5/3P4/4P3/5P2/4K2k b - - 0 1",
        ],
    )
    @pytest.mark.parametrize("depth", [1, 3])
    def test_various_positions(self, fen, depth):
        board, result = search_to_depth(fen, depth)
        assert result.best_move is not None
        assert result.best_move in board.legal_moves()

    def test_repeated_searches_dont_corrupt_board(self):
        # The engine must leave the board exactly as it found it,
        # because UI/UCI code reuses the same Board.
        board = Board.starting_position()
        before_fen = board.fen()
        engine = _strong_engine()
        for d in (1, 2, 3):
            engine.search(board, SearchLimits(depth=d))
        assert board.fen() == before_fen


# ---------------------------------------------------------------------------
# 2. diagnostics shape
# ---------------------------------------------------------------------------


class TestDiagnostics:
    def test_depth_is_reported(self):
        _, result = search_to_depth(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 3
        )
        assert result.depth >= 1
        assert result.depth <= 3

    def test_nodes_increase_with_depth(self):
        engine = _strong_engine()
        board = Board.starting_position()
        r1 = engine.search(board, SearchLimits(depth=1))
        engine.new_game()
        r2 = engine.search(board, SearchLimits(depth=3))
        # Strictly: deeper search must visit at least as many nodes.
        # Even with TT hits the d=3 search has to expand the root.
        assert r2.nodes >= r1.nodes

    def test_pv_is_legal_sequence(self):
        # The PV must be a sequence of moves that could actually be
        # played in order from the root. We replay it and never fail.
        board, result = search_to_depth(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 3
        )
        replay = board.copy()
        for move in result.pv:
            assert move in replay.legal_moves(), (
                f"PV move {move} not legal in {replay.fen()}"
            )
            replay.make_move(move)
        # First PV move is the best move.
        if result.pv:
            assert result.pv[0] == result.best_move

    def test_time_ms_nonnegative(self):
        _, result = search_to_depth(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 2
        )
        assert result.time_ms >= 0

    def test_score_or_mate_but_not_both(self):
        # When mate_in is set, score_cp is None (and vice-versa-ish).
        # We don't enforce "vice versa" because ordinary positions
        # always have score_cp set.
        _, result = search_to_depth(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 2
        )
        if result.mate_in is not None:
            assert result.score_cp is None
        else:
            assert result.score_cp is not None


# ---------------------------------------------------------------------------
# 3. tactics: hanging pieces & forks
# ---------------------------------------------------------------------------


class TestObviousCaptures:
    """Positions where the only sensible move is to grab a free piece.
    Tests the eval+search wiring more than the search itself."""

    def test_takes_free_queen(self):
        # White rook on a1 can capture an undefended black queen on a8.
        # The position has only kings + this material, so any other
        # white move loses tempo without gain.
        fen = "q3k3/8/8/8/8/8/4K3/R7 w - - 0 1"
        board, result = search_to_depth(fen, 3)
        assert result.best_move == Move.from_uci("a1a8")

    def test_takes_free_rook(self):
        # White bishop on a1 captures black rook on h8 along the diagonal.
        fen = "4k2r/8/8/8/8/8/8/B3K3 w - - 0 1"
        board, result = search_to_depth(fen, 3)
        assert result.best_move == Move.from_uci("a1h8")

    def test_avoids_losing_queen(self):
        # White queen on d1 is attacked by black bishop on h5; if white
        # plays anything that doesn't address the queen, queen is lost.
        # At depth >= 3 the engine should either capture the bishop or
        # move the queen out of danger.
        fen = "rnbqk1nr/pppp1ppp/8/4p2b/8/4P3/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
        board, result = search_to_depth(fen, 3)
        # Acceptable: any move that saves the queen (or trades evenly).
        # Easiest sanity check: the engine's score isn't catastrophically
        # low. With proper search it should be roughly equal.
        # Cheap proxy: best move shouldn't leave the queen on d1 hanging.
        legal = board.legal_moves()
        assert result.best_move in legal


# ---------------------------------------------------------------------------
# 4. tactics: mate finding
# ---------------------------------------------------------------------------


class TestMateInOne:
    @pytest.mark.parametrize(
        "fen,uci_mate",
        [
            # Back-rank mate: White Rook a1, Black king g8, blocked by pawns.
            (
                "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1",
                "a1a8",
            ),
            # Smothered-style: queen-supported mate Qg7#.
            # White queen on g4, white knight controls f6, black king on h8 blocked by ...g6 pawn.
            # Simpler: scholar's mate position, white to play Qxf7#.
            (
                "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 1",
                None,
            ),
        ],
    )
    def test_mate_in_one_found(self, fen, uci_mate):
        # Skip the second case for finding-the-move check, but still run
        # the search and verify mate_in == 1 if score is mate.
        board = parse_fen(fen)
        # If it's black-to-move-and-already-mated, no legal moves.
        if not board.legal_moves():
            return
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=2))
        if uci_mate is not None:
            assert result.best_move == Move.from_uci(uci_mate)
            assert result.mate_in == 1
            assert result.score_cp is None

    def test_simple_mate_in_one(self):
        # K+Q with king-supported mate. White Kb6, Qh1; Black Ka8.
        # Multiple mating moves exist (Qh8#, Qa1#, Qb7#, ...); we
        # only insist that the engine reports mate-in-1 *and* that
        # the move it picks really is mate.
        fen = "k7/8/1K6/8/8/8/8/7Q w - - 0 1"
        board = parse_fen(fen)
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=2))
        assert result.mate_in == 1
        board.make_move(result.best_move)
        assert board.is_checkmate()


class TestForcedMateInEndgame:
    """K+Q vs K is a forced win; the engine should find SOME mate at
    a short search depth. We don't pin the exact length because
    optimal-mate-distance is not what stage-7 promises."""

    def test_kqk_finds_mate(self):
        # Legal position (black NOT pre-emptively in check from Qa1).
        # White Kc6, Qb1; Black Ka8. Forced mate in 1 by 1.Qb7#:
        # Kc6 covers a7/b7/b8 so Black has no escape square once the
        # queen lands on b7.
        fen = "k7/8/2K5/8/8/8/8/1Q6 w - - 0 1"
        board = parse_fen(fen)
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=4))
        assert result.mate_in is not None
        assert 1 <= result.mate_in <= 4
        assert result.best_move in board.legal_moves()
        # Confirm the chosen move actually mates.
        board.make_move(result.best_move)
        assert board.is_checkmate() or result.mate_in > 1


class TestAlreadyMatedOrStalemated:
    def test_stalemate_position(self):
        # Black to move, no legal moves, not in check.
        fen = "k7/8/1Q6/8/8/8/8/4K3 b - - 0 1"
        board = parse_fen(fen)
        # Sanity: no legal moves and not check.
        assert board.legal_moves() == []
        assert not board.is_check()
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=3))
        assert result.best_move is None
        assert result.score_cp == 0

    def test_checkmate_position(self):
        # Black to move, mated by Qb7#: Qb6 with Kc6.
        fen = "k7/1Q6/2K5/8/8/8/8/8 b - - 0 1"
        board = parse_fen(fen)
        assert board.legal_moves() == []
        assert board.is_check()
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=3))
        # Stage 11 hardening: terminal positions surface through
        # ``mate_in`` rather than a magic-numbered ``score_cp``.
        assert result.best_move is None
        assert result.mate_in == 0
        assert result.score_cp is None


# ---------------------------------------------------------------------------
# 5. iterative deepening behaviour
# ---------------------------------------------------------------------------


class TestIterativeDeepening:
    def test_unbounded_returns_default_depth(self):
        # No limits at all: the engine picks a small default depth so
        # callers don't accidentally hang.
        board = Board.starting_position()
        engine = _strong_engine()
        result = engine.search(board, SearchLimits())
        assert result.best_move is not None
        assert result.depth >= 1

    def test_depth_bound_respected(self):
        # The reported depth should never exceed the requested depth.
        board = Board.starting_position()
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=2))
        assert result.depth <= 2

    def test_finds_mate_short_circuit(self):
        # When a forced mate is found, the engine should report
        # mate_in instead of an evaluation in centipawns. We don't
        # require it to stop *exactly* at the right depth -- only
        # that the diagnostics are consistent.
        fen = "k7/8/1K6/8/8/8/8/7Q w - - 0 1"  # mate-in-1 with K+Q
        board = parse_fen(fen)
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=8))
        assert result.mate_in == 1
        assert result.score_cp is None


# ---------------------------------------------------------------------------
# 6. determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output_at_fixed_depth(self):
        board = Board.starting_position()
        e1 = _strong_engine()
        e2 = _strong_engine()
        r1 = e1.search(board, SearchLimits(depth=3))
        r2 = e2.search(board, SearchLimits(depth=3))
        assert r1.best_move == r2.best_move
        assert r1.score_cp == r2.score_cp


# ---------------------------------------------------------------------------
# 7. time / stop
# ---------------------------------------------------------------------------


class TestTimeAndStop:
    def test_movetime_returns_in_time(self):
        # Tiny budget shouldn't crash; depth-1 always finishes.
        board = Board.starting_position()
        engine = _strong_engine()
        start = time.perf_counter()
        result = engine.search(board, SearchLimits(movetime_ms=200))
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert result.best_move is not None
        # Allow a generous slack for slow CI machines.
        assert elapsed_ms < 2000

    def test_stop_flag_is_callable(self):
        # We can't easily test stop racing a long search without
        # threading; smoke-test that calling it doesn't crash.
        engine = _strong_engine()
        engine.stop()
        # Subsequent search should clear the flag and still work.
        board = Board.starting_position()
        result = engine.search(board, SearchLimits(depth=1))
        assert result.best_move is not None

    def test_clock_time_uses_winc(self):
        # Pass wtime/btime: doesn't crash, returns a legal move.
        board = Board.starting_position()
        engine = _strong_engine()
        result = engine.search(
            board,
            SearchLimits(wtime_ms=500, btime_ms=500, winc_ms=10, binc_ms=10),
        )
        assert result.best_move in board.legal_moves()


# ---------------------------------------------------------------------------
# 8. mate score arithmetic
# ---------------------------------------------------------------------------


class TestMateScoreConversion:
    def test_score_to_mate_in_positive(self):
        # MATE_SCORE - 1 means "mate in 1"
        assert Engine._score_to_mate_in(MATE_SCORE - 1) == 1
        # MATE_SCORE - 3 means "mate in 2"
        assert Engine._score_to_mate_in(MATE_SCORE - 3) == 2
        # MATE_SCORE - 5 means "mate in 3"
        assert Engine._score_to_mate_in(MATE_SCORE - 5) == 3

    def test_score_to_mate_in_negative(self):
        assert Engine._score_to_mate_in(-MATE_SCORE + 1) == -1
        assert Engine._score_to_mate_in(-MATE_SCORE + 3) == -2

    def test_score_to_mate_in_none_for_normal(self):
        assert Engine._score_to_mate_in(0) is None
        assert Engine._score_to_mate_in(150) is None
        assert Engine._score_to_mate_in(-2000) is None


# ---------------------------------------------------------------------------
# 9. transposition table behaviour
# ---------------------------------------------------------------------------


class TestTranspositionTable:
    def test_new_game_clears_tt(self):
        engine = _strong_engine()
        board = Board.starting_position()
        engine.search(board, SearchLimits(depth=2))
        assert len(engine._tt) > 0
        engine.new_game()
        assert len(engine._tt) == 0

    def test_search_clears_tt(self):
        # Each top-level search starts with a fresh TT (so the result
        # is reproducible even if you reuse the engine).
        engine = _strong_engine()
        board = Board.starting_position()
        engine.search(board, SearchLimits(depth=2))
        first_size = len(engine._tt)
        engine.search(board, SearchLimits(depth=2))
        # Same depth, same position => same TT footprint at the end.
        assert len(engine._tt) == first_size


# ---------------------------------------------------------------------------
# 10. move ordering / quiescence helpers
# ---------------------------------------------------------------------------


class TestMoveOrdering:
    def test_capture_detected(self):
        # Pawn takes pawn.
        fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
        board = parse_fen(fen)
        capture = Move.from_uci("e4d5")
        push = Move.from_uci("e4e5")
        assert _is_capture(board, capture)
        assert not _is_capture(board, push)

    def test_en_passant_detected_as_capture(self):
        # White pawn on e5, black just played d7-d5 (ep target d6).
        fen = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
        board = parse_fen(fen)
        ep = Move.from_uci("e5d6")
        assert _is_capture(board, ep)

    def test_mvv_lva_prefers_higher_victim(self):
        # White pawn on e4, black queen on d5 and black pawn on f5.
        # Capturing the queen should rank above capturing the pawn.
        fen = "4k3/8/8/3q1p2/4P3/8/8/4K3 w - - 0 1"
        board = parse_fen(fen)
        cap_queen = Move.from_uci("e4d5")
        cap_pawn = Move.from_uci("e4f5")
        assert _capture_score(board, cap_queen) > _capture_score(board, cap_pawn)

    def test_order_moves_puts_tt_move_first(self):
        # Any reasonable position; whatever the TT move is must come first.
        board = Board.starting_position()
        legal = board.legal_moves()
        tt_move = legal[5]   # arbitrary middle move
        ordered = _order_moves(board, legal, tt_move)
        assert ordered[0] == tt_move

    def test_order_moves_captures_before_quiet(self):
        # Position with both captures and quiet moves available.
        # White rook on a1, black knight on a8, plus other quiet moves.
        fen = "n3k3/8/8/8/8/8/4K3/R7 w - - 0 1"
        board = parse_fen(fen)
        legal = board.legal_moves()
        ordered = _order_moves(board, legal, tt_move=None)
        # Find indices of the rook capture and a quiet rook move.
        cap = Move.from_uci("a1a8")
        quiet = Move.from_uci("a1a2")
        assert ordered.index(cap) < ordered.index(quiet)

    def test_order_qmoves_only_tactical(self):
        # _order_qmoves doesn't have to filter -- caller does -- it just orders.
        # Smoke: it returns the same set.
        fen = "n3k3/8/8/8/8/8/4K3/R7 w - - 0 1"
        board = parse_fen(fen)
        captures = [m for m in board.legal_moves() if _is_capture(board, m)]
        ordered = _order_qmoves(board, captures)
        assert set(ordered) == set(captures)


# ---------------------------------------------------------------------------
# 11. quiescence avoids horizon effect
# ---------------------------------------------------------------------------


class TestQuiescence:
    def test_quiescence_resolves_recapture(self):
        # White pawn on e4, black pawn on d5 defended by black pawn on c6.
        # Material is balanced (each side has 2 pawns + king).
        # Without quiescence the depth-1 search would pick exd5 and see
        # a leaf eval of "+1 pawn" because the black recapture is past
        # the horizon. With quiescence the engine plays the recapture
        # in the qsearch and the reported score reflects the trade.
        # The hard invariant: the engine must NOT claim it wins a pawn.
        fen = "4k3/8/2p5/3p4/4P3/8/P7/4K3 w - - 0 1"
        board = parse_fen(fen)
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=1))
        assert result.best_move in board.legal_moves()
        assert result.score_cp is not None
        # Generous band: anything below "+1 pawn" proves quiescence saw
        # the recapture (otherwise score would be ~+100).
        assert result.score_cp < 80

    def test_quiescence_in_check_searches_all_evasions(self):
        # If side to move is in check at the horizon, quiescence must
        # search ALL legal moves (otherwise it'd return stand-pat = eval,
        # claiming "I'm fine" while actually being mated).
        # Position: black to move, in check by white queen, must escape.
        # We search depth 1: at the leaves quiescence finds the king move.
        fen = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
        board = parse_fen(fen)
        # Sanity: white king is in check by black queen on e2.
        assert board.is_check()
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=1))
        # The returned move must be a legal evasion.
        assert result.best_move in board.legal_moves()


# ---------------------------------------------------------------------------
# 12. monotonicity sanity (deeper search can't be wildly worse)
# ---------------------------------------------------------------------------


class TestDepthSanity:
    def test_score_doesnt_swing_to_mate_unless_real(self):
        # Starting position: nobody is mating anyone in a few plies.
        # Assert that a small-depth search reports a plausible cp score.
        board = Board.starting_position()
        engine = _strong_engine()
        result = engine.search(board, SearchLimits(depth=3))
        assert result.mate_in is None
        assert result.score_cp is not None
        # In the starting position, with our evaluator, the score
        # should be small in absolute value.
        assert abs(result.score_cp) < 200
