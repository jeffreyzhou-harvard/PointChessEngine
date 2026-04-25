"""Cross-cutting hardening / fuzz-lite tests.

This file's job is to catch regressions in behaviour that no single
module owns:

  - The ``Engine.search`` / terminal-position contract (best_move
    is None, mate_in is 0 if mated, score_cp is 0 if stalemate).
  - The UCI loop surviving long position commands and pathological
    setoption / position sequences.
  - The browser-UI :class:`Session` surviving rapid state mutations
    (resign/new game/elo cycling).
  - End-to-end consistency: positions reached by different move
    orders share a position_key; FEN export survives long games.

Per-module unit tests (test_board, test_legality, test_uci, ...)
already cover their own surfaces. The point of *this* file is to
catch the cracks between them.
"""

from __future__ import annotations

import io
import threading

import pytest

from engines.chainofthought.core.board import Board
from engines.chainofthought.core.fen import parse_fen
from engines.chainofthought.core.game import GameState
from engines.chainofthought.core.move import Move
from engines.chainofthought.core.types import Color
from engines.chainofthought.search.elo import MAX_ELO, MIN_ELO
from engines.chainofthought.search.engine import Engine, SearchLimits
from engines.chainofthought.uci.protocol import UCIProtocol
from engines.chainofthought.ui.session import Session


# ---------------------------------------------------------------------------
# 1. Engine: terminal positions surface cleanly through SearchResult
# ---------------------------------------------------------------------------


class TestEngineTerminalContract:
    """The fix in stage 11 made terminal positions report ``mate_in``
    (or stalemate as ``score_cp == 0``) instead of leaking the
    internal ``-MATE_SCORE`` magic number. Lock that in."""

    def test_checkmate_reports_mate_in_zero(self):
        # Black to move, mated.
        board = parse_fen("k7/1Q6/2K5/8/8/8/8/8 b - - 0 1")
        result = Engine(elo=MAX_ELO).search(board, SearchLimits(depth=1))
        assert result.best_move is None
        assert result.mate_in == 0
        assert result.score_cp is None

    def test_stalemate_reports_zero_score_no_move(self):
        board = parse_fen("k7/8/1Q6/8/8/8/8/4K3 b - - 0 1")
        assert board.legal_moves() == []
        assert not board.is_check()
        result = Engine(elo=MAX_ELO).search(board, SearchLimits(depth=1))
        assert result.best_move is None
        assert result.score_cp == 0
        assert result.mate_in is None

    def test_terminal_search_does_not_clear_random_seed(self):
        """Searching a terminal position must not perturb the RNG."""
        engine = Engine(elo=MIN_ELO, seed=42)
        terminal = parse_fen("k7/1Q6/2K5/8/8/8/8/8 b - - 0 1")
        engine.search(terminal, SearchLimits(depth=1))
        # Now run a real search; with seed=42 it must match a fresh
        # engine on the same fresh seed (proving the terminal call
        # didn't consume randomness).
        live_pos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        a = engine.search(parse_fen(live_pos), SearchLimits(depth=2))
        b = Engine(elo=MIN_ELO, seed=42).search(
            parse_fen(live_pos), SearchLimits(depth=2)
        )
        assert a.best_move == b.best_move


# ---------------------------------------------------------------------------
# 2. UCI: pathological inputs don't crash the loop
# ---------------------------------------------------------------------------


def _new_proto() -> tuple[UCIProtocol, io.StringIO]:
    out = io.StringIO()
    return UCIProtocol(stdout=out), out


def _wait(proto: UCIProtocol, timeout: float = 5.0) -> None:
    """Block until any background search thread has returned."""
    if proto.is_searching():
        proto.wait_for_search()


class TestUCIRobustness:
    def test_long_position_moves_chain(self):
        """A 60-ply position string parses and applies cleanly."""
        proto, out = _new_proto()
        # Build a long but fully legal sequence using a known opening
        # / middlegame line. We use the engine to play both sides
        # against itself to guarantee legality without typing 60 SAN
        # moves.
        engine = Engine(elo=MAX_ELO, seed=0)
        board = Board.starting_position()
        moves: list[str] = []
        for _ in range(60):
            r = engine.search(board, SearchLimits(depth=1))
            if r.best_move is None:
                break
            moves.append(r.best_move.uci())
            board.make_move(r.best_move)
        cmd = "position startpos moves " + " ".join(moves)
        proto.handle(cmd)
        # Now run a 1-ply search from there and ensure we get a
        # bestmove (or the null-move terminal marker, which is also
        # acceptable -- the point is no crash).
        proto.handle("go depth 1")
        _wait(proto)
        assert "bestmove " in out.getvalue()

    def test_rapid_position_changes(self):
        """Three back-to-back 'position' commands must each replace
        state cleanly. No leakage from earlier positions."""
        proto, out = _new_proto()
        for fen in [
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "k7/1Q6/2K5/8/8/8/8/8 b - - 0 1",
        ]:
            proto.handle(f"position fen {fen}")
        proto.handle("go depth 1")
        _wait(proto)
        # The current position is the K+Q mating pos for black
        # (terminal). UCI emits the null move in that case.
        assert "bestmove 0000" in out.getvalue()

    def test_setoption_with_unknown_name_is_ignored(self):
        """Unknown options must be silently accepted (UCI spec)."""
        proto, _ = _new_proto()
        proto.handle("setoption name NotARealOption value 42")  # no raise

    def test_setoption_with_garbage_value(self):
        """A non-int value for an int option should produce
        ``info string`` (not crash, not silently set)."""
        proto, out = _new_proto()
        proto.handle("setoption name UCI_Elo value not_a_number")
        # Either ignored or info-stringed; what matters is no crash
        # AND the engine's elo wasn't corrupted.
        assert MIN_ELO <= proto.engine.elo <= MAX_ELO

    def test_unknown_command_is_silent(self):
        """Spec: ignore unknown commands, don't crash."""
        proto, out = _new_proto()
        proto.handle("xyzzy 1 2 3")
        # No bestmove/info-string-error required; just no exception.
        # We do allow info string for diagnostics, but it's optional.

    def test_isready_during_active_search(self):
        """``isready`` must return ``readyok`` immediately even with
        a search in flight (UCI spec)."""
        proto, out = _new_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        try:
            assert proto.is_searching()
            proto.handle("isready")
            assert "readyok" in out.getvalue()
        finally:
            proto.handle("stop")
            _wait(proto)


# ---------------------------------------------------------------------------
# 3. Session: rapid state mutations
# ---------------------------------------------------------------------------


class TestSessionResilience:
    def test_rapid_resign_and_new_game(self):
        """Cycling resign + new_game many times shouldn't accumulate
        any state."""
        s = Session(elo=1200, seed=0)
        for _ in range(10):
            s.play_user_move("e2e4")
            s.play_engine_move()
            s.resign()
            assert s.is_game_over()
            s.start_new_game()
            assert not s.is_game_over()
            assert s.state_dict()["history_uci"] == []

    def test_elo_cycling_mid_game(self):
        """Changing ELO while the game is ongoing must not corrupt
        state."""
        s = Session(elo=1500, seed=0)
        s.play_user_move("e2e4")
        for elo in (400, 2400, 800, 1700, 1500):
            s.set_elo(elo)
            assert s.elo == elo
            assert s.state_dict()["elo"] == elo

    def test_post_mate_play_rejected(self):
        """Once the game is mate, further play_user_move calls raise
        rather than silently no-op."""
        s = Session()
        # Fool's mate complete; white is mated.
        s._game = GameState.from_fen(
            "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        )
        assert s.is_game_over()
        with pytest.raises(ValueError):
            s.play_user_move("e1f2")  # any move at all

    def test_engine_move_after_resign_rejected(self):
        s = Session()
        s.resign()
        with pytest.raises(ValueError):
            s.play_engine_move()


# ---------------------------------------------------------------------------
# 4. Cross-system: position_key consistency via different move orders
# ---------------------------------------------------------------------------


class TestPositionKeyTransposition:
    """Two different move orders that reach the same position must
    yield the same ``position_key()``. This is the foundation of
    the transposition table; if it ever breaks, threefold-repetition
    detection breaks too."""

    def test_simple_transposition_via_knight_orders(self):
        # 1.Nf3 Nf6 2.Nc3 Nc6  vs  1.Nc3 Nc6 2.Nf3 Nf6
        path_a = ["g1f3", "g8f6", "b1c3", "b8c6"]
        path_b = ["b1c3", "b8c6", "g1f3", "g8f6"]
        assert _key_after(path_a) == _key_after(path_b)

    def test_d4_e4_transposition(self):
        # 1.d4 d5 2.c4 e6  vs  1.c4 e6 2.d4 d5
        path_a = ["d2d4", "d7d5", "c2c4", "e7e6"]
        path_b = ["c2c4", "e7e6", "d2d4", "d7d5"]
        assert _key_after(path_a) == _key_after(path_b)

    def test_different_positions_have_different_keys(self):
        # Sanity check on the test itself.
        a = _key_after(["e2e4"])
        b = _key_after(["d2d4"])
        assert a != b


def _key_after(uci_moves: list[str]) -> tuple:
    board = Board.starting_position()
    for u in uci_moves:
        for legal in board.legal_moves():
            if legal.uci() == u:
                board.make_move(legal)
                break
        else:
            raise AssertionError(f"illegal move in fixture: {u}")
    return board.position_key()


# ---------------------------------------------------------------------------
# 5. Long-game smoke: 100 plies of legal play, FEN never desyncs
# ---------------------------------------------------------------------------


class TestLongGameConsistency:
    def test_engine_self_play_fen_stays_consistent(self):
        """Engine plays both sides for up to 100 plies. After every
        move:
          - serialize -> parse -> serialize is a fixed point.
          - position_key matches what we'd get from a fresh
            parse_fen of the same position.
        Catches any drift between the live ``Board`` state and its
        FEN serialization."""
        engine = Engine(elo=MAX_ELO, seed=0)
        board = Board.starting_position()
        for ply in range(100):
            if not board.legal_moves():
                break
            r = engine.search(board, SearchLimits(depth=1))
            board.make_move(r.best_move)
            fen = board.fen()
            assert parse_fen(fen).fen() == fen, (
                f"ply {ply}: FEN serializer is not idempotent on {fen!r}"
            )
            assert parse_fen(fen).position_key() == board.position_key(), (
                f"ply {ply}: live board key != parse_fen(b.fen()) key"
            )


# ---------------------------------------------------------------------------
# 6. Concurrent UCI search/stop stress
# ---------------------------------------------------------------------------


class TestConcurrentStop:
    def test_repeated_go_stop_cycle(self):
        """Five rapid go/stop cycles -- the engine must always
        emit a bestmove and the searcher thread must terminate."""
        proto, out = _new_proto()
        proto.handle("position startpos")
        for _ in range(5):
            proto.handle("go infinite")
            proto.handle("stop")
            # Drain the search; we don't care about the value.
            if proto.is_searching():
                proto.wait_for_search()
        # Five bestmove lines, one per cycle.
        assert out.getvalue().count("bestmove ") == 5

    def test_quit_during_active_search_does_not_hang(self):
        """``quit`` while a search runs must join the thread and
        return promptly."""
        proto, _ = _new_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        # Run quit on a watchdog timer: if it hangs > 5 sec the
        # test fails noisily rather than wedging the suite.
        done = threading.Event()
        def quit_target() -> None:
            proto.handle("quit")
            done.set()
        t = threading.Thread(target=quit_target, daemon=True)
        t.start()
        assert done.wait(timeout=5.0), "quit hung waiting for search"


# ---------------------------------------------------------------------------
# 7. Move object hardening
# ---------------------------------------------------------------------------


class TestMoveParsing:
    def test_uci_round_trip(self):
        """Round-tripping the realistic UCI string shapes.

        Note: ``"0000"`` is the UCI **null-move sentinel** the
        protocol emits when there is no legal move. It is *not* a
        ``Move`` value and intentionally doesn't round-trip
        through ``Move.from_uci``; that contract belongs to the
        UCI layer, not core."""
        for s in ("e2e4", "e7e8q", "a7a8n", "e1g1", "h2h1r", "b7b8b"):
            assert Move.from_uci(s).uci() == s

    def test_invalid_uci_raises(self):
        for bad in ("", "e2", "e2e4z", "z9z9", "e2e4qq", "0000"):
            with pytest.raises(ValueError):
                Move.from_uci(bad)
