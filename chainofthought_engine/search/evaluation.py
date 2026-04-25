"""Static evaluation function.

Returns a centipawn score from the SIDE TO MOVE's point of view:

    > 0  =>  side to move is better
    < 0  =>  side to move is worse
    = 0  =>  equal

This perspective makes the function drop straight into a negamax
search later. Tests in this stage that want a fixed perspective
construct positions where it is White to move; then the side-to-move
score equals the white-perspective score by construction.

Term breakdown
--------------

The total score is a weighted sum:

    eval = material
         + pst
         + mobility
         + king_safety
         + pawn_structure
         + center_control
         + tempo

All terms are computed in white's perspective (positive = good for
white) and the final value is negated when it is Black to move.

1. Material balance
   Σ (white piece values) − Σ (black piece values).

2. Piece-square tables (PST)
   A per-piece, per-square lookup. The tables encode classical
   middlegame heuristics (knights toward the center, rooks on open
   ranks, kings tucked into the corner, pawns advancing). For black,
   the square is mirrored across the equator (``sq ^ 56``).

   We use a single set of tables (no separate middlegame/endgame
   phase) for stage 6. Tapered evaluation is a future tuning pass.

3. Mobility
   ``mobility_per_move * (#white_pseudo_legal − #black_pseudo_legal)``.
   Pseudo-legal is cheaper than legal and is a fine proxy here.

4. King safety
   Per side: pawn-shield bonus for own pawns one rank in front of the
   king on the king's file and the two adjacent files; penalty for
   each enemy attack on a square in the 3x3 "king zone"; penalty if
   the king's file has no friendly pawns (an open file in front of
   the king).

5. Pawn structure
   - Doubled: penalty per extra pawn on a file.
   - Isolated: penalty per pawn with no friendly pawns on either
     adjacent file.
   - Passed: bonus per pawn with no enemy pawn on the same or an
     adjacent file ahead of it.

6. Center control
   Bonus per attack on each of d4/e4/d5/e5; subtract for the enemy.

7. Tempo
   A small bonus for the side to move (added in white's perspective
   when it is White to move; otherwise subtracted).

Default weights (centipawns)
----------------------------
    pawn=100, knight=320, bishop=330, rook=500, queen=900
    pst_weight=1
    mobility_per_move=4
    king_zone_attack=-8
    pawn_shield_bonus=10
    open_file_near_king=-25
    doubled_pawn=-15
    isolated_pawn=-20
    passed_pawn=30
    center_attack=10
    tempo=10

Tunability
----------
Pass a custom :class:`Weights` to ``evaluate(board, weights=...)``
to override the defaults. A future stage can swap in tuned weights
without changing the eval logic.

Game-end handling
-----------------
- Checkmate: returns ``-MATE_SCORE`` from the mated side's POV (so
  the search sees a near-infinite negative value when the position
  is mate against it).
- Stalemate / insufficient material: returns 0 (drawn).
- Otherwise: sum of the term contributions above.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..core.board import Board
from ..core.movegen import is_square_attacked
from ..core.types import Color, Piece, PieceType, Square


MATE_SCORE: Final[int] = 100_000

CENTER_SQUARES: Final[tuple[Square, ...]] = (27, 28, 35, 36)  # d4, e4, d5, e5


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Weights:
    """Tunable evaluation weights. All values are centipawns."""

    # material
    pawn_value: int = 100
    knight_value: int = 320
    bishop_value: int = 330
    rook_value: int = 500
    queen_value: int = 900

    # term multipliers / per-unit weights
    pst_weight: int = 1
    mobility_per_move: int = 4
    king_zone_attack: int = -8           # per enemy attack on a king-zone square
    pawn_shield_bonus: int = 10          # per friendly pawn directly ahead of king
    open_file_near_king: int = -25       # if king's file has no friendly pawn
    doubled_pawn: int = -15              # per extra pawn on the same file
    isolated_pawn: int = -20             # per pawn with no neighbour on adj. files
    passed_pawn: int = 30                # per pawn with a clear path to promotion
    center_attack: int = 10              # per attack on a central square
    tempo: int = 10                      # for the side to move

    def piece_value(self, pt: PieceType) -> int:
        if pt is PieceType.PAWN:
            return self.pawn_value
        if pt is PieceType.KNIGHT:
            return self.knight_value
        if pt is PieceType.BISHOP:
            return self.bishop_value
        if pt is PieceType.ROOK:
            return self.rook_value
        if pt is PieceType.QUEEN:
            return self.queen_value
        return 0  # KING: priceless; never traded


DEFAULT_WEIGHTS: Final[Weights] = Weights()


# ---------------------------------------------------------------------------
# piece-square tables (white's perspective; ``sq ^ 56`` mirrors for black)
# index convention: 0 = a1, 7 = h1, 56 = a8, 63 = h8
# values are listed rank-1 first (so PST[:8] is the back rank)
# ---------------------------------------------------------------------------

# fmt: off
PAWN_PST: Final[tuple[int, ...]] = (
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-20,-20, 10, 10,  5,
     5, -5,-10,  0,  0,-10, -5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
     0,  0,  0,  0,  0,  0,  0,  0,
)

KNIGHT_PST: Final[tuple[int, ...]] = (
   -50,-40,-30,-30,-30,-30,-40,-50,
   -40,-20,  0,  5,  5,  0,-20,-40,
   -30,  5, 10, 15, 15, 10,  5,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  5, 15, 20, 20, 15,  5,-30,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -40,-20,  0,  0,  0,  0,-20,-40,
   -50,-40,-30,-30,-30,-30,-40,-50,
)

BISHOP_PST: Final[tuple[int, ...]] = (
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10,  5,  5, 10, 10,  5,  5,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -20,-10,-10,-10,-10,-10,-10,-20,
)

ROOK_PST: Final[tuple[int, ...]] = (
     0,  0,  5, 10, 10,  5,  0,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     5, 10, 10, 10, 10, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
)

QUEEN_PST: Final[tuple[int, ...]] = (
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  5,  0,  0,  0,  0,-10,
   -10,  5,  5,  5,  5,  5,  0,-10,
     0,  0,  5,  5,  5,  5,  0, -5,
    -5,  0,  5,  5,  5,  5,  0, -5,
   -10,  0,  5,  5,  5,  5,  0,-10,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -20,-10,-10, -5, -5,-10,-10,-20,
)

# Middlegame king PST: prefer corners (castled), avoid the center.
KING_PST: Final[tuple[int, ...]] = (
    20, 30, 10,  0,  0, 10, 30, 20,
    20, 20,  0,  0,  0,  0, 20, 20,
   -10,-20,-20,-20,-20,-20,-20,-10,
   -20,-30,-30,-40,-40,-30,-30,-20,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
)
# fmt: on

_PST: Final[dict[PieceType, tuple[int, ...]]] = {
    PieceType.PAWN: PAWN_PST,
    PieceType.KNIGHT: KNIGHT_PST,
    PieceType.BISHOP: BISHOP_PST,
    PieceType.ROOK: ROOK_PST,
    PieceType.QUEEN: QUEEN_PST,
    PieceType.KING: KING_PST,
}


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------


def evaluate(board: Board, weights: Weights = DEFAULT_WEIGHTS) -> int:
    """Static centipawn score from the side-to-move's perspective."""
    if board.is_checkmate():
        # The player to move is mated. From their POV that's the worst
        # possible outcome.
        return -MATE_SCORE
    if board.is_stalemate():
        return 0
    if board.is_insufficient_material():
        return 0

    white_score = (
        _material_term(board, weights)
        + _pst_term(board, weights)
        + _mobility_term(board, weights)
        + _king_safety_term(board, weights)
        + _pawn_structure_term(board, weights)
        + _center_control_term(board, weights)
    )
    if board.turn is Color.WHITE:
        white_score += weights.tempo
    else:
        white_score -= weights.tempo

    return white_score if board.turn is Color.WHITE else -white_score


# ---------------------------------------------------------------------------
# individual terms (all return scores in WHITE'S perspective)
# ---------------------------------------------------------------------------


def _material_term(board: Board, w: Weights) -> int:
    score = 0
    for sq in range(64):
        p = board.piece_at(sq)
        if p is None:
            continue
        v = w.piece_value(p.type)
        score += v if p.color is Color.WHITE else -v
    return score


def _pst_term(board: Board, w: Weights) -> int:
    score = 0
    for sq in range(64):
        p = board.piece_at(sq)
        if p is None:
            continue
        table = _PST[p.type]
        if p.color is Color.WHITE:
            score += table[sq] * w.pst_weight
        else:
            score -= table[sq ^ 56] * w.pst_weight
    return score


def _mobility_term(board: Board, w: Weights) -> int:
    white_moves = len(board.pseudo_legal_moves_for(Color.WHITE))
    black_moves = len(board.pseudo_legal_moves_for(Color.BLACK))
    return w.mobility_per_move * (white_moves - black_moves)


def _king_safety_term(board: Board, w: Weights) -> int:
    return _king_safety_for(board, Color.WHITE, w) - _king_safety_for(
        board, Color.BLACK, w
    )


def _king_safety_for(board: Board, color: Color, w: Weights) -> int:
    king_sq = board.king_square(color)
    if king_sq is None:
        return 0
    score = 0
    file = king_sq & 7
    rank = king_sq >> 3
    own_pawn = Piece(color, PieceType.PAWN)
    enemy = color.opponent()

    # Pawn shield: own pawns on the rank directly in front, on the
    # king's file and the two adjacent files. (Direction depends on
    # color: white shields with pawns one rank up; black, one down.)
    forward = 1 if color is Color.WHITE else -1
    shield_rank = rank + forward
    if 0 <= shield_rank < 8:
        for df in (-1, 0, 1):
            f = file + df
            if 0 <= f < 8:
                if board.piece_at(shield_rank * 8 + f) == own_pawn:
                    score += w.pawn_shield_bonus

    # King zone: the 3x3 box centred on the king. Each enemy attack
    # on a zone square is a small penalty.
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            f = file + df
            r = rank + dr
            if 0 <= f < 8 and 0 <= r < 8:
                if is_square_attacked(board, r * 8 + f, enemy):
                    score += w.king_zone_attack

    # Open file in front of the king: penalty if no friendly pawn
    # exists on the king's file.
    has_pawn_on_file = any(
        board.piece_at(r * 8 + file) == own_pawn for r in range(8)
    )
    if not has_pawn_on_file:
        score += w.open_file_near_king

    return score


def _pawn_structure_term(board: Board, w: Weights) -> int:
    return _pawn_structure_for(board, Color.WHITE, w) - _pawn_structure_for(
        board, Color.BLACK, w
    )


def _pawn_structure_for(board: Board, color: Color, w: Weights) -> int:
    files: list[int] = [0] * 8
    pawn_squares: list[Square] = []
    own_pawn = Piece(color, PieceType.PAWN)
    enemy_pawn = Piece(color.opponent(), PieceType.PAWN)

    for sq in range(64):
        if board.piece_at(sq) == own_pawn:
            files[sq & 7] += 1
            pawn_squares.append(sq)

    score = 0

    # Doubled: penalise each extra pawn on a file (so two pawns on the
    # same file = one penalty; three = two).
    for cnt in files:
        if cnt > 1:
            score += w.doubled_pawn * (cnt - 1)

    # Isolated: penalise each pawn with no friendly pawn on either
    # adjacent file.
    for sq in pawn_squares:
        f = sq & 7
        left = files[f - 1] if f > 0 else 0
        right = files[f + 1] if f < 7 else 0
        if left == 0 and right == 0:
            score += w.isolated_pawn

    # Passed: bonus if no enemy pawn on the same or adjacent file is
    # ahead of this pawn (ahead = higher rank for white, lower for black).
    for sq in pawn_squares:
        if _is_passed_pawn(board, sq, color, enemy_pawn):
            score += w.passed_pawn

    return score


def _is_passed_pawn(
    board: Board, sq: Square, color: Color, enemy_pawn: Piece
) -> bool:
    f = sq & 7
    r = sq >> 3
    if color is Color.WHITE:
        rank_range = range(r + 1, 8)
    else:
        rank_range = range(r - 1, -1, -1)
    for ar in rank_range:
        for df in (-1, 0, 1):
            af = f + df
            if 0 <= af < 8 and board.piece_at(ar * 8 + af) == enemy_pawn:
                return False
    return True


def _center_control_term(board: Board, w: Weights) -> int:
    score = 0
    for sq in CENTER_SQUARES:
        if is_square_attacked(board, sq, Color.WHITE):
            score += w.center_attack
        if is_square_attacked(board, sq, Color.BLACK):
            score -= w.center_attack
    return score
