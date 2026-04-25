"""Position evaluation for the chess engine.

Evaluates positions based on:
- Material balance
- Piece-square tables (positional value)
- King safety
- Mobility
- Pawn structure (doubled, isolated, passed pawns)
- Center control
"""

from engines.oneshot_nocontext.core.types import Color, PieceType, Piece, Square
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from engines.oneshot_nocontext.core.board import Board


# Material values in centipawns
PIECE_VALUES = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 20000,
}

# Piece-square tables (from White's perspective, index [row][col] where row 0 = rank 8)
# Values are centipawn bonuses for having a piece on that square

PAWN_TABLE = [
    [  0,  0,  0,  0,  0,  0,  0,  0],
    [ 50, 50, 50, 50, 50, 50, 50, 50],
    [ 10, 10, 20, 30, 30, 20, 10, 10],
    [  5,  5, 10, 25, 25, 10,  5,  5],
    [  0,  0,  0, 20, 20,  0,  0,  0],
    [  5, -5,-10,  0,  0,-10, -5,  5],
    [  5, 10, 10,-20,-20, 10, 10,  5],
    [  0,  0,  0,  0,  0,  0,  0,  0],
]

KNIGHT_TABLE = [
    [-50,-40,-30,-30,-30,-30,-40,-50],
    [-40,-20,  0,  0,  0,  0,-20,-40],
    [-30,  0, 10, 15, 15, 10,  0,-30],
    [-30,  5, 15, 20, 20, 15,  5,-30],
    [-30,  0, 15, 20, 20, 15,  0,-30],
    [-30,  5, 10, 15, 15, 10,  5,-30],
    [-40,-20,  0,  5,  5,  0,-20,-40],
    [-50,-40,-30,-30,-30,-30,-40,-50],
]

BISHOP_TABLE = [
    [-20,-10,-10,-10,-10,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0, 10, 10, 10, 10,  0,-10],
    [-10,  5,  5, 10, 10,  5,  5,-10],
    [-10,  0,  5, 10, 10,  5,  0,-10],
    [-10, 10,  5, 10, 10,  5, 10,-10],
    [-10,  5,  0,  0,  0,  0,  5,-10],
    [-20,-10,-10,-10,-10,-10,-10,-20],
]

ROOK_TABLE = [
    [  0,  0,  0,  0,  0,  0,  0,  0],
    [  5, 10, 10, 10, 10, 10, 10,  5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [ -5,  0,  0,  0,  0,  0,  0, -5],
    [  0,  0,  0,  5,  5,  0,  0,  0],
]

QUEEN_TABLE = [
    [-20,-10,-10, -5, -5,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5,  5,  5,  5,  0,-10],
    [ -5,  0,  5,  5,  5,  5,  0, -5],
    [  0,  0,  5,  5,  5,  5,  0, -5],
    [-10,  5,  5,  5,  5,  5,  0,-10],
    [-10,  0,  5,  0,  0,  0,  0,-10],
    [-20,-10,-10, -5, -5,-10,-10,-20],
]

# King middlegame - stay safe behind pawns
KING_MIDDLE_TABLE = [
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-20,-30,-30,-40,-40,-30,-30,-20],
    [-10,-20,-20,-20,-20,-20,-20,-10],
    [ 20, 20,  0,  0,  0,  0, 20, 20],
    [ 20, 30, 10,  0,  0, 10, 30, 20],
]

# King endgame - centralize
KING_END_TABLE = [
    [-50,-40,-30,-20,-20,-30,-40,-50],
    [-30,-20,-10,  0,  0,-10,-20,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-30,  0,  0,  0,  0,-30,-30],
    [-50,-30,-30,-30,-30,-30,-30,-50],
]

PST = {
    PieceType.PAWN: PAWN_TABLE,
    PieceType.KNIGHT: KNIGHT_TABLE,
    PieceType.BISHOP: BISHOP_TABLE,
    PieceType.ROOK: ROOK_TABLE,
    PieceType.QUEEN: QUEEN_TABLE,
}


def _is_endgame(board: 'Board') -> bool:
    """Simple endgame detection: no queens, or queen + minor piece only."""
    queens = 0
    minors = 0
    rooks = 0
    for r in range(8):
        for c in range(8):
            p = board.squares[r][c]
            if p and p.piece_type != PieceType.KING and p.piece_type != PieceType.PAWN:
                if p.piece_type == PieceType.QUEEN:
                    queens += 1
                elif p.piece_type == PieceType.ROOK:
                    rooks += 1
                else:
                    minors += 1
    # Endgame if no queens, or each side has at most queen + 1 minor
    return queens == 0 or (queens <= 2 and rooks == 0 and minors <= 1)


def _pawn_structure_score(board: 'Board', color: Color) -> int:
    """Evaluate pawn structure: doubled, isolated, passed pawns."""
    score = 0
    pawns_by_file = [0] * 8
    pawn_rows = [[] for _ in range(8)]

    for r in range(8):
        for c in range(8):
            p = board.squares[r][c]
            if p and p.color == color and p.piece_type == PieceType.PAWN:
                pawns_by_file[c] += 1
                pawn_rows[c].append(r)

    for c in range(8):
        if pawns_by_file[c] == 0:
            continue

        # Doubled pawns penalty
        if pawns_by_file[c] > 1:
            score -= 15 * (pawns_by_file[c] - 1)

        # Isolated pawn penalty
        has_neighbor = False
        if c > 0 and pawns_by_file[c - 1] > 0:
            has_neighbor = True
        if c < 7 and pawns_by_file[c + 1] > 0:
            has_neighbor = True
        if not has_neighbor:
            score -= 20

        # Passed pawn bonus
        for row in pawn_rows[c]:
            passed = True
            direction = -1 if color == Color.WHITE else 1
            check_start = row + direction
            check_end = 0 if color == Color.WHITE else 7

            r_range = range(check_start, check_end + direction, direction) if direction == -1 else range(check_start, check_end + 1)
            for check_row in r_range:
                if not (0 <= check_row < 8):
                    break
                for dc in [-1, 0, 1]:
                    fc = c + dc
                    if 0 <= fc < 8:
                        p = board.squares[check_row][fc]
                        if p and p.color != color and p.piece_type == PieceType.PAWN:
                            passed = False
                            break
                if not passed:
                    break
            if passed:
                # Bonus based on how far advanced
                advance = (7 - row) if color == Color.WHITE else row
                score += 20 + advance * 10

    return score


def _mobility_score(board: 'Board', color: Color) -> int:
    """Count pseudo-legal moves as a rough mobility measure."""
    count = 0
    for r in range(8):
        for c in range(8):
            p = board.squares[r][c]
            if p and p.color == color and p.piece_type not in (PieceType.PAWN, PieceType.KING):
                # Count squares attacked/accessible
                if p.piece_type == PieceType.KNIGHT:
                    for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 8 and 0 <= nc < 8:
                            target = board.squares[nr][nc]
                            if target is None or target.color != color:
                                count += 1
                elif p.piece_type in (PieceType.BISHOP, PieceType.QUEEN):
                    for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                        nr, nc = r + dr, c + dc
                        while 0 <= nr < 8 and 0 <= nc < 8:
                            target = board.squares[nr][nc]
                            if target is None:
                                count += 1
                            elif target.color != color:
                                count += 1
                                break
                            else:
                                break
                            nr += dr
                            nc += dc
                if p.piece_type in (PieceType.ROOK, PieceType.QUEEN):
                    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nr, nc = r + dr, c + dc
                        while 0 <= nr < 8 and 0 <= nc < 8:
                            target = board.squares[nr][nc]
                            if target is None:
                                count += 1
                            elif target.color != color:
                                count += 1
                                break
                            else:
                                break
                            nr += dr
                            nc += dc
    return count * 3  # 3 centipawns per mobility square


def _king_safety_score(board: 'Board', color: Color) -> int:
    """Basic king safety: pawn shield bonus."""
    king_sq = board.find_king(color)
    score = 0
    direction = -1 if color == Color.WHITE else 1

    # Check pawn shield (3 squares in front of king)
    for dc in [-1, 0, 1]:
        nr, nc = king_sq.row + direction, king_sq.col + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            p = board.squares[nr][nc]
            if p and p.color == color and p.piece_type == PieceType.PAWN:
                score += 15
            # Also check two squares ahead
            nr2 = king_sq.row + 2 * direction
            if 0 <= nr2 < 8:
                p2 = board.squares[nr2][nc]
                if p2 and p2.color == color and p2.piece_type == PieceType.PAWN:
                    score += 5

    return score


def _bishop_pair_bonus(board: 'Board', color: Color) -> int:
    """Bonus for having the bishop pair."""
    bishops = 0
    for r in range(8):
        for c in range(8):
            p = board.squares[r][c]
            if p and p.color == color and p.piece_type == PieceType.BISHOP:
                bishops += 1
    return 30 if bishops >= 2 else 0


def evaluate(board: 'Board') -> int:
    """Evaluate the position from the current player's perspective.

    Returns a score in centipawns. Positive = good for the side to move.
    """
    score = 0
    endgame = _is_endgame(board)
    king_table = KING_END_TABLE if endgame else KING_MIDDLE_TABLE

    for r in range(8):
        for c in range(8):
            piece = board.squares[r][c]
            if piece is None:
                continue

            # Material
            value = PIECE_VALUES[piece.piece_type]

            # Piece-square table
            if piece.piece_type == PieceType.KING:
                pst_value = king_table[r][c] if piece.color == Color.WHITE else king_table[7-r][c]
            elif piece.piece_type in PST:
                table = PST[piece.piece_type]
                pst_value = table[r][c] if piece.color == Color.WHITE else table[7-r][c]
            else:
                pst_value = 0

            total = value + pst_value
            if piece.color == Color.WHITE:
                score += total
            else:
                score -= total

    # Pawn structure
    score += _pawn_structure_score(board, Color.WHITE)
    score -= _pawn_structure_score(board, Color.BLACK)

    # Mobility
    score += _mobility_score(board, Color.WHITE)
    score -= _mobility_score(board, Color.BLACK)

    # King safety (mainly in middlegame)
    if not endgame:
        score += _king_safety_score(board, Color.WHITE)
        score -= _king_safety_score(board, Color.BLACK)

    # Bishop pair
    score += _bishop_pair_bonus(board, Color.WHITE)
    score -= _bishop_pair_bonus(board, Color.BLACK)

    # Return from perspective of side to move
    if board.turn == Color.BLACK:
        score = -score

    return score
