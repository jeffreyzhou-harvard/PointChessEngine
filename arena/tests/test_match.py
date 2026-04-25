"""Tests for arena/match.py: stats accumulation + Match orchestration."""
from __future__ import annotations

import json
import time

import pytest

from arena.match import EngineStats, Match


# --------------------------------------------------------------------------- #
# EngineStats: pure accumulator                                               #
# --------------------------------------------------------------------------- #

class TestEngineStats:
    def test_empty_to_dict(self):
        d = EngineStats().to_dict()
        assert d["moves"] == 0
        assert d["nodes_total"] == 0
        assert d["avg_depth"] == 0.0
        assert d["avg_time_ms"] == 0.0
        assert d["last_score_cp"] is None

    def test_accumulates_avg_depth_and_time(self):
        s = EngineStats()
        s.moves, s.nodes, s.time_ms, s.depth_sum = 4, 8000, 1200, 16
        s.last_depth, s.last_score_cp, s.last_nps = 5, 25, 6500
        d = s.to_dict()
        assert d["moves"] == 4
        assert d["nodes_total"] == 8000
        assert d["avg_depth"] == 4.0       # 16 / 4
        assert d["avg_time_ms"] == 300.0   # 1200 / 4
        assert d["last_score_cp"] == 25
        assert d["last_nps"] == 6500


# --------------------------------------------------------------------------- #
# Match orchestration with two scripted fake engines                          #
# --------------------------------------------------------------------------- #

def _drain(match: Match, expect_end: bool = True, timeout: float = 30.0) -> list[dict]:
    """Subscribe, run match.run() in a thread, collect events until 'end'."""
    import threading

    events: list[dict] = []
    q = match.subscribe()
    t = threading.Thread(target=match.run, daemon=True)
    t.start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            chunk = q.get(timeout=1)
        except Exception:
            continue
        # SSE-shaped: "data: {json}\n\n"
        payload = chunk.replace("data: ", "", 1).strip()
        ev = json.loads(payload)
        events.append(ev)
        if ev["type"] == "end":
            break
    t.join(timeout=5)
    if expect_end:
        assert events and events[-1]["type"] == "end", "match did not finish"
    return events


class TestMatchHappyPath:
    def test_full_match_emits_init_moves_end(self, registered_fakes, fake_b_env):
        m = Match(white_id="fake", black_id="fake_b",
                  movetime_ms=20, max_plies=8)
        events = _drain(m)
        types = [e["type"] for e in events]
        assert types[0] == "init"
        assert types[-1] == "end"
        moves = [e for e in events if e["type"] == "move"]
        assert len(moves) == 8  # ply cap
        assert events[-1]["result"] == "1/2-1/2"
        assert events[-1]["reason"] == "ply cap reached"

    def test_init_event_includes_engine_metadata(self, registered_fakes, fake_b_env):
        m = Match("fake", "fake_b", movetime_ms=20, max_plies=2)
        events = _drain(m)
        init = events[0]
        assert init["white"]["id"] == "fake"
        assert init["black"]["id"] == "fake_b"
        assert init["movetime_ms"] == 20
        assert "fen" in init

    def test_move_events_carry_metrics(self, registered_fakes, fake_b_env):
        m = Match("fake", "fake_b", movetime_ms=20, max_plies=2)
        events = _drain(m)
        first_move = next(e for e in events if e["type"] == "move")
        assert first_move["color"] == "white"
        assert first_move["uci"] == "e2e4"
        assert first_move["ply"] == 1
        assert first_move["depth"] == 4
        assert first_move["score_cp"] == 25
        assert first_move["wall_ms"] >= 0
        # Per-color cumulative stats are present and consistent.
        assert first_move["stats"]["fake"]["moves"] == 1
        assert first_move["stats"]["fake_b"]["moves"] == 0


class TestMatchStop:
    def test_stop_halts_in_progress_match(self, registered_fakes):
        # Force the fakes to stall so we can stop the match mid-flight.
        from arena.engines import REGISTRY
        from arena.tests.conftest import _make_fake_spec, WHITE_LINE, BLACK_LINE
        slow_w = _make_fake_spec("fake", "FakeUCI", WHITE_LINE)
        slow_w.cmd = slow_w.cmd + ["--delay", "0.5"]
        slow_b = _make_fake_spec("fake_b", "FakeUCI-B", BLACK_LINE)
        slow_b.cmd = slow_b.cmd + ["--delay", "0.5"]
        REGISTRY["fake"] = slow_w
        REGISTRY["fake_b"] = slow_b
        m = Match("fake", "fake_b", movetime_ms=20, max_plies=20)
        # Start the match thread but stop almost immediately.
        import threading
        t = threading.Thread(target=m.run, daemon=True)
        t.start()
        time.sleep(0.05)
        m.stop()
        t.join(timeout=10)
        assert m.done is True
        assert m.result == "*" or m.reason in ("stopped", None) or "stopped" in (m.reason or "")


class TestMatchSubscribe:
    def test_subscribe_replays_history(self, registered_fakes, fake_b_env):
        m = Match("fake", "fake_b", movetime_ms=20, max_plies=2)
        # Run synchronously; afterwards a new subscriber should receive
        # the full event log immediately.
        m.run()
        q = m.subscribe()
        replayed = []
        while not q.empty():
            chunk = q.get_nowait()
            replayed.append(json.loads(chunk.replace("data: ", "", 1).strip()))
        types = [e["type"] for e in replayed]
        assert types[0] == "init"
        assert types[-1] == "end"


class TestMatchIllegalMove:
    def test_engine_returning_illegal_move_loses(self, registered_fakes):
        # Force the white fake to play an illegal opening (a1a8 is impossible
        # from the start position) - the match should halt with white losing.
        from arena.engines import REGISTRY
        from arena.tests.conftest import _make_fake_spec
        REGISTRY["fake"] = _make_fake_spec("fake", "FakeUCI", ["a1a8"])
        m = Match("fake", "fake_b", movetime_ms=20, max_plies=4)
        events = _drain(m)
        end = events[-1]
        assert end["result"] == "0-1"
        assert "illegal move from fake" in (end["reason"] or "")
