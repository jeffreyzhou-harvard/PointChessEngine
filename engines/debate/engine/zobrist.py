"""Zobrist hash tables. Seeded for determinism."""

from __future__ import annotations
import random

from .board import (
    EMPTY, WHITE, BLACK, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    file_of,
)

_rng = random.Random(0xC0FFEE)
_MASK64 = (1 << 64) - 1


def _r64() -> int:
    return _rng.getrandbits(64)


# ZOB_PIECE[piece_int][square] -> 64-bit key. Indexed by raw piece int (0..14).
ZOB_PIECE = [[0] * 64 for _ in range(16)]
for p in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14):
    for s in range(64):
        ZOB_PIECE[p][s] = _r64()

ZOB_SIDE = _r64()  # XOR'd when black to move

# castling rights: precompute table over the 16 possible 4-bit combos
ZOB_CASTLE = [0] * 16
for i in range(16):
    ZOB_CASTLE[i] = _r64() if i else 0

# en passant by file (0..7)
ZOB_EP_FILE = [_r64() for _ in range(8)]


def compute_zobrist(board) -> int:
    key = 0
    for s in range(64):
        p = board.squares[s]
        if p:
            key ^= ZOB_PIECE[p][s]
    if board.side_to_move == BLACK:
        key ^= ZOB_SIDE
    key ^= ZOB_CASTLE[board.castling_rights]
    if board.ep_square >= 0:
        key ^= ZOB_EP_FILE[file_of(board.ep_square)]
    return key
