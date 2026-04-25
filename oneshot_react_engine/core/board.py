"""Board state and make/unmake.

The ``Board`` is intentionally a mutable mailbox-style data structure.
Move generation lives in :mod:`oneshot_react_engine.core.movegen` so this
file can stay focused on representation, FEN round-tripping, and applying /
reverting moves with full undo information.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .fen import STARTING_FEN, board_to_fen, parse_fen
from .move import Move
from .pieces import Color, Piece, PieceType
from .square import Square
from . import movegen


class Board:
    def __init__(self, fen: str = STARTING_FEN):
        self.squares: List[List[Optional[Piece]]] = [[None] * 8 for _ in range(8)]
        self.turn: Color = Color.WHITE
        self.castling_rights: Dict[str, bool] = {"K": True, "Q": True, "k": True, "q": True}
        self.en_passant: Optional[Square] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self.move_history: List[Tuple[Move, dict]] = []
        self.position_history: List[str] = []
        self._apply_fen_dict(parse_fen(fen))
        self.position_history.append(self._position_key())

    def _apply_fen_dict(self, parsed: dict) -> None:
        self.squares = parsed["squares"]
        self.turn = parsed["turn"]
        self.castling_rights = parsed["castling_rights"]
        self.en_passant = parsed["en_passant"]
        self.halfmove_clock = parsed["halfmove_clock"]
        self.fullmove_number = parsed["fullmove_number"]

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        return cls(fen)

    def to_fen(self) -> str:
        return board_to_fen(
            self.squares,
            self.turn,
            self.castling_rights,
            self.en_passant,
            self.halfmove_clock,
            self.fullmove_number,
        )

    def piece_at(self, sq: Square) -> Optional[Piece]:
        return self.squares[sq.row][sq.col]

    def find_king(self, color: Color) -> Square:
        for r in range(8):
            for c in range(8):
                p = self.squares[r][c]
                if p and p.color == color and p.piece_type == PieceType.KING:
                    return Square(r, c)
        raise ValueError(f"no {color.name} king on the board")

    # ------------------------------------------------------------------
    # Move generation pass-throughs (kept as methods for ergonomic call sites)

    def legal_moves(self) -> List[Move]:
        return movegen.legal_moves(self)

    def is_in_check(self, color: Optional[Color] = None) -> bool:
        return movegen.is_in_check(self, color if color is not None else self.turn)

    def is_square_attacked(self, sq: Square, by_color: Color) -> bool:
        return movegen.is_square_attacked(self, sq, by_color)

    # ------------------------------------------------------------------
    # Make/unmake

    def make_move(self, move: Move) -> bool:
        """Execute the move iff it is legal in the current position."""
        if move not in self.legal_moves():
            return False
        undo = self._make_move_internal(move)
        self.move_history.append((move, undo))
        self.position_history.append(self._position_key())
        return True

    def unmake_move(self) -> Optional[Move]:
        if not self.move_history:
            return None
        move, undo = self.move_history.pop()
        self.position_history.pop()
        self._unmake_move_internal(move, undo)
        return move

    def _make_move_internal(self, move: Move) -> dict:
        fr_r, fr_c = move.from_sq.row, move.from_sq.col
        to_r, to_c = move.to_sq.row, move.to_sq.col
        piece = self.squares[fr_r][fr_c]
        captured = self.squares[to_r][to_c]
        if piece is None:
            raise ValueError(f"no piece at {move.from_sq}")

        undo = {
            "captured": captured,
            "captured_sq": move.to_sq,
            "castling": dict(self.castling_rights),
            "en_passant": self.en_passant,
            "halfmove_clock": self.halfmove_clock,
            "ep_captured_sq": None,
            "ep_captured_piece": None,
            "castled_rook": None,
            "promotion": move.promotion,
        }

        if piece.piece_type == PieceType.PAWN and move.to_sq == self.en_passant:
            ep_pawn_row = fr_r
            undo["ep_captured_sq"] = Square(ep_pawn_row, to_c)
            undo["ep_captured_piece"] = self.squares[ep_pawn_row][to_c]
            self.squares[ep_pawn_row][to_c] = None

        self.squares[to_r][to_c] = piece
        self.squares[fr_r][fr_c] = None

        if move.promotion is not None:
            self.squares[to_r][to_c] = Piece(piece.color, move.promotion)

        king_row = 7 if piece.color == Color.WHITE else 0
        if piece.piece_type == PieceType.KING and abs(fr_c - to_c) == 2:
            if to_c == 6:
                rook = self.squares[king_row][7]
                self.squares[king_row][5] = rook
                self.squares[king_row][7] = None
                undo["castled_rook"] = ("K", king_row)
            elif to_c == 2:
                rook = self.squares[king_row][0]
                self.squares[king_row][3] = rook
                self.squares[king_row][0] = None
                undo["castled_rook"] = ("Q", king_row)

        self.en_passant = None
        if piece.piece_type == PieceType.PAWN and abs(fr_r - to_r) == 2:
            self.en_passant = Square((fr_r + to_r) // 2, fr_c)

        if piece.piece_type == PieceType.KING:
            if piece.color == Color.WHITE:
                self.castling_rights["K"] = False
                self.castling_rights["Q"] = False
            else:
                self.castling_rights["k"] = False
                self.castling_rights["q"] = False

        if piece.piece_type == PieceType.ROOK:
            if piece.color == Color.WHITE:
                if move.from_sq == Square(7, 7):
                    self.castling_rights["K"] = False
                elif move.from_sq == Square(7, 0):
                    self.castling_rights["Q"] = False
            else:
                if move.from_sq == Square(0, 7):
                    self.castling_rights["k"] = False
                elif move.from_sq == Square(0, 0):
                    self.castling_rights["q"] = False

        if captured is not None and captured.piece_type == PieceType.ROOK:
            if move.to_sq == Square(7, 7):
                self.castling_rights["K"] = False
            elif move.to_sq == Square(7, 0):
                self.castling_rights["Q"] = False
            elif move.to_sq == Square(0, 7):
                self.castling_rights["k"] = False
            elif move.to_sq == Square(0, 0):
                self.castling_rights["q"] = False

        if piece.piece_type == PieceType.PAWN or captured is not None:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        if self.turn == Color.BLACK:
            self.fullmove_number += 1
        self.turn = self.turn.opposite()

        return undo

    def _unmake_move_internal(self, move: Move, undo: dict) -> None:
        self.turn = self.turn.opposite()

        fr_r, fr_c = move.from_sq.row, move.from_sq.col
        to_r, to_c = move.to_sq.row, move.to_sq.col

        moved_piece = self.squares[to_r][to_c]
        if undo["promotion"] is not None and moved_piece is not None:
            moved_piece = Piece(moved_piece.color, PieceType.PAWN)

        self.squares[fr_r][fr_c] = moved_piece
        self.squares[to_r][to_c] = undo["captured"]

        ep_sq = undo["ep_captured_sq"]
        if ep_sq is not None:
            self.squares[ep_sq.row][ep_sq.col] = undo["ep_captured_piece"]

        castled = undo["castled_rook"]
        if castled is not None:
            side, row = castled
            if side == "K":
                self.squares[row][7] = self.squares[row][5]
                self.squares[row][5] = None
            else:
                self.squares[row][0] = self.squares[row][3]
                self.squares[row][3] = None

        self.castling_rights = undo["castling"]
        self.en_passant = undo["en_passant"]
        self.halfmove_clock = undo["halfmove_clock"]

        if self.turn == Color.BLACK:
            self.fullmove_number -= 1

    # ------------------------------------------------------------------
    # Game-state predicates

    def is_checkmate(self) -> bool:
        return self.is_in_check(self.turn) and not self.legal_moves()

    def is_stalemate(self) -> bool:
        return not self.is_in_check(self.turn) and not self.legal_moves()

    def is_insufficient_material(self) -> bool:
        non_kings: List[Tuple[Piece, int, int]] = []
        for r in range(8):
            for c in range(8):
                p = self.squares[r][c]
                if p and p.piece_type != PieceType.KING:
                    non_kings.append((p, r, c))

        if not non_kings:
            return True
        if len(non_kings) == 1:
            return non_kings[0][0].piece_type in (PieceType.BISHOP, PieceType.KNIGHT)
        if len(non_kings) == 2 and all(p.piece_type == PieceType.BISHOP for p, _, _ in non_kings):
            sq_colors = [(r + c) % 2 for _, r, c in non_kings]
            if sq_colors[0] == sq_colors[1]:
                return True
        return False

    def is_threefold_repetition(self) -> bool:
        if len(self.position_history) < 5:
            return False
        return self.position_history.count(self.position_history[-1]) >= 3

    def is_fifty_move_rule(self) -> bool:
        return self.halfmove_clock >= 100

    def is_draw(self) -> bool:
        return (
            self.is_stalemate()
            or self.is_insufficient_material()
            or self.is_threefold_repetition()
            or self.is_fifty_move_rule()
        )

    def is_game_over(self) -> Tuple[bool, str]:
        if self.is_checkmate():
            winner = "White" if self.turn == Color.BLACK else "Black"
            return True, f"Checkmate - {winner} wins"
        if self.is_stalemate():
            return True, "Draw by stalemate"
        if self.is_insufficient_material():
            return True, "Draw by insufficient material"
        if self.is_threefold_repetition():
            return True, "Draw by threefold repetition"
        if self.is_fifty_move_rule():
            return True, "Draw by fifty-move rule"
        return False, ""

    def result(self) -> str:
        """Return PGN result token: '1-0', '0-1', '1/2-1/2', or '*'."""
        over, reason = self.is_game_over()
        if not over:
            return "*"
        if "White wins" in reason:
            return "1-0"
        if "Black wins" in reason:
            return "0-1"
        return "1/2-1/2"

    # ------------------------------------------------------------------
    # Repetition key & utilities

    def _ep_is_actually_capturable(self) -> bool:
        if self.en_passant is None:
            return False
        ep = self.en_passant
        direction = 1 if self.turn == Color.WHITE else -1
        pawn_row = ep.row + direction
        for dc in (-1, 1):
            pc = ep.col + dc
            if 0 <= pc < 8 and 0 <= pawn_row < 8:
                p = self.squares[pawn_row][pc]
                if p and p.color == self.turn and p.piece_type == PieceType.PAWN:
                    return True
        return False

    def _position_key(self) -> str:
        """Repetition key.  Includes en-passant target only if a capture is possible."""
        rank_strs = []
        for r in range(8):
            row_str = ""
            empty = 0
            for c in range(8):
                p = self.squares[r][c]
                if p is None:
                    empty += 1
                else:
                    if empty:
                        row_str += str(empty)
                        empty = 0
                    row_str += p.fen_char()
            if empty:
                row_str += str(empty)
            rank_strs.append(row_str)
        key = "/".join(rank_strs)
        key += " w" if self.turn == Color.WHITE else " b"
        cr = "".join(ch for ch in "KQkq" if self.castling_rights.get(ch)) or "-"
        key += f" {cr}"
        if self.en_passant is not None and self._ep_is_actually_capturable():
            key += f" {self.en_passant.algebraic()}"
        else:
            key += " -"
        return key

    def perft(self, depth: int) -> int:
        """Count leaf nodes at ``depth`` for move-generation correctness tests.

        Uses the low-level make/unmake path (bypassing repetition history) for
        speed, but captures the undo dict returned by ``_make_move_internal``.
        """
        if depth == 0:
            return 1
        nodes = 0
        for move in self.legal_moves():
            undo = self._make_move_internal(move)
            nodes += self.perft(depth - 1)
            self._unmake_move_internal(move, undo)
        return nodes

    def __str__(self) -> str:
        out = []
        for r in range(8):
            line = f"{8 - r} "
            for c in range(8):
                p = self.squares[r][c]
                line += (p.symbol() if p else ".") + " "
            out.append(line)
        out.append("  a b c d e f g h")
        return "\n".join(out)
