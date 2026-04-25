"""Tests for arena/analysis.py: parallel position analysis."""
from __future__ import annotations

import chess

from arena.analysis import STARTING_FEN, analyze


class TestAnalyze:
    def test_returns_per_engine_result_for_each_id(self, registered_fakes):
        # Only the white-side fake on a white-to-move position - fake_b's
        # script returns black-side moves which would be illegal here.
        out = analyze(fen=STARTING_FEN, engine_ids=["fake"], movetime_ms=20)
        assert out["fen"] == STARTING_FEN
        assert [r["engine_id"] for r in out["results"]] == ["fake"]
        r = out["results"][0]
        assert r["bestmove"] in {m.uci() for m in chess.Board().legal_moves}
        assert r["wall_ms"] >= 0
        assert r["error"] is None

    def test_empty_fen_falls_back_to_starting_position(self, registered_fakes):
        out = analyze(fen="", engine_ids=["fake"], movetime_ms=20)
        assert out["fen"] == STARTING_FEN

    def test_invalid_fen_returns_error(self, registered_fakes):
        out = analyze(fen="not a fen at all",
                      engine_ids=["fake"], movetime_ms=20)
        assert "error" in out
        assert "invalid FEN" in out["error"]
        assert out["results"] == []

    def test_unknown_engine_filtered_out(self, registered_fakes):
        out = analyze(fen=STARTING_FEN,
                      engine_ids=["fake", "ghost"], movetime_ms=20)
        assert {r["engine_id"] for r in out["results"]} == {"fake"}

    def test_no_valid_engines_errors(self, registered_fakes):
        out = analyze(fen=STARTING_FEN,
                      engine_ids=["ghost", "phantom"], movetime_ms=20)
        assert "no valid" in out["error"]

    def test_san_attached_for_legal_move(self, registered_fakes):
        out = analyze(fen=STARTING_FEN, engine_ids=["fake"], movetime_ms=20)
        r = out["results"][0]
        # Fake plays e2e4 -> SAN "e4".
        assert r["bestmove"] == "e2e4"
        assert r["san"] == "e4"
