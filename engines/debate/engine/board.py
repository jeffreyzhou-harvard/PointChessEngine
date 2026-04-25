"""Board representation and make/unmake.

8x8 mailbox in a flat 64-element list. Index 0 = a1, 7 = h1, 56 = a8, 63 = h8
(`sq = rank * 8 + file`).

Piece encoding: integers. EMPTY = 0. White pieces = 1..6 (P,N,B,R,Q,K).
Black pieces = 9..14 (P,N,B,R,Q,K). Color bit = piece & 8. Type = piece & 7.
"""

from __future__ import annotations

from collections import namedtuple
from typing import List, Optional, Tuple

# --- Piece constants -------------------------------------------------------

EMPTY = 0
WHITE = 0
BLACK = 1

# type bits
PAWN = 1
KNIGHT = 2
BISHOP = 3
ROOK = 4
QUEEN = 5
KING = 6

WP, WN, WB, WR, WQ, WK = 1, 2, 3, 4, 5, 6
BP, BN, BB, BR, BQ, BK = 9, 10, 11, 12, 13, 14

PIECE_CHARS = {
    EMPTY: ".",
    WP: "P", WN: "N", WB: "B", WR: "R", WQ: "Q", WK: "K",
    BP: "p", BN: "n", BB: "b", BR: "r", BQ: "q", BK: "k",
}
CHAR_TO_PIECE = {v: k for k, v in PIECE_CHARS.items() if k != EMPTY}

# castling rights bits
CR_WK = 1
CR_WQ = 2
CR_BK = 4
CR_BQ = 8


def sq(file: int, rank: int) -> int:
    return rank * 8 + file


def file_of(s: int) -> int:
    return s & 7


def rank_of(s: int) -> int:
    return s >> 3


def mirror(s: int) -> int:
    """Mirror square vertically (used to look up black PSTs)."""
    return s ^ 56


def color_of(piece: int) -> int:
    """Returns 0 (white) or 1 (black). Undefined for EMPTY."""
    return 1 if piece & 8 else 0


def type_of(piece: int) -> int:
    return piece & 7


def make_piece(color: int, ptype: int) -> int:
    return ptype | (8 if color == BLACK else 0)


def square_name(s: int) -> str:
    return "abcdefgh"[file_of(s)] + "12345678"[rank_of(s)]


def parse_square(name: str) -> int:
    f = "abcdefgh".index(name[0])
    r = "12345678".index(name[1])
    return sq(f, r)


# --- Move ------------------------------------------------------------------

# flag bits
F_QUIET = 0
F_CAPTURE = 1
F_EP = 2
F_CASTLE = 4
F_DOUBLE = 8
F_PROMO = 16

Move = namedtuple("Move", ["from_sq", "to_sq", "promo", "flags"])


def move_uci(m: Move) -> str:
    s = square_name(m.from_sq) + square_name(m.to_sq)
    if m.promo:
        s += {KNIGHT: "n", BISHOP: "b", ROOK: "r", QUEEN: "q"}[m.promo]
    return s


def move_from_uci(board: "Board", s: str) -> Optional[Move]:
    """Parse a UCI move string against the current position to recover full flags."""
    from_sq = parse_square(s[0:2])
    to_sq = parse_square(s[2:4])
    promo = 0
    if len(s) >= 5:
        promo = {"n": KNIGHT, "b": BISHOP, "r": ROOK, "q": QUEEN}.get(s[4].lower(), 0)
    # find a matching legal move
    from .movegen import generate_legal_moves
    for m in generate_legal_moves(board, board.side_to_move):
        if m.from_sq == from_sq and m.to_sq == to_sq and m.promo == promo:
            return m
    return None


# --- Board -----------------------------------------------------------------


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class Board:
    __slots__ = (
        "squares", "side_to_move", "castling_rights", "ep_square",
        "halfmove_clock", "fullmove_number", "zobrist_key",
        "history", "king_sq",
    )

    def __init__(self):
        self.squares: List[int] = [EMPTY] * 64
        self.side_to_move: int = WHITE
        self.castling_rights: int = 0
        self.ep_square: int = -1
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self.zobrist_key: int = 0
        self.history: list = []
        # cached king squares: [white_king_sq, black_king_sq]
        self.king_sq: List[int] = [-1, -1]

    # --- copy ---------------------------------------------------------
    def copy(self) -> "Board":
        b = Board()
        b.squares = self.squares[:]
        b.side_to_move = self.side_to_move
        b.castling_rights = self.castling_rights
        b.ep_square = self.ep_square
        b.halfmove_clock = self.halfmove_clock
        b.fullmove_number = self.fullmove_number
        b.zobrist_key = self.zobrist_key
        b.history = []  # do not share undo stack
        b.king_sq = self.king_sq[:]
        return b

    # --- FEN ----------------------------------------------------------
    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        b = cls()
        parts = fen.strip().split()
        if len(parts) < 4:
            raise ValueError(f"Invalid FEN: {fen!r}")
        placement = parts[0]
        rows = placement.split("/")
        if len(rows) != 8:
            raise ValueError(f"FEN must have 8 ranks: {fen!r}")
        for i, row in enumerate(rows):
            r = 7 - i  # rows top-to-bottom = rank 8..1
            f = 0
            for c in row:
                if c.isdigit():
                    f += int(c)
                else:
                    p = CHAR_TO_PIECE[c]
                    s = sq(f, r)
                    b.squares[s] = p
                    if p == WK:
                        b.king_sq[WHITE] = s
                    elif p == BK:
                        b.king_sq[BLACK] = s
                    f += 1
        b.side_to_move = WHITE if parts[1] == "w" else BLACK
        cr = 0
        if "K" in parts[2]:
            cr |= CR_WK
        if "Q" in parts[2]:
            cr |= CR_WQ
        if "k" in parts[2]:
            cr |= CR_BK
        if "q" in parts[2]:
            cr |= CR_BQ
        b.castling_rights = cr
        b.ep_square = -1 if parts[3] == "-" else parse_square(parts[3])
        b.halfmove_clock = int(parts[4]) if len(parts) > 4 else 0
        b.fullmove_number = int(parts[5]) if len(parts) > 5 else 1

        from .zobrist import compute_zobrist
        b.zobrist_key = compute_zobrist(b)
        return b

    @classmethod
    def starting_position(cls) -> "Board":
        return cls.from_fen(STARTING_FEN)

    def to_fen(self) -> str:
        rows = []
        for r in range(7, -1, -1):
            row = ""
            empty = 0
            for f in range(8):
                p = self.squares[sq(f, r)]
                if p == EMPTY:
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += PIECE_CHARS[p]
            if empty:
                row += str(empty)
            rows.append(row)
        placement = "/".join(rows)
        stm = "w" if self.side_to_move == WHITE else "b"
        cr = ""
        if self.castling_rights & CR_WK: cr += "K"
        if self.castling_rights & CR_WQ: cr += "Q"
        if self.castling_rights & CR_BK: cr += "k"
        if self.castling_rights & CR_BQ: cr += "q"
        if not cr:
            cr = "-"
        ep = "-" if self.ep_square < 0 else square_name(self.ep_square)
        return f"{placement} {stm} {cr} {ep} {self.halfmove_clock} {self.fullmove_number}"

    # --- pretty print ------------------------------------------------
    def __str__(self) -> str:
        out = []
        for r in range(7, -1, -1):
            row = []
            for f in range(8):
                row.append(PIECE_CHARS[self.squares[sq(f, r)]])
            out.append(str(r + 1) + " " + " ".join(row))
        out.append("  a b c d e f g h")
        return "\n".join(out)

    # --- make / unmake ----------------------------------------------
    def make_move(self, m: Move) -> None:
        from .zobrist import (
            ZOB_PIECE, ZOB_SIDE, ZOB_CASTLE, ZOB_EP_FILE,
        )

        sqs = self.squares
        frm = m.from_sq
        to = m.to_sq
        flags = m.flags
        moved = sqs[frm]
        moved_type = moved & 7
        moved_color = 1 if moved & 8 else 0
        captured = sqs[to]

        # save undo record BEFORE mutation
        undo = (
            m, captured,
            self.castling_rights, self.ep_square,
            self.halfmove_clock, self.fullmove_number,
            self.zobrist_key,
            self.king_sq[0], self.king_sq[1],
        )
        self.history.append(undo)

        key = self.zobrist_key
        # remove ep file from key
        if self.ep_square >= 0:
            key ^= ZOB_EP_FILE[file_of(self.ep_square)]

        # remove castling-rights bits from key (we'll xor new in at end)
        key ^= ZOB_CASTLE[self.castling_rights]

        # halfmove clock
        if moved_type == PAWN or captured != EMPTY or (flags & F_EP):
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # handle en passant capture (captured pawn is on a different square)
        if flags & F_EP:
            cap_sq = to + (-8 if moved_color == WHITE else 8)
            cap_piece = sqs[cap_sq]
            sqs[cap_sq] = EMPTY
            key ^= ZOB_PIECE[cap_piece][cap_sq]
            captured_record = cap_piece
            # rewrite history entry's "captured" to be the ep pawn for unmake
            # simpler: encode ep capture sq via flags; we re-derive on unmake
        else:
            if captured != EMPTY:
                key ^= ZOB_PIECE[captured][to]

        # move the piece
        sqs[frm] = EMPTY
        key ^= ZOB_PIECE[moved][frm]

        # promotion?
        if m.promo:
            promoted = make_piece(moved_color, m.promo)
            sqs[to] = promoted
            key ^= ZOB_PIECE[promoted][to]
        else:
            sqs[to] = moved
            key ^= ZOB_PIECE[moved][to]

        # update king cache
        if moved_type == KING:
            self.king_sq[moved_color] = to

        # castling: move the rook
        if flags & F_CASTLE:
            if to == 6:  # white kingside, g1
                sqs[5] = sqs[7]; sqs[7] = EMPTY
                key ^= ZOB_PIECE[WR][7]; key ^= ZOB_PIECE[WR][5]
            elif to == 2:  # white queenside, c1
                sqs[3] = sqs[0]; sqs[0] = EMPTY
                key ^= ZOB_PIECE[WR][0]; key ^= ZOB_PIECE[WR][3]
            elif to == 62:  # black kingside, g8
                sqs[61] = sqs[63]; sqs[63] = EMPTY
                key ^= ZOB_PIECE[BR][63]; key ^= ZOB_PIECE[BR][61]
            elif to == 58:  # black queenside, c8
                sqs[59] = sqs[56]; sqs[56] = EMPTY
                key ^= ZOB_PIECE[BR][56]; key ^= ZOB_PIECE[BR][59]

        # update castling rights
        cr = self.castling_rights
        # losing rights when a king moves
        if moved_type == KING:
            if moved_color == WHITE:
                cr &= ~(CR_WK | CR_WQ)
            else:
                cr &= ~(CR_BK | CR_BQ)
        # losing rights when a rook moves from its home, or is captured on its home
        for s in (frm, to):
            if s == 0:   cr &= ~CR_WQ
            elif s == 7: cr &= ~CR_WK
            elif s == 56: cr &= ~CR_BQ
            elif s == 63: cr &= ~CR_BK
        self.castling_rights = cr
        key ^= ZOB_CASTLE[cr]

        # ep square: only if double pawn push and a same-rank enemy pawn could capture
        new_ep = -1
        if flags & F_DOUBLE:
            new_ep = (frm + to) // 2
        self.ep_square = new_ep
        if new_ep >= 0:
            key ^= ZOB_EP_FILE[file_of(new_ep)]

        # side to move
        self.side_to_move ^= 1
        key ^= ZOB_SIDE
        if self.side_to_move == WHITE:
            self.fullmove_number += 1

        self.zobrist_key = key

    def unmake_move(self) -> None:
        if not self.history:
            raise RuntimeError("unmake_move on empty history")
        (m, captured,
         cr, ep, hmc, fmn, key,
         wk_sq, bk_sq) = self.history.pop()
        sqs = self.squares
        frm = m.from_sq
        to = m.to_sq
        flags = m.flags

        # side to move flips back BEFORE we read moved color
        self.side_to_move ^= 1
        moved_color = self.side_to_move

        # undo promotion
        if m.promo:
            sqs[frm] = make_piece(moved_color, PAWN)
        else:
            sqs[frm] = sqs[to]

        # restore destination square
        if flags & F_EP:
            sqs[to] = EMPTY
            cap_sq = to + (-8 if moved_color == WHITE else 8)
            sqs[cap_sq] = make_piece(moved_color ^ 1, PAWN)
        else:
            sqs[to] = captured

        # undo castling rook
        if flags & F_CASTLE:
            if to == 6:
                sqs[7] = sqs[5]; sqs[5] = EMPTY
            elif to == 2:
                sqs[0] = sqs[3]; sqs[3] = EMPTY
            elif to == 62:
                sqs[63] = sqs[61]; sqs[61] = EMPTY
            elif to == 58:
                sqs[56] = sqs[59]; sqs[59] = EMPTY

        # restore state
        self.castling_rights = cr
        self.ep_square = ep
        self.halfmove_clock = hmc
        self.fullmove_number = fmn
        self.zobrist_key = key
        self.king_sq[0] = wk_sq
        self.king_sq[1] = bk_sq

    # --- null move (for future use) ----------------------------------
    def make_null_move(self) -> None:
        from .zobrist import ZOB_SIDE, ZOB_EP_FILE
        undo = (
            None, EMPTY,
            self.castling_rights, self.ep_square,
            self.halfmove_clock, self.fullmove_number,
            self.zobrist_key,
            self.king_sq[0], self.king_sq[1],
        )
        self.history.append(undo)
        if self.ep_square >= 0:
            self.zobrist_key ^= ZOB_EP_FILE[file_of(self.ep_square)]
            self.ep_square = -1
        self.side_to_move ^= 1
        self.zobrist_key ^= ZOB_SIDE
        self.halfmove_clock += 1

    def unmake_null_move(self) -> None:
        (_m, _cap, cr, ep, hmc, fmn, key, wk_sq, bk_sq) = self.history.pop()
        self.castling_rights = cr
        self.ep_square = ep
        self.halfmove_clock = hmc
        self.fullmove_number = fmn
        self.zobrist_key = key
        self.king_sq[0] = wk_sq
        self.king_sq[1] = bk_sq
        self.side_to_move ^= 1

    # --- draw detection ----------------------------------------------
    def is_repetition(self, count: int = 3) -> bool:
        """Return True if current position has occurred `count` times in history."""
        n = 0
        key = self.zobrist_key
        # Walk back through irreversible moves limit
        # history entries store prior keys; current key is self.zobrist_key
        # Count occurrences of current key among stored prior keys + current
        n = 1  # current
        # entries[6] is the prior key. After a series of moves, the key BEFORE move i
        # is at entries[i][6]. The position AFTER move i has the key matching entry[i+1][6].
        # Easier: walk back, after each unmake-step consider key.
        # We mimic without unmaking: compare with prior keys at each point.
        # The key AFTER N moves equals self.zobrist_key. Earlier "after" keys are
        # the prior keys stored in subsequent history entries. The key after move i
        # is entry[i+1].prior_key. The key after the last move = self.zobrist_key.
        # The key before move 0 = entry[0].prior_key.
        # So all "after-move" keys are: entry[1].prior, entry[2].prior, ..., self.zobrist_key.
        for i in range(1, len(self.history)):
            if self.history[i][6] == key:
                n += 1
                if n >= count:
                    return True
        return False

    def is_fifty_move_draw(self) -> bool:
        return self.halfmove_clock >= 100

    def has_insufficient_material(self) -> bool:
        bishops_w = []
        bishops_b = []
        knights_w = 0
        knights_b = 0
        others = False
        for s, p in enumerate(self.squares):
            if p == EMPTY:
                continue
            t = p & 7
            if t == KING:
                continue
            if t == PAWN or t == ROOK or t == QUEEN:
                return False
            if t == KNIGHT:
                if p & 8:
                    knights_b += 1
                else:
                    knights_w += 1
            elif t == BISHOP:
                color_sq = (file_of(s) + rank_of(s)) & 1
                if p & 8:
                    bishops_b.append(color_sq)
                else:
                    bishops_w.append(color_sq)
        # K vs K
        if not bishops_w and not bishops_b and knights_w == 0 and knights_b == 0:
            return True
        # K+N vs K, K+B vs K
        total_minor_w = knights_w + len(bishops_w)
        total_minor_b = knights_b + len(bishops_b)
        if total_minor_w + total_minor_b == 1:
            return True
        # K+B vs K+B same color bishops
        if knights_w == 0 and knights_b == 0 and len(bishops_w) == 1 and len(bishops_b) == 1:
            if bishops_w[0] == bishops_b[0]:
                return True
        return False
