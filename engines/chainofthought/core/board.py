"""Board state.

Stage 4 brings move application (``make_move`` / ``unmake_move``),
legal move generation (``legal_moves``), and game-status queries
(``is_check`` / ``is_checkmate`` / ``is_stalemate``).

Insufficient material is still ``NotImplementedError`` (stage 6, with
threefold repetition and fifty-move).

Representation
--------------
A flat 64-entry list of ``Optional[Piece]`` indexed by ``Square``
(0=a1, 63=h8). Position state mirrors the six FEN fields. An undo
stack (``self._history``) records what was needed to reverse each
``make_move``; ``unmake_move`` pops it.

Legality model
--------------
``legal_moves`` is built from ``pseudo_legal_moves`` with two filters:

1. **Castling pre-check.** The standard rules forbid castling out of
   check, through an attacked square, or into an attacked square. We
   verify the three relevant squares (king's start / transit / end)
   against the opponent's attack set BEFORE any state change. Doing
   this in advance avoids having to "almost-make" the move just to
   probe transit attacks.

2. **Make / king-in-check / unmake.** For every other pseudo-legal
   move, we play it, ask whether our king is now attacked, and undo.
   This catches pinned-piece moves, the en-passant discovered-check
   edge case (the captured pawn vanishes from the rank, exposing the
   king to a rook/queen on that rank), and any other tactical pin
   without dedicated code paths.

Performance is not the goal yet; correctness is. Search-time
optimizations (incremental king location, attack tables, etc.) come
later under the same public surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .move import Move
from .types import Color, Piece, PieceType, Square


@dataclass(frozen=True, slots=True)
class CastlingRights:
    white_kingside: bool = False
    white_queenside: bool = False
    black_kingside: bool = False
    black_queenside: bool = False

    @classmethod
    def all(cls) -> "CastlingRights":
        return cls(True, True, True, True)

    @classmethod
    def none(cls) -> "CastlingRights":
        return cls(False, False, False, False)

    def to_fen(self) -> str:
        out = (
            ("K" if self.white_kingside else "")
            + ("Q" if self.white_queenside else "")
            + ("k" if self.black_kingside else "")
            + ("q" if self.black_queenside else "")
        )
        return out or "-"

    @classmethod
    def from_fen(cls, text: str) -> "CastlingRights":
        if text == "-":
            return cls.none()
        if not text:
            raise ValueError("castling field is empty")
        valid = set("KQkq")
        bad = [ch for ch in text if ch not in valid]
        if bad:
            raise ValueError(f"invalid character(s) in castling field: {''.join(bad)!r}")
        if len(set(text)) != len(text):
            raise ValueError(f"duplicate character in castling field: {text!r}")
        return cls(
            white_kingside="K" in text,
            white_queenside="Q" in text,
            black_kingside="k" in text,
            black_queenside="q" in text,
        )


# Castling-relevant square indexes, used by make_move's rights bookkeeping.
_A1 = 0
_E1 = 4
_H1 = 7
_A8 = 56
_E8 = 60
_H8 = 63


@dataclass(frozen=True, slots=True)
class _UndoInfo:
    """Everything needed to reverse one ``make_move``."""

    move: Move
    captured_piece: Optional[Piece]
    captured_sq: Square                 # differs from move.to_sq for ep
    prev_castling: CastlingRights
    prev_ep_square: Optional[Square]
    prev_halfmove_clock: int
    prev_fullmove_number: int
    is_castle: bool
    is_ep: bool


class Board:
    """Mutable chess position with full move application."""

    STARTING_FEN: str = (
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        squares: Optional[list[Optional[Piece]]] = None,
        turn: Color = Color.WHITE,
        castling: Optional[CastlingRights] = None,
        ep_square: Optional[Square] = None,
        halfmove_clock: int = 0,
        fullmove_number: int = 1,
    ) -> None:
        if squares is None:
            squares = [None] * 64
        elif len(squares) != 64:
            raise ValueError(f"squares must have length 64, got {len(squares)}")
        if ep_square is not None and not (0 <= ep_square < 64):
            raise ValueError(f"ep_square out of range: {ep_square}")
        if halfmove_clock < 0:
            raise ValueError(f"halfmove_clock must be >= 0, got {halfmove_clock}")
        if fullmove_number < 1:
            raise ValueError(f"fullmove_number must be >= 1, got {fullmove_number}")

        self._squares: list[Optional[Piece]] = list(squares)
        self._turn: Color = turn
        self._castling: CastlingRights = (
            castling if castling is not None else CastlingRights.none()
        )
        self._ep_square: Optional[Square] = ep_square
        self._halfmove_clock: int = halfmove_clock
        self._fullmove_number: int = fullmove_number
        self._history: List[_UndoInfo] = []

    @classmethod
    def empty(cls) -> "Board":
        return cls()

    @classmethod
    def starting_position(cls) -> "Board":
        return cls.from_fen(cls.STARTING_FEN)

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        from .fen import parse_fen
        return parse_fen(fen)

    def fen(self) -> str:
        from .fen import board_to_fen
        return board_to_fen(self)

    def copy(self) -> "Board":
        b = Board(
            squares=list(self._squares),
            turn=self._turn,
            castling=self._castling,
            ep_square=self._ep_square,
            halfmove_clock=self._halfmove_clock,
            fullmove_number=self._fullmove_number,
        )
        # Shallow-copy is correct: _UndoInfo is frozen.
        b._history = list(self._history)
        return b

    # ------------------------------------------------------------------
    # value semantics (position-only; history is bookkeeping)
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return NotImplemented
        return (
            self._squares == other._squares
            and self._turn == other._turn
            and self._castling == other._castling
            and self._ep_square == other._ep_square
            and self._halfmove_clock == other._halfmove_clock
            and self._fullmove_number == other._fullmove_number
        )

    def __hash__(self) -> int:
        return hash(
            (
                tuple(self._squares),
                int(self._turn),
                self._castling,
                self._ep_square,
                self._halfmove_clock,
                self._fullmove_number,
            )
        )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"Board(fen={self.fen()!r})"

    # ------------------------------------------------------------------
    # inspection
    # ------------------------------------------------------------------

    def piece_at(self, sq: Square) -> Optional[Piece]:
        if not (0 <= sq < 64):
            raise ValueError(f"square out of range: {sq}")
        return self._squares[sq]

    def set_piece_at(self, sq: Square, piece: Optional[Piece]) -> None:
        """Direct mailbox edit. Setup-only; bypasses bookkeeping."""
        if not (0 <= sq < 64):
            raise ValueError(f"square out of range: {sq}")
        self._squares[sq] = piece

    @property
    def turn(self) -> Color:
        return self._turn

    @property
    def castling_rights(self) -> CastlingRights:
        return self._castling

    @property
    def ep_square(self) -> Optional[Square]:
        return self._ep_square

    @property
    def halfmove_clock(self) -> int:
        return self._halfmove_clock

    @property
    def fullmove_number(self) -> int:
        return self._fullmove_number

    @property
    def move_history_length(self) -> int:
        """Number of made-but-not-unmade moves; useful in tests."""
        return len(self._history)

    # ------------------------------------------------------------------
    # move generation
    # ------------------------------------------------------------------

    def pseudo_legal_moves(self) -> list[Move]:
        from .movegen import generate_pseudo_legal_moves
        return generate_pseudo_legal_moves(self)

    def legal_moves(self) -> list[Move]:
        """All legal moves for the side to move.

        Pseudo-legal output filtered such that the moving side's king
        is not in check after the move, and castling rules about
        check/transit/destination are obeyed.
        """
        from .movegen import is_square_attacked

        own = self._turn
        enemy = own.opponent()
        legal: list[Move] = []

        for move in self.pseudo_legal_moves():
            if self._is_castling_move(move):
                if not self._castling_path_safe(move, enemy):
                    continue

            self.make_move(move)
            king_sq = self._find_king(own)
            if king_sq is None or not is_square_attacked(self, king_sq, enemy):
                legal.append(move)
            self.unmake_move()

        return legal

    def is_legal(self, move: Move) -> bool:
        return move in self.legal_moves()

    # ------------------------------------------------------------------
    # status queries
    # ------------------------------------------------------------------

    def is_check(self) -> bool:
        """Is the side to move currently in check?"""
        from .movegen import is_square_attacked

        king_sq = self._find_king(self._turn)
        if king_sq is None:
            return False
        return is_square_attacked(self, king_sq, self._turn.opponent())

    def is_checkmate(self) -> bool:
        return self.is_check() and not self.legal_moves()

    def is_stalemate(self) -> bool:
        return (not self.is_check()) and not self.legal_moves()

    def is_insufficient_material(self) -> bool:
        """Position has too little material for either side to mate.

        Standard FIDE-ish interpretation:

          - K vs K
          - K + (single B or N) vs K
          - K + bishops vs K + bishops, ALL bishops on the same color
            complex of squares

        Pawns, rooks, and queens always leave mate possible; so does
        K + N + N (forced mate is impossible against a defending king,
        but a mate position is reachable, so FIDE does NOT rule this
        as insufficient under Article 5.2.2).
        """
        white_pieces: list[tuple[Square, Piece]] = []
        black_pieces: list[tuple[Square, Piece]] = []
        for sq, p in enumerate(self._squares):
            if p is None or p.type is PieceType.KING:
                continue
            if p.type in (PieceType.PAWN, PieceType.ROOK, PieceType.QUEEN):
                return False
            if p.color is Color.WHITE:
                white_pieces.append((sq, p))
            else:
                black_pieces.append((sq, p))

        # K vs K
        if not white_pieces and not black_pieces:
            return True
        # K + minor vs K
        if len(white_pieces) == 1 and not black_pieces:
            return True
        if len(black_pieces) == 1 and not white_pieces:
            return True
        # K + bishop(s) vs K + bishop(s), all bishops on one square color
        all_pieces = white_pieces + black_pieces
        if all(p.type is PieceType.BISHOP for _, p in all_pieces):
            colors = {((sq & 7) + (sq >> 3)) & 1 for sq, _ in all_pieces}
            if len(colors) <= 1:
                return True
        return False

    # ------------------------------------------------------------------
    # repetition support
    # ------------------------------------------------------------------

    def position_key(self) -> tuple:
        """Hashable position-only key for repetition detection.

        Includes piece placement, side to move, castling rights, and
        an *effective* en-passant square (the raw ep target only counts
        when an enemy pawn could actually capture there; see
        ``_effective_ep_square``). Excludes halfmove/fullmove counters,
        because two positions reached on different moves are still the
        "same position" for repetition purposes.
        """
        return (
            tuple(self._squares),
            int(self._turn),
            self._castling,
            self._effective_ep_square(),
        )

    def _effective_ep_square(self) -> Optional[Square]:
        """The ep_square if an enemy pawn could pseudo-legally capture
        there, else None.

        FIDE Article 9.2 says two positions are equal only if the same
        moves are available, including en passant. Tracking the raw
        ep_square would over-count differences whenever a double push
        was made but no capturing pawn is in place to use it.
        """
        if self._ep_square is None:
            return None
        ep_file = self._ep_square & 7
        ep_rank = self._ep_square >> 3
        capturer_rank = ep_rank - 1 if self._turn is Color.WHITE else ep_rank + 1
        if not (0 <= capturer_rank < 8):
            return None
        for df in (-1, 1):
            f = ep_file + df
            if 0 <= f < 8:
                p = self._squares[capturer_rank * 8 + f]
                if p is not None and p.color is self._turn and p.type is PieceType.PAWN:
                    return self._ep_square
        return None

    # ------------------------------------------------------------------
    # mutation: make / unmake
    # ------------------------------------------------------------------

    def make_move(self, move: Move) -> None:
        """Apply ``move`` in place. Caller must already know ``move`` is
        at least pseudo-legal; full legality is the caller's job (or use
        ``is_legal``).

        Bookkeeping handled here:
          - removes the captured piece (handles en-passant capture
            square correctly)
          - moves the rook on castling
          - replaces the pawn with the promotion piece on promotion
          - updates castling rights (king/rook moves, capture of a rook
            on its starting corner)
          - sets / clears the en-passant target square
          - advances halfmove clock (or resets on capture/pawn move)
          - increments fullmove number after Black's move
          - flips side to move
          - pushes a ``_UndoInfo`` so ``unmake_move`` can reverse it
        """
        from_sq = move.from_sq
        to_sq = move.to_sq
        promotion = move.promotion

        piece = self._squares[from_sq]
        if piece is None:
            raise ValueError(f"no piece on {from_sq} to move")

        captured = self._squares[to_sq]
        captured_sq = to_sq

        is_ep = (
            piece.type is PieceType.PAWN
            and to_sq == self._ep_square
            and captured is None
        )
        if is_ep:
            # Captured pawn sits one rank back from the destination,
            # i.e. on the from-square's rank, on the to-square's file.
            captured_sq = (from_sq // 8) * 8 + (to_sq % 8)
            captured = self._squares[captured_sq]
            if captured is None or captured.type is not PieceType.PAWN:
                raise ValueError("en-passant target square has no captured pawn")

        is_castle = (
            piece.type is PieceType.KING
            and abs((to_sq & 7) - (from_sq & 7)) == 2
        )
        is_double_push = (
            piece.type is PieceType.PAWN
            and abs(to_sq - from_sq) == 16
        )

        # ---- record undo info BEFORE mutating ----
        self._history.append(
            _UndoInfo(
                move=move,
                captured_piece=captured,
                captured_sq=captured_sq,
                prev_castling=self._castling,
                prev_ep_square=self._ep_square,
                prev_halfmove_clock=self._halfmove_clock,
                prev_fullmove_number=self._fullmove_number,
                is_castle=is_castle,
                is_ep=is_ep,
            )
        )

        # ---- apply ----
        if is_ep:
            self._squares[captured_sq] = None

        self._squares[from_sq] = None
        if promotion is not None:
            self._squares[to_sq] = Piece(piece.color, promotion)
        else:
            self._squares[to_sq] = piece

        if is_castle:
            rank_base = (to_sq // 8) * 8
            if (to_sq & 7) == 6:                       # king-side, king lands on g
                rook_from = rank_base + 7              # h-file
                rook_to = rank_base + 5                # f-file
            else:                                      # queen-side, king lands on c
                rook_from = rank_base + 0              # a-file
                rook_to = rank_base + 3                # d-file
            self._squares[rook_to] = self._squares[rook_from]
            self._squares[rook_from] = None

        # ---- castling rights bookkeeping ----
        wk = self._castling.white_kingside
        wq = self._castling.white_queenside
        bk = self._castling.black_kingside
        bq = self._castling.black_queenside
        if piece.type is PieceType.KING:
            if piece.color is Color.WHITE:
                wk = wq = False
            else:
                bk = bq = False
        # A move FROM or TO a corner kills the corresponding right
        # (rook moves out of the corner, or a rook in the corner is
        # captured / replaced).
        if from_sq == _A1 or to_sq == _A1:
            wq = False
        if from_sq == _H1 or to_sq == _H1:
            wk = False
        if from_sq == _A8 or to_sq == _A8:
            bq = False
        if from_sq == _H8 or to_sq == _H8:
            bk = False
        self._castling = CastlingRights(wk, wq, bk, bq)

        # ---- ep square ----
        if is_double_push:
            self._ep_square = (from_sq + to_sq) // 2
        else:
            self._ep_square = None

        # ---- counters ----
        if piece.type is PieceType.PAWN or captured is not None:
            self._halfmove_clock = 0
        else:
            self._halfmove_clock += 1
        if piece.color is Color.BLACK:
            self._fullmove_number += 1

        self._turn = piece.color.opponent()

    def unmake_move(self) -> None:
        if not self._history:
            raise IndexError("no move to unmake")
        undo = self._history.pop()
        move = undo.move
        from_sq = move.from_sq
        to_sq = move.to_sq

        # Reverse counters / state first.
        self._castling = undo.prev_castling
        self._ep_square = undo.prev_ep_square
        self._halfmove_clock = undo.prev_halfmove_clock
        self._fullmove_number = undo.prev_fullmove_number
        self._turn = self._turn.opponent()

        # Move the moving piece back. If it was promoted, restore the pawn.
        moved_piece = self._squares[to_sq]
        if move.promotion is not None and moved_piece is not None:
            moved_piece = Piece(moved_piece.color, PieceType.PAWN)
        self._squares[from_sq] = moved_piece
        self._squares[to_sq] = None

        # Put the captured piece back on its actual square (ep != to_sq).
        if undo.captured_piece is not None:
            self._squares[undo.captured_sq] = undo.captured_piece

        # Undo the rook hop on castling.
        if undo.is_castle:
            rank_base = (to_sq // 8) * 8
            if (to_sq & 7) == 6:
                rook_from = rank_base + 7
                rook_to = rank_base + 5
            else:
                rook_from = rank_base + 0
                rook_to = rank_base + 3
            self._squares[rook_from] = self._squares[rook_to]
            self._squares[rook_to] = None

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def king_square(self, color: Color) -> Optional[Square]:
        """Square of the king of ``color``, or None if no such king."""
        return self._find_king(color)

    def pseudo_legal_moves_for(self, color: Color) -> list[Move]:
        """Pseudo-legal moves for ``color`` regardless of whose turn it is.

        Used by evaluation (mobility) and by other inspection utilities
        that need "what could side X play here" without committing the
        position. Internally swaps the turn for the duration of move
        generation; safe because ``pseudo_legal_moves`` does no caching.
        """
        if self._turn is color:
            return self.pseudo_legal_moves()
        saved = self._turn
        self._turn = color
        try:
            return self.pseudo_legal_moves()
        finally:
            self._turn = saved

    def _find_king(self, color: Color) -> Optional[Square]:
        target = Piece(color, PieceType.KING)
        for sq, piece in enumerate(self._squares):
            if piece == target:
                return sq
        return None

    def _is_castling_move(self, move: Move) -> bool:
        piece = self._squares[move.from_sq]
        if piece is None or piece.type is not PieceType.KING:
            return False
        return abs((move.to_sq & 7) - (move.from_sq & 7)) == 2

    def _castling_path_safe(self, move: Move, enemy: Color) -> bool:
        """Standard rule: king must not be in check, must not transit
        through an attacked square, must not land on an attacked square.
        """
        from .movegen import is_square_attacked

        from_sq = move.from_sq
        to_sq = move.to_sq
        # The transit square is the one between from and to (king moves
        # exactly two files, so this is the average).
        transit = (from_sq + to_sq) // 2
        for sq in (from_sq, transit, to_sq):
            if is_square_attacked(self, sq, enemy):
                return False
        return True
