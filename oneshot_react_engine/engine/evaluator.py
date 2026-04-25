"""Static evaluation function.

Returns a centipawn score from the perspective of the side to move.

Components:
    - material balance
    - piece-square table bonuses (with separate king PST for midgame/endgame)
    - bishop pair (+30cp)
    - mobility (small bonus per legal move count for the side to move)
    - pawn structure: doubled / isolated penalties, passed pawn bonus
    - king safety: pawn shield in midgame
    - center control: bonus for occupying or attacking d4/e4/d5/e5 with pawns/knights
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from ..core.pieces import Color, PieceType
from .psqt import PIECE_VALUES, pst_value

if TYPE_CHECKING:  # pragma: no cover
    from ..core.board import Board


# Threshold (in non-pawn material per side) below which we treat the position
# as an "endgame" for king PSQT purposes.
ENDGAME_MATERIAL_THRESHOLD = 1300  # roughly Q + minor or two minors

CENTER_SQUARES = ((3, 3), (3, 4), (4, 3), (4, 4))


def evaluate(board: "Board") -> int:
    """Return a centipawn score from the side-to-move perspective."""
    white_material = 0
    black_material = 0
    white_non_pawn = 0
    black_non_pawn = 0
    white_pst = 0
    black_pst = 0
    white_bishops = 0
    black_bishops = 0

    pawn_files_white: List[int] = [0] * 8
    pawn_files_black: List[int] = [0] * 8
    pawns_white_rows: dict = {}
    pawns_black_rows: dict = {}

    for r in range(8):
        for c in range(8):
            piece = board.squares[r][c]
            if piece is None:
                continue
            val = PIECE_VALUES[piece.piece_type]
            if piece.color == Color.WHITE:
                white_material += val
                if piece.piece_type != PieceType.PAWN:
                    white_non_pawn += val
                if piece.piece_type == PieceType.BISHOP:
                    white_bishops += 1
                if piece.piece_type == PieceType.PAWN:
                    pawn_files_white[c] += 1
                    pawns_white_rows.setdefault(c, []).append(r)
            else:
                black_material += val
                if piece.piece_type != PieceType.PAWN:
                    black_non_pawn += val
                if piece.piece_type == PieceType.BISHOP:
                    black_bishops += 1
                if piece.piece_type == PieceType.PAWN:
                    pawn_files_black[c] += 1
                    pawns_black_rows.setdefault(c, []).append(r)

    endgame = (white_non_pawn + black_non_pawn) <= ENDGAME_MATERIAL_THRESHOLD

    for r in range(8):
        for c in range(8):
            piece = board.squares[r][c]
            if piece is None:
                continue
            bonus = pst_value(piece.piece_type, piece.color, r, c, endgame)
            if piece.color == Color.WHITE:
                white_pst += bonus
            else:
                black_pst += bonus

    score = (white_material - black_material) + (white_pst - black_pst)

    if white_bishops >= 2:
        score += 30
    if black_bishops >= 2:
        score -= 30

    # Pawn structure
    score += _pawn_structure(pawn_files_white, pawns_white_rows, Color.WHITE)
    score -= _pawn_structure(pawn_files_black, pawns_black_rows, Color.BLACK)

    # Passed pawns
    score += _passed_pawns(board, Color.WHITE)
    score -= _passed_pawns(board, Color.BLACK)

    # King safety in the midgame
    if not endgame:
        score += _king_pawn_shield(board, Color.WHITE)
        score -= _king_pawn_shield(board, Color.BLACK)

    # Mobility (cheap proxy: count own legal moves; minus opponent legal moves
    # is too slow because it requires switching turn). We use just side-to-move.
    score += _mobility(board)

    # Center control (small)
    score += _center_control(board)

    return score if board.turn == Color.WHITE else -score


def _pawn_structure(file_counts: List[int], rows_by_file: dict, color: Color) -> int:
    """Return doubled/isolated penalties from one side's perspective (positive = good)."""
    penalty = 0
    for f in range(8):
        cnt = file_counts[f]
        if cnt > 1:
            penalty -= 15 * (cnt - 1)  # doubled
        if cnt > 0:
            left = file_counts[f - 1] if f - 1 >= 0 else 0
            right = file_counts[f + 1] if f + 1 < 8 else 0
            if left == 0 and right == 0:
                penalty -= 20  # isolated
    return penalty


def _passed_pawns(board: "Board", color: Color) -> int:
    """Bonus for pawns with no opposing pawns blocking or on adjacent files ahead."""
    bonus = 0
    direction = -1 if color == Color.WHITE else 1
    for r in range(8):
        for c in range(8):
            p = board.squares[r][c]
            if p is None or p.color != color or p.piece_type != PieceType.PAWN:
                continue
            blocked = False
            scan_r = r + direction
            while 0 <= scan_r < 8 and not blocked:
                for dc in (-1, 0, 1):
                    nc = c + dc
                    if 0 <= nc < 8:
                        q = board.squares[scan_r][nc]
                        if q and q.color != color and q.piece_type == PieceType.PAWN:
                            blocked = True
                            break
                scan_r += direction
            if not blocked:
                # bonus scales with advancement
                if color == Color.WHITE:
                    rank_from_back = 7 - r  # 0..6
                else:
                    rank_from_back = r
                bonus += 10 + 5 * rank_from_back
    return bonus


def _king_pawn_shield(board: "Board", color: Color) -> int:
    """Reward intact pawns in front of the king (only meaningful in midgame)."""
    try:
        king_sq = board.find_king(color)
    except ValueError:
        return 0
    bonus = 0
    direction = -1 if color == Color.WHITE else 1
    for dc in (-1, 0, 1):
        nc = king_sq.col + dc
        if not (0 <= nc < 8):
            continue
        nr = king_sq.row + direction
        if 0 <= nr < 8:
            p = board.squares[nr][nc]
            if p and p.color == color and p.piece_type == PieceType.PAWN:
                bonus += 8
    return bonus


def _mobility(board: "Board") -> int:
    """+2cp per legal move available to the side to move."""
    count = len(board.legal_moves())
    return 2 * count if board.turn == Color.WHITE else -2 * count


def _center_control(board: "Board") -> int:
    """Bonus for pawns/knights occupying central squares."""
    bonus = 0
    for r, c in CENTER_SQUARES:
        p = board.squares[r][c]
        if p is None:
            continue
        weight = 5 if p.piece_type in (PieceType.PAWN, PieceType.KNIGHT) else 0
        bonus += weight if p.color == Color.WHITE else -weight
    return bonus
