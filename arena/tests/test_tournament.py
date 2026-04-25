"""Tests for arena/tournament.py: schedule generation + run loop."""
from __future__ import annotations

import json
import time

import pytest

from arena.tournament import Standings, Tournament, _round_robin_pairs


# --------------------------------------------------------------------------- #
# pure-function tests                                                         #
# --------------------------------------------------------------------------- #

def test_round_robin_pairs_two_engines():
    assert _round_robin_pairs(["a", "b"]) == [("a", "b"), ("b", "a")]


def test_round_robin_pairs_three_engines():
    pairs = _round_robin_pairs(["a", "b", "c"])
    # 3 engines -> 3 unordered pairs -> 6 ordered pairs (each gets both colors).
    assert len(pairs) == 6
    assert ("a", "b") in pairs and ("b", "a") in pairs
    assert ("a", "c") in pairs and ("c", "a") in pairs
    assert ("b", "c") in pairs and ("c", "b") in pairs


def test_standings_points_and_dict():
    s = Standings(played=4, wins=2, draws=1, losses=1)
    assert s.points == 2.5
    d = s.to_dict()
    assert d["played"] == 4 and d["wins"] == 2
    assert d["points"] == 2.5
    assert d["win_pct"] == 50.0


# --------------------------------------------------------------------------- #
# Tournament orchestration with two scripted fake engines                     #
# --------------------------------------------------------------------------- #

def _drain_tournament(t: Tournament, timeout: float = 60.0) -> list[dict]:
    """Subscribe + run inline; return the parsed event sequence."""
    import threading
    events: list[dict] = []
    q = t.subscribe()
    th = threading.Thread(target=t.run, daemon=True)
    th.start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            chunk = q.get(timeout=2)
        except Exception:
            continue
        ev = json.loads(chunk.replace("data: ", "", 1).strip())
        events.append(ev)
        if ev["type"] == "end":
            break
    th.join(timeout=5)
    assert events and events[-1]["type"] == "end", "tournament didn't finish"
    return events


class TestTournamentRun:
    def test_full_round_robin_two_engines(self, registered_fakes, fake_b_env):
        # 2 engines, 1 game per ordered pair -> 2 games.
        t = Tournament(engine_ids=["fake", "fake_b"],
                       movetime_ms=20, max_plies=4, games_per_pair=1)
        assert len(t.games) == 2  # (fake vs fake_b) + (fake_b vs fake)
        events = _drain_tournament(t)
        types = [e["type"] for e in events]
        assert types[0] == "init"
        assert types.count("match_start") == 2
        assert types.count("match_end")   == 2
        end = events[-1]
        assert end["games_played"] == 2
        assert end["total_games"] == 2

    def test_emits_standings_after_each_match(self, registered_fakes, fake_b_env):
        t = Tournament(engine_ids=["fake", "fake_b"],
                       movetime_ms=20, max_plies=4, games_per_pair=1)
        events = _drain_tournament(t)
        standings_events = [e for e in events if e["type"] == "standings"]
        # init standings + after each match_end.
        assert len(standings_events) >= 3
        final = events[-1]
        # Both engines played the same number of games (white once, black once).
        played = {row["engine_id"]: row["played"] for row in final["final_standings"]}
        assert played["fake"] == 2
        assert played["fake_b"] == 2

    def test_cross_table_records_results(self, registered_fakes, fake_b_env):
        t = Tournament(engine_ids=["fake", "fake_b"],
                       movetime_ms=20, max_plies=4, games_per_pair=1)
        events = _drain_tournament(t)
        end = events[-1]
        # Each ordered pair has exactly one result recorded.
        assert "fake" in end["cross_table"] and "fake_b" in end["cross_table"]["fake"]
        assert len(end["cross_table"]["fake"]["fake_b"]) == 1
        assert len(end["cross_table"]["fake_b"]["fake"]) == 1


class TestTournamentValidation:
    def test_unknown_engine_id_rejected(self):
        with pytest.raises(ValueError, match="unknown engine_id"):
            Tournament(engine_ids=["fake", "ghost"])

    def test_too_few_engines_rejected(self, registered_fakes):
        with pytest.raises(ValueError, match="at least 2"):
            Tournament(engine_ids=["fake"])
