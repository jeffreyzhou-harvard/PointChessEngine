"""UCI protocol tests.

Coverage layers:

  1. **Pure parsers and formatters.** Module-level helpers in
     ``protocol`` -- ``_parse_bool``, ``_format_option``,
     ``_resolve_move`` -- tested in isolation.
  2. **Single-command dispatch.** Drive ``UCIProtocol.handle`` with
     individual command lines, inspect captured stdout. Exercises
     parsing, error handling, and the synchronous side effects
     (board mutation, option mutation).
  3. **Threaded search behaviour.** ``go`` spawns a search thread;
     verify ``isready`` returns immediately mid-search, ``stop``
     terminates an ``infinite`` search, ``ucinewgame`` resets state.
  4. **Full session transcripts.** End-to-end ``run()`` invocations
     to confirm command sequences produce the expected output.
  5. **Robustness.** Malformed input, unknown commands, illegal
     moves -- the loop must never crash.

Tests use ``io.StringIO`` for stdin/stdout so nothing escapes to the
real terminal. Searches are pinned to MAX_ELO (no weakening) when
the test cares about determinism, and to short depth/movetime so
the suite stays fast.
"""

from __future__ import annotations

import io
import time

import pytest

from engines.chainofthought import __version__
from engines.chainofthought.core.board import Board
from engines.chainofthought.core.move import Move
from engines.chainofthought.core.types import PieceType
from engines.chainofthought.search import (
    DEFAULT_ELO,
    Engine,
    MAX_ELO,
    MIN_ELO,
)
from engines.chainofthought.uci.protocol import (
    ENGINE_AUTHOR,
    ENGINE_NAME,
    UCIProtocol,
    _format_option,
    _parse_bool,
    _resolve_move,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_proto(
    *,
    elo: int = MAX_ELO,
    seed: int | None = 0,
    stdin_text: str = "",
) -> tuple[UCIProtocol, io.StringIO]:
    """Construct a protocol with a captured stdout and pinned engine."""
    out = io.StringIO()
    proto = UCIProtocol(
        engine=Engine(elo=elo, seed=seed),
        stdin=io.StringIO(stdin_text),
        stdout=out,
    )
    return proto, out


def _lines(out: io.StringIO) -> list[str]:
    return out.getvalue().splitlines()


def _wait(proto: UCIProtocol, timeout: float = 5.0) -> None:
    assert proto.wait_for_search(timeout), "search did not finish in time"


# ===========================================================================
# 1. pure helpers
# ===========================================================================


class TestParseBool:
    @pytest.mark.parametrize("s", ["true", "True", "TRUE", "1", "yes", "on"])
    def test_truthy(self, s):
        assert _parse_bool(s) is True

    @pytest.mark.parametrize("s", ["false", "False", "0", "no", "off"])
    def test_falsy(self, s):
        assert _parse_bool(s) is False

    @pytest.mark.parametrize("s", ["maybe", "", "tru", "2"])
    def test_invalid_raises(self, s):
        with pytest.raises(ValueError):
            _parse_bool(s)


class TestFormatOption:
    def test_spin(self):
        line = _format_option(
            {"name": "UCI_Elo", "type": "spin",
             "default": 1500, "min": 400, "max": 2400}
        )
        assert line == (
            "option name UCI_Elo type spin default 1500 min 400 max 2400"
        )

    def test_check_true(self):
        line = _format_option(
            {"name": "UCI_LimitStrength", "type": "check", "default": True}
        )
        # Bools must be the lowercase strings UCI GUIs expect.
        assert line == "option name UCI_LimitStrength type check default true"

    def test_check_false(self):
        line = _format_option(
            {"name": "Foo", "type": "check", "default": False}
        )
        assert line == "option name Foo type check default false"


class TestResolveMove:
    def test_legal_move_in_starting_position(self):
        b = Board.starting_position()
        m = _resolve_move(b, "e2e4")
        assert m == Move.from_uci("e2e4")

    def test_illegal_move_raises(self):
        b = Board.starting_position()
        with pytest.raises(ValueError):
            _resolve_move(b, "e2e5")  # pawn doesn't jump three

    def test_promotion_inferred_when_omitted(self):
        # White pawn on a7 ready to promote; UCI string sent without
        # the promotion letter should fall back to queen-promotion.
        from engines.chainofthought.core.fen import parse_fen
        b = parse_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        m = _resolve_move(b, "a7a8")
        assert m.promotion is PieceType.QUEEN

    def test_explicit_promotion_letter_respected(self):
        from engines.chainofthought.core.fen import parse_fen
        b = parse_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        m = _resolve_move(b, "a7a8n")
        assert m.promotion is PieceType.KNIGHT

    def test_garbage_string_raises(self):
        b = Board.starting_position()
        with pytest.raises(ValueError):
            _resolve_move(b, "not-a-move")


# ===========================================================================
# 2. single-command dispatch
# ===========================================================================


class TestUciCommand:
    """``uci`` advertises identity, options, and ``uciok``."""

    def test_identifies_engine(self):
        proto, out = _make_proto()
        proto.handle("uci")
        lines = _lines(out)
        assert lines[0] == f"id name {ENGINE_NAME} {__version__}"
        assert lines[1] == f"id author {ENGINE_AUTHOR}"

    def test_advertises_uci_elo_option(self):
        proto, out = _make_proto()
        proto.handle("uci")
        text = out.getvalue()
        assert "option name UCI_Elo type spin" in text
        assert f"min {MIN_ELO}" in text
        assert f"max {MAX_ELO}" in text
        assert f"default {DEFAULT_ELO}" in text

    def test_terminates_with_uciok(self):
        proto, out = _make_proto()
        proto.handle("uci")
        assert _lines(out)[-1] == "uciok"


class TestIsreadyCommand:
    def test_replies_readyok(self):
        proto, out = _make_proto()
        proto.handle("isready")
        assert _lines(out) == ["readyok"]

    def test_replies_immediately_during_search(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        # We are mid-search. ``isready`` must not block on the search.
        t0 = time.perf_counter()
        proto.handle("isready")
        dt = time.perf_counter() - t0
        proto.handle("stop")
        _wait(proto)
        assert "readyok" in out.getvalue()
        # 1s slack is generous; isready should return in ms.
        assert dt < 1.0


class TestPositionCommand:
    def test_startpos_resets_board(self):
        proto, _ = _make_proto()
        proto.handle("position startpos")
        assert proto._board.fen() == Board.STARTING_FEN

    def test_startpos_with_moves(self):
        proto, _ = _make_proto()
        proto.handle("position startpos moves e2e4 e7e5")
        assert proto._board.piece_at(Move.from_uci("e7e5").to_sq) is not None
        assert proto._board.piece_at(Move.from_uci("e2e4").to_sq) is not None

    def test_fen_six_fields(self):
        proto, _ = _make_proto()
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        proto.handle(f"position fen {fen}")
        assert proto._board.fen() == fen

    def test_fen_with_moves(self):
        proto, _ = _make_proto()
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        proto.handle(f"position fen {fen} moves e2e4")
        assert "e3" in proto._board.fen() or "e4" in proto._board.fen()

    def test_malformed_position_does_not_corrupt(self):
        proto, out = _make_proto()
        proto.handle("position startpos moves e2e4")
        before = proto._board.fen()
        # ``moves`` followed by an illegal move: the partial parse
        # must NOT mutate the committed board.
        proto.handle("position startpos moves e2e4 e2e5")  # 2nd is illegal
        assert "info string" in out.getvalue()
        assert proto._board.fen() == before, (
            "malformed position must not corrupt committed board"
        )

    def test_missing_argument_emits_info_string(self):
        proto, out = _make_proto()
        proto.handle("position")
        assert "info string" in out.getvalue()

    def test_bad_keyword_emits_info_string(self):
        proto, out = _make_proto()
        proto.handle("position somethingweird")
        assert "info string" in out.getvalue()


class TestGoCommand:
    def test_go_depth_emits_info_and_bestmove(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go depth 1")
        _wait(proto)
        text = out.getvalue()
        assert "info " in text
        assert "depth 1" in text
        assert "bestmove " in text

    def test_go_movetime(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go movetime 50")
        _wait(proto)
        assert "bestmove " in out.getvalue()

    def test_go_with_clock(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go wtime 1000 btime 1000 winc 100 binc 100")
        _wait(proto)
        assert "bestmove " in out.getvalue()

    def test_go_infinite_runs_until_stop(self):
        proto, _ = _make_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        # Briefly check it's actually running.
        assert proto.is_searching()
        proto.handle("stop")
        _wait(proto)
        assert not proto.is_searching()

    def test_go_unknown_token_doesnt_crash(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go banana movetime 30 ponder")
        _wait(proto)
        assert "bestmove " in out.getvalue()

    def test_go_bad_int_emits_info_string(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go depth notanint")
        # No search should have started; no crash.
        _wait(proto)
        assert "info string" in out.getvalue()

    def test_bestmove_is_legal_uci(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go depth 2")
        _wait(proto)
        bestmove_lines = [
            l for l in _lines(out) if l.startswith("bestmove ")
        ]
        assert len(bestmove_lines) == 1
        uci = bestmove_lines[0].split()[1]
        # Must round-trip and be legal in starting position.
        m = Move.from_uci(uci)
        assert m in Board.starting_position().legal_moves()

    def test_info_includes_pv_and_score(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go depth 2")
        _wait(proto)
        info = next(l for l in _lines(out) if l.startswith("info "))
        assert " score " in info
        assert " pv " in info
        assert " nodes " in info
        assert " time " in info

    def test_no_legal_moves_emits_null_move(self):
        # Stalemate: black to move, no legal moves.
        proto, out = _make_proto()
        proto.handle(
            "position fen 7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
        )
        proto.handle("go depth 2")
        _wait(proto)
        assert "bestmove 0000" in out.getvalue()


class TestStopCommand:
    def test_stop_with_no_search_is_noop(self):
        proto, out = _make_proto()
        proto.handle("stop")
        # No bestmove (no search to terminate), no crash.
        assert "bestmove" not in out.getvalue()

    def test_stop_aborts_infinite_search(self):
        proto, out = _make_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        # Tiny sleep so the search has *started* its first iteration.
        time.sleep(0.05)
        proto.handle("stop")
        _wait(proto)
        assert "bestmove " in out.getvalue()
        assert not proto.is_searching()


class TestUcinewgameCommand:
    def test_resets_board(self):
        proto, _ = _make_proto()
        proto.handle("position startpos moves e2e4 e7e5 g1f3")
        proto.handle("ucinewgame")
        assert proto._board.fen() == Board.STARTING_FEN

    def test_aborts_running_search(self):
        proto, _ = _make_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        proto.handle("ucinewgame")
        assert not proto.is_searching()

    def test_can_reuse_protocol_for_new_game(self):
        proto, out = _make_proto()
        proto.handle("position startpos moves e2e4")
        proto.handle("go depth 1")
        _wait(proto)
        first_count = out.getvalue().count("bestmove ")
        proto.handle("ucinewgame")
        proto.handle("position startpos")
        proto.handle("go depth 1")
        _wait(proto)
        assert out.getvalue().count("bestmove ") == first_count + 1


class TestSetoptionCommand:
    def test_set_uci_elo(self):
        proto, _ = _make_proto()
        assert proto.engine.elo == MAX_ELO  # from fixture
        proto.handle("setoption name UCI_Elo value 800")
        assert proto.engine.elo == 800

    def test_set_uci_elo_clamps(self):
        proto, _ = _make_proto()
        proto.handle("setoption name UCI_Elo value 99999")
        assert proto.engine.elo == MAX_ELO

    def test_set_uci_elo_rejects_garbage(self):
        proto, out = _make_proto()
        proto.handle("setoption name UCI_Elo value notanumber")
        assert "info string" in out.getvalue()
        # Engine ELO must be unchanged.
        assert proto.engine.elo == MAX_ELO

    def test_set_uci_limit_strength_accepts_bool(self):
        proto, out = _make_proto()
        proto.handle("setoption name UCI_LimitStrength value false")
        # No info string for valid bool.
        assert "info string" not in out.getvalue()

    def test_set_uci_limit_strength_rejects_garbage(self):
        proto, out = _make_proto()
        proto.handle("setoption name UCI_LimitStrength value maybe")
        assert "info string" in out.getvalue()

    def test_unknown_option_is_logged_not_fatal(self):
        proto, out = _make_proto()
        proto.handle("setoption name FooBar value 42")
        assert "unknown option" in out.getvalue()
        # The loop is still alive.
        proto.handle("isready")
        assert "readyok" in out.getvalue()

    def test_setoption_missing_name_logs_error(self):
        proto, out = _make_proto()
        proto.handle("setoption value 42")
        assert "info string" in out.getvalue()


class TestUnknownCommand:
    """Spec: ignore unknown commands silently."""

    def test_unknown_command_ignored(self):
        proto, out = _make_proto()
        proto.handle("explode all the things")
        assert out.getvalue() == ""

    def test_blank_line_ignored(self):
        proto, out = _make_proto()
        proto.handle("")
        proto.handle("   ")
        assert out.getvalue() == ""

    def test_loop_survives_unknown_then_known(self):
        proto, out = _make_proto()
        proto.handle("hocus pocus")
        proto.handle("isready")
        assert "readyok" in out.getvalue()


# ===========================================================================
# 3. threaded behaviour
# ===========================================================================


class TestThreading:
    def test_go_returns_immediately(self):
        proto, _ = _make_proto()
        proto.handle("position startpos")
        t0 = time.perf_counter()
        proto.handle("go infinite")
        dt = time.perf_counter() - t0
        # ``go`` only spawns a thread; should return in milliseconds.
        assert dt < 0.5
        proto.handle("stop")
        _wait(proto)

    def test_only_one_search_at_a_time(self):
        proto, _ = _make_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        # Issuing another go while one is running: the first is
        # stopped & joined before the second starts.
        proto.handle("go depth 1")
        _wait(proto)
        assert not proto.is_searching()

    def test_quit_joins_running_search(self):
        proto, _ = _make_proto()
        proto.handle("position startpos")
        proto.handle("go infinite")
        proto.handle("quit")
        # ``quit`` flagged AND the thread joined.
        assert proto._quit_requested
        assert not proto.is_searching()


# ===========================================================================
# 4. full session transcripts via run()
# ===========================================================================


class TestRunTranscripts:
    def test_minimal_handshake(self):
        proto, out = _make_proto(stdin_text="uci\nquit\n")
        proto.run()
        text = out.getvalue()
        assert "uciok" in text
        assert text.splitlines()[0].startswith("id name")

    def test_full_search_session(self):
        # Realistic GUI-style transcript.
        session = (
            "uci\n"
            "isready\n"
            "ucinewgame\n"
            "position startpos\n"
            "go depth 2\n"
            "quit\n"
        )
        proto, out = _make_proto(stdin_text=session)
        proto.run()
        text = out.getvalue()
        # Mandatory output ordering.
        idx_uciok = text.index("uciok")
        idx_readyok = text.index("readyok")
        idx_bestmove = text.index("bestmove")
        assert idx_uciok < idx_readyok < idx_bestmove

    def test_set_elo_then_search(self):
        session = (
            "uci\n"
            "setoption name UCI_Elo value 1200\n"
            "isready\n"
            "position startpos\n"
            "go depth 1\n"
            "quit\n"
        )
        proto, _ = _make_proto(stdin_text=session)
        proto.run()
        # ELO setoption took effect.
        assert proto.engine.elo == 1200

    def test_eof_closes_cleanly(self):
        # No ``quit`` -- EOF on stdin must still cause a clean exit
        # and join the search thread.
        session = (
            "position startpos\n"
            "go depth 1\n"
        )
        proto, out = _make_proto(stdin_text=session)
        proto.run()
        assert "bestmove " in out.getvalue()
        assert not proto.is_searching()


# ===========================================================================
# 5. robustness / fuzz-lite
# ===========================================================================


class TestRobustness:
    @pytest.mark.parametrize(
        "line",
        [
            "uci\x00with-null",
            "position fen too few fields",
            "position fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 moves not_a_move",
            "go depth",
            "go depth -1 movetime banana",
            "setoption",
            "setoption name",
            "setoption name UCI_Elo",
            "stop",
            "ucinewgame extra args",
        ],
    )
    def test_loop_never_crashes(self, line):
        proto, _ = _make_proto()
        # Single bad command.
        proto.handle(line)
        # Loop is still alive.
        proto.handle("isready")
        # And searches still work.
        proto.handle("position startpos")
        proto.handle("go depth 1")
        _wait(proto)

    def test_run_survives_garbage_session(self):
        session = "\n".join([
            "garbage line",
            "uci",
            "totally not a command",
            "isready",
            "position fen i am not a fen",
            "position startpos",
            "go depth 1",
            "quit",
        ]) + "\n"
        proto, out = _make_proto(stdin_text=session)
        proto.run()
        assert "uciok" in out.getvalue()
        assert "readyok" in out.getvalue()
        assert "bestmove " in out.getvalue()
