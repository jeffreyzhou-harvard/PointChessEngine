"""Pseudo-legal and legal move generation.

Move generation is split out of ``Board`` so the board class can stay focused
on state management.  Functions here only depend on a board's read-only
attributes (``squares``, ``turn``, ``castling_rights``, ``en_passant``) and the
board's ``make_move`` / ``unmake_move`` for legality checks.

Legality is verified by trial-and-rollback (make/check/unmake) which is the
simplest, most clearly-correct approach for a Python engine.  More elaborate
pin-detection schemes were considered but rejected for clarity (see the ReAct
build log).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from .move import Move
from .pieces import Color, PieceType
from .square import Square

if TYPE_CHECKING:  # pragma: no cover
    from .board import Board


KNIGHT_OFFSETS: Tuple[Tuple[int, int], ...] = (
    (-2, -1), (-2, 1), (-1, -2), (-1, 2),
    (1, -2), (1, 2), (2, -1), (2, 1),
)
BISHOP_DIRS: Tuple[Tuple[int, int], ...] = ((-1, -1), (-1, 1), (1, -1), (1, 1))
ROOK_DIRS: Tuple[Tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))
QUEEN_DIRS: Tuple[Tuple[int, int], ...] = BISHOP_DIRS + ROOK_DIRS
KING_OFFSETS: Tuple[Tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)


def is_square_attacked(board: "Board", sq: Square, by_color: Color) -> bool:
    """Return True if ``sq`` is attacked by any piece of ``by_color``."""
    r, c = sq.row, sq.col
    sqs = board.squares

    # Pawn attacks: a white pawn on (r+1, c±1) attacks (r, c). Black mirrored.
    pawn_dir = 1 if by_color == Color.WHITE else -1
    for dc in (-1, 1):
        pr, pc = r + pawn_dir, c + dc
        if 0 <= pr < 8 and 0 <= pc < 8:
            p = sqs[pr][pc]
            if p and p.color == by_color and p.piece_type == PieceType.PAWN:
                return True

    for dr, dc in KNIGHT_OFFSETS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            p = sqs[nr][nc]
            if p and p.color == by_color and p.piece_type == PieceType.KNIGHT:
                return True

    for dr, dc in KING_OFFSETS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            p = sqs[nr][nc]
            if p and p.color == by_color and p.piece_type == PieceType.KING:
                return True

    for dr, dc in BISHOP_DIRS:
        nr, nc = r + dr, c + dc
        while 0 <= nr < 8 and 0 <= nc < 8:
            p = sqs[nr][nc]
            if p:
                if p.color == by_color and p.piece_type in (PieceType.BISHOP, PieceType.QUEEN):
                    return True
                break
            nr += dr
            nc += dc

    for dr, dc in ROOK_DIRS:
        nr, nc = r + dr, c + dc
        while 0 <= nr < 8 and 0 <= nc < 8:
            p = sqs[nr][nc]
            if p:
                if p.color == by_color and p.piece_type in (PieceType.ROOK, PieceType.QUEEN):
                    return True
                break
            nr += dr
            nc += dc

    return False


def _pawn_moves(board: "Board", sq: Square, color: Color) -> List[Move]:
    out: List[Move] = []
    r, c = sq.row, sq.col
    direction = -1 if color == Color.WHITE else 1
    start_row = 6 if color == Color.WHITE else 1
    promo_row = 0 if color == Color.WHITE else 7
    sqs = board.squares

    nr = r + direction
    if 0 <= nr < 8 and sqs[nr][c] is None:
        if nr == promo_row:
            for pt in (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT):
                out.append(Move(sq, Square(nr, c), pt))
        else:
            out.append(Move(sq, Square(nr, c)))
            if r == start_row:
                nr2 = r + 2 * direction
                if sqs[nr2][c] is None:
                    out.append(Move(sq, Square(nr2, c)))

    for dc in (-1, 1):
        nc = c + dc
        if not (0 <= nc < 8):
            continue
        nr = r + direction
        if not (0 <= nr < 8):
            continue
        target = sqs[nr][nc]
        if target is not None and target.color != color:
            if nr == promo_row:
                for pt in (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT):
                    out.append(Move(sq, Square(nr, nc), pt))
            else:
                out.append(Move(sq, Square(nr, nc)))
        if board.en_passant is not None and Square(nr, nc) == board.en_passant:
            out.append(Move(sq, board.en_passant))

    return out


def _knight_moves(board: "Board", sq: Square, color: Color) -> List[Move]:
    out: List[Move] = []
    r, c = sq.row, sq.col
    sqs = board.squares
    for dr, dc in KNIGHT_OFFSETS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            t = sqs[nr][nc]
            if t is None or t.color != color:
                out.append(Move(sq, Square(nr, nc)))
    return out


def _sliding_moves(
    board: "Board", sq: Square, color: Color, dirs: Tuple[Tuple[int, int], ...]
) -> List[Move]:
    out: List[Move] = []
    r, c = sq.row, sq.col
    sqs = board.squares
    for dr, dc in dirs:
        nr, nc = r + dr, c + dc
        while 0 <= nr < 8 and 0 <= nc < 8:
            t = sqs[nr][nc]
            if t is None:
                out.append(Move(sq, Square(nr, nc)))
            elif t.color != color:
                out.append(Move(sq, Square(nr, nc)))
                break
            else:
                break
            nr += dr
            nc += dc
    return out


def _king_moves(board: "Board", sq: Square, color: Color) -> List[Move]:
    out: List[Move] = []
    r, c = sq.row, sq.col
    sqs = board.squares
    for dr, dc in KING_OFFSETS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            t = sqs[nr][nc]
            if t is None or t.color != color:
                out.append(Move(sq, Square(nr, nc)))

    enemy = color.opposite()
    king_row = 7 if color == Color.WHITE else 0
    if r != king_row or c != 4:
        return out

    rights_k = "K" if color == Color.WHITE else "k"
    if board.castling_rights.get(rights_k):
        if (
            sqs[king_row][5] is None
            and sqs[king_row][6] is None
            and not is_square_attacked(board, Square(king_row, 4), enemy)
            and not is_square_attacked(board, Square(king_row, 5), enemy)
            and not is_square_attacked(board, Square(king_row, 6), enemy)
        ):
            out.append(Move(sq, Square(king_row, 6)))

    rights_q = "Q" if color == Color.WHITE else "q"
    if board.castling_rights.get(rights_q):
        if (
            sqs[king_row][3] is None
            and sqs[king_row][2] is None
            and sqs[king_row][1] is None
            and not is_square_attacked(board, Square(king_row, 4), enemy)
            and not is_square_attacked(board, Square(king_row, 3), enemy)
            and not is_square_attacked(board, Square(king_row, 2), enemy)
        ):
            out.append(Move(sq, Square(king_row, 2)))

    return out


def pseudo_legal_moves(board: "Board") -> List[Move]:
    """Generate moves that respect movement geometry but may leave king in check."""
    moves: List[Move] = []
    color = board.turn
    sqs = board.squares
    for r in range(8):
        for c in range(8):
            piece = sqs[r][c]
            if piece is None or piece.color != color:
                continue
            sq = Square(r, c)
            pt = piece.piece_type
            if pt == PieceType.PAWN:
                moves.extend(_pawn_moves(board, sq, color))
            elif pt == PieceType.KNIGHT:
                moves.extend(_knight_moves(board, sq, color))
            elif pt == PieceType.BISHOP:
                moves.extend(_sliding_moves(board, sq, color, BISHOP_DIRS))
            elif pt == PieceType.ROOK:
                moves.extend(_sliding_moves(board, sq, color, ROOK_DIRS))
            elif pt == PieceType.QUEEN:
                moves.extend(_sliding_moves(board, sq, color, QUEEN_DIRS))
            elif pt == PieceType.KING:
                moves.extend(_king_moves(board, sq, color))
    return moves


def legal_moves(board: "Board") -> List[Move]:
    """Filter pseudo-legal moves by simulating each and discarding king-leaves-check."""
    legal: List[Move] = []
    own_color = board.turn
    for move in pseudo_legal_moves(board):
        undo = board._make_move_internal(move)
        in_check = is_in_check(board, own_color)
        board._unmake_move_internal(move, undo)
        if not in_check:
            legal.append(move)
    return legal


def is_in_check(board: "Board", color: Color) -> bool:
    king_sq = board.find_king(color)
    return is_square_attacked(board, king_sq, color.opposite())
