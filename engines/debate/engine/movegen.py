"""Pseudo-legal and legal move generation, plus attack detection.

Per design contract: precompute KNIGHT_TARGETS, KING_TARGETS, RAYS,
PAWN_ATTACKS at import time. No 0x88 checks. No per-step bounds checks
in hot paths.
"""

from __future__ import annotations
from typing import List

from .board import (
    Board, Move, EMPTY, WHITE, BLACK,
    PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    WP, WN, WB, WR, WQ, WK,
    BP, BN, BB, BR, BQ, BK,
    CR_WK, CR_WQ, CR_BK, CR_BQ,
    F_QUIET, F_CAPTURE, F_EP, F_CASTLE, F_DOUBLE, F_PROMO,
    sq, file_of, rank_of,
)


# --- Precomputed tables ----------------------------------------------------

def _in_bounds(f: int, r: int) -> bool:
    return 0 <= f < 8 and 0 <= r < 8


KNIGHT_DELTAS = [(1, 2), (2, 1), (2, -1), (1, -2),
                 (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING_DELTAS = [(1, 0), (1, 1), (0, 1), (-1, 1),
               (-1, 0), (-1, -1), (0, -1), (1, -1)]

# direction order matching KING_DELTAS for sliders
BISHOP_DIRS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
ROOK_DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
QUEEN_DIRS = BISHOP_DIRS + ROOK_DIRS

KNIGHT_TARGETS: List[List[int]] = [[] for _ in range(64)]
KING_TARGETS: List[List[int]] = [[] for _ in range(64)]
# RAYS[(df,dr)][sq] = list of squares along that ray from sq
RAYS: dict = {}

for d in BISHOP_DIRS + ROOK_DIRS:
    RAYS[d] = [[] for _ in range(64)]

# white_pawn_pushes[sq] = (single_push_sq_or_-1, double_push_sq_or_-1)
WHITE_PAWN_PUSHES: List[tuple] = [(-1, -1)] * 64
BLACK_PAWN_PUSHES: List[tuple] = [(-1, -1)] * 64
# pawn attacks: PAWN_ATTACKS[color][sq] = list of attacked squares
PAWN_ATTACKS: List[List[List[int]]] = [[[] for _ in range(64)], [[] for _ in range(64)]]


def _build_tables() -> None:
    for s in range(64):
        f = s & 7
        r = s >> 3
        # knight
        for df, dr in KNIGHT_DELTAS:
            nf, nr = f + df, r + dr
            if _in_bounds(nf, nr):
                KNIGHT_TARGETS[s].append(nr * 8 + nf)
        # king
        for df, dr in KING_DELTAS:
            nf, nr = f + df, r + dr
            if _in_bounds(nf, nr):
                KING_TARGETS[s].append(nr * 8 + nf)
        # rays
        for d in BISHOP_DIRS + ROOK_DIRS:
            df, dr = d
            ray = []
            nf, nr = f + df, r + dr
            while _in_bounds(nf, nr):
                ray.append(nr * 8 + nf)
                nf += df
                nr += dr
            RAYS[d][s] = ray
        # pawn pushes / attacks
        # white pawn from rank 1..6 has push to r+1
        if 1 <= r <= 6:
            single = (r + 1) * 8 + f
            double = -1
            if r == 1:
                double = (r + 2) * 8 + f
            WHITE_PAWN_PUSHES[s] = (single, double)
        if 1 <= r <= 6:
            single = (r - 1) * 8 + f
            double = -1
            if r == 6:
                double = (r - 2) * 8 + f
            BLACK_PAWN_PUSHES[s] = (single, double)
        # pawn attacks white
        for df in (-1, 1):
            nf, nr = f + df, r + 1
            if _in_bounds(nf, nr):
                PAWN_ATTACKS[WHITE][s].append(nr * 8 + nf)
            nf, nr = f + df, r - 1
            if _in_bounds(nf, nr):
                PAWN_ATTACKS[BLACK][s].append(nr * 8 + nf)


_build_tables()


# --- Attack detection ------------------------------------------------------

def is_square_attacked(board: Board, square: int, by_color: int) -> bool:
    """Authoritative attack oracle. Returns True if `square` is attacked by
    any piece of color `by_color`."""
    sqs = board.squares
    # pawn attacks: a pawn on X attacks PAWN_ATTACKS[pawn_color][X].
    # So `square` is attacked by a `by_color` pawn iff there is a pawn of
    # `by_color` on a square s such that `square in PAWN_ATTACKS[by_color][s]`.
    # Equivalently: scan PAWN_ATTACKS[opposite_color][square] for a pawn.
    enemy_pawn = PAWN | (8 if by_color == BLACK else 0)
    for s in PAWN_ATTACKS[1 - by_color][square]:
        if sqs[s] == enemy_pawn:
            return True

    # knights
    enemy_knight = KNIGHT | (8 if by_color == BLACK else 0)
    for s in KNIGHT_TARGETS[square]:
        if sqs[s] == enemy_knight:
            return True

    # king
    enemy_king = KING | (8 if by_color == BLACK else 0)
    for s in KING_TARGETS[square]:
        if sqs[s] == enemy_king:
            return True

    # bishops / queens (diagonal rays)
    enemy_bishop = BISHOP | (8 if by_color == BLACK else 0)
    enemy_queen = QUEEN | (8 if by_color == BLACK else 0)
    for d in BISHOP_DIRS:
        for s in RAYS[d][square]:
            p = sqs[s]
            if p == EMPTY:
                continue
            if p == enemy_bishop or p == enemy_queen:
                return True
            break

    # rooks / queens (orthogonal rays)
    enemy_rook = ROOK | (8 if by_color == BLACK else 0)
    for d in ROOK_DIRS:
        for s in RAYS[d][square]:
            p = sqs[s]
            if p == EMPTY:
                continue
            if p == enemy_rook or p == enemy_queen:
                return True
            break

    return False


def in_check(board: Board, color: int) -> bool:
    ks = board.king_sq[color]
    if ks < 0:
        return False
    return is_square_attacked(board, ks, 1 - color)


# --- Pseudo-legal generation ----------------------------------------------

def generate_pseudo_legal_moves(board: Board, color: int) -> List[Move]:
    sqs = board.squares
    moves: List[Move] = []
    own_mask = 0 if color == WHITE else 8
    enemy_mask = 8 if color == WHITE else 0

    for s in range(64):
        p = sqs[s]
        if p == EMPTY:
            continue
        if (p & 8) != own_mask:
            continue
        t = p & 7
        if t == PAWN:
            _gen_pawn(board, s, color, moves)
        elif t == KNIGHT:
            for to in KNIGHT_TARGETS[s]:
                tp = sqs[to]
                if tp == EMPTY:
                    moves.append(Move(s, to, 0, F_QUIET))
                elif (tp & 8) == enemy_mask:
                    moves.append(Move(s, to, 0, F_CAPTURE))
        elif t == KING:
            for to in KING_TARGETS[s]:
                tp = sqs[to]
                if tp == EMPTY:
                    moves.append(Move(s, to, 0, F_QUIET))
                elif (tp & 8) == enemy_mask:
                    moves.append(Move(s, to, 0, F_CAPTURE))
            _gen_castles(board, s, color, moves)
        elif t == BISHOP:
            _gen_slider(board, s, BISHOP_DIRS, enemy_mask, moves)
        elif t == ROOK:
            _gen_slider(board, s, ROOK_DIRS, enemy_mask, moves)
        elif t == QUEEN:
            _gen_slider(board, s, QUEEN_DIRS, enemy_mask, moves)
    return moves


def _gen_slider(board, s, dirs, enemy_mask, moves):
    sqs = board.squares
    for d in dirs:
        for to in RAYS[d][s]:
            tp = sqs[to]
            if tp == EMPTY:
                moves.append(Move(s, to, 0, F_QUIET))
            elif (tp & 8) == enemy_mask:
                moves.append(Move(s, to, 0, F_CAPTURE))
                break
            else:
                break


def _gen_pawn(board, s, color, moves):
    sqs = board.squares
    enemy_mask = 8 if color == WHITE else 0
    if color == WHITE:
        single, double = WHITE_PAWN_PUSHES[s]
        promo_rank = 7
    else:
        single, double = BLACK_PAWN_PUSHES[s]
        promo_rank = 0

    # single push
    if single >= 0 and sqs[single] == EMPTY:
        if (single >> 3) == promo_rank:
            for promo in (QUEEN, ROOK, BISHOP, KNIGHT):
                moves.append(Move(s, single, promo, F_PROMO))
        else:
            moves.append(Move(s, single, 0, F_QUIET))
            # double push
            if double >= 0 and sqs[double] == EMPTY:
                moves.append(Move(s, double, 0, F_DOUBLE))
    # captures
    for to in PAWN_ATTACKS[color][s]:
        tp = sqs[to]
        if tp != EMPTY and (tp & 8) == enemy_mask:
            if (to >> 3) == promo_rank:
                for promo in (QUEEN, ROOK, BISHOP, KNIGHT):
                    moves.append(Move(s, to, promo, F_PROMO | F_CAPTURE))
            else:
                moves.append(Move(s, to, 0, F_CAPTURE))
        elif to == board.ep_square and board.ep_square >= 0:
            moves.append(Move(s, to, 0, F_EP | F_CAPTURE))


def _gen_castles(board, ks, color, moves):
    cr = board.castling_rights
    sqs = board.squares
    if color == WHITE:
        if ks != 4:
            return
        if (cr & CR_WK) and sqs[5] == EMPTY and sqs[6] == EMPTY and sqs[7] == WR:
            moves.append(Move(4, 6, 0, F_CASTLE))
        if (cr & CR_WQ) and sqs[1] == EMPTY and sqs[2] == EMPTY and sqs[3] == EMPTY and sqs[0] == WR:
            moves.append(Move(4, 2, 0, F_CASTLE))
    else:
        if ks != 60:
            return
        if (cr & CR_BK) and sqs[61] == EMPTY and sqs[62] == EMPTY and sqs[63] == BR:
            moves.append(Move(60, 62, 0, F_CASTLE))
        if (cr & CR_BQ) and sqs[57] == EMPTY and sqs[58] == EMPTY and sqs[59] == EMPTY and sqs[56] == BR:
            moves.append(Move(60, 58, 0, F_CASTLE))


# --- Legal move filter ----------------------------------------------------

def generate_legal_moves(board: Board, color: int) -> List[Move]:
    pseudo = generate_pseudo_legal_moves(board, color)
    legal: List[Move] = []
    opponent = 1 - color
    for m in pseudo:
        # castling pre-filter: cannot castle out of, through, or into check.
        if m.flags & F_CASTLE:
            if in_check(board, color):
                continue
            # transit squares = origin, intermediate, destination
            if m.to_sq == 6:
                transit = (4, 5, 6)
            elif m.to_sq == 2:
                transit = (4, 3, 2)
            elif m.to_sq == 62:
                transit = (60, 61, 62)
            elif m.to_sq == 58:
                transit = (60, 59, 58)
            else:
                transit = ()
            attacked = False
            for t in transit:
                if is_square_attacked(board, t, opponent):
                    attacked = True
                    break
            if attacked:
                continue
        board.make_move(m)
        own_king = board.king_sq[color]
        if not is_square_attacked(board, own_king, opponent):
            legal.append(m)
        board.unmake_move()
    return legal


def perft(board: Board, depth: int) -> int:
    if depth == 0:
        return 1
    moves = generate_legal_moves(board, board.side_to_move)
    if depth == 1:
        return len(moves)
    n = 0
    for m in moves:
        board.make_move(m)
        n += perft(board, depth - 1)
        board.unmake_move()
    return n
