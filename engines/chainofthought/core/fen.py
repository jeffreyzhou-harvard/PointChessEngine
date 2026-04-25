"""FEN parsing and serialization.

Two public functions:

* :func:`parse_fen`     - ``str -> Board``, raising ``ValueError`` on any
  malformed input (six-field FEN, well-formed placement, valid side,
  valid castling field, valid en-passant square on rank 3 or 6,
  non-negative halfmove clock, positive fullmove number).
* :func:`board_to_fen`  - ``Board -> str``.

Validation is **structural**: we check that the FEN string is
syntactically well-formed and within the obvious range checks. We do
*not* validate full chess legality of the position (e.g. both kings
present, side-not-to-move not in check, no pawn on the back rank). That
belongs to the rules stage and would otherwise force the FEN module to
depend on move generation.
"""

from __future__ import annotations

from typing import List, Optional

from .board import Board, CastlingRights
from .types import (
    Color,
    Piece,
    Square,
    square_from_algebraic,
    square_to_algebraic,
)


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------


def parse_fen(fen: str) -> Board:
    if not isinstance(fen, str):
        raise ValueError(f"FEN must be a string, got {type(fen).__name__}")

    fields = fen.strip().split()
    if len(fields) != 6:
        raise ValueError(
            f"FEN must have 6 fields (placement, side, castling, ep, "
            f"halfmove, fullmove), got {len(fields)}: {fen!r}"
        )

    placement, side, castling, ep, halfmove_str, fullmove_str = fields

    squares = _parse_placement(placement)
    turn = _parse_side(side)
    rights = CastlingRights.from_fen(castling)
    ep_square = _parse_ep(ep)
    halfmove = _parse_halfmove(halfmove_str)
    fullmove = _parse_fullmove(fullmove_str)

    return Board(
        squares=squares,
        turn=turn,
        castling=rights,
        ep_square=ep_square,
        halfmove_clock=halfmove,
        fullmove_number=fullmove,
    )


def _parse_placement(placement: str) -> List[Optional[Piece]]:
    ranks = placement.split("/")
    if len(ranks) != 8:
        raise ValueError(
            f"FEN placement must have 8 ranks separated by '/', "
            f"got {len(ranks)}: {placement!r}"
        )
    squares: List[Optional[Piece]] = [None] * 64
    # FEN ranks are listed from rank 8 down to rank 1.
    for fen_rank_idx, rank_str in enumerate(ranks):
        if not rank_str:
            raise ValueError(f"empty rank in placement: {placement!r}")
        rank = 7 - fen_rank_idx
        file = 0
        for ch in rank_str:
            if ch.isdigit():
                empties = int(ch)
                if empties < 1 or empties > 8:
                    raise ValueError(
                        f"empty-square count must be 1..8, got {ch!r} in {rank_str!r}"
                    )
                file += empties
                if file > 8:
                    raise ValueError(f"rank overflows 8 squares: {rank_str!r}")
            else:
                try:
                    piece = Piece.from_symbol(ch)
                except ValueError:
                    raise ValueError(
                        f"invalid piece symbol {ch!r} in rank {rank_str!r}"
                    ) from None
                if file >= 8:
                    raise ValueError(f"rank overflows 8 squares: {rank_str!r}")
                squares[rank * 8 + file] = piece
                file += 1
        if file != 8:
            raise ValueError(
                f"rank does not sum to 8 squares: {rank_str!r} (got {file})"
            )
    return squares


def _parse_side(text: str) -> Color:
    if text == "w":
        return Color.WHITE
    if text == "b":
        return Color.BLACK
    raise ValueError(f"side to move must be 'w' or 'b', got {text!r}")


def _parse_ep(text: str) -> Optional[Square]:
    if text == "-":
        return None
    try:
        sq = square_from_algebraic(text)
    except ValueError:
        raise ValueError(f"en-passant target must be '-' or a square, got {text!r}") from None
    rank = sq >> 3
    # White just played a double-step => ep square is on rank 3 (idx 2).
    # Black just played a double-step => ep square is on rank 6 (idx 5).
    if rank not in (2, 5):
        raise ValueError(
            f"en-passant target must be on rank 3 or 6, got {text!r}"
        )
    return sq


def _parse_halfmove(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        raise ValueError(f"halfmove clock must be an integer, got {text!r}") from None
    if n < 0:
        raise ValueError(f"halfmove clock must be >= 0, got {n}")
    return n


def _parse_fullmove(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        raise ValueError(f"fullmove number must be an integer, got {text!r}") from None
    if n < 1:
        raise ValueError(f"fullmove number must be >= 1, got {n}")
    return n


# ---------------------------------------------------------------------------
# serialize
# ---------------------------------------------------------------------------


def board_to_fen(board: Board) -> str:
    rank_strs: list[str] = []
    for rank in range(7, -1, -1):
        run = ""
        empty = 0
        for file in range(8):
            piece = board.piece_at(rank * 8 + file)
            if piece is None:
                empty += 1
            else:
                if empty:
                    run += str(empty)
                    empty = 0
                run += piece.symbol
        if empty:
            run += str(empty)
        rank_strs.append(run)
    placement = "/".join(rank_strs)

    side = "w" if board.turn is Color.WHITE else "b"
    castling = board.castling_rights.to_fen()
    ep = "-" if board.ep_square is None else square_to_algebraic(board.ep_square)
    return (
        f"{placement} {side} {castling} {ep} "
        f"{board.halfmove_clock} {board.fullmove_number}"
    )
