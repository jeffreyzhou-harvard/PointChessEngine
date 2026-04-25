"""FEN parsing and serialization.

Kept independent of ``Board`` so that other modules can read FEN strings
without pulling in the whole rules engine.  The parser returns a plain
dictionary which ``Board._apply_fen_dict`` consumes.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .pieces import Color, FEN_TO_PIECE, Piece
from .square import Square


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def parse_fen(fen: str) -> dict:
    """Parse a FEN string into a structured dict.

    Returns keys:
        squares: 8x8 list of Optional[Piece]
        turn: Color
        castling_rights: dict[str, bool]
        en_passant: Optional[Square]
        halfmove_clock: int
        fullmove_number: int
    """
    parts = fen.strip().split()
    if len(parts) < 4:
        raise ValueError(f"FEN must have at least 4 fields: {fen!r}")
    rows = parts[0].split("/")
    if len(rows) != 8:
        raise ValueError(f"FEN board section must have 8 ranks: {fen!r}")

    squares: List[List[Optional[Piece]]] = [[None] * 8 for _ in range(8)]
    for r, row_str in enumerate(rows):
        c = 0
        for ch in row_str:
            if ch.isdigit():
                c += int(ch)
            else:
                if ch not in FEN_TO_PIECE:
                    raise ValueError(f"invalid FEN piece char {ch!r}")
                color, pt = FEN_TO_PIECE[ch]
                squares[r][c] = Piece(color, pt)
                c += 1
        if c != 8:
            raise ValueError(f"FEN rank does not fill 8 squares: {row_str!r}")

    turn = Color.WHITE if parts[1] == "w" else Color.BLACK
    castling_rights: Dict[str, bool] = {"K": False, "Q": False, "k": False, "q": False}
    if parts[2] != "-":
        for ch in parts[2]:
            if ch in castling_rights:
                castling_rights[ch] = True

    en_passant = None if parts[3] == "-" else Square.from_algebraic(parts[3])
    halfmove_clock = int(parts[4]) if len(parts) > 4 else 0
    fullmove_number = int(parts[5]) if len(parts) > 5 else 1

    return {
        "squares": squares,
        "turn": turn,
        "castling_rights": castling_rights,
        "en_passant": en_passant,
        "halfmove_clock": halfmove_clock,
        "fullmove_number": fullmove_number,
    }


def board_to_fen(
    squares: List[List[Optional[Piece]]],
    turn: Color,
    castling_rights: Dict[str, bool],
    en_passant: Optional[Square],
    halfmove_clock: int,
    fullmove_number: int,
) -> str:
    rank_strs = []
    for r in range(8):
        row_str = ""
        empty = 0
        for c in range(8):
            piece = squares[r][c]
            if piece is None:
                empty += 1
            else:
                if empty:
                    row_str += str(empty)
                    empty = 0
                row_str += piece.fen_char()
        if empty:
            row_str += str(empty)
        rank_strs.append(row_str)

    castling_str = "".join(ch for ch in "KQkq" if castling_rights.get(ch))
    if not castling_str:
        castling_str = "-"

    ep_str = en_passant.algebraic() if en_passant else "-"
    turn_str = "w" if turn == Color.WHITE else "b"

    return (
        f"{'/'.join(rank_strs)} {turn_str} {castling_str} {ep_str}"
        f" {halfmove_clock} {fullmove_number}"
    )
