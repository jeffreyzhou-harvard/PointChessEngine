"""Engine facade shared by UCI and the web UI.

Class `Engine` exposes:
    new_game(), set_position(fen, moves), go(params), stop(),
    set_elo(elo), quit().
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .board import Board, INITIAL_FEN, Move, WHITE, BLACK
from .movegen import generate_legal
from .search import SearchLimits, Searcher, SearchResult
from .strength import StrengthParams, params_for_elo, select_move


@dataclass
class GoParams:
    depth: Optional[int] = None
    movetime: Optional[int] = None        # ms
    wtime: Optional[int] = None           # ms remaining for white
    btime: Optional[int] = None
    winc: Optional[int] = None
    binc: Optional[int] = None
    nodes: Optional[int] = None
    infinite: bool = False


class Engine:
    def __init__(self) -> None:
        self.board = Board.initial()
        self.elo: int = 2400
        self.params: StrengthParams = params_for_elo(self.elo)
        self._stop_flag = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._seed: Optional[int] = None
        self.rng = random.Random()
        self.last_result: Optional[SearchResult] = None
        self.last_best_move: Optional[Move] = None

    # --------------- state setup ---------------
    def new_game(self) -> None:
        self.stop()
        self.board = Board.initial()

    def set_position(self, fen: Optional[str] = None, moves: Optional[List[str]] = None) -> None:
        if fen is None or fen == "startpos":
            self.board = Board.initial()
        else:
            self.board = Board.from_fen(fen)
        if moves:
            for u in moves:
                self._apply_uci_move(u)

    def _apply_uci_move(self, uci: str) -> None:
        legal = generate_legal(self.board)
        for m in legal:
            if m.uci() == uci:
                self.board.make_move(m)
                return
        raise ValueError(f"illegal move: {uci}")

    def set_elo(self, elo: int) -> None:
        if not (400 <= elo <= 2400):
            raise ValueError("elo out of range 400..2400")
        self.elo = elo
        self.params = params_for_elo(elo)

    def set_seed(self, seed: Optional[int]) -> None:
        self._seed = seed
        self.rng = random.Random(seed) if seed is not None else random.Random()

    # --------------- search dispatch ---------------
    def _decide_limits(self, go: GoParams) -> SearchLimits:
        depth = go.depth if go.depth is not None else self.params.max_depth
        # Time budget.
        if go.movetime is not None:
            time_ms = go.movetime
        elif go.infinite:
            time_ms = None
        else:
            # Use clock if provided.
            stm = self.board.side_to_move
            remaining = go.wtime if stm == WHITE else go.btime
            inc = (go.winc if stm == WHITE else go.binc) or 0
            if remaining is not None:
                time_ms = max(50, remaining // 30 + inc // 2)
                # Cap by ELO budget too.
                time_ms = min(time_ms, self.params.time_ms)
            else:
                time_ms = self.params.time_ms
        return SearchLimits(max_depth=depth, time_ms=time_ms, nodes=go.nodes)

    def go(self, params: Optional[GoParams] = None,
           on_bestmove: Optional[Callable[[Optional[Move], SearchResult], None]] = None,
           on_info: Optional[Callable[[dict], None]] = None,
           sync: bool = False) -> Optional[SearchResult]:
        """Start a search in a worker thread (or sync if requested)."""
        if params is None:
            params = GoParams()
        self.stop()  # cancel any prior search
        self._stop_flag = threading.Event()
        limits = self._decide_limits(params)

        def _run() -> SearchResult:
            searcher = Searcher(info_callback=on_info)
            res = searcher.search(self.board, limits, stop_flag=self._stop_flag)
            # ELO-based selection from scored root moves.
            if res.scored_moves:
                chosen = select_move(res.scored_moves, self.params, self.rng)
                # Replace best_move with sampled one (keep original score for logging).
                res = SearchResult(
                    best_move=chosen,
                    score=next((s for (m, s) in res.scored_moves if m == chosen), res.score),
                    depth=res.depth, nodes=res.nodes,
                    pv=res.pv, scored_moves=res.scored_moves,
                )
            with self._lock:
                self.last_result = res
                self.last_best_move = res.best_move
            if on_bestmove is not None:
                on_bestmove(res.best_move, res)
            return res

        if sync:
            return _run()
        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()
        return None

    def stop(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            self._stop_flag.set()
            self._worker.join(timeout=5.0)
        self._worker = None

    def wait(self, timeout: Optional[float] = None) -> None:
        if self._worker is not None:
            self._worker.join(timeout=timeout)

    def quit(self) -> None:
        self.stop()

    # --------------- helpers used by UI ---------------
    def legal_uci_moves(self) -> List[str]:
        return [m.uci() for m in generate_legal(self.board)]

    def fen(self) -> str:
        return self.board.to_fen()

    def game_status(self) -> str:
        """Return one of: 'ongoing', 'checkmate', 'stalemate',
           'fifty-move', 'insufficient'."""
        legal = generate_legal(self.board)
        if not legal:
            if self.board.in_check():
                return "checkmate"
            return "stalemate"
        if self.board.halfmove_clock >= 100:
            return "fifty-move"
        if self.board.insufficient_material():
            return "insufficient"
        return "ongoing"

    def push_uci(self, uci: str) -> None:
        self._apply_uci_move(uci)
