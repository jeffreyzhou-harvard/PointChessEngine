"""Tapered evaluation per the contract.

Returns centipawns from the side-to-move's perspective.
"""
from __future__ import annotations

from typing import Dict, Tuple

from .board import (
    Board,
    EMPTY, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    WHITE, BLACK,
    KNIGHT_OFFSETS, BISHOP_OFFSETS, ROOK_OFFSETS, KING_OFFSETS,
    OFFBOARD,
)
from .squares import MAILBOX64, MAILBOX120

# ----------------- Material -----------------
MATERIAL_MG = {PAWN: 100, KNIGHT: 320, BISHOP: 330, ROOK: 500, QUEEN: 900, KING: 0}
MATERIAL_EG = {PAWN: 120, KNIGHT: 330, BISHOP: 360, ROOK: 550, QUEEN: 950, KING: 0}

# ----------------- Piece-square tables -----------------
# 64-entry tables indexed by sq64 (0=a8 ... 63=h1) for WHITE.
def _t(rows):
    flat = []
    for r in rows:
        flat.extend(r)
    assert len(flat) == 64
    return flat


PAWN_MG = _t([
    [  0,  0,  0,  0,  0,  0,  0,  0],
    [ 50, 50, 50, 50, 50, 50, 50, 50],
    [ 10, 10, 20, 30, 30, 20, 10, 10],
    [  5,  5, 10, 25, 25, 10,  5,  5],
    [  0,  0,  0, 20, 20,  0,  0,  0],
    [  5, -5,-10,  0,  0,-10, -5,  5],
    [  5, 10, 10,-20,-20, 10, 10,  5],
    [  0,  0,  0,  0,  0,  0,  0,  0],
])
PAWN_EG = _t([
    [  0,  0,  0,  0,  0,  0,  0,  0],
    [ 80, 80, 80, 80, 80, 80, 80, 80],
    [ 50, 50, 50, 50, 50, 50, 50, 50],
    [ 30, 30, 30, 30, 30, 30, 30, 30],
    [ 20, 20, 20, 20, 20, 20, 20, 20],
    [ 10, 10, 10, 10, 10, 10, 10, 10],
    [  0,  0,  0,  0,  0,  0,  0,  0],
    [  0,  0,  0,  0,  0,  0,  0,  0],
])
KNIGHT_MG = _t([
    [-50,-40,-30,-30,-30,-30,-40,-50],
    [-40,-20,  0,  0,  0,  0,-20,-40],
    [-30,  0, 10, 15, 15, 10,  0,-30],
    [-30,  5, 15, 20, 20, 15,  5,-30],
    [-30,  0, 15, 20, 20, 15,  0,-30],
    [-30,  5, 10, 15, 15, 10,  5,-30],
    [-40,-20,  0,  5,  5,  0,-20,-40],
    [-50,-40,-30,-30,-30,-30,-40,-50],
])
KNIGHT_EG = KNIGHT_MG

BISHOP_MG = _t([
    [-20,-10,-10,-10,-10,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5, 10, 10,  5,  0,-10],
    [-10,  5,  5, 10, 10,  5,  5,-10],
    [-10,  0, 10, 10, 10, 10,  0,-10],
    [-10, 10, 10, 10, 10, 10, 10,-10],
    [-10,  5,  0,  0,  0,  0,  5,-10],
    [-20,-10,-10,-10,-10,-10,-10,-20],
])
BISHOP_EG = BISHOP_MG

ROOK_MG = _t([
    [  0,  0,  0,  0,  0,  0,  0,  0],
    [  5, 10, 10, 10, 10, 10, 10,  5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [  0,  0,  0,  5,  5,  0,  0,  0],
])
ROOK_EG = ROOK_MG

QUEEN_MG = _t([
    [-20,-10,-10, -5, -5,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5,  5,  5,  5,  0,-10],
    [ -5,  0,  5,  5,  5,  5,  0, -5],
    [  0,  0,  5,  5,  5,  5,  0, -5],
    [-10,  5,  5,  5,  5,  5,  0,-10],
    [-10,  0,  5,  0,  0,  0,  0,-10],
    [-20,-10,-10, -5, -5,-10,-10,-20],
])
QUEEN_EG = QUEEN_MG

KING_MG = _t([
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-20,-30,-30,-40,-40,-30,-30,-20],
    [-10,-20,-20,-20,-20,-20,-20,-10],
    [ 20, 20,  0,  0,  0,  0, 20, 20],
    [ 20, 30, 10,  0,  0, 10, 30, 20],
])
KING_EG = _t([
    [-50,-40,-30,-20,-20,-30,-40,-50],
    [-30,-20,-10,  0,  0,-10,-20,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-30,  0,  0,  0,  0,-30,-30],
    [-50,-30,-30,-30,-30,-30,-30,-50],
])

PST_MG = {
    PAWN: PAWN_MG, KNIGHT: KNIGHT_MG, BISHOP: BISHOP_MG,
    ROOK: ROOK_MG, QUEEN: QUEEN_MG, KING: KING_MG,
}
PST_EG = {
    PAWN: PAWN_EG, KNIGHT: KNIGHT_EG, BISHOP: BISHOP_EG,
    ROOK: ROOK_EG, QUEEN: QUEEN_EG, KING: KING_EG,
}


def _mirror_sq64(sq: int) -> int:
    """Vertical mirror (rank flip)."""
    file = sq & 7
    rank_from_top = sq >> 3
    return (7 - rank_from_top) * 8 + file


# ----------------- Mobility weights -----------------
MOBILITY_MG = {KNIGHT: 4, BISHOP: 5, ROOK: 2, QUEEN: 1}
MOBILITY_EG = {KNIGHT: 4, BISHOP: 5, ROOK: 4, QUEEN: 1}


# ----------------- Pawn structure cache -----------------
_pawn_cache: Dict[int, Tuple[int, int]] = {}


def _pawn_hash(board: Board) -> int:
    h = 0
    sqs = board.squares
    for sq in MAILBOX64:
        p = sqs[sq]
        if abs(p) == PAWN:
            h ^= (sq * 0x9E3779B97F4A7C15 + (1 if p > 0 else 2))
            h &= (1 << 64) - 1
    return h


# Passed-pawn rank bonuses (index = rank advanced, 0..6 with 7 = promoted/never-used).
PASSED_MG = [0, 5, 10, 20, 35, 60, 100, 0]
PASSED_EG = [0, 10, 20, 35, 60, 100, 150, 0]


def _evaluate_pawn_structure(board: Board) -> Tuple[int, int]:
    """Return (mg, eg) from white's perspective."""
    sqs = board.squares
    # white_files[f] = list of white-perspective ranks (0=rank1 .. 7=rank8) for white pawns.
    # black_files[f] = list of black-perspective ranks (0=rank8 .. 7=rank1) for black pawns.
    white_files = [[] for _ in range(8)]
    black_files = [[] for _ in range(8)]
    for sq in MAILBOX64:
        p = sqs[sq]
        if p == PAWN:
            file = (sq - 21) % 10
            rank_from_top = (sq - 21) // 10
            white_files[file].append(7 - rank_from_top)
        elif p == -PAWN:
            file = (sq - 21) % 10
            rank_from_top = (sq - 21) // 10
            black_files[file].append(rank_from_top)

    mg = 0
    eg = 0

    # Doubled / isolated.
    for f in range(8):
        wn = len(white_files[f])
        bn = len(black_files[f])
        if wn >= 2:
            mg -= 15 * (wn - 1)
            eg -= 15 * (wn - 1)
        if bn >= 2:
            mg += 15 * (bn - 1)
            eg += 15 * (bn - 1)
        if wn:
            iso = True
            if f > 0 and white_files[f - 1]: iso = False
            if f < 7 and white_files[f + 1]: iso = False
            if iso:
                mg -= 12 * wn
                eg -= 12 * wn
        if bn:
            iso = True
            if f > 0 and black_files[f - 1]: iso = False
            if f < 7 and black_files[f + 1]: iso = False
            if iso:
                mg += 12 * bn
                eg += 12 * bn

    # Backward (coarse): pawn whose stop-square is attacked by enemy pawn
    # and has no friendly pawn on adjacent files at same-or-lower rank.
    for sq in MAILBOX64:
        p = sqs[sq]
        if p == PAWN:
            file = (sq - 21) % 10
            wrank = 7 - (sq - 21) // 10
            supported = False
            for af in (file - 1, file + 1):
                if 0 <= af < 8:
                    for r in white_files[af]:
                        if r <= wrank:
                            supported = True
                            break
                if supported: break
            if not supported:
                stop = sq - 10
                if sqs[stop - 9] == -PAWN or sqs[stop - 11] == -PAWN:
                    mg -= 8
                    eg -= 8
        elif p == -PAWN:
            file = (sq - 21) % 10
            brank = (sq - 21) // 10  # rank from black baseline
            supported = False
            for af in (file - 1, file + 1):
                if 0 <= af < 8:
                    for r in black_files[af]:
                        if r <= brank:
                            supported = True
                            break
                if supported: break
            if not supported:
                stop = sq + 10
                if sqs[stop + 9] == PAWN or sqs[stop + 11] == PAWN:
                    mg += 8
                    eg += 8

    # Passed pawns.
    # White pawn at (file=f, white-rank=r) is passed iff no black pawn on files f-1,f,f+1
    # at white-rank > r. A black pawn stored as black-rank `br` sits at white-rank = 7 - br.
    # Wait — we stored black-rank as rank_from_top, which means a black pawn with rank_from_top=1
    # is on rank 7 (one square from promotion). White-rank of that pawn = 7 - 1 = 6.
    for f in range(8):
        for r in white_files[f]:
            blocked = False
            for af in (f - 1, f, f + 1):
                if 0 <= af < 8:
                    for br in black_files[af]:
                        wr_of_b = 7 - br
                        if wr_of_b > r:
                            blocked = True
                            break
                if blocked: break
            if not blocked:
                mg += PASSED_MG[r]
                eg += PASSED_EG[r]
        for r in black_files[f]:
            blocked = False
            for af in (f - 1, f, f + 1):
                if 0 <= af < 8:
                    for wr in white_files[af]:
                        # White pawn ahead of this black pawn: white-rank wr < (white-rank of black pawn) = 7 - r.
                        if wr < (7 - r):
                            blocked = True
                            break
                if blocked: break
            if not blocked:
                mg -= PASSED_MG[r]
                eg -= PASSED_EG[r]

    return mg, eg


def _evaluate_king_safety(board: Board) -> int:
    """mg-only king safety, white-perspective."""
    sqs = board.squares
    score = 0
    for color in (WHITE, BLACK):
        ksq = board.king_sq[color]
        file = (ksq - 21) % 10
        if color == WHITE:
            shield_squares = [ksq - 10 + df for df in (-1, 0, 1) if 0 <= file + df < 8]
            shield_pawn = PAWN
        else:
            shield_squares = [ksq + 10 + df for df in (-1, 0, 1) if 0 <= file + df < 8]
            shield_pawn = -PAWN
        missing = 0
        for s in shield_squares:
            if sqs[s] != shield_pawn:
                missing += 1
        s_score = -15 * missing

        for df in (-1, 0, 1):
            af = file + df
            if not (0 <= af < 8):
                continue
            has_white_pawn = has_black_pawn = False
            for rt in range(8):
                p = sqs[21 + af + rt * 10]
                if p == PAWN: has_white_pawn = True
                elif p == -PAWN: has_black_pawn = True
            if not has_white_pawn and not has_black_pawn:
                s_score -= 20

        if color == WHITE:
            score += s_score
        else:
            score -= s_score
    return score


def _count_mobility(board: Board) -> Tuple[int, int, int, int]:
    """Returns (mg_w, eg_w, mg_b, eg_b)."""
    sqs = board.squares
    mg_w = eg_w = mg_b = eg_b = 0
    for sq in MAILBOX64:
        p = sqs[sq]
        if p == EMPTY:
            continue
        a = abs(p)
        if a not in (KNIGHT, BISHOP, ROOK, QUEEN):
            continue
        color = 1 if p > 0 else -1
        n = 0
        if a == KNIGHT:
            for d in KNIGHT_OFFSETS:
                tp = sqs[sq + d]
                if tp != OFFBOARD and (tp == EMPTY or (tp * color) < 0):
                    n += 1
        else:
            offsets = []
            if a in (BISHOP, QUEEN): offsets += list(BISHOP_OFFSETS)
            if a in (ROOK, QUEEN): offsets += list(ROOK_OFFSETS)
            for d in offsets:
                t = sq + d
                while True:
                    tp = sqs[t]
                    if tp == OFFBOARD: break
                    if tp == EMPTY:
                        n += 1
                    else:
                        if (tp * color) < 0: n += 1
                        break
                    t += d
        if color == WHITE:
            mg_w += MOBILITY_MG[a] * n
            eg_w += MOBILITY_EG[a] * n
        else:
            mg_b += MOBILITY_MG[a] * n
            eg_b += MOBILITY_EG[a] * n
    return mg_w, eg_w, mg_b, eg_b


def evaluate(board: Board) -> int:
    sqs = board.squares
    mg = eg = 0
    phase = 0
    bishops_w = bishops_b = 0

    for sq120 in MAILBOX64:
        p = sqs[sq120]
        if p == EMPTY:
            continue
        a = abs(p)
        sq64 = MAILBOX120[sq120]
        if p > 0:
            mg += MATERIAL_MG[a] + PST_MG[a][sq64]
            eg += MATERIAL_EG[a] + PST_EG[a][sq64]
            if a == BISHOP: bishops_w += 1
        else:
            ms = _mirror_sq64(sq64)
            mg -= MATERIAL_MG[a] + PST_MG[a][ms]
            eg -= MATERIAL_EG[a] + PST_EG[a][ms]
            if a == BISHOP: bishops_b += 1
        if a == QUEEN: phase += 4
        elif a == ROOK: phase += 2
        elif a in (BISHOP, KNIGHT): phase += 1
    if phase > 24: phase = 24

    mg_w, eg_w, mg_b, eg_b = _count_mobility(board)
    mg += (mg_w - mg_b)
    eg += (eg_w - eg_b)

    mg += _evaluate_king_safety(board)

    ph = _pawn_hash(board)
    cached = _pawn_cache.get(ph)
    if cached is None:
        cached = _evaluate_pawn_structure(board)
        if len(_pawn_cache) >= 100_000:
            _pawn_cache.clear()
        _pawn_cache[ph] = cached
    pmg, peg = cached
    mg += pmg
    eg += peg

    if bishops_w >= 2:
        mg += 30; eg += 50
    if bishops_b >= 2:
        mg -= 30; eg -= 50

    if board.side_to_move == WHITE:
        mg += 10
    else:
        mg -= 10

    score = (mg * phase + eg * (24 - phase)) // 24
    return score if board.side_to_move == WHITE else -score
