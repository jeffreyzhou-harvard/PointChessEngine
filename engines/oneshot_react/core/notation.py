"""Standard Algebraic Notation (SAN) and Portable Game Notation (PGN)."""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from .fen import STARTING_FEN
from .move import Move
from .pieces import PieceType

if TYPE_CHECKING:  # pragma: no cover
    from .board import Board


_PIECE_LETTER = {
    PieceType.KNIGHT: "N",
    PieceType.BISHOP: "B",
    PieceType.ROOK: "R",
    PieceType.QUEEN: "Q",
    PieceType.KING: "K",
}
_PROMO_LETTER = {
    PieceType.QUEEN: "Q",
    PieceType.ROOK: "R",
    PieceType.BISHOP: "B",
    PieceType.KNIGHT: "N",
}


def move_to_san(board: "Board", move: Move) -> str:
    """Render ``move`` in SAN notation against the current position of ``board``.

    The move must be legal in ``board``.
    """
    piece = board.piece_at(move.from_sq)
    if piece is None:
        return move.uci()

    if piece.piece_type == PieceType.KING and abs(move.from_sq.col - move.to_sq.col) == 2:
        san_base = "O-O" if move.to_sq.col == 6 else "O-O-O"
        return san_base + _check_suffix(board, move)

    is_capture = (
        board.piece_at(move.to_sq) is not None
        or (piece.piece_type == PieceType.PAWN and move.to_sq == board.en_passant)
    )

    san = ""
    if piece.piece_type == PieceType.PAWN:
        if is_capture:
            san += chr(ord("a") + move.from_sq.col)
    else:
        san += _PIECE_LETTER[piece.piece_type]
        ambig = []
        for m in board.legal_moves():
            if (
                m.to_sq == move.to_sq
                and m.from_sq != move.from_sq
                and board.piece_at(m.from_sq) is not None
                and board.piece_at(m.from_sq).piece_type == piece.piece_type
                and board.piece_at(m.from_sq).color == piece.color
            ):
                ambig.append(m)
        if ambig:
            same_col = any(m.from_sq.col == move.from_sq.col for m in ambig)
            same_row = any(m.from_sq.row == move.from_sq.row for m in ambig)
            if not same_col:
                san += chr(ord("a") + move.from_sq.col)
            elif not same_row:
                san += str(8 - move.from_sq.row)
            else:
                san += chr(ord("a") + move.from_sq.col) + str(8 - move.from_sq.row)

    if is_capture:
        san += "x"
    san += move.to_sq.algebraic()
    if move.promotion is not None:
        san += "=" + _PROMO_LETTER[move.promotion]

    return san + _check_suffix(board, move)


def _check_suffix(board: "Board", move: Move) -> str:
    """Append '+' or '#' if the move gives check / checkmate."""
    undo = board._make_move_internal(move)
    suffix = ""
    if board.is_in_check(board.turn):
        suffix = "#" if not board.legal_moves() else "+"
    board._unmake_move_internal(move, undo)
    return suffix


def board_to_pgn(board: "Board", headers: Optional[Dict[str, str]] = None) -> str:
    """Export the move history of ``board`` as a PGN string."""
    from .board import Board  # local import to avoid cycles

    default_headers = {
        "Event": "PointChess ReAct Game",
        "Site": "Local",
        "Date": "????.??.??",
        "Round": "-",
        "White": "Human",
        "Black": "PointChess ReAct",
        "Result": board.result(),
    }
    if headers:
        default_headers.update(headers)

    replay = Board(STARTING_FEN)
    tokens = []
    for i, (move, _) in enumerate(board.move_history):
        if i % 2 == 0:
            tokens.append(f"{i // 2 + 1}.")
        tokens.append(move_to_san(replay, move))
        replay.make_move(move)
    tokens.append(default_headers["Result"])

    lines = [f'[{k} "{v}"]' for k, v in default_headers.items()]
    lines.append("")

    line = ""
    for tok in tokens:
        if len(line) + len(tok) + 1 > 80:
            lines.append(line)
            line = tok
        else:
            line = (line + " " + tok).strip()
    if line:
        lines.append(line)

    return "\n".join(lines) + "\n"
