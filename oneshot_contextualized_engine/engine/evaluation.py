"""Static evaluation.

Tapered evaluation in the PeSTO style: every term has a middlegame and
endgame value, blended by a phase scalar derived from remaining non-pawn
material. Score is returned in centipawns from the side-to-move's
perspective (positive = side-to-move is better).

The PST (piece-square table) values come from PeSTO
(https://www.chessprogramming.org/PeSTO%27s_Evaluation_Function), which is in
the public domain. The blend, mobility, king-safety, and pawn-structure
terms are written from scratch here.
"""

from __future__ import annotations

import chess


# --- Material -----------------------------------------------------------

# PeSTO baseline piece values (mg, eg). King is implicitly +inf;
# we leave it at 0 here because mate is detected separately.
MG_VALUE = {chess.PAWN: 82,  chess.KNIGHT: 337, chess.BISHOP: 365,
            chess.ROOK: 477, chess.QUEEN: 1025, chess.KING: 0}
EG_VALUE = {chess.PAWN: 94,  chess.KNIGHT: 281, chess.BISHOP: 297,
            chess.ROOK: 512, chess.QUEEN: 936,  chess.KING: 0}

# Phase weights per piece. The starting position has phase = 24.
PHASE_WEIGHT = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 1,
                chess.ROOK: 2, chess.QUEEN: 4,  chess.KING: 0}
PHASE_TOTAL = 24


# --- Piece-square tables ------------------------------------------------
#
# Each table is 64 ints; index 0 is a8, index 63 is h1 (chess-notation
# top-left to bottom-right, white's perspective). We mirror for black at
# probe time.

PST_MG = {
    chess.PAWN: [
          0,   0,   0,   0,   0,   0,   0,   0,
         98, 134,  61,  95,  68, 126,  34, -11,
         -6,   7,  26,  31,  65,  56,  25, -20,
        -14,  13,   6,  21,  23,  12,  17, -23,
        -27,  -2,  -5,  12,  17,   6,  10, -25,
        -26,  -4,  -4, -10,   3,   3,  33, -12,
        -35,  -1, -20, -23, -15,  24,  38, -22,
          0,   0,   0,   0,   0,   0,   0,   0,
    ],
    chess.KNIGHT: [
       -167, -89, -34, -49,  61, -97, -15, -107,
        -73, -41,  72,  36,  23,  62,   7,  -17,
        -47,  60,  37,  65,  84, 129,  73,   44,
         -9,  17,  19,  53,  37,  69,  18,   22,
        -13,   4,  16,  13,  28,  19,  21,   -8,
        -23,  -9,  12,  10,  19,  17,  25,  -16,
        -29, -53, -12,  -3,  -1,  18, -14,  -19,
       -105, -21, -58, -33, -17, -28, -19,  -23,
    ],
    chess.BISHOP: [
        -29,   4, -82, -37, -25, -42,   7,  -8,
        -26,  16, -18, -13,  30,  59,  18, -47,
        -16,  37,  43,  40,  35,  50,  37,  -2,
         -4,   5,  19,  50,  37,  37,   7,  -2,
         -6,  13,  13,  26,  34,  12,  10,   4,
          0,  15,  15,  15,  14,  27,  18,  10,
          4,  15,  16,   0,   7,  21,  33,   1,
        -33,  -3, -14, -21, -13, -12, -39, -21,
    ],
    chess.ROOK: [
         32,  42,  32,  51,  63,   9,  31,  43,
         27,  32,  58,  62,  80,  67,  26,  44,
         -5,  19,  26,  36,  17,  45,  61,  16,
        -24, -11,   7,  26,  24,  35,  -8, -20,
        -36, -26, -12,  -1,   9,  -7,   6, -23,
        -45, -25, -16, -17,   3,   0,  -5, -33,
        -44, -16, -20,  -9,  -1,  11,  -6, -71,
        -19, -13,   1,  17,  16,   7, -37, -26,
    ],
    chess.QUEEN: [
        -28,   0,  29,  12,  59,  44,  43,  45,
        -24, -39,  -5,   1, -16,  57,  28,  54,
        -13, -17,   7,   8,  29,  56,  47,  57,
        -27, -27, -16, -16,  -1,  17,  -2,   1,
         -9, -26,  -9, -10,  -2,  -4,   3,  -3,
        -14,   2, -11,  -2,  -5,   2,  14,   5,
        -35,  -8,  11,   2,   8,  15,  -3,   1,
         -1, -18,  -9,  10, -15, -25, -31, -50,
    ],
    chess.KING: [
        -65,  23,  16, -15, -56, -34,   2,  13,
         29,  -1, -20,  -7,  -8,  -4, -38, -29,
         -9,  24,   2, -16, -20,   6,  22, -22,
        -17, -20, -12, -27, -30, -25, -14, -36,
        -49,  -1, -27, -39, -46, -44, -33, -51,
        -14, -14, -22, -46, -44, -30, -15, -27,
          1,   7,  -8, -64, -43, -16,   9,   8,
        -15,  36,  12, -54,   8, -28,  24,  14,
    ],
}

PST_EG = {
    chess.PAWN: [
          0,   0,   0,   0,   0,   0,   0,   0,
        178, 173, 158, 134, 147, 132, 165, 187,
         94, 100,  85,  67,  56,  53,  82,  84,
         32,  24,  13,   5,  -2,   4,  17,  17,
         13,   9,  -3,  -7,  -7,  -8,   3,  -1,
          4,   7,  -6,   1,   0,  -5,  -1,  -8,
         13,   8,   8,  10,  13,   0,   2,  -7,
          0,   0,   0,   0,   0,   0,   0,   0,
    ],
    chess.KNIGHT: [
        -58, -38, -13, -28, -31, -27, -63, -99,
        -25,  -8, -25,  -2,  -9, -25, -24, -52,
        -24, -20,  10,   9,  -1,  -9, -19, -41,
        -17,   3,  22,  22,  22,  11,   8, -18,
        -18,  -6,  16,  25,  16,  17,   4, -18,
        -23,  -3,  -1,  15,  10,  -3, -20, -22,
        -42, -20, -10,  -5,  -2, -20, -23, -44,
        -29, -51, -23, -15, -22, -18, -50, -64,
    ],
    chess.BISHOP: [
        -14, -21, -11,  -8,  -7,  -9, -17, -24,
         -8,  -4,   7, -12,  -3, -13,  -4, -14,
          2,  -8,   0,  -1,  -2,   6,   0,   4,
         -3,   9,  12,   9,  14,  10,   3,   2,
         -6,   3,  13,  19,   7,  10,  -3,  -9,
        -12,  -3,   8,  10,  13,   3,  -7, -15,
        -14, -18,  -7,  -1,   4,  -9, -15, -27,
        -23,  -9, -23,  -5,  -9, -16,  -5, -17,
    ],
    chess.ROOK: [
         13,  10,  18,  15,  12,  12,   8,   5,
         11,  13,  13,  11,  -3,   3,   8,   3,
          7,   7,   7,   5,   4,  -3,  -5,  -3,
          4,   3,  13,   1,   2,   1,  -1,   2,
          3,   5,   8,   4,  -5,  -6,  -8, -11,
         -4,   0,  -5,  -1,  -7, -12,  -8, -16,
         -6,  -6,   0,   2,  -9,  -9, -11,  -3,
         -9,   2,   3,  -1,  -5, -13,   4, -20,
    ],
    chess.QUEEN: [
         -9,  22,  22,  27,  27,  19,  10,  20,
        -17,  20,  32,  41,  58,  25,  30,   0,
        -20,   6,   9,  49,  47,  35,  19,   9,
          3,  22,  24,  45,  57,  40,  57,  36,
        -18,  28,  19,  47,  31,  34,  39,  23,
        -16, -27,  15,   6,   9,  17,  10,   5,
        -22, -23, -30, -16, -16, -23, -36, -32,
        -33, -28, -22, -43,  -5, -32, -20, -41,
    ],
    chess.KING: [
        -74, -35, -18, -18, -11,  15,   4, -17,
        -12,  17,  14,  17,  17,  38,  23,  11,
         10,  17,  23,  15,  20,  45,  44,  13,
         -8,  22,  24,  27,  26,  33,  26,   3,
        -18,  -4,  21,  24,  27,  23,   9, -11,
        -19,  -3,  11,  21,  23,  16,   7,  -9,
        -27, -11,   4,  13,  14,   4,  -5, -17,
        -53, -34, -21, -11, -28, -14, -24, -43,
    ],
}


def _square_index(square: chess.Square, color: chess.Color) -> int:
    """Map a python-chess square (0=a1) to PST index (0=a8) for a given color.

    For black we mirror vertically so the table is read from black's POV.
    """
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    if color == chess.WHITE:
        return (7 - rank) * 8 + file
    else:
        return rank * 8 + file


# --- Helper bitboards ---------------------------------------------------

_FILE_BB = [chess.BB_FILES[f] for f in range(8)]
_ADJ_FILE_BB = [
    (_FILE_BB[f - 1] if f > 0 else 0) | (_FILE_BB[f + 1] if f < 7 else 0)
    for f in range(8)
]


def _pawn_structure(board: chess.Board, color: chess.Color) -> int:
    """Returns a centipawn bonus for the side `color` from pawn structure."""
    pawns = board.pieces_mask(chess.PAWN, color)
    enemy_pawns = board.pieces_mask(chess.PAWN, not color)
    score = 0

    # Doubled / isolated penalties, passed-pawn bonus.
    for f in range(8):
        on_file = pawns & _FILE_BB[f]
        if not on_file:
            continue
        # Doubled
        n = bin(on_file).count("1")
        if n > 1:
            score -= 12 * (n - 1)
        # Isolated (no friendly pawn on adjacent files)
        if not (pawns & _ADJ_FILE_BB[f]):
            score -= 14 * n

    # Passed pawns.
    for sq in chess.scan_forward(pawns):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        # Mask of files (own + adjacent) on ranks "in front" of this pawn.
        if color == chess.WHITE:
            front_ranks = sum(chess.BB_RANKS[rr] for rr in range(r + 1, 8))
        else:
            front_ranks = sum(chess.BB_RANKS[rr] for rr in range(0, r))
        block_mask = front_ranks & (_FILE_BB[f] | _ADJ_FILE_BB[f])
        if not (enemy_pawns & block_mask):
            # Bonus scales with how far advanced the pawn is.
            advance = r if color == chess.WHITE else 7 - r
            score += [0, 5, 10, 20, 35, 60, 100, 0][advance]
    return score


def _bishop_pair(board: chess.Board, color: chess.Color) -> int:
    return 30 if bin(board.pieces_mask(chess.BISHOP, color)).count("1") >= 2 else 0


def _rook_open_file(board: chess.Board, color: chess.Color) -> int:
    own_pawns = board.pieces_mask(chess.PAWN, color)
    enemy_pawns = board.pieces_mask(chess.PAWN, not color)
    score = 0
    for sq in chess.scan_forward(board.pieces_mask(chess.ROOK, color)):
        file_bb = _FILE_BB[chess.square_file(sq)]
        if not (own_pawns & file_bb):
            score += 20 if not (enemy_pawns & file_bb) else 10
    return score


def _mobility(board: chess.Board, color: chess.Color) -> int:
    """Approximate mobility: count of pseudo-legal moves for `color`.

    We use pseudo-legal to keep this cheap; we exclude king moves to avoid
    double-counting king safety.
    """
    if board.turn == color:
        return sum(1 for m in board.pseudo_legal_moves
                   if board.piece_type_at(m.from_square) != chess.KING)
    # Cheap trick: temporarily flip side-to-move. We must also clear
    # en-passant since it isn't valid for the other side.
    board.push(chess.Move.null())
    try:
        return sum(1 for m in board.pseudo_legal_moves
                   if board.piece_type_at(m.from_square) != chess.KING)
    finally:
        board.pop()


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    """Penalty for missing pawn shield + count of attackers near king."""
    king_sq = board.king(color)
    if king_sq is None:
        return 0
    score = 0

    # Pawn shield: 3 squares directly in front of the king.
    pawns = board.pieces_mask(chess.PAWN, color)
    f = chess.square_file(king_sq)
    r = chess.square_rank(king_sq)
    shield_rank = r + 1 if color == chess.WHITE else r - 1
    if 0 <= shield_rank < 8:
        for df in (-1, 0, 1):
            ff = f + df
            if 0 <= ff < 8:
                sq = chess.square(ff, shield_rank)
                if not (pawns & chess.BB_SQUARES[sq]):
                    score -= 8

    # Attackers in the king zone (a 3x3 around the king + 2 squares ahead).
    zone = 0
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            ff, rr = f + df, r + dr
            if 0 <= ff < 8 and 0 <= rr < 8:
                zone |= chess.BB_SQUARES[chess.square(ff, rr)]
    attackers = 0
    enemy = not color
    for sq in chess.scan_forward(zone):
        attackers += len(board.attackers(enemy, sq))
    score -= 3 * attackers
    return score


# --- Public API ---------------------------------------------------------

def _phase(board: chess.Board) -> int:
    p = 0
    for piece_type, weight in PHASE_WEIGHT.items():
        if weight == 0:
            continue
        p += weight * len(board.pieces(piece_type, chess.WHITE))
        p += weight * len(board.pieces(piece_type, chess.BLACK))
    return min(p, PHASE_TOTAL)


def evaluate(board: chess.Board) -> int:
    """Return the score in centipawns from the side-to-move's perspective.

    Mate scores are *not* returned here — search handles that. We only
    return a static evaluation valid for non-terminal nodes.
    """
    if board.is_insufficient_material():
        return 0

    mg = 0
    eg = 0

    for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP,
                       chess.ROOK, chess.QUEEN, chess.KING):
        for color in (chess.WHITE, chess.BLACK):
            sign = 1 if color == chess.WHITE else -1
            squares = board.pieces(piece_type, color)
            mg_pst = PST_MG[piece_type]
            eg_pst = PST_EG[piece_type]
            mg_v = MG_VALUE[piece_type]
            eg_v = EG_VALUE[piece_type]
            for sq in squares:
                idx = _square_index(sq, color)
                mg += sign * (mg_v + mg_pst[idx])
                eg += sign * (eg_v + eg_pst[idx])

    # Tapered blend.
    phase = _phase(board)
    score = (mg * phase + eg * (PHASE_TOTAL - phase)) // PHASE_TOTAL

    # Structural / positional terms (centipawns, white-positive).
    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        score += sign * _pawn_structure(board, color)
        score += sign * _bishop_pair(board, color)
        score += sign * _rook_open_file(board, color)
        score += sign * _king_safety(board, color)

    # Cheap mobility difference (white - black).
    score += (_mobility(board, chess.WHITE) - _mobility(board, chess.BLACK)) * 2

    # Side-to-move tempo.
    score += 10 if board.turn == chess.WHITE else -10

    return score if board.turn == chess.WHITE else -score
