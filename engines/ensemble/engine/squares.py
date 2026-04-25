"""Square coordinate helpers for the 10x12 mailbox.

The mailbox is a flat list of 120 ints. Files a..h occupy mailbox columns 1..8
and ranks 1..8 occupy mailbox rows 2..9 (rows 0,1,10,11 are sentinel rows).

Index layout:
    sq120 = 21 + file + (7 - rank_from_bottom_zero) * 10  # rank 8 at top
We use the convention that mailbox index 21 == a8 and 98 == h1, mirroring
how FEN is written from rank 8 down to rank 1.
"""

# Build translation tables.
# 64-square index: 0 = a8, 7 = h8, 56 = a1, 63 = h1 (matches FEN order).
MAILBOX64 = [0] * 64  # sq64 -> sq120
for sq in range(64):
    file = sq % 8
    rank_from_top = sq // 8  # 0 = rank 8, 7 = rank 1
    MAILBOX64[sq] = 21 + file + rank_from_top * 10

MAILBOX120 = [-1] * 120  # sq120 -> sq64 or -1 for off-board
for sq64, sq120 in enumerate(MAILBOX64):
    MAILBOX120[sq120] = sq64

FILES = "abcdefgh"
RANKS = "87654321"  # rank string indexed by rank_from_top


def algebraic_to_120(s: str) -> int:
    if len(s) != 2:
        raise ValueError(f"bad square: {s!r}")
    f = FILES.index(s[0].lower())
    r = "12345678".index(s[1])  # 0 = rank1, 7 = rank8
    rank_from_top = 7 - r
    return 21 + f + rank_from_top * 10


def sq120_to_algebraic(i: int) -> str:
    if not (0 <= i < 120) or MAILBOX120[i] < 0:
        raise ValueError(f"off-board sq120: {i}")
    rel = i - 21
    rank_from_top = rel // 10
    file = rel % 10
    return FILES[file] + "12345678"[7 - rank_from_top]


def sq64_to_120(s: int) -> int:
    return MAILBOX64[s]


def sq120_to_64(s: int) -> int:
    return MAILBOX120[s]


def algebraic_to_64(s: str) -> int:
    return MAILBOX120[algebraic_to_120(s)]


def sq64_to_algebraic(s: int) -> str:
    return sq120_to_algebraic(MAILBOX64[s])
