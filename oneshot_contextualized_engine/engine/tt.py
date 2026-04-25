"""Transposition table.

Keyed by python-chess's polyglot Zobrist hash. We store an `(value, depth,
flag, best_move)` tuple per key. Replacement: depth-preferred — we keep the
deeper entry on collision; ties go to the new entry (so newer search
information replaces stale).

`flag` is one of:
    EXACT  -- value is the true minimax score
    LOWER  -- value is a lower bound (failed-high in the previous search)
    UPPER  -- value is an upper bound (failed-low in the previous search)
"""

from __future__ import annotations

from typing import Optional, Tuple

import chess
import chess.polyglot

EXACT = 0
LOWER = 1
UPPER = 2


class TranspositionTable:
    __slots__ = ("_table", "_capacity")

    def __init__(self, mb: int = 16):
        # Each entry is ~64 bytes in CPython; pick capacity accordingly.
        self._capacity = max(1024, (mb * 1024 * 1024) // 64)
        self._table: dict = {}

    def clear(self) -> None:
        self._table.clear()

    def resize(self, mb: int) -> None:
        self._capacity = max(1024, (mb * 1024 * 1024) // 64)
        if len(self._table) > self._capacity:
            self.clear()

    def store(self, key: int, depth: int, value: int, flag: int,
              best_move: Optional[chess.Move]) -> None:
        existing = self._table.get(key)
        if existing is not None and existing[1] > depth:
            # Keep the deeper existing entry.
            return
        if len(self._table) >= self._capacity and key not in self._table:
            # Naive eviction: drop a random-ish entry to bound memory.
            try:
                self._table.pop(next(iter(self._table)))
            except StopIteration:
                pass
        self._table[key] = (value, depth, flag, best_move)

    def probe(self, key: int) -> Optional[Tuple[int, int, int, Optional[chess.Move]]]:
        return self._table.get(key)

    def __len__(self) -> int:
        return len(self._table)

    @staticmethod
    def hash_for(board: chess.Board) -> int:
        return chess.polyglot.zobrist_hash(board)
