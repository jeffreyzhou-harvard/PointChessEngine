"""Tests for arena/engines.py: parse_info, EngineSpec, UCIClient subprocess."""
from __future__ import annotations

from pathlib import Path

import pytest

from arena.engines import (
    REGISTRY,
    UCIClient,
    _count_loc,
    parse_info,
    populate_static_metadata,
)


# --------------------------------------------------------------------------- #
# parse_info: pure UCI info-line parser                                       #
# --------------------------------------------------------------------------- #

class TestParseInfo:
    def test_parses_standard_fields(self):
        line = "info depth 5 nodes 12345 time 234 nps 52778 score cp 25 pv e2e4"
        out = parse_info(line)
        assert out["depth"] == 5
        assert out["nodes"] == 12345
        assert out["time"] == 234
        assert out["nps"] == 52778
        assert out["score_kind"] == "cp"
        assert out["score_val"] == 25
        assert out["pv"] == "e2e4"

    def test_parses_mate_score(self):
        out = parse_info("info depth 4 score mate 3 nodes 100")
        assert out["score_kind"] == "mate"
        assert out["score_val"] == 3
        assert out["nodes"] == 100

    def test_negative_score(self):
        out = parse_info("info depth 2 score cp -150 nodes 50")
        assert out["score_val"] == -150

    def test_ignores_unknown_tokens(self):
        out = parse_info("info depth 3 currmove e2e4 nodes 200")
        assert out["depth"] == 3
        assert out["nodes"] == 200

    def test_pv_consumes_tail(self):
        out = parse_info("info depth 2 pv e2e4 e7e5 g1f3")
        assert out["pv"] == "e2e4 e7e5 g1f3"
        # Anything after pv stays inside pv (UCI grammar).

    def test_handles_string_clause(self):
        out = parse_info("info depth 2 string this is a debug line that should be ignored")
        assert out["depth"] == 2
        assert "string" not in out

    def test_garbage_is_safe(self):
        # Should not raise on malformed/non-numeric values.
        out = parse_info("info depth notanumber nodes whatever")
        assert isinstance(out, dict)  # graceful


# --------------------------------------------------------------------------- #
# UCIClient subprocess wrapper (drives the in-tree fake engine)               #
# --------------------------------------------------------------------------- #

class TestUCIClient:
    def test_handshake_and_bestmove(self, fake_engine_spec):
        client = UCIClient(fake_engine_spec)
        try:
            assert client.id_name == "FakeUCI"
            client.new_game()
            bm, infos = client.go(moves_uci=[], movetime_ms=50)
            assert bm == "e2e4"  # first move in the default fake script
            assert any("nodes" in i for i in infos)
            last = infos[-1]
            assert last["depth"] == 4
            assert last["score_kind"] == "cp"
            assert last["score_val"] == 25
        finally:
            client.close()

    def test_multiple_goes_advance_script(self, fake_engine_spec):
        client = UCIClient(fake_engine_spec)
        try:
            bm1, _ = client.go([], movetime_ms=20)
            bm2, _ = client.go([bm1], movetime_ms=20)
            bm3, _ = client.go([bm1, bm2], movetime_ms=20)
            # The white-side fake walks WHITE_LINE in conftest.py.
            assert (bm1, bm2, bm3) == ("e2e4", "g1f3", "f1c4")
        finally:
            client.close()

    def test_close_is_idempotent(self, fake_engine_spec):
        client = UCIClient(fake_engine_spec)
        client.close()
        client.close()  # second close must not raise


# --------------------------------------------------------------------------- #
# Static metadata: LOC counter + populate_static_metadata wiring              #
# --------------------------------------------------------------------------- #

class TestStaticMetadata:
    def test_count_loc_skips_pycache_and_venv(self, tmp_path: Path):
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "a.py").write_text("a = 1\nb = 2\nc = 3\n")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "ignored.py").write_text("x\n" * 99)
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "site.py").write_text("x\n" * 99)
        assert _count_loc(tmp_path) == 3

    def test_populate_static_metadata_loads_costs(self, tmp_path, monkeypatch):
        # Point to the real REGISTRY but make engine_costs.json a temp file.
        before = {eid: spec.build_cost_usd for eid, spec in REGISTRY.items()}
        try:
            costs = tmp_path / "engine_costs.json"
            costs.write_text('{"oneshot_nocontext": {"build_cost_usd": 1.23, "build_tokens": 50000}}')
            import arena.engines as eng_mod
            monkeypatch.setattr(eng_mod, "Path", eng_mod.Path)
            # Monkeypatch the file resolution by temporarily renaming.
            real = eng_mod.Path(eng_mod.__file__).parent / "engine_costs.json"
            backup = real.read_text() if real.exists() else None
            real.write_text(costs.read_text())
            try:
                populate_static_metadata()
                assert REGISTRY["oneshot_nocontext"].build_cost_usd == 1.23
                assert REGISTRY["oneshot_nocontext"].build_tokens == 50000
            finally:
                if backup is not None:
                    real.write_text(backup)
                else:
                    real.unlink()
        finally:
            for eid, val in before.items():
                REGISTRY[eid].build_cost_usd = val
