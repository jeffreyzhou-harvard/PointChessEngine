"""Match orchestration: drive two UCI engines to play a full game and
publish per-event updates to subscribers (the SSE endpoint)."""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import chess

from arena.engines import REGISTRY, UCIClient, EngineSpec


@dataclass
class EngineStats:
    moves: int = 0
    nodes: int = 0
    time_ms: int = 0
    depth_sum: int = 0
    score_sum_cp: int = 0
    last_score_cp: int | None = None
    last_depth: int | None = None
    last_nps: int | None = None

    def to_dict(self) -> dict:
        avg_depth = (self.depth_sum / self.moves) if self.moves else 0.0
        avg_time = (self.time_ms / self.moves) if self.moves else 0.0
        return {
            "moves": self.moves,
            "nodes_total": self.nodes,
            "time_ms_total": self.time_ms,
            "avg_depth": round(avg_depth, 2),
            "avg_time_ms": round(avg_time, 1),
            "last_score_cp": self.last_score_cp,
            "last_depth": self.last_depth,
            "last_nps": self.last_nps,
        }


class Match:
    def __init__(self, white_id: str, black_id: str, movetime_ms: int, max_plies: int):
        self.id = uuid.uuid4().hex[:10]
        self.white_id = white_id
        self.black_id = black_id
        self.movetime_ms = movetime_ms
        self.max_plies = max_plies
        self.board = chess.Board()
        self.subscribers: list[queue.Queue[str]] = []
        self.lock = threading.Lock()
        self.history: list[dict] = []
        self.done = False
        self.result: str | None = None
        self.reason: str | None = None
        self.stats: dict[str, EngineStats] = {white_id: EngineStats(), black_id: EngineStats()}
        self._stop = False

    # --- pub/sub --------------------------------------------------------------
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

    # --- main loop ------------------------------------------------------------
    def run(self) -> None:
        white_spec = REGISTRY[self.white_id]
        black_spec = REGISTRY[self.black_id]
        engines: dict[str, UCIClient | None] = {self.white_id: None, self.black_id: None}
        try:
            self._publish({
                "type": "init",
                "white": _engine_dict(white_spec),
                "black": _engine_dict(black_spec),
                "movetime_ms": self.movetime_ms,
                "max_plies": self.max_plies,
                "fen": self.board.fen(),
            })
            engines[self.white_id] = UCIClient(white_spec)
            engines[self.black_id] = UCIClient(black_spec)
            for c in engines.values():
                c.new_game()  # type: ignore[union-attr]

            moves_uci: list[str] = []
            ply = 0
            while not self.board.is_game_over(claim_draw=True) and ply < self.max_plies and not self._stop:
                turn = chess.WHITE if self.board.turn == chess.WHITE else chess.BLACK
                eid = self.white_id if turn == chess.WHITE else self.black_id
                color = "white" if turn == chess.WHITE else "black"
                client = engines[eid]
                assert client is not None

                t0 = time.time()
                bestmove, infos = client.go(moves_uci, self.movetime_ms)
                wall_ms = int((time.time() - t0) * 1000)

                last = infos[-1] if infos else {}
                depth = last.get("depth")
                nodes = last.get("nodes")
                nps = last.get("nps")
                score_cp = None
                mate = None
                if last.get("score_kind") == "cp":
                    score_cp = last.get("score_val")
                elif last.get("score_kind") == "mate":
                    mate = last.get("score_val")

                # Apply move to board.
                try:
                    move = chess.Move.from_uci(bestmove)
                except ValueError:
                    move = None
                if move is None or move not in self.board.legal_moves:
                    self.result = "0-1" if color == "white" else "1-0"
                    self.reason = f"illegal move from {eid}: {bestmove}"
                    break

                san = self.board.san(move)
                self.board.push(move)
                moves_uci.append(bestmove)
                ply += 1

                stats = self.stats[eid]
                stats.moves += 1
                if nodes:
                    stats.nodes += nodes
                stats.time_ms += wall_ms
                if depth:
                    stats.depth_sum += depth
                    stats.last_depth = depth
                if nps:
                    stats.last_nps = nps
                if score_cp is not None:
                    stats.last_score_cp = score_cp
                    stats.score_sum_cp += score_cp

                self._publish({
                    "type": "move",
                    "color": color,
                    "engine_id": eid,
                    "ply": ply,
                    "uci": bestmove,
                    "san": san,
                    "fen": self.board.fen(),
                    "depth": depth,
                    "nodes": nodes,
                    "nps": nps,
                    "score_cp": score_cp,
                    "mate": mate,
                    "wall_ms": wall_ms,
                    "stats": {self.white_id: self.stats[self.white_id].to_dict(),
                              self.black_id: self.stats[self.black_id].to_dict()},
                })

            if self.result is None:
                if self._stop:
                    self.result = "*"
                    self.reason = "stopped"
                elif self.board.is_checkmate():
                    self.result = "1-0" if self.board.turn == chess.BLACK else "0-1"
                    self.reason = "checkmate"
                elif self.board.is_stalemate():
                    self.result = "1/2-1/2"
                    self.reason = "stalemate"
                elif self.board.is_insufficient_material():
                    self.result = "1/2-1/2"
                    self.reason = "insufficient material"
                elif self.board.can_claim_threefold_repetition():
                    self.result = "1/2-1/2"
                    self.reason = "threefold repetition"
                elif self.board.can_claim_fifty_moves():
                    self.result = "1/2-1/2"
                    self.reason = "fifty-move rule"
                elif ply >= self.max_plies:
                    self.result = "1/2-1/2"
                    self.reason = "ply cap reached"
                else:
                    self.result = "*"
                    self.reason = "unknown"

        except Exception as exc:  # surface to UI rather than dying silently
            self.result = self.result or "*"
            self.reason = f"error: {exc}"
        finally:
            for c in engines.values():
                if c is not None:
                    try:
                        c.close()
                    except Exception:
                        pass
            self.done = True
            self._publish({
                "type": "end",
                "result": self.result,
                "reason": self.reason,
                "fen": self.board.fen(),
                "stats": {self.white_id: self.stats[self.white_id].to_dict(),
                          self.black_id: self.stats[self.black_id].to_dict()},
            })


def _engine_dict(spec: EngineSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "label": spec.label,
        "blurb": spec.blurb,
        "build_pattern": spec.build_pattern,
        "build_cost_usd": spec.build_cost_usd,
        "build_tokens": spec.build_tokens,
        "build_model": spec.build_model,
        "loc": spec.loc,
    }
