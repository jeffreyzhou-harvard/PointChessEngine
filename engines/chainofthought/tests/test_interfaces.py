"""Stage 1 interface tests.

These tests exercise *only* what scaffolding promises: the public
surface exists, the value types behave like value types, and the
unimplemented behaviour raises ``NotImplementedError`` rather than
silently doing the wrong thing. As real behaviour lands in later
stages, the ``NotImplementedError`` checks will be replaced by real
behavioural tests in their respective files.
"""

from __future__ import annotations

import pytest

from engines.chainofthought.core import (
    Board,
    Color,
    GameState,
    Move,
    Piece,
    PieceType,
)
from engines.chainofthought.core.types import (
    square,
    square_file,
    square_from_algebraic,
    square_rank,
    square_to_algebraic,
)
from engines.chainofthought.search import (
    Engine,
    EloConfig,
    MAX_ELO,
    MIN_ELO,
    SearchLimits,
    SearchResult,
    config_from_elo,
)
from engines.chainofthought.uci import UCIProtocol
from engines.chainofthought.uci.protocol import ENGINE_AUTHOR, ENGINE_NAME
from engines.chainofthought.ui import serve


# ---------------------------------------------------------------------------
# core.types
# ---------------------------------------------------------------------------


class TestColor:
    def test_values(self):
        assert int(Color.WHITE) == 0
        assert int(Color.BLACK) == 1

    def test_opponent(self):
        assert Color.WHITE.opponent() is Color.BLACK
        assert Color.BLACK.opponent() is Color.WHITE


class TestPiece:
    @pytest.mark.parametrize(
        "symbol,color,ptype",
        [
            ("P", Color.WHITE, PieceType.PAWN),
            ("p", Color.BLACK, PieceType.PAWN),
            ("N", Color.WHITE, PieceType.KNIGHT),
            ("k", Color.BLACK, PieceType.KING),
            ("Q", Color.WHITE, PieceType.QUEEN),
        ],
    )
    def test_from_and_to_symbol(self, symbol, color, ptype):
        piece = Piece.from_symbol(symbol)
        assert piece.color is color
        assert piece.type is ptype
        assert piece.symbol == symbol

    def test_value_semantics(self):
        a = Piece(Color.WHITE, PieceType.ROOK)
        b = Piece(Color.WHITE, PieceType.ROOK)
        assert a == b
        assert hash(a) == hash(b)

    def test_invalid_symbol(self):
        with pytest.raises(ValueError):
            Piece.from_symbol("x")
        with pytest.raises(ValueError):
            Piece.from_symbol("")


class TestSquares:
    def test_square_construct(self):
        assert square(0, 0) == 0           # a1
        assert square(7, 0) == 7           # h1
        assert square(0, 7) == 56          # a8
        assert square(7, 7) == 63          # h8
        assert square(4, 3) == 28          # e4

    @pytest.mark.parametrize(
        "name,index",
        [
            ("a1", 0),
            ("h1", 7),
            ("a8", 56),
            ("h8", 63),
            ("e4", 28),
            ("d5", 35),
        ],
    )
    def test_algebraic_roundtrip(self, name, index):
        assert square_from_algebraic(name) == index
        assert square_to_algebraic(index) == name

    def test_file_rank(self):
        sq = square_from_algebraic("e4")
        assert square_file(sq) == 4
        assert square_rank(sq) == 3

    def test_invalid_algebraic(self):
        with pytest.raises(ValueError):
            square_from_algebraic("z9")
        with pytest.raises(ValueError):
            square_from_algebraic("e")
        with pytest.raises(ValueError):
            square_from_algebraic("e10")

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            square(8, 0)
        with pytest.raises(ValueError):
            square_to_algebraic(64)


# ---------------------------------------------------------------------------
# core.move
# ---------------------------------------------------------------------------


class TestMove:
    @pytest.mark.parametrize(
        "text,from_sq,to_sq,promo",
        [
            ("e2e4", square_from_algebraic("e2"), square_from_algebraic("e4"), None),
            ("e7e8q", square_from_algebraic("e7"), square_from_algebraic("e8"), PieceType.QUEEN),
            ("a7a8n", square_from_algebraic("a7"), square_from_algebraic("a8"), PieceType.KNIGHT),
        ],
    )
    def test_uci_roundtrip(self, text, from_sq, to_sq, promo):
        move = Move.from_uci(text)
        assert move.from_sq == from_sq
        assert move.to_sq == to_sq
        assert move.promotion is promo
        assert move.uci() == text

    def test_value_semantics(self):
        a = Move.from_uci("e2e4")
        b = Move.from_uci("e2e4")
        assert a == b
        assert hash(a) == hash(b)
        assert {a, b} == {a}

    @pytest.mark.parametrize("bad", ["", "e2", "e2e", "z9z8", "e7e8x"])
    def test_invalid(self, bad):
        with pytest.raises(ValueError):
            Move.from_uci(bad)


# ---------------------------------------------------------------------------
# core.board / core.game placeholders
# ---------------------------------------------------------------------------


class TestBoardScaffold:
    def test_starting_fen_constant(self):
        # The canonical constant. Behavioural FEN tests live in test_fen.py.
        assert Board.STARTING_FEN.startswith("rnbqkbnr/")
        assert Board.STARTING_FEN.endswith(" w KQkq - 0 1")

class TestGameStateScaffold:
    def test_constructs_with_starting_position(self):
        # Behavioural game-state tests live in test_game.py; this is
        # only the scaffold-level "the constructor exists" assertion.
        g = GameState()
        assert g.board.fen() == Board.STARTING_FEN
        assert len(g) == 0


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearchLimits:
    def test_default_is_unbounded(self):
        assert SearchLimits().is_unbounded() is True

    def test_depth_bound(self):
        assert SearchLimits(depth=4).is_unbounded() is False

    def test_movetime_bound(self):
        assert SearchLimits(movetime_ms=1000).is_unbounded() is False

    def test_infinite(self):
        assert SearchLimits(infinite=True).is_unbounded() is False


class TestSearchResultShape:
    def test_minimum_fields(self):
        m = Move.from_uci("e2e4")
        r = SearchResult(best_move=m)
        assert r.best_move == m
        assert r.score_cp is None
        assert r.mate_in is None
        assert r.depth == 0
        assert r.nodes == 0
        assert r.pv == ()


class TestEngineScaffold:
    def test_default_elo(self):
        e = Engine()
        assert e.elo == 1500

    def test_set_elo(self):
        e = Engine()
        e.set_elo(2000)
        assert e.elo == 2000

    def test_search_returns_legal_move(self):
        # Stage 7: search is implemented. The smoke check belongs in
        # test_search.py; here we only confirm the surface is wired up.
        e = Engine()
        result = e.search(Board.starting_position(), SearchLimits(depth=1))
        assert result.best_move is not None
        assert result.depth >= 1

    def test_new_game_is_safe_noop(self):
        # ``new_game`` must be safe to call even before search exists,
        # because UCI ``ucinewgame`` will call it on every new game.
        Engine().new_game()


# ---------------------------------------------------------------------------
# search.elo
# ---------------------------------------------------------------------------


class TestEloMapping:
    def test_clamps_low(self):
        cfg = config_from_elo(0)
        assert cfg.elo == MIN_ELO

    def test_clamps_high(self):
        cfg = config_from_elo(99999)
        assert cfg.elo == MAX_ELO

    def test_returns_eloconfig(self):
        cfg = config_from_elo(1500)
        assert isinstance(cfg, EloConfig)

    def test_monotonic_in_depth(self):
        # Depth must be (non-strictly) non-decreasing across the band.
        depths = [config_from_elo(e).max_depth for e in range(MIN_ELO, MAX_ELO + 1, 100)]
        assert depths == sorted(depths)

    def test_monotonic_movetime(self):
        times = [config_from_elo(e).movetime_ms for e in range(MIN_ELO, MAX_ELO + 1, 100)]
        assert times == sorted(times)

    def test_noise_decreases(self):
        noises = [config_from_elo(e).eval_noise_cp for e in range(MIN_ELO, MAX_ELO + 1, 100)]
        assert noises == sorted(noises, reverse=True)

    def test_blunder_decreases(self):
        blunders = [config_from_elo(e).blunder_pct for e in range(MIN_ELO, MAX_ELO + 1, 100)]
        assert blunders == sorted(blunders, reverse=True)

    def test_endpoints(self):
        lo = config_from_elo(MIN_ELO)
        hi = config_from_elo(MAX_ELO)
        assert lo.max_depth >= 1
        assert hi.max_depth > lo.max_depth
        assert hi.eval_noise_cp == 0
        assert hi.blunder_pct == 0.0


# ---------------------------------------------------------------------------
# uci
# ---------------------------------------------------------------------------


class TestUCIScaffold:
    def test_engine_identity_constants(self):
        assert isinstance(ENGINE_NAME, str) and ENGINE_NAME
        assert isinstance(ENGINE_AUTHOR, str) and ENGINE_AUTHOR

    def test_options_includes_uci_elo(self):
        opts = UCIProtocol.options()
        names = [o["name"] for o in opts]
        assert "UCI_Elo" in names
        elo_opt = next(o for o in opts if o["name"] == "UCI_Elo")
        assert elo_opt["type"] == "spin"
        assert elo_opt["min"] == MIN_ELO
        assert elo_opt["max"] == MAX_ELO

    def test_constructor_uses_default_engine(self):
        proto = UCIProtocol()
        assert isinstance(proto.engine, Engine)

    def test_run_handles_quit(self):
        # Stage 9: ``run`` is implemented. The smoke check belongs in
        # test_uci.py; here we only confirm the surface is wired up
        # by feeding a trivial transcript.
        import io

        proto = UCIProtocol(stdin=io.StringIO("quit\n"), stdout=io.StringIO())
        proto.run()  # must return cleanly


# ---------------------------------------------------------------------------
# ui
# ---------------------------------------------------------------------------


class TestUIScaffold:
    def test_make_server_returns_uiserver(self):
        # Stage 10: serve is implemented. Bind to port 0 (OS-picked)
        # so we don't conflict with anything; close immediately.
        from engines.chainofthought.ui import make_server, UIServer

        server = make_server(host="127.0.0.1", port=0)
        try:
            assert isinstance(server, UIServer)
            assert server.server_address[1] != 0  # OS bound a real port
        finally:
            server.server_close()


# ---------------------------------------------------------------------------
# Layering: core must not import search/uci/ui.
# ---------------------------------------------------------------------------


class TestLayering:
    """Cheap structural test: scan source for forbidden imports."""

    def test_core_has_no_outward_imports(self):
        import pathlib

        core_dir = pathlib.Path(__file__).resolve().parent.parent / "core"
        forbidden = ("engines.chainofthought.search", "engines.chainofthought.uci",
                     "engines.chainofthought.ui")
        for path in core_dir.glob("*.py"):
            text = path.read_text()
            for needle in forbidden:
                assert needle not in text, f"{path.name} imports {needle}"

    def test_search_does_not_import_uci_or_ui(self):
        import pathlib

        search_dir = pathlib.Path(__file__).resolve().parent.parent / "search"
        forbidden = ("engines.chainofthought.uci", "engines.chainofthought.ui")
        for path in search_dir.glob("*.py"):
            text = path.read_text()
            for needle in forbidden:
                assert needle not in text, f"{path.name} imports {needle}"
