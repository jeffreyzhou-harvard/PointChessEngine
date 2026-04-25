"""Tiny built-in opening book.

A handful of mainline openings, indexed by Zobrist hash of the resulting
position. Each entry maps a position to a list of (move_uci, weight) pairs.
The book is intentionally small — it exists to give the engine some humanlike
opening variety, not to play perfect theory. To extend, add lines below; the
position keys are computed at import time.

A polyglot `.bin` reader can be slotted in later (python-chess provides one)
without touching call sites.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

import chess
import chess.polyglot

# Lines listed as SAN sequences from the starting position.
_LINES_SAN: List[List[str]] = [
    # 1.e4 ...
    ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O"],   # Ruy Lopez
    ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],                       # Italian
    ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3"],  # Najdorf-ish
    ["e4", "c5", "Nf3", "Nc6", "d4", "cxd4", "Nxd4"],               # Open Sicilian
    ["e4", "e6", "d4", "d5", "Nc3"],                                # French Classical
    ["e4", "c6", "d4", "d5", "Nc3"],                                # Caro-Kann
    ["e4", "d6", "d4", "Nf6", "Nc3", "g6"],                         # Pirc
    # 1.d4 ...
    ["d4", "d5", "c4", "e6", "Nc3", "Nf6"],                         # QGD
    ["d4", "d5", "c4", "c6", "Nc3", "Nf6"],                         # Slav
    ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4"],                  # KID
    ["d4", "Nf6", "c4", "e6", "Nf3", "b6"],                         # QID
    # Other
    ["c4", "e5", "Nc3", "Nf6"],                                     # English
    ["Nf3", "d5", "g3", "Nf6", "Bg2"],                              # Reti
]


def _build_book() -> dict:
    """Build a {zobrist_hash: [(move, weight), ...]} dictionary."""
    book: dict = {}
    for line in _LINES_SAN:
        board = chess.Board()
        for san in line:
            try:
                move = board.parse_san(san)
            except Exception:
                break  # malformed line, skip
            key = chess.polyglot.zobrist_hash(board)
            entry = book.setdefault(key, {})
            entry[move.uci()] = entry.get(move.uci(), 0) + 1
            board.push(move)
    # Convert inner dicts to sorted lists.
    return {k: sorted(v.items(), key=lambda x: -x[1]) for k, v in book.items()}


_BOOK = _build_book()


def lookup(board: chess.Board, rng: Optional[random.Random] = None) -> Optional[chess.Move]:
    """Pick a book move for `board`, weighted by frequency. Returns None if
    no book entry matches."""
    rng = rng or random
    key = chess.polyglot.zobrist_hash(board)
    entries: Optional[List[Tuple[str, int]]] = _BOOK.get(key)
    if not entries:
        return None
    total = sum(w for _, w in entries)
    pick = rng.uniform(0, total)
    cum = 0
    for uci, w in entries:
        cum += w
        if pick <= cum:
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                return move
            break
    return None
