"""Round-robin tournament orchestrator.

Each pair of engines plays ``games_per_pair`` games (with colors
alternating when ``games_per_pair`` is even). Games are run sequentially
- enough for the arena's scale and avoids contention on the same engine
subprocess being spawned twice in parallel.

Events streamed to subscribers (SSE-shaped strings, ``data: {...}\\n\\n``):

- ``init``         schedule + engine list
- ``match_start``  game N of M about to begin
- ``match_end``    game N finished, with result + reason
- ``standings``    full standings table (emitted after every match_end)
- ``end``          tournament complete (or stopped)
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from arena.engines import REGISTRY
from arena.match import Match, _engine_dict


@dataclass
class Standings:
    """Per-engine accumulator. Points: win=1, draw=0.5, loss=0."""
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    @property
    def points(self) -> float:
        return self.wins + 0.5 * self.draws

    def to_dict(self) -> dict:
        wp = (self.wins / self.played * 100.0) if self.played else 0.0
        return {
            "played": self.played,
            "wins":   self.wins,
            "draws":  self.draws,
            "losses": self.losses,
            "points": round(self.points, 2),
            "win_pct": round(wp, 1),
        }


def _round_robin_pairs(engine_ids: list[str]) -> list[tuple[str, str]]:
    """Every ordered pair (each color permutation gets its own slot).

    For engines [A, B, C] returns [(A,B), (B,A), (A,C), (C,A), (B,C), (C,B)].
    The caller decides how many games per ordered pair to actually play.
    """
    pairs: list[tuple[str, str]] = []
    n = len(engine_ids)
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((engine_ids[i], engine_ids[j]))
            pairs.append((engine_ids[j], engine_ids[i]))
    return pairs


@dataclass
class GameRecord:
    game_idx: int
    white: str
    black: str
    result: str = ""           # "1-0" / "0-1" / "1/2-1/2" / "*"
    reason: str = ""
    pgn_moves: list[str] = field(default_factory=list)


class Tournament:
    def __init__(
        self,
        engine_ids: list[str],
        movetime_ms: int = 200,
        max_plies: int = 60,
        games_per_pair: int = 1,
    ):
        for eid in engine_ids:
            if eid not in REGISTRY:
                raise ValueError(f"unknown engine_id: {eid}")
        if len(engine_ids) < 2:
            raise ValueError("need at least 2 engines for a tournament")
        self.id = uuid.uuid4().hex[:10]
        self.engine_ids = list(engine_ids)
        self.movetime_ms = max(50, int(movetime_ms))
        self.max_plies = max(2, int(max_plies))
        self.games_per_pair = max(1, int(games_per_pair))

        # Build the schedule. games_per_pair=1 means each ordered pair
        # plays once (so each engine pair is played twice total - once
        # with each color). =2 doubles that, etc.
        ordered_pairs = _round_robin_pairs(self.engine_ids)
        self.games: list[GameRecord] = []
        for rep in range(self.games_per_pair):
            for white, black in ordered_pairs:
                self.games.append(GameRecord(
                    game_idx=len(self.games), white=white, black=black,
                ))
        self.standings: dict[str, Standings] = {eid: Standings() for eid in engine_ids}
        # cross_table[white][black] -> list[result_str]
        self.cross_table: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )

        self.subscribers: list[queue.Queue[str]] = []
        self.history: list[dict] = []
        self.lock = threading.Lock()
        self.done = False
        self._stop = False
        self.current_game_idx: int | None = None

    # ----- pub/sub -----------------------------------------------------------
    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self.lock:
            for evt in self.history:
                q.put(self._encode(evt))
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def _publish(self, event: dict) -> None:
        with self.lock:
            self.history.append(event)
            payload = self._encode(event)
            for q in self.subscribers:
                q.put(payload)

    @staticmethod
    def _encode(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def stop(self) -> None:
        self._stop = True

    # ----- main loop ---------------------------------------------------------
    def run(self) -> None:
        try:
            self._publish({
                "type": "init",
                "tournament_id": self.id,
                "engines": [_engine_dict(REGISTRY[eid]) for eid in self.engine_ids],
                "schedule": [{"game_idx": g.game_idx, "white": g.white, "black": g.black}
                             for g in self.games],
                "movetime_ms": self.movetime_ms,
                "max_plies": self.max_plies,
                "games_per_pair": self.games_per_pair,
                "total_games": len(self.games),
            })
            self._emit_standings()

            for game in self.games:
                if self._stop:
                    break
                self.current_game_idx = game.game_idx
                self._publish({
                    "type": "match_start",
                    "game_idx": game.game_idx,
                    "white": game.white,
                    "black": game.black,
                    "total_games": len(self.games),
                })
                match = Match(
                    white_id=game.white,
                    black_id=game.black,
                    movetime_ms=self.movetime_ms,
                    max_plies=self.max_plies,
                )
                # Run inline (we want sequential matches anyway).
                match.run()
                game.result = match.result or "*"
                game.reason = match.reason or ""
                self._update_standings(game)
                self._publish({
                    "type": "match_end",
                    "game_idx": game.game_idx,
                    "white": game.white,
                    "black": game.black,
                    "result": game.result,
                    "reason": game.reason,
                })
                self._emit_standings()

            self.done = True
            self._publish({
                "type": "end",
                "stopped": self._stop,
                "games_played": sum(1 for g in self.games if g.result),
                "total_games": len(self.games),
                "final_standings": self._standings_payload(),
                "cross_table": self._cross_table_payload(),
            })
        except Exception as exc:
            self.done = True
            self._publish({
                "type": "end",
                "error": f"{type(exc).__name__}: {exc}",
                "final_standings": self._standings_payload(),
                "cross_table": self._cross_table_payload(),
            })

    # ----- accumulators ------------------------------------------------------
    def _update_standings(self, game: GameRecord) -> None:
        sw = self.standings[game.white]
        sb = self.standings[game.black]
        sw.played += 1
        sb.played += 1
        if game.result == "1-0":
            sw.wins += 1
            sb.losses += 1
        elif game.result == "0-1":
            sb.wins += 1
            sw.losses += 1
        elif game.result == "1/2-1/2":
            sw.draws += 1
            sb.draws += 1
        # "*" (incomplete) doesn't update W/D/L.
        self.cross_table[game.white][game.black].append(game.result)

    def _emit_standings(self) -> None:
        self._publish({
            "type": "standings",
            "standings": self._standings_payload(),
            "cross_table": self._cross_table_payload(),
        })

    def _standings_payload(self) -> list[dict]:
        rows = [{"engine_id": eid, **s.to_dict()} for eid, s in self.standings.items()]
        rows.sort(key=lambda r: (-r["points"], -r["win_pct"], r["engine_id"]))
        return rows

    def _cross_table_payload(self) -> dict[str, dict[str, list[str]]]:
        return {w: dict(opps) for w, opps in self.cross_table.items()}
