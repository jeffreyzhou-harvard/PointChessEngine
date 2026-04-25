"""Pseudo-legal move generation.

Pseudo-legal moves obey piece-movement rules and board occupancy but
are NOT filtered against putting/leaving the side-to-move's own king
in check. The legality filter lives in a later stage; this module is
intentionally agnostic about it.

Inputs / outputs
----------------
* ``generate_pseudo_legal_moves(board)`` -> ``list[Move]`` for the side
  to move.
* ``generate_pseudo_legal_moves_for_square(board, sq)`` -> the subset
  originating from ``sq`` (used by tests; later by SAN/UI hints).

What is included
----------------
* pawn single push, double push, captures, promotion (one Move per
  promotion piece), en-passant captures
* knight L-jumps
* bishop / rook / queen sliding stops
* king single steps
* castling - both flanks - if all of:
    - the relevant castling right is set in the position,
    - the king is on its starting square,
    - the corresponding rook is on its starting square,
    - the squares between king and rook are empty.
  Castling is **not** filtered for "king in check", "king passes
  through attacked square", or "king lands on attacked square" - those
  are legality checks.

What is excluded (deliberately)
-------------------------------
* anything that requires knowing what squares the opponent attacks
  (king safety, pin discovery, "castle through check"); those are
  legality concerns.
"""

from __future__ import annotations

from typing import List

from .board import Board
from .move import Move
from .types import (
    Color,
    Piece,
    PieceType,
    Square,
    square_file,
    square_from_algebraic,
    square_rank,
)


# ---------------------------------------------------------------------------
# direction tables (file_delta, rank_delta)
# ---------------------------------------------------------------------------

_KNIGHT_DELTAS = (
    (2, 1), (2, -1), (-2, 1), (-2, -1),
    (1, 2), (1, -2), (-1, 2), (-1, -2),
)

_KING_DELTAS = (
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
)

_BISHOP_DIRS = ((1, 1), (-1, 1), (1, -1), (-1, -1))
_ROOK_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_QUEEN_DIRS = _BISHOP_DIRS + _ROOK_DIRS


# ---------------------------------------------------------------------------
# attack detection
# ---------------------------------------------------------------------------


def is_square_attacked(board: Board, sq: Square, by_color: Color) -> bool:
    """Does any piece of ``by_color`` currently attack ``sq``?

    "Attack" here is the standard chess sense: it includes squares the
    attacker could move to as a capture (so a pinned piece still
    "attacks" the squares it eyes), but it does NOT include squares
    blocked by intervening pieces. The piece sitting ON ``sq`` does
    not affect attacks coming through other squares.

    Used by:
      - the legality filter (king-in-check test after a candidate move)
      - the castling-path check (king's transit squares)
      - ``Board.is_check``
    """
    if not (0 <= sq < 64):
        raise ValueError(f"square out of range: {sq}")

    f = square_file(sq)
    r = square_rank(sq)

    # Knight attacks.
    for df, dr in _KNIGHT_DELTAS:
        nf, nr = f + df, r + dr
        if 0 <= nf < 8 and 0 <= nr < 8:
            p = board.piece_at(nr * 8 + nf)
            if p is not None and p.color is by_color and p.type is PieceType.KNIGHT:
                return True

    # King attacks.
    for df, dr in _KING_DELTAS:
        nf, nr = f + df, r + dr
        if 0 <= nf < 8 and 0 <= nr < 8:
            p = board.piece_at(nr * 8 + nf)
            if p is not None and p.color is by_color and p.type is PieceType.KING:
                return True

    # Pawn attacks. A white pawn on (f', r') attacks (f'+/-1, r'+1).
    # So sq=(f,r) is attacked by a white pawn sitting on (f+/-1, r-1).
    pawn_attacker_dr = -1 if by_color is Color.WHITE else 1
    for df in (-1, 1):
        nf, nr = f + df, r + pawn_attacker_dr
        if 0 <= nf < 8 and 0 <= nr < 8:
            p = board.piece_at(nr * 8 + nf)
            if p is not None and p.color is by_color and p.type is PieceType.PAWN:
                return True

    # Sliding attacks along ranks/files (rook, queen).
    for df, dr in _ROOK_DIRS:
        nf, nr = f + df, r + dr
        while 0 <= nf < 8 and 0 <= nr < 8:
            p = board.piece_at(nr * 8 + nf)
            if p is not None:
                if p.color is by_color and p.type in (PieceType.ROOK, PieceType.QUEEN):
                    return True
                break
            nf += df
            nr += dr

    # Sliding attacks along diagonals (bishop, queen).
    for df, dr in _BISHOP_DIRS:
        nf, nr = f + df, r + dr
        while 0 <= nf < 8 and 0 <= nr < 8:
            p = board.piece_at(nr * 8 + nf)
            if p is not None:
                if p.color is by_color and p.type in (PieceType.BISHOP, PieceType.QUEEN):
                    return True
                break
            nf += df
            nr += dr

    return False

# Promotion order matches conventional engine output (queen first).
PROMOTION_PIECES = (
    PieceType.QUEEN,
    PieceType.ROOK,
    PieceType.BISHOP,
    PieceType.KNIGHT,
)


# ---------------------------------------------------------------------------
# public entry points
# ---------------------------------------------------------------------------


def generate_pseudo_legal_moves(board: Board) -> List[Move]:
    """All pseudo-legal moves for the side to move."""
    moves: List[Move] = []
    color = board.turn
    for sq in range(64):
        piece = board.piece_at(sq)
        if piece is None or piece.color is not color:
            continue
        _generate_for_piece(board, sq, piece, moves)
    return moves


def generate_pseudo_legal_moves_for_square(board: Board, sq: Square) -> List[Move]:
    """Pseudo-legal moves originating from ``sq``.

    If the square is empty, or the piece on it does not belong to the
    side to move, returns an empty list.
    """
    if not (0 <= sq < 64):
        raise ValueError(f"square out of range: {sq}")
    piece = board.piece_at(sq)
    if piece is None or piece.color is not board.turn:
        return []
    moves: List[Move] = []
    _generate_for_piece(board, sq, piece, moves)
    return moves


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def _generate_for_piece(
    board: Board, sq: Square, piece: Piece, moves: List[Move]
) -> None:
    pt = piece.type
    if pt is PieceType.PAWN:
        _gen_pawn(board, sq, piece.color, moves)
    elif pt is PieceType.KNIGHT:
        _gen_step(board, sq, piece.color, _KNIGHT_DELTAS, moves)
    elif pt is PieceType.BISHOP:
        _gen_slide(board, sq, piece.color, _BISHOP_DIRS, moves)
    elif pt is PieceType.ROOK:
        _gen_slide(board, sq, piece.color, _ROOK_DIRS, moves)
    elif pt is PieceType.QUEEN:
        _gen_slide(board, sq, piece.color, _QUEEN_DIRS, moves)
    elif pt is PieceType.KING:
        _gen_step(board, sq, piece.color, _KING_DELTAS, moves)
        _gen_castling(board, sq, piece.color, moves)


# ---------------------------------------------------------------------------
# step pieces (knight, king without castling)
# ---------------------------------------------------------------------------


def _gen_step(
    board: Board,
    sq: Square,
    color: Color,
    deltas,
    moves: List[Move],
) -> None:
    f = square_file(sq)
    r = square_rank(sq)
    for df, dr in deltas:
        nf, nr = f + df, r + dr
        if not (0 <= nf < 8 and 0 <= nr < 8):
            continue
        target = nr * 8 + nf
        target_piece = board.piece_at(target)
        if target_piece is None or target_piece.color is not color:
            moves.append(Move(sq, target))


# ---------------------------------------------------------------------------
# sliding pieces (bishop, rook, queen)
# ---------------------------------------------------------------------------


def _gen_slide(
    board: Board,
    sq: Square,
    color: Color,
    dirs,
    moves: List[Move],
) -> None:
    f = square_file(sq)
    r = square_rank(sq)
    for df, dr in dirs:
        nf, nr = f + df, r + dr
        while 0 <= nf < 8 and 0 <= nr < 8:
            target = nr * 8 + nf
            target_piece = board.piece_at(target)
            if target_piece is None:
                moves.append(Move(sq, target))
            else:
                if target_piece.color is not color:
                    moves.append(Move(sq, target))
                break
            nf += df
            nr += dr


# ---------------------------------------------------------------------------
# pawns
# ---------------------------------------------------------------------------


def _gen_pawn(
    board: Board,
    sq: Square,
    color: Color,
    moves: List[Move],
) -> None:
    f = square_file(sq)
    r = square_rank(sq)

    if color is Color.WHITE:
        forward = 1
        start_rank = 1          # pawns start on rank 2 -> index 1
        promo_rank = 7          # promote on rank 8 -> index 7
        ep_capture_rank = 4     # white pawn captures ep from rank 5 -> index 4
    else:
        forward = -1
        start_rank = 6
        promo_rank = 0
        ep_capture_rank = 3

    # ---- pushes -----------------------------------------------------
    nr = r + forward
    if 0 <= nr < 8:
        target = nr * 8 + f
        if board.piece_at(target) is None:
            if nr == promo_rank:
                for promo in PROMOTION_PIECES:
                    moves.append(Move(sq, target, promo))
            else:
                moves.append(Move(sq, target))
                # double push only from starting rank, both squares empty
                if r == start_rank:
                    nr2 = r + 2 * forward
                    target2 = nr2 * 8 + f
                    if board.piece_at(target2) is None:
                        moves.append(Move(sq, target2))

    # ---- diagonal captures (incl. promotion captures + en-passant) --
    for df in (-1, 1):
        nf = f + df
        nr = r + forward
        if not (0 <= nf < 8 and 0 <= nr < 8):
            continue
        target = nr * 8 + nf
        target_piece = board.piece_at(target)
        if target_piece is not None:
            if target_piece.color is not color:
                if nr == promo_rank:
                    for promo in PROMOTION_PIECES:
                        moves.append(Move(sq, target, promo))
                else:
                    moves.append(Move(sq, target))
        else:
            # En-passant: target square must be the board's ep square,
            # and the pawn must be on the rank from which ep is possible.
            if board.ep_square == target and r == ep_capture_rank:
                moves.append(Move(sq, target))


# ---------------------------------------------------------------------------
# castling
# ---------------------------------------------------------------------------


# Pre-computed once.
_E1 = square_from_algebraic("e1")
_F1 = square_from_algebraic("f1")
_G1 = square_from_algebraic("g1")
_D1 = square_from_algebraic("d1")
_C1 = square_from_algebraic("c1")
_B1 = square_from_algebraic("b1")
_A1 = square_from_algebraic("a1")
_H1 = square_from_algebraic("h1")

_E8 = square_from_algebraic("e8")
_F8 = square_from_algebraic("f8")
_G8 = square_from_algebraic("g8")
_D8 = square_from_algebraic("d8")
_C8 = square_from_algebraic("c8")
_B8 = square_from_algebraic("b8")
_A8 = square_from_algebraic("a8")
_H8 = square_from_algebraic("h8")


def _gen_castling(
    board: Board,
    sq: Square,
    color: Color,
    moves: List[Move],
) -> None:
    rights = board.castling_rights

    if color is Color.WHITE:
        if sq != _E1:
            return
        wk = Piece(Color.WHITE, PieceType.KING)
        wr = Piece(Color.WHITE, PieceType.ROOK)
        if board.piece_at(_E1) != wk:
            return
        if rights.white_kingside:
            if (
                board.piece_at(_H1) == wr
                and board.piece_at(_F1) is None
                and board.piece_at(_G1) is None
            ):
                moves.append(Move(_E1, _G1))
        if rights.white_queenside:
            if (
                board.piece_at(_A1) == wr
                and board.piece_at(_B1) is None
                and board.piece_at(_C1) is None
                and board.piece_at(_D1) is None
            ):
                moves.append(Move(_E1, _C1))
    else:
        if sq != _E8:
            return
        bk = Piece(Color.BLACK, PieceType.KING)
        br = Piece(Color.BLACK, PieceType.ROOK)
        if board.piece_at(_E8) != bk:
            return
        if rights.black_kingside:
            if (
                board.piece_at(_H8) == br
                and board.piece_at(_F8) is None
                and board.piece_at(_G8) is None
            ):
                moves.append(Move(_E8, _G8))
        if rights.black_queenside:
            if (
                board.piece_at(_A8) == br
                and board.piece_at(_B8) is None
                and board.piece_at(_C8) is None
                and board.piece_at(_D8) is None
            ):
                moves.append(Move(_E8, _C8))
