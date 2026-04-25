"""High-level Engine facade.

The UCI layer and the web UI both go through this class. It owns the
transposition table, the searcher, the active strength configuration, and
an opening book. It does NOT own a board — callers pass one in.

Move selection at less-than-full strength:

    1. If `use_book` is on and the position is in our small book, play from
       book (weighted).
    2. Otherwise run an iterative-deepening search at multipv = N.
    3. Add gaussian noise (sigma = eval_noise_cp/2) to each candidate's
       score, then with probability `blunder_prob` pick uniformly from the
       top-N candidates; otherwise pick the noisy-argmax.

This keeps weak play *plausible*: weaker engines miss subtle differences
between top moves but don't produce one-move blunders out of nowhere.
"""

from __future__ import annotations

import random
import threading
from typing import Callable, List, Optional

import chess

from .elo import StrengthConfig, config_from_elo
from .opening_book import lookup as book_lookup
from .search import SearchInfo, Searcher, SearchLimits
from .tt import TranspositionTable


class Engine:
    def __init__(self, hash_mb: int = 16):
        self.tt = TranspositionTable(mb=hash_mb)
        self.searcher = Searcher(self.tt)
        self.strength: StrengthConfig = config_from_elo(2400)
        self._limit_strength: bool = False
        self._random = random.Random()
        self._lock = threading.Lock()

    # ------------- configuration ----------------------------------------

    def set_hash_mb(self, mb: int) -> None:
        self.tt.resize(mb)

    def set_elo(self, elo: int) -> None:
        self.strength = config_from_elo(elo)

    def set_limit_strength(self, enabled: bool) -> None:
        self._limit_strength = bool(enabled)

    def set_skill_level(self, skill_level: int) -> None:
        from .elo import config_from_skill
        self.strength = config_from_skill(skill_level)

    def new_game(self) -> None:
        self.tt.clear()
        self.searcher.orderer.reset()

    def stop(self) -> None:
        self.searcher.request_stop()

    # ------------- search ----------------------------------------------

    def choose_move(self, board: chess.Board,
                    *, time_ms: Optional[int] = None,
                    depth: Optional[int] = None,
                    info_callback: Optional[Callable[[SearchInfo], None]] = None,
                    ) -> SearchInfo:
        """Pick a move respecting current strength config.

        The returned SearchInfo always has best_move set if a legal move
        exists. `info_callback` (if given) receives intermediate UCI infos
        from iterative deepening.
        """
        with self._lock:
            cfg = self.strength

            # 1. Opening book — only at less-than-full strength. At full
            # strength we want deterministic search-best play, not random
            # opening variety.
            if cfg.use_book and self._limit_strength_active():
                book_move = book_lookup(board, self._random)
                if book_move is not None:
                    info = SearchInfo()
                    info.best_move = book_move
                    info.pv = [book_move]
                    info.depth = 0
                    info.score_cp = 0
                    if info_callback:
                        info_callback(info)
                    return info

            # 2. Search.
            limits = SearchLimits(
                max_depth=depth if depth is not None else cfg.max_depth,
                max_time_ms=time_ms if time_ms is not None else cfg.move_time_ms,
            )
            multipv = cfg.multipv if self._limit_strength_active() else 1

            principal = self.searcher.search(
                board, limits,
                info_callback=info_callback,
                multipv=multipv,
            )

            if not self._limit_strength_active() or not principal.multipv:
                return principal

            # 3. Strength-adjusted pick from MultiPV.
            choice = self._pick_with_noise(principal.multipv, cfg)
            principal.best_move = choice.best_move
            principal.pv = choice.pv
            principal.score_cp = choice.score_cp
            principal.mate_in = choice.mate_in
            return principal

    # ------------- internals -------------------------------------------

    def _limit_strength_active(self) -> bool:
        return self._limit_strength or self.strength.elo < 2400

    def _pick_with_noise(self, candidates: List[SearchInfo],
                         cfg: StrengthConfig) -> SearchInfo:
        if not candidates:
            raise ValueError("no candidates to pick from")
        if len(candidates) == 1:
            return candidates[0]

        sigma = cfg.eval_noise_cp / 2.0
        scored = []
        for info in candidates:
            n = self._random.gauss(0, sigma) if sigma > 0 else 0
            scored.append((info.score_cp + n, info))

        if cfg.blunder_prob > 0 and self._random.random() < cfg.blunder_prob:
            return self._random.choice(candidates)

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
