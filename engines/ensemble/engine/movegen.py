"""Move generation: pseudo-legal, captures, and legal moves.

Per the contract:
  - generate_pseudo_legal(board) -> list[Move]
  - generate_legal(board) -> list[Move]
  - generate_captures(board) -> list[Move]
Castling is generated directly in legal form.
"""
from __future__ import annotations

from typing import List

from .board import (
    Board, Move,
    EMPTY, OFFBOARD, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    KNIGHT_OFFSETS, BISHOP_OFFSETS, ROOK_OFFSETS, KING_OFFSETS,
    WHITE, BLACK,
    CR_WK, CR_WQ, CR_BK, CR_BQ,
)
from .squares import MAILBOX64, MAILBOX120, algebraic_to_120


# Pre-cache the home/transit/dest squares for castling.
_E1 = algebraic_to_120("e1")
_F1 = algebraic_to_120("f1")
_G1 = algebraic_to_120("g1")
_D1 = algebraic_to_120("d1")
_C1 = algebraic_to_120("c1")
_B1 = algebraic_to_120("b1")
_E8 = algebraic_to_120("e8")
_F8 = algebraic_to_120("f8")
_G8 = algebraic_to_120("g8")
_D8 = algebraic_to_120("d8")
_C8 = algebraic_to_120("c8")
_B8 = algebraic_to_120("b8")


def _add_pawn_moves(board: Board, src: int, color: int, moves: List[Move], captures_only: bool = False) -> None:
    sqs = board.squares
    piece = PAWN * color
    # Direction: white moves "up" (decreasing index, since rank 1 is at the bottom of mailbox).
    fwd = -10 if color == WHITE else 10
    start_rank_top = 6 if color == WHITE else 1   # rank_from_top of starting rank
    promo_rank_top = 0 if color == WHITE else 7
    rel = src - 21
    src_rank_top = rel // 10

    one = src + fwd
    # Pushes (not in captures-only mode).
    if not captures_only and sqs[one] == EMPTY:
        if (src_rank_top + (-1 if color == WHITE else 1)) == promo_rank_top:
            for promo in (QUEEN, ROOK, BISHOP, KNIGHT):
                moves.append(Move(src, one, piece, 0, promo * color))
        else:
            moves.append(Move(src, one, piece))
            two = src + 2 * fwd
            if src_rank_top == start_rank_top and sqs[two] == EMPTY:
                moves.append(Move(src, two, piece, is_double_push=True))

    # Captures (incl. promotions and en-passant).
    for diag in (fwd - 1, fwd + 1):
        target = src + diag
        tp = sqs[target]
        if tp == OFFBOARD:
            continue
        target_rank_top = (target - 21) // 10
        if tp != EMPTY and (tp * color) < 0:
            if target_rank_top == promo_rank_top:
                for promo in (QUEEN, ROOK, BISHOP, KNIGHT):
                    moves.append(Move(src, target, piece, tp, promo * color))
            else:
                moves.append(Move(src, target, piece, tp))
        elif board.ep_square is not None and target == board.ep_square:
            moves.append(Move(src, target, piece, -PAWN * color, is_ep=True))


def _add_leaper_moves(board: Board, src: int, piece: int, offsets, moves: List[Move], captures_only: bool = False) -> None:
    sqs = board.squares
    color = 1 if piece > 0 else -1
    for d in offsets:
        target = src + d
        tp = sqs[target]
        if tp == OFFBOARD:
            continue
        if tp == EMPTY:
            if not captures_only:
                moves.append(Move(src, target, piece))
        elif (tp * color) < 0:
            moves.append(Move(src, target, piece, tp))


def _add_slider_moves(board: Board, src: int, piece: int, offsets, moves: List[Move], captures_only: bool = False) -> None:
    sqs = board.squares
    color = 1 if piece > 0 else -1
    for d in offsets:
        t = src + d
        while True:
            tp = sqs[t]
            if tp == OFFBOARD:
                break
            if tp == EMPTY:
                if not captures_only:
                    moves.append(Move(src, t, piece))
            else:
                if (tp * color) < 0:
                    moves.append(Move(src, t, piece, tp))
                break
            t += d


def _add_castling(board: Board, moves: List[Move]) -> None:
    """Castling — generated legally, including unattacked-transit checks."""
    color = board.side_to_move
    enemy = -color
    cr = board.castling_rights
    if color == WHITE:
        if cr & CR_WK:
            if (board.squares[_F1] == EMPTY and board.squares[_G1] == EMPTY
                and not board.is_square_attacked(_E1, enemy)
                and not board.is_square_attacked(_F1, enemy)
                and not board.is_square_attacked(_G1, enemy)):
                moves.append(Move(_E1, _G1, KING, is_castle=True))
        if cr & CR_WQ:
            if (board.squares[_D1] == EMPTY and board.squares[_C1] == EMPTY
                and board.squares[_B1] == EMPTY
                and not board.is_square_attacked(_E1, enemy)
                and not board.is_square_attacked(_D1, enemy)
                and not board.is_square_attacked(_C1, enemy)):
                moves.append(Move(_E1, _C1, KING, is_castle=True))
    else:
        if cr & CR_BK:
            if (board.squares[_F8] == EMPTY and board.squares[_G8] == EMPTY
                and not board.is_square_attacked(_E8, enemy)
                and not board.is_square_attacked(_F8, enemy)
                and not board.is_square_attacked(_G8, enemy)):
                moves.append(Move(_E8, _G8, -KING, is_castle=True))
        if cr & CR_BQ:
            if (board.squares[_D8] == EMPTY and board.squares[_C8] == EMPTY
                and board.squares[_B8] == EMPTY
                and not board.is_square_attacked(_E8, enemy)
                and not board.is_square_attacked(_D8, enemy)
                and not board.is_square_attacked(_C8, enemy)):
                moves.append(Move(_E8, _C8, -KING, is_castle=True))


def generate_pseudo_legal(board: Board) -> List[Move]:
    color = board.side_to_move
    moves: List[Move] = []
    sqs = board.squares
    for sq in MAILBOX64:
        p = sqs[sq]
        if p == EMPTY:
            continue
        if (p > 0) != (color > 0):
            continue
        a = abs(p)
        if a == PAWN:
            _add_pawn_moves(board, sq, color, moves)
        elif a == KNIGHT:
            _add_leaper_moves(board, sq, p, KNIGHT_OFFSETS, moves)
        elif a == BISHOP:
            _add_slider_moves(board, sq, p, BISHOP_OFFSETS, moves)
        elif a == ROOK:
            _add_slider_moves(board, sq, p, ROOK_OFFSETS, moves)
        elif a == QUEEN:
            _add_slider_moves(board, sq, p, BISHOP_OFFSETS, moves)
            _add_slider_moves(board, sq, p, ROOK_OFFSETS, moves)
        elif a == KING:
            _add_leaper_moves(board, sq, p, KING_OFFSETS, moves)
    # Castling generated legally, appended at the end.
    _add_castling(board, moves)
    return moves


def generate_captures(board: Board) -> List[Move]:
    """Pseudo-legal captures and promotions (used for quiescence)."""
    color = board.side_to_move
    moves: List[Move] = []
    sqs = board.squares
    for sq in MAILBOX64:
        p = sqs[sq]
        if p == EMPTY:
            continue
        if (p > 0) != (color > 0):
            continue
        a = abs(p)
        if a == PAWN:
            _add_pawn_moves(board, sq, color, moves, captures_only=False)
            # In captures_only=True, push-promotions are missed; include them.
            # We instead call full pawn gen and filter to captures+promotions below.
        elif a == KNIGHT:
            _add_leaper_moves(board, sq, p, KNIGHT_OFFSETS, moves, captures_only=True)
        elif a == BISHOP:
            _add_slider_moves(board, sq, p, BISHOP_OFFSETS, moves, captures_only=True)
        elif a == ROOK:
            _add_slider_moves(board, sq, p, ROOK_OFFSETS, moves, captures_only=True)
        elif a == QUEEN:
            _add_slider_moves(board, sq, p, BISHOP_OFFSETS, moves, captures_only=True)
            _add_slider_moves(board, sq, p, ROOK_OFFSETS, moves, captures_only=True)
        elif a == KING:
            _add_leaper_moves(board, sq, p, KING_OFFSETS, moves, captures_only=True)
    # Filter to captures + promotions.
    out = [m for m in moves if m.captured != EMPTY or m.promotion != EMPTY or m.is_ep]
    return out


def generate_legal(board: Board) -> List[Move]:
    pseudo = generate_pseudo_legal(board)
    legal: List[Move] = []
    for m in pseudo:
        if m.is_castle:
            # Already generated legally.
            legal.append(m)
            continue
        mover = board.side_to_move
        board.make_move(m)
        # After make_move, side_to_move flipped. Mover's king must not be in check.
        if not board.is_square_attacked(board.king_sq[mover], -mover):
            legal.append(m)
        board.unmake_move()
    return legal
