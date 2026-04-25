"""Game state: a board plus the history needed for draw rules and PGN.

A bare ``Board`` cannot, on its own, decide threefold repetition (it
needs a list of past positions) or fifty-move-rule draws by claim
(needs the position-after-each-move clock trail). It also cannot emit
a PGN, since PGN is a record of moves, not of a single position.

``GameState`` owns those concerns. Search operates on a ``Board``;
the UI and UCI operate on a ``GameState`` and hand the underlying
``Board`` to the search.

Layering note
-------------
``GameState`` depends on ``Board`` (via make/unmake) and on the
movegen-derived ``legal_moves`` for legality validation and SAN
disambiguation. It does NOT touch search/UCI/UI. PGN is a pure
serialization concern and lives entirely in this module.
"""

from __future__ import annotations

from typing import List, Optional

from .board import Board
from .move import Move
from .types import Color, PieceType, square_to_algebraic


# PGN Standard Tag Roster (STR), in canonical order.
_STR_TAGS = ("Event", "Site", "Date", "Round", "White", "Black", "Result")
_STR_DEFAULTS = {
    "Event": "?",
    "Site": "?",
    "Date": "????.??.??",
    "Round": "?",
    "White": "?",
    "Black": "?",
    "Result": "*",
}

_PIECE_LETTER = {
    PieceType.KNIGHT: "N",
    PieceType.BISHOP: "B",
    PieceType.ROOK: "R",
    PieceType.QUEEN: "Q",
    PieceType.KING: "K",
}


class GameState:
    """A live game: position + move history + draw bookkeeping."""

    def __init__(
        self,
        board: Optional[Board] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self._board: Board = board if board is not None else Board.starting_position()
        self._initial_fen: str = self._board.fen()
        self._initial_turn: Color = self._board.turn
        self._initial_fullmove: int = self._board.fullmove_number

        # Position keys: index 0 is the starting position; subsequent
        # entries are the positions AFTER each played move.
        self._position_keys: List[tuple] = [self._board.position_key()]

        # Aligned history of moves and their SAN strings.
        self._moves: List[Move] = []
        self._sans: List[str] = []

        self._headers: dict[str, str] = dict(headers) if headers else {}

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    @classmethod
    def new_game(cls) -> "GameState":
        return cls(Board.starting_position())

    @classmethod
    def from_fen(cls, fen: str) -> "GameState":
        return cls(Board.from_fen(fen))

    # ------------------------------------------------------------------
    # access
    # ------------------------------------------------------------------

    @property
    def board(self) -> Board:
        return self._board

    @property
    def initial_fen(self) -> str:
        return self._initial_fen

    def history(self) -> List[Move]:
        """Moves played in this game, oldest first."""
        return list(self._moves)

    def san_history(self) -> List[str]:
        """SAN of each played move, aligned with ``history()``."""
        return list(self._sans)

    @property
    def headers(self) -> dict[str, str]:
        """User-overridable PGN headers (mutable view)."""
        return self._headers

    def __len__(self) -> int:
        return len(self._moves)

    # ------------------------------------------------------------------
    # mutation
    # ------------------------------------------------------------------

    def play(self, move: Move) -> None:
        """Apply ``move``, recording it for PGN and draw bookkeeping.

        Raises ``ValueError`` if the move is not legal in the current
        position. SAN is computed BEFORE the move is made (so it can
        see all legal sibling moves for disambiguation), then the
        move is committed.
        """
        legal = self._board.legal_moves()
        if move not in legal:
            raise ValueError(f"illegal move: {move.uci()}")
        san = self._compute_san(move, legal)
        self._board.make_move(move)
        self._position_keys.append(self._board.position_key())
        self._moves.append(move)
        self._sans.append(san)

    def undo(self) -> Move:
        """Reverse the most recent ``play`` and return that move."""
        if not self._moves:
            raise IndexError("no move to undo")
        self._board.unmake_move()
        self._position_keys.pop()
        self._sans.pop()
        return self._moves.pop()

    # ------------------------------------------------------------------
    # draw rules that need history
    # ------------------------------------------------------------------

    def position_repetition_count(self) -> int:
        """How many times the current position has appeared so far,
        counting the current occurrence."""
        return self._position_keys.count(self._position_keys[-1])

    def is_threefold_repetition(self) -> bool:
        return self.position_repetition_count() >= 3

    def is_fivefold_repetition(self) -> bool:
        return self.position_repetition_count() >= 5

    def is_fifty_move_rule(self) -> bool:
        # FIDE: 50 moves by EACH side without pawn move or capture
        # = 100 half-moves = halfmove_clock >= 100.
        return self._board.halfmove_clock >= 100

    def is_seventy_five_move_rule(self) -> bool:
        return self._board.halfmove_clock >= 150

    def is_game_over(self) -> bool:
        if self._board.is_checkmate():
            return True
        if self._board.is_stalemate():
            return True
        if self._board.is_insufficient_material():
            return True
        if self.is_fifty_move_rule():
            return True
        if self.is_threefold_repetition():
            return True
        return False

    def result(self) -> str:
        """One of "1-0", "0-1", "1/2-1/2", "*"."""
        if self._board.is_checkmate():
            # The side to move just got mated; the OTHER side wins.
            return "0-1" if self._board.turn is Color.WHITE else "1-0"
        if (
            self._board.is_stalemate()
            or self._board.is_insufficient_material()
            or self.is_fifty_move_rule()
            or self.is_threefold_repetition()
        ):
            return "1/2-1/2"
        return "*"

    # ------------------------------------------------------------------
    # SAN
    # ------------------------------------------------------------------

    def _compute_san(self, move: Move, legal_moves: List[Move]) -> str:
        """Standard Algebraic Notation for ``move``, given the full set
        of legal moves in the current position (for disambiguation).

        Check / mate suffix is computed by playing the move on the
        underlying board, querying status, and unmaking.
        """
        board = self._board
        piece = board.piece_at(move.from_sq)
        if piece is None:
            raise ValueError("no piece on from-square")

        from_file = move.from_sq & 7
        from_rank = move.from_sq >> 3
        to_file = move.to_sq & 7

        # Castling: king moves exactly two files.
        is_castle = piece.type is PieceType.KING and abs(to_file - from_file) == 2
        if is_castle:
            san = "O-O" if to_file == 6 else "O-O-O"
        else:
            is_capture = (
                board.piece_at(move.to_sq) is not None
                or (piece.type is PieceType.PAWN and move.to_sq == board.ep_square)
            )

            if piece.type is PieceType.PAWN:
                if is_capture:
                    san = (
                        f"{chr(ord('a') + from_file)}"
                        f"x{square_to_algebraic(move.to_sq)}"
                    )
                else:
                    san = square_to_algebraic(move.to_sq)
                if move.promotion is not None:
                    san += f"={_PIECE_LETTER[move.promotion]}"
            else:
                qualifier = self._disambiguator(move, piece, legal_moves)
                san = _PIECE_LETTER[piece.type] + qualifier
                if is_capture:
                    san += "x"
                san += square_to_algebraic(move.to_sq)

        # Check / mate suffix. Playing the move temporarily is the
        # simplest correct way; the cost is one extra make/unmake per
        # SAN, which is fine for UI/PGN paths.
        board.make_move(move)
        try:
            if board.is_checkmate():
                san += "#"
            elif board.is_check():
                san += "+"
        finally:
            board.unmake_move()

        return san

    def _disambiguator(
        self, move: Move, piece, legal_moves: List[Move]
    ) -> str:
        """Return "", "<file>", "<rank>", or "<file><rank>" qualifier."""
        from_file = move.from_sq & 7
        from_rank = move.from_sq >> 3

        # Other pieces of the same type that could LEGALLY play to
        # the same destination (legal, so pinned siblings drop out).
        rivals: list[Move] = []
        for other in legal_moves:
            if other == move:
                continue
            if other.to_sq != move.to_sq:
                continue
            other_piece = self._board.piece_at(other.from_sq)
            if other_piece == piece:
                rivals.append(other)
        if not rivals:
            return ""

        same_file = any((m.from_sq & 7) == from_file for m in rivals)
        same_rank = any((m.from_sq >> 3) == from_rank for m in rivals)
        if not same_file:
            return chr(ord("a") + from_file)
        if not same_rank:
            return str(from_rank + 1)
        # Multiple rivals share both file and rank dimensions; need both.
        return f"{chr(ord('a') + from_file)}{from_rank + 1}"

    # ------------------------------------------------------------------
    # PGN
    # ------------------------------------------------------------------

    def pgn(self, headers: Optional[dict[str, str]] = None) -> str:
        """Render this game as a PGN string.

        ``headers`` may override defaults / instance headers for this
        export only (it does not mutate ``self.headers``).

        The seven Standard Tag Roster headers are always emitted.
        Non-standard starting positions also emit ``[FEN ...]`` and
        ``[SetUp "1"]``.
        """
        merged = dict(_STR_DEFAULTS)
        merged.update(self._headers)
        if headers:
            merged.update(headers)
        # Result tag should reflect current state unless the caller
        # explicitly overrode it.
        if "Result" not in self._headers and not (headers and "Result" in headers):
            merged["Result"] = self.result()

        is_custom_start = self._initial_fen != Board.STARTING_FEN
        if is_custom_start:
            merged.setdefault("FEN", self._initial_fen)
            merged.setdefault("SetUp", "1")

        lines: list[str] = []
        for tag in _STR_TAGS:
            lines.append(f'[{tag} "{merged.get(tag, "?")}"]')
        # Optional headers in deterministic order; FEN/SetUp first if present.
        ordered_extras: list[str] = []
        for tag in ("FEN", "SetUp"):
            if tag in merged and tag not in _STR_TAGS:
                ordered_extras.append(tag)
        for tag in merged:
            if tag in _STR_TAGS or tag in ("FEN", "SetUp"):
                continue
            ordered_extras.append(tag)
        for tag in ordered_extras:
            lines.append(f'[{tag} "{merged[tag]}"]')

        lines.append("")  # blank line separates header from movetext

        movetext = self._build_movetext(merged["Result"])
        lines.append(movetext)

        return "\n".join(lines) + "\n"

    def _build_movetext(self, result: str) -> str:
        tokens: list[str] = []
        turn = self._initial_turn
        fullmove = self._initial_fullmove

        for i, san in enumerate(self._sans):
            if turn is Color.WHITE:
                tokens.append(f"{fullmove}.")
            elif i == 0:
                # Game starts with Black to move (e.g. SetUp from a
                # mid-game FEN). PGN convention: "N..." prefix.
                tokens.append(f"{fullmove}...")
            tokens.append(san)
            if turn is Color.BLACK:
                fullmove += 1
            turn = Color.BLACK if turn is Color.WHITE else Color.WHITE

        tokens.append(result)
        return _wrap_tokens(tokens, max_width=80)


def _wrap_tokens(tokens: list[str], max_width: int = 80) -> str:
    """Join PGN tokens with single spaces, wrapping at ``max_width``.

    Wrapping is at token boundaries only; we never split a token like
    "Nbd2" or "1." across lines. PGN spec recommends <=80 chars.
    """
    if not tokens:
        return ""
    lines: list[str] = []
    current = tokens[0]
    for tok in tokens[1:]:
        if len(current) + 1 + len(tok) <= max_width:
            current += " " + tok
        else:
            lines.append(current)
            current = tok
    lines.append(current)
    return "\n".join(lines)
