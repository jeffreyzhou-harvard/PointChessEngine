"""Transposition table. Replace-always policy, fixed 2^20 entries."""

from __future__ import annotations

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2

TT_SIZE = 1 << 20


class TranspositionTable:
    __slots__ = ("table",)

    def __init__(self):
        self.table = {}

    def clear(self) -> None:
        self.table.clear()

    def store(self, key: int, depth: int, value: int, flag: int, best_move) -> None:
        # replace-always; bound size
        if len(self.table) >= TT_SIZE:
            # cheap eviction: drop an arbitrary item
            try:
                self.table.pop(next(iter(self.table)))
            except StopIteration:
                pass
        self.table[key] = (key, depth, value, flag, best_move)

    def probe(self, key: int):
        return self.table.get(key)
