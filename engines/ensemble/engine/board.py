"""10x12 mailbox board representation.

Piece codes are signed ints:
    0 = empty
    1 = pawn, 2 = knight, 3 = bishop, 4 = rook, 5 = queen, 6 = king
    + for white, - for black
    7 = OFFBOARD sentinel (used to fill mailbox borders)

Castling rights bitmask (4 bits, KQkq):
    1 = White kingside  (K)
    2 = White queenside (Q)
    4 = Black kingside  (k)
    8 = Black queenside (q)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .squares import (
    MAILBOX64,
    MAILBOX120,
    algebraic_to_120,
    sq120_to_algebraic,
)

# Piece codes
EMPTY = 0
PAWN = 1
KNIGHT = 2
BISHOP = 3
ROOK = 4
QUEEN = 5
KING = 6
OFFBOARD = 7

WHITE = 1
BLACK = -1

# Movement offsets for the 10x12 mailbox.
KNIGHT_OFFSETS = (-21, -19, -12, -8, 8, 12, 19, 21)
BISHOP_OFFSETS = (-11, -9, 9, 11)
ROOK_OFFSETS = (-10, -1, 1, 10)
KING_OFFSETS = (-11, -10, -9, -1, 1, 9, 10, 11)
QUEEN_OFFSETS = KING_OFFSETS  # same directions but sliding

# Castling masks
CR_WK, CR_WQ, CR_BK, CR_BQ = 1, 2, 4, 8

# Update castling rights when these squares are vacated/captured-on.
# (Maps sq120 -> bits to clear from castling_rights.)
CASTLE_CLEAR_ON_MOVE = {
    # White king
    algebraic_to_120("e1"): CR_WK | CR_WQ,
    # White rooks
    algebraic_to_120("a1"): CR_WQ,
    algebraic_to_120("h1"): CR_WK,
    # Black king
    algebraic_to_120("e8"): CR_BK | CR_BQ,
    # Black rooks
    algebraic_to_120("a8"): CR_BQ,
    algebraic_to_120("h8"): CR_BK,
}

# ----------------------- Zobrist hashing -----------------------
# Pieces are indexed 0..11: P,N,B,R,Q,K (white), then black.
def _piece_index(piece: int) -> int:
    color = 0 if piece > 0 else 6
    return (abs(piece) - 1) + color


_zob_rng = random.Random(0xC0FFEE)
ZOBRIST_PIECE = [[_zob_rng.getrandbits(64) for _ in range(120)] for _ in range(12)]
ZOBRIST_SIDE = _zob_rng.getrandbits(64)
ZOBRIST_CASTLE = [_zob_rng.getrandbits(64) for _ in range(16)]
ZOBRIST_EP_FILE = [_zob_rng.getrandbits(64) for _ in range(8)]


# ----------------------- Move object ---------------------------
@dataclass(frozen=True)
class Move:
    src: int            # sq120
    dst: int            # sq120
    piece: int          # signed piece moved
    captured: int = 0   # signed piece captured (or 0)
    promotion: int = 0  # signed promotion piece (or 0)
    is_ep: bool = False
    is_castle: bool = False
    is_double_push: bool = False

    def uci(self) -> str:
        s = sq120_to_algebraic(self.src) + sq120_to_algebraic(self.dst)
        if self.promotion:
            s += "nbrq"[abs(self.promotion) - 2]
        return s


@dataclass
class Undo:
    move: Move
    captured: int
    castling_rights: int
    ep_square: Optional[int]
    halfmove_clock: int
    fullmove_number: int
    zobrist_key: int


# ----------------------- Board class ---------------------------
INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

_FEN_PIECE = {
    "P": PAWN, "N": KNIGHT, "B": BISHOP, "R": ROOK, "Q": QUEEN, "K": KING,
    "p": -PAWN, "n": -KNIGHT, "b": -BISHOP, "r": -ROOK, "q": -QUEEN, "k": -KING,
}
_PIECE_FEN = {v: k for k, v in _FEN_PIECE.items()}


class Board:
    __slots__ = (
        "squares", "side_to_move", "castling_rights", "ep_square",
        "halfmove_clock", "fullmove_number", "zobrist_key", "history",
        "king_sq",
    )

    def __init__(self) -> None:
        self.squares: List[int] = [OFFBOARD] * 120
        for sq in MAILBOX64:
            self.squares[sq] = EMPTY
        self.side_to_move: int = WHITE
        self.castling_rights: int = 0
        self.ep_square: Optional[int] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self.zobrist_key: int = 0
        self.history: List[Undo] = []
        # Cached king squares (sq120) for fast in-check tests.
        self.king_sq = {WHITE: 0, BLACK: 0}

    # ---------------- Construction / FEN ----------------
    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        b = cls()
        parts = fen.strip().split()
        if len(parts) < 4:
            raise ValueError(f"bad FEN: {fen!r}")
        placement = parts[0]
        side = parts[1]
        castling = parts[2]
        ep = parts[3]
        halfmove = parts[4] if len(parts) > 4 else "0"
        fullmove = parts[5] if len(parts) > 5 else "1"

        # Placement: rank 8 first.
        ranks = placement.split("/")
        if len(ranks) != 8:
            raise ValueError(f"bad FEN ranks: {placement!r}")
        for rank_from_top, row in enumerate(ranks):
            file = 0
            for ch in row:
                if ch.isdigit():
                    file += int(ch)
                else:
                    sq120 = 21 + file + rank_from_top * 10
                    b.squares[sq120] = _FEN_PIECE[ch]
                    file += 1
            if file != 8:
                raise ValueError(f"bad FEN rank {row!r}")

        b.side_to_move = WHITE if side == "w" else BLACK
        b.castling_rights = 0
        if "K" in castling: b.castling_rights |= CR_WK
        if "Q" in castling: b.castling_rights |= CR_WQ
        if "k" in castling: b.castling_rights |= CR_BK
        if "q" in castling: b.castling_rights |= CR_BQ
        b.ep_square = None if ep == "-" else algebraic_to_120(ep)
        b.halfmove_clock = int(halfmove)
        b.fullmove_number = int(fullmove)

        b._refresh_kings()
        b.zobrist_key = b._compute_zobrist()
        return b

    def to_fen(self) -> str:
        rows = []
        for rank_from_top in range(8):
            row = ""
            empty = 0
            for file in range(8):
                p = self.squares[21 + file + rank_from_top * 10]
                if p == EMPTY:
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += _PIECE_FEN[p]
            if empty:
                row += str(empty)
            rows.append(row)
        placement = "/".join(rows)
        side = "w" if self.side_to_move == WHITE else "b"
        c = ""
        if self.castling_rights & CR_WK: c += "K"
        if self.castling_rights & CR_WQ: c += "Q"
        if self.castling_rights & CR_BK: c += "k"
        if self.castling_rights & CR_BQ: c += "q"
        c = c or "-"
        ep = "-" if self.ep_square is None else sq120_to_algebraic(self.ep_square)
        return f"{placement} {side} {c} {ep} {self.halfmove_clock} {self.fullmove_number}"

    @classmethod
    def initial(cls) -> "Board":
        return cls.from_fen(INITIAL_FEN)

    # ---------------- Helpers ----------------
    def piece_at(self, sq: int) -> int:
        return self.squares[sq]

    def _refresh_kings(self) -> None:
        for sq in MAILBOX64:
            p = self.squares[sq]
            if p == KING:
                self.king_sq[WHITE] = sq
            elif p == -KING:
                self.king_sq[BLACK] = sq

    def _compute_zobrist(self) -> int:
        key = 0
        for sq in MAILBOX64:
            p = self.squares[sq]
            if p != EMPTY:
                key ^= ZOBRIST_PIECE[_piece_index(p)][sq]
        if self.side_to_move == BLACK:
            key ^= ZOBRIST_SIDE
        key ^= ZOBRIST_CASTLE[self.castling_rights]
        if self.ep_square is not None:
            file = (self.ep_square - 21) % 10
            key ^= ZOBRIST_EP_FILE[file]
        return key

    # ---------------- Attack detection ----------------
    def is_square_attacked(self, sq: int, by_color: int) -> bool:
        sqs = self.squares
        # Pawn attacks: white pawns attack -9,-11 (one rank up); black pawns +9,+11.
        if by_color == WHITE:
            if sqs[sq + 9] == PAWN or sqs[sq + 11] == PAWN:
                return True
        else:
            if sqs[sq - 9] == -PAWN or sqs[sq - 11] == -PAWN:
                return True
        # Knights
        target_n = KNIGHT * by_color
        for d in KNIGHT_OFFSETS:
            if sqs[sq + d] == target_n:
                return True
        # King
        target_k = KING * by_color
        for d in KING_OFFSETS:
            if sqs[sq + d] == target_k:
                return True
        # Bishops / Queens (diagonal)
        target_b = BISHOP * by_color
        target_q = QUEEN * by_color
        for d in BISHOP_OFFSETS:
            t = sq + d
            while True:
                p = sqs[t]
                if p == OFFBOARD:
                    break
                if p != EMPTY:
                    if p == target_b or p == target_q:
                        return True
                    break
                t += d
        # Rooks / Queens (orthogonal)
        target_r = ROOK * by_color
        for d in ROOK_OFFSETS:
            t = sq + d
            while True:
                p = sqs[t]
                if p == OFFBOARD:
                    break
                if p != EMPTY:
                    if p == target_r or p == target_q:
                        return True
                    break
                t += d
        return False

    def in_check(self, color: Optional[int] = None) -> bool:
        if color is None:
            color = self.side_to_move
        return self.is_square_attacked(self.king_sq[color], -color)

    # ---------------- Make / Unmake ----------------
    def make_move(self, move: Move) -> None:
        sqs = self.squares
        src, dst = move.src, move.dst
        piece = move.piece
        captured = sqs[dst]
        if move.is_ep:
            # The captured pawn is behind the destination (from mover's perspective).
            cap_sq = dst + (10 if piece > 0 else -10)
            captured = sqs[cap_sq]
        undo = Undo(
            move=move,
            captured=captured,
            castling_rights=self.castling_rights,
            ep_square=self.ep_square,
            halfmove_clock=self.halfmove_clock,
            fullmove_number=self.fullmove_number,
            zobrist_key=self.zobrist_key,
        )
        self.history.append(undo)

        key = self.zobrist_key
        # Clear ep from key (will re-add new ep below).
        if self.ep_square is not None:
            key ^= ZOBRIST_EP_FILE[(self.ep_square - 21) % 10]
        # Clear old castling rights from key.
        key ^= ZOBRIST_CASTLE[self.castling_rights]

        # Move the piece on the board.
        sqs[src] = EMPTY
        key ^= ZOBRIST_PIECE[_piece_index(piece)][src]

        # Handle capture.
        if move.is_ep:
            cap_sq = dst + (10 if piece > 0 else -10)
            cap_piece = sqs[cap_sq]
            sqs[cap_sq] = EMPTY
            key ^= ZOBRIST_PIECE[_piece_index(cap_piece)][cap_sq]
        elif captured != EMPTY:
            # capture on dst square — XOR out before placing mover.
            key ^= ZOBRIST_PIECE[_piece_index(captured)][dst]

        # Place piece (or promotion) on dst.
        placed = move.promotion if move.promotion else piece
        sqs[dst] = placed
        key ^= ZOBRIST_PIECE[_piece_index(placed)][dst]

        # Castling: move the rook.
        if move.is_castle:
            if dst == src + 2:  # kingside
                rook_from = src + 3
                rook_to = src + 1
            else:               # queenside (dst == src - 2)
                rook_from = src - 4
                rook_to = src - 1
            rook = sqs[rook_from]
            sqs[rook_from] = EMPTY
            sqs[rook_to] = rook
            key ^= ZOBRIST_PIECE[_piece_index(rook)][rook_from]
            key ^= ZOBRIST_PIECE[_piece_index(rook)][rook_to]

        # King-square cache.
        if abs(piece) == KING:
            self.king_sq[piece // abs(piece)] = dst

        # Update castling rights.
        cr = self.castling_rights
        cr &= ~CASTLE_CLEAR_ON_MOVE.get(src, 0)
        cr &= ~CASTLE_CLEAR_ON_MOVE.get(dst, 0)
        self.castling_rights = cr
        key ^= ZOBRIST_CASTLE[cr]

        # En-passant square.
        if move.is_double_push:
            self.ep_square = (src + dst) // 2
            key ^= ZOBRIST_EP_FILE[(self.ep_square - 21) % 10]
        else:
            self.ep_square = None

        # Halfmove clock.
        if abs(piece) == PAWN or captured != EMPTY:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Fullmove number / side to move.
        if self.side_to_move == BLACK:
            self.fullmove_number += 1
        self.side_to_move = -self.side_to_move
        key ^= ZOBRIST_SIDE

        self.zobrist_key = key

    def unmake_move(self) -> None:
        if not self.history:
            raise IndexError("no move to unmake")
        undo = self.history.pop()
        move = undo.move
        sqs = self.squares
        src, dst = move.src, move.dst
        piece = move.piece

        # Restore side first so king-cache logic is intuitive.
        self.side_to_move = -self.side_to_move

        # Move piece back to src (un-promote if needed).
        sqs[src] = piece
        sqs[dst] = EMPTY

        # Restore captured.
        if move.is_ep:
            cap_sq = dst + (10 if piece > 0 else -10)
            sqs[cap_sq] = undo.captured
        elif undo.captured != EMPTY:
            sqs[dst] = undo.captured

        # Castling: move the rook back.
        if move.is_castle:
            if dst == src + 2:
                rook_from = src + 3
                rook_to = src + 1
            else:
                rook_from = src - 4
                rook_to = src - 1
            rook = sqs[rook_to]
            sqs[rook_to] = EMPTY
            sqs[rook_from] = rook

        # King cache.
        if abs(piece) == KING:
            self.king_sq[piece // abs(piece)] = src

        self.castling_rights = undo.castling_rights
        self.ep_square = undo.ep_square
        self.halfmove_clock = undo.halfmove_clock
        self.fullmove_number = undo.fullmove_number
        self.zobrist_key = undo.zobrist_key

    # ---------------- Insufficient material ----------------
    def insufficient_material(self) -> bool:
        knights = bishops_w = bishops_b = 0
        bishops_w_color = []
        bishops_b_color = []
        for sq in MAILBOX64:
            p = self.squares[sq]
            if p == EMPTY or abs(p) == KING:
                continue
            if abs(p) in (PAWN, ROOK, QUEEN):
                return False
            if abs(p) == KNIGHT:
                knights += 1
            elif abs(p) == BISHOP:
                # Square color: (file + rank_from_top) parity.
                rel = sq - 21
                color = (rel // 10 + rel % 10) & 1
                if p > 0:
                    bishops_w += 1
                    bishops_w_color.append(color)
                else:
                    bishops_b += 1
                    bishops_b_color.append(color)
        minors = knights + bishops_w + bishops_b
        if minors == 0:
            return True  # K vs K
        if minors == 1:
            return True  # K+minor vs K
        # K+B vs K+B same color
        if knights == 0 and bishops_w == 1 and bishops_b == 1:
            if bishops_w_color[0] == bishops_b_color[0]:
                return True
        return False
