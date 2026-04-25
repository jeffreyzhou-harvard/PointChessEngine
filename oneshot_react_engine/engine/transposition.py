"""Tiny transposition table.

Keyed on the board's repetition key (FEN-ish string).  Values store the best
move found and a search depth so we can re-use entries from shallower searches
for move-ordering (we are conservative about reusing scores).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..core.move import Move


# Score-bound flags (alpha-beta convention)
EXACT = 0
LOWER = 1   # score is a lower bound (beta cutoff)
UPPER = 2   # score is an upper bound (failed low)


@dataclass
class TTEntry:
    depth: int
    score: int
    flag: int
    best_move: Optional[Move]


class TranspositionTable:
    def __init__(self, max_entries: int = 200_000) -> None:
        self.max_entries = max_entries
        self._table: Dict[str, TTEntry] = {}

    def clear(self) -> None:
        self._table.clear()

    def get(self, key: str) -> Optional[TTEntry]:
        return self._table.get(key)

    def put(self, key: str, entry: TTEntry) -> None:
        if len(self._table) >= self.max_entries:
            # naive eviction: drop ~10% oldest entries
            for k in list(self._table.keys())[: self.max_entries // 10]:
                del self._table[k]
        self._table[key] = entry

    def __len__(self) -> int:
        return len(self._table)
