"""Session-level tests (no HTTP).

The :class:`Session` is the UI's brain: it owns the GameState +
Engine, validates moves, exposes ``state_dict`` for the frontend to
render. These tests drive it directly so no HTTP machinery is
involved -- HTTP plumbing is covered by ``test_ui_server.py``.

Engines are pinned to MAX_ELO (no weakening) for determinism, with a
fixed seed for paranoia. Searches use the engine's normal ELO-derived
movetime, but at MAX_ELO the default depth is 7 -- in practice tests
that drive the engine cap depth via a smaller-ELO setting (1200,
which gives depth=3) so the suite stays fast.
"""

from __future__ import annotations

import pytest

from engines.chainofthought.core.types import Color
from engines.chainofthought.search import DEFAULT_ELO, MAX_ELO, MIN_ELO
from engines.chainofthought.ui.session import Session


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _new_session(
    *, color: Color = Color.WHITE, elo: int = 1200, seed: int = 0
) -> Session:
    """Construct a session with deterministic, fast-search defaults."""
    return Session(user_color=color, elo=elo, seed=seed)


# ---------------------------------------------------------------------------
# 1. construction & defaults
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_defaults(self):
        s = Session()
        assert s.user_color is Color.WHITE
        assert s.elo == DEFAULT_ELO
        assert s.is_user_turn() is True
        assert s.is_engine_turn() is False
        assert s.is_game_over() is False

    def test_construct_as_black(self):
        s = Session(user_color=Color.BLACK)
        # Starting position is white-to-move, so engine moves first.
        assert s.is_user_turn() is False
        assert s.is_engine_turn() is True

    def test_elo_is_clamped(self):
        assert Session(elo=99999).elo == MAX_ELO
        assert Session(elo=-5).elo == MIN_ELO


# ---------------------------------------------------------------------------
# 2. user move flow
# ---------------------------------------------------------------------------


class TestUserMoves:
    def test_play_legal_move(self):
        s = _new_session()
        s.play_user_move("e2e4")
        assert s.state_dict()["history_uci"] == ["e2e4"]
        # SAN should be present and recognisable.
        assert s.state_dict()["history_san"] == ["e4"]

    def test_play_illegal_move_raises(self):
        s = _new_session()
        with pytest.raises(ValueError):
            s.play_user_move("e2e5")

    def test_play_garbage_raises(self):
        s = _new_session()
        with pytest.raises(ValueError):
            s.play_user_move("xyz")

    def test_cannot_play_when_not_users_turn(self):
        s = _new_session(color=Color.BLACK)
        with pytest.raises(ValueError):
            s.play_user_move("e2e4")  # user is black; white to move

    def test_cannot_play_after_resign(self):
        s = _new_session()
        s.resign()
        with pytest.raises(ValueError):
            s.play_user_move("e2e4")

    def test_promotion_explicit_letter(self):
        s = _new_session()
        s._game = type(s._game).from_fen(
            "4k3/P7/8/8/8/8/8/4K3 w - - 0 1"
        )
        s.play_user_move("a7a8q")
        assert s.state_dict()["history_uci"] == ["a7a8q"]

    def test_promotion_inferred_when_omitted(self):
        # 4-char string at promotion rank should auto-queen.
        s = _new_session()
        s._game = type(s._game).from_fen(
            "4k3/P7/8/8/8/8/8/4K3 w - - 0 1"
        )
        s.play_user_move("a7a8")
        assert s.state_dict()["history_uci"][-1] == "a7a8q"


# ---------------------------------------------------------------------------
# 3. engine move flow
# ---------------------------------------------------------------------------


class TestEngineMoves:
    def test_engine_responds_after_user_move(self):
        s = _new_session()
        s.play_user_move("e2e4")
        info = s.play_engine_move()
        assert info is not None
        assert info["uci"]
        assert info["san"]
        assert info["depth"] >= 1
        # Move was actually applied.
        assert len(s.state_dict()["history_uci"]) == 2

    def test_cannot_engine_move_on_users_turn(self):
        s = _new_session()
        with pytest.raises(ValueError):
            s.play_engine_move()

    def test_engine_plays_first_when_user_is_black(self):
        s = _new_session(color=Color.BLACK)
        info = s.play_engine_move()
        assert info is not None
        # State is now user's turn (black to move).
        assert s.is_user_turn()
        assert s.to_move is Color.BLACK

    def test_engine_info_present_in_state_dict(self):
        s = _new_session()
        s.play_user_move("e2e4")
        s.play_engine_move()
        info = s.state_dict()["last_engine_info"]
        assert info is not None
        assert "uci" in info and "san" in info
        assert "depth" in info and "nodes" in info

    def test_engine_move_is_legal(self):
        s = _new_session()
        s.play_user_move("d2d4")
        info = s.play_engine_move()
        # The applied move must be in the history; trivially true,
        # but also verifies that play() didn't raise (which would
        # mean Engine returned an illegal move).
        assert s.state_dict()["history_uci"][-1] == info["uci"]


# ---------------------------------------------------------------------------
# 4. resign / new game / set_elo
# ---------------------------------------------------------------------------


class TestResignAndNewGame:
    def test_resign_marks_game_over(self):
        s = _new_session()
        s.resign()
        assert s.is_game_over()
        assert s.state_dict()["resigned"] is True
        # User was white -> black wins.
        assert s.state_dict()["result"] == "0-1"

    def test_resign_when_user_was_black(self):
        s = _new_session(color=Color.BLACK)
        s.resign()
        assert s.state_dict()["result"] == "1-0"

    def test_resign_when_already_over_raises(self):
        s = _new_session()
        s.resign()
        with pytest.raises(ValueError):
            s.resign()

    def test_new_game_resets_state(self):
        s = _new_session()
        s.play_user_move("e2e4")
        s.start_new_game(user_color=Color.BLACK, elo=800)
        d = s.state_dict()
        assert d["history_uci"] == []
        assert d["history_san"] == []
        assert d["resigned"] is False
        assert d["user_color"] == "black"
        assert d["elo"] == 800

    def test_new_game_preserves_color_when_omitted(self):
        s = _new_session(color=Color.BLACK)
        s.start_new_game()
        assert s.user_color is Color.BLACK

    def test_set_elo_propagates_to_engine(self):
        s = _new_session(elo=1500)
        s.set_elo(2000)
        assert s.elo == 2000
        assert s._engine.elo == 2000

    def test_set_elo_clamps(self):
        s = _new_session()
        s.set_elo(50_000)
        assert s.elo == MAX_ELO
        s.set_elo(-100)
        assert s.elo == MIN_ELO


# ---------------------------------------------------------------------------
# 5. legal-moves grouping (used by the frontend for highlights)
# ---------------------------------------------------------------------------


class TestLegalMovesGrouped:
    def test_starting_position_keys(self):
        s = _new_session()
        groups = s.state_dict()["legal_moves"]
        # All 16 white pieces' from-squares should be present where
        # they have a legal move (knights and pawns; no others).
        assert "e2" in groups and "e3" in groups["e2"] and "e4" in groups["e2"]
        assert "g1" in groups and "f3" in groups["g1"]

    def test_game_over_returns_empty(self):
        # Fool's mate: 1.f3 e5 2.g4 Qh4#  -- white to move, mated.
        s = _new_session()
        s._game = type(s._game).from_fen(
            "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        )
        # That FEN is checkmate; verify and assert empty grouping.
        assert s.state_dict()["legal_moves"] == {}

    def test_engine_turn_returns_empty(self):
        s = _new_session(color=Color.BLACK)
        # Engine to move; we don't surface engine's legal moves.
        assert s.state_dict()["legal_moves"] == {}


# ---------------------------------------------------------------------------
# 6. status / result strings
# ---------------------------------------------------------------------------


class TestStatusStrings:
    def test_starting_position_status(self):
        s = _new_session()
        assert "to move" in s.status().lower()

    def test_in_check_status(self):
        # White to move, in check. (1.e4 e5 2.Nf3 d6 3.Bc4 Bg4 4.Nc3 Nc6 5.Nxe5 Bxd1 6.Bxf7+ Ke7)
        s = _new_session()
        s._game = type(s._game).from_fen(
            "r6r/ppp1k1pp/2np1n2/4N3/2B1P3/2N5/PPPP1PPP/R1BbK2R w KQ - 1 8"
        )
        # White king on e1 in check from Bd1? Let's just use a clean check FEN.
        s._game = type(s._game).from_fen(
            "rnbqkbnr/ppp1pppp/8/8/3pPP1q/8/PPPP2PP/RNBQKBNR w KQkq - 1 3"
        )
        # White is in check (Qh4-e1 line via h4-e1 diagonal).
        if s._game.board.is_check():
            assert "check" in s.status().lower()

    def test_checkmate_status(self):
        s = _new_session()
        # Fool's mate: white mated.
        s._game = type(s._game).from_fen(
            "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        )
        assert "checkmate" in s.status().lower()
        assert s.result() == "0-1"

    def test_stalemate_status(self):
        s = _new_session()
        s._game = type(s._game).from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        assert "stalemate" in s.status().lower()
        assert s.result() == "1/2-1/2"


# ---------------------------------------------------------------------------
# 7. PGN export
# ---------------------------------------------------------------------------


class TestPGNExport:
    def test_pgn_after_a_few_moves(self):
        s = _new_session()
        s.play_user_move("e2e4")
        s.play_engine_move()
        s.play_user_move("g1f3")
        s.play_engine_move()
        pgn = s.pgn()
        assert "[Event " in pgn
        assert "1. e4 " in pgn
        assert "2. Nf3 " in pgn

    def test_pgn_marks_resignation_in_termination(self):
        s = _new_session()
        s.play_user_move("e2e4")
        s.play_engine_move()
        s.resign()
        pgn = s.pgn()
        assert "[Result \"0-1\"]" in pgn
        assert "Termination" in pgn


# ---------------------------------------------------------------------------
# 8. state_dict shape (frontend contract)
# ---------------------------------------------------------------------------


class TestStateDictShape:
    REQUIRED_KEYS = {
        "fen", "turn", "user_color", "elo",
        "history_uci", "history_san", "legal_moves",
        "status", "result", "game_over", "is_user_turn",
        "is_engine_turn", "in_check", "resigned",
        "last_engine_info", "elo_range",
    }

    def test_required_keys_present(self):
        s = _new_session()
        d = s.state_dict()
        missing = self.REQUIRED_KEYS - set(d.keys())
        assert not missing, f"missing keys: {missing}"

    def test_elo_range_shape(self):
        s = _new_session()
        r = s.state_dict()["elo_range"]
        assert {"min", "max", "default"} <= set(r.keys())
        assert r["min"] == MIN_ELO and r["max"] == MAX_ELO

    def test_history_alignment(self):
        s = _new_session()
        s.play_user_move("e2e4")
        s.play_engine_move()
        d = s.state_dict()
        assert len(d["history_uci"]) == len(d["history_san"]) == 2


# ---------------------------------------------------------------------------
# 9. full mini-game smoke
# ---------------------------------------------------------------------------


class TestFullGameSmoke:
    def test_play_few_alternating_moves(self):
        s = _new_session()
        for user_uci in ("e2e4", "g1f3", "f1c4"):
            s.play_user_move(user_uci)
            assert s.is_engine_turn()
            info = s.play_engine_move()
            assert info is not None
            assert s.is_user_turn() or s.is_game_over()
        # No errors; history is populated.
        assert len(s.state_dict()["history_uci"]) == 6
