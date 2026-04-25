"""Evaluation: tapered material + PST + mobility + king safety + pawn structure
+ bishop pair + passed pawns. Returns centipawns from side-to-move's perspective.

Implements the lazy-eval pattern: cheap material+PST first; full eval when the
lazy score is within MARGIN of the alpha-beta window.
"""

from __future__ import annotations

from .board import (
    Board, EMPTY, WHITE, BLACK,
    PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    WP, WN, WB, WR, WQ, WK, BP, BN, BB, BR, BQ, BK,
    file_of, rank_of, mirror,
)
from .movegen import (
    KNIGHT_TARGETS, KING_TARGETS, RAYS,
    BISHOP_DIRS, ROOK_DIRS, QUEEN_DIRS,
    is_square_attacked,
)


# --- Material -------------------------------------------------------------

MATERIAL = [0] * 16
MATERIAL[WP] = 100
MATERIAL[WN] = 320
MATERIAL[WB] = 330
MATERIAL[WR] = 500
MATERIAL[WQ] = 900
MATERIAL[WK] = 0
MATERIAL[BP] = 100
MATERIAL[BN] = 320
MATERIAL[BB] = 330
MATERIAL[BR] = 500
MATERIAL[BQ] = 900
MATERIAL[BK] = 0


# --- PSTs (white POV; mirror via sq^56 for black) ------------------------
# Tables ordered from rank 1 (a1..h1) to rank 8 (a8..h8).

def _flip_for_table(rows):
    """Tables below are written rank 8 at top for readability; flip to a1..h8."""
    flat = [v for row in reversed(rows) for v in row]
    assert len(flat) == 64
    return flat


PST_PAWN_MG = _flip_for_table([
    [0, 0, 0, 0, 0, 0, 0, 0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5, 5, 10, 25, 25, 10, 5, 5],
    [0, 0, 0, 20, 20, 0, 0, 0],
    [5, -5, -10, 0, 0, -10, -5, 5],
    [5, 10, 10, -20, -20, 10, 10, 5],
    [0, 0, 0, 0, 0, 0, 0, 0],
])

PST_PAWN_EG = _flip_for_table([
    [0, 0, 0, 0, 0, 0, 0, 0],
    [80, 80, 80, 80, 80, 80, 80, 80],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [30, 30, 30, 30, 30, 30, 30, 30],
    [20, 20, 20, 20, 20, 20, 20, 20],
    [10, 10, 10, 10, 10, 10, 10, 10],
    [10, 10, 10, 10, 10, 10, 10, 10],
    [0, 0, 0, 0, 0, 0, 0, 0],
])

PST_KNIGHT_MG = _flip_for_table([
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20, 0, 0, 0, 0, -20, -40],
    [-30, 0, 10, 15, 15, 10, 0, -30],
    [-30, 5, 15, 20, 20, 15, 5, -30],
    [-30, 0, 15, 20, 20, 15, 0, -30],
    [-30, 5, 10, 15, 15, 10, 5, -30],
    [-40, -20, 0, 5, 5, 0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
])
PST_KNIGHT_EG = PST_KNIGHT_MG  # close enough

PST_BISHOP_MG = _flip_for_table([
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10, 0, 0, 0, 0, 0, 0, -10],
    [-10, 0, 5, 10, 10, 5, 0, -10],
    [-10, 5, 5, 10, 10, 5, 5, -10],
    [-10, 0, 10, 10, 10, 10, 0, -10],
    [-10, 10, 10, 10, 10, 10, 10, -10],
    [-10, 5, 0, 0, 0, 0, 5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
])
PST_BISHOP_EG = PST_BISHOP_MG

PST_ROOK_MG = _flip_for_table([
    [0, 0, 0, 0, 0, 0, 0, 0],
    [5, 10, 10, 10, 10, 10, 10, 5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [0, 0, 0, 5, 5, 0, 0, 0],
])
PST_ROOK_EG = PST_ROOK_MG

PST_QUEEN_MG = _flip_for_table([
    [-20, -10, -10, -5, -5, -10, -10, -20],
    [-10, 0, 0, 0, 0, 0, 0, -10],
    [-10, 0, 5, 5, 5, 5, 0, -10],
    [-5, 0, 5, 5, 5, 5, 0, -5],
    [0, 0, 5, 5, 5, 5, 0, -5],
    [-10, 5, 5, 5, 5, 5, 0, -10],
    [-10, 0, 5, 0, 0, 0, 0, -10],
    [-20, -10, -10, -5, -5, -10, -10, -20],
])
PST_QUEEN_EG = PST_QUEEN_MG

# King MG: prefer castled corners
PST_KING_MG = _flip_for_table([
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [20, 20, 0, 0, 0, 0, 20, 20],
    [20, 30, 10, 0, 0, 10, 30, 20],
])

# King EG: prefer center
PST_KING_EG = _flip_for_table([
    [-50, -40, -30, -20, -20, -30, -40, -50],
    [-30, -20, -10, 0, 0, -10, -20, -30],
    [-30, -10, 20, 30, 30, 20, -10, -30],
    [-30, -10, 30, 40, 40, 30, -10, -30],
    [-30, -10, 30, 40, 40, 30, -10, -30],
    [-30, -10, 20, 30, 30, 20, -10, -30],
    [-30, -30, 0, 0, 0, 0, -30, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50],
])

# Indexed by piece type 1..6
PST_MG = [None,
          PST_PAWN_MG, PST_KNIGHT_MG, PST_BISHOP_MG,
          PST_ROOK_MG, PST_QUEEN_MG, PST_KING_MG]
PST_EG = [None,
          PST_PAWN_EG, PST_KNIGHT_EG, PST_BISHOP_EG,
          PST_ROOK_EG, PST_QUEEN_EG, PST_KING_EG]

PHASE_WEIGHTS = {KNIGHT: 1, BISHOP: 1, ROOK: 2, QUEEN: 4}


# --- Lazy material+PST ----------------------------------------------------

def _material_pst_score(board: Board) -> tuple:
    """Return (mg_score, eg_score, phase) all from white's POV."""
    mg = 0
    eg = 0
    phase = 0
    sqs = board.squares
    for s in range(64):
        p = sqs[s]
        if p == EMPTY:
            continue
        t = p & 7
        is_black = p & 8
        if is_black:
            mg -= MATERIAL[p]
            eg -= MATERIAL[p]
            mg -= PST_MG[t][mirror(s)]
            eg -= PST_EG[t][mirror(s)]
        else:
            mg += MATERIAL[p]
            eg += MATERIAL[p]
            mg += PST_MG[t][s]
            eg += PST_EG[t][s]
        if t in PHASE_WEIGHTS:
            phase += PHASE_WEIGHTS[t]
    if phase > 24:
        phase = 24
    return mg, eg, phase


def _taper(mg: int, eg: int, phase: int) -> int:
    return (mg * phase + eg * (24 - phase)) // 24


# --- Mobility -------------------------------------------------------------

def _mobility_score(board: Board, phase: int) -> int:
    """Quiet-target-square count per piece (excludes pawns and king)."""
    sqs = board.squares
    score_mg = 0
    score_eg = 0
    for s in range(64):
        p = sqs[s]
        if p == EMPTY:
            continue
        t = p & 7
        sign = -1 if (p & 8) else 1
        if t == KNIGHT:
            empties = 0
            for to in KNIGHT_TARGETS[s]:
                if sqs[to] == EMPTY:
                    empties += 1
            score_mg += sign * 4 * empties
            score_eg += sign * 4 * empties
        elif t == BISHOP:
            empties = _slider_quiet_count(sqs, s, BISHOP_DIRS)
            score_mg += sign * 5 * empties
            score_eg += sign * 5 * empties
        elif t == ROOK:
            empties = _slider_quiet_count(sqs, s, ROOK_DIRS)
            score_mg += sign * 2 * empties
            score_eg += sign * 4 * empties
        elif t == QUEEN:
            empties = _slider_quiet_count(sqs, s, QUEEN_DIRS)
            score_mg += sign * 1 * empties
            score_eg += sign * 1 * empties
    return _taper(score_mg, score_eg, phase)


def _slider_quiet_count(sqs, s, dirs) -> int:
    n = 0
    for d in dirs:
        for to in RAYS[d][s]:
            if sqs[to] == EMPTY:
                n += 1
            else:
                break
    return n


# --- Pawn structure -------------------------------------------------------

def _pawn_structure_and_passed(board: Board, phase: int) -> int:
    sqs = board.squares
    # Build per-file pawn rank lists for both sides.
    white_files = [[] for _ in range(8)]
    black_files = [[] for _ in range(8)]
    for s in range(64):
        p = sqs[s]
        if p == WP:
            white_files[file_of(s)].append(rank_of(s))
        elif p == BP:
            black_files[file_of(s)].append(rank_of(s))

    mg = 0
    eg = 0

    for color, my_files, enemy_files in (
        (WHITE, white_files, black_files),
        (BLACK, black_files, white_files),
    ):
        sign = 1 if color == WHITE else -1
        for f in range(8):
            ranks = my_files[f]
            if not ranks:
                continue
            # doubled (per extra pawn beyond the first)
            if len(ranks) > 1:
                extra = len(ranks) - 1
                mg -= sign * 15 * extra
                eg -= sign * 25 * extra
            # isolated: no friendly pawns on adjacent files
            iso = True
            if f > 0 and my_files[f - 1]:
                iso = False
            if f < 7 and my_files[f + 1]:
                iso = False
            if iso:
                mg -= sign * 15 * len(ranks)
                eg -= sign * 20 * len(ranks)
            # backward (simple: behind both neighbors and cannot safely advance)
            for r in ranks:
                neighbor_min = 8
                if f > 0 and my_files[f - 1]:
                    neighbor_min = min(neighbor_min, min(my_files[f - 1]))
                if f < 7 and my_files[f + 1]:
                    neighbor_min = min(neighbor_min, min(my_files[f + 1]))
                if color == WHITE:
                    if neighbor_min < 8 and r < neighbor_min:
                        mg -= sign * 10
                        eg -= sign * 10
                else:
                    # for black, "ahead" means smaller rank; backward means larger rank
                    neighbor_max = -1
                    if f > 0 and my_files[f - 1]:
                        neighbor_max = max(neighbor_max, max(my_files[f - 1]))
                    if f < 7 and my_files[f + 1]:
                        neighbor_max = max(neighbor_max, max(my_files[f + 1]))
                    if neighbor_max >= 0 and r > neighbor_max:
                        mg -= sign * 10
                        eg -= sign * 10
            # passed pawns
            for r in ranks:
                if _is_passed(color, f, r, enemy_files):
                    if color == WHITE:
                        bonus = _PASSED_BONUS_W[r]
                    else:
                        bonus = _PASSED_BONUS_B[r]
                    mg += sign * bonus
                    eg += sign * (bonus * 3 // 2)

    return _taper(mg, eg, phase)


_PASSED_BONUS_W = [0, 10, 17, 25, 40, 70, 120, 0]
# Mirrored for black (rank 6 is their "rank 2", etc.)
_PASSED_BONUS_B = [0, 120, 70, 40, 25, 17, 10, 0]


def _is_passed(color, f, r, enemy_files):
    files_to_check = [f]
    if f > 0:
        files_to_check.append(f - 1)
    if f < 7:
        files_to_check.append(f + 1)
    if color == WHITE:
        for ef in files_to_check:
            for er in enemy_files[ef]:
                if er > r:
                    return False
    else:
        for ef in files_to_check:
            for er in enemy_files[ef]:
                if er < r:
                    return False
    return True


# --- Bishop pair ----------------------------------------------------------

def _bishop_pair_score(board: Board, phase: int) -> int:
    wb = bb = 0
    for p in board.squares:
        if p == WB:
            wb += 1
        elif p == BB:
            bb += 1
    score_mg = 0
    score_eg = 0
    if wb >= 2:
        score_mg += 30
        score_eg += 50
    if bb >= 2:
        score_mg -= 30
        score_eg -= 50
    return _taper(score_mg, score_eg, phase)


# --- King safety (MG only, scaled by phase/24) ---------------------------

def _king_safety(board: Board, phase: int) -> int:
    if phase == 0:
        return 0
    mg = 0
    for color in (WHITE, BLACK):
        sign = 1 if color == WHITE else -1
        ks = board.king_sq[color]
        if ks < 0:
            continue
        score = 0
        kf = file_of(ks)
        kr = rank_of(ks)
        # Pawn shield: 3 files in front (kf-1, kf, kf+1), one rank ahead
        for df in (-1, 0, 1):
            f = kf + df
            if f < 0 or f > 7:
                continue
            # find friendly pawn on this file
            friendly_pawn_rank = None
            for r in range(8):
                p = board.squares[r * 8 + f]
                if (color == WHITE and p == WP) or (color == BLACK and p == BP):
                    if friendly_pawn_rank is None:
                        friendly_pawn_rank = r
                    elif color == WHITE and r < friendly_pawn_rank:
                        friendly_pawn_rank = r
                    elif color == BLACK and r > friendly_pawn_rank:
                        friendly_pawn_rank = r
            if friendly_pawn_rank is None:
                score -= 15
            else:
                if color == WHITE:
                    advanced = friendly_pawn_rank - kr
                else:
                    advanced = kr - friendly_pawn_rank
                if advanced > 2:
                    score -= 10
        # Open / semi-open file on king
        own_pawn = WP if color == WHITE else BP
        enemy_pawn = BP if color == WHITE else WP
        own_on_file = any(board.squares[r * 8 + kf] == own_pawn for r in range(8))
        enemy_on_file = any(board.squares[r * 8 + kf] == enemy_pawn for r in range(8))
        if not own_on_file and not enemy_on_file:
            score -= 25
        elif not own_on_file:
            score -= 15
        # Attacker count in king zone
        zone = []
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                f = kf + df
                r = kr + dr
                if 0 <= f < 8 and 0 <= r < 8:
                    zone.append(r * 8 + f)
        # plus one rank further forward
        forward = 1 if color == WHITE else -1
        for df in (-1, 0, 1):
            f = kf + df
            r = kr + 2 * forward
            if 0 <= f < 8 and 0 <= r < 8:
                s = r * 8 + f
                if s not in zone:
                    zone.append(s)
        attackers = 0
        opp = 1 - color
        for z in zone:
            if is_square_attacked(board, z, opp):
                attackers += 1
        if attackers == 1:
            score -= 20
        elif attackers == 2:
            score -= 50
        elif attackers == 3:
            score -= 90
        elif attackers >= 4:
            score -= 140
        mg += sign * score
    # Scale by phase/24 (only matters in MG)
    return mg * phase // 24


# --- Public eval ----------------------------------------------------------

LAZY_MARGIN = 200


def evaluate(board: Board, alpha: int = None, beta: int = None) -> int:
    """Static evaluation in centipawns from side-to-move's POV.

    If `alpha` and `beta` are provided, applies the lazy-eval pattern: returns
    early with material+PST if the lazy score is more than LAZY_MARGIN outside
    the [alpha, beta] window.
    """
    mg, eg, phase = _material_pst_score(board)
    lazy = _taper(mg, eg, phase)
    if board.side_to_move == BLACK:
        lazy = -lazy

    if alpha is not None and beta is not None:
        # Note: lazy_score - alpha and lazy_score - beta both > LAZY_MARGIN
        # means we're well outside the window in both directions, which can't
        # happen; the contract says BOTH abs(lazy-alpha) AND abs(lazy-beta)
        # exceed margin -> return lazy. That is: lazy outside [alpha-MARGIN, beta+MARGIN].
        if (lazy - alpha) > LAZY_MARGIN and (lazy - beta) > LAZY_MARGIN:
            return lazy
        if (alpha - lazy) > LAZY_MARGIN and (beta - lazy) > LAZY_MARGIN:
            return lazy

    # Full eval (still from white's POV in mg/eg, then flip)
    mob = _mobility_score(board, phase)
    pawns = _pawn_structure_and_passed(board, phase)
    bp = _bishop_pair_score(board, phase)
    ks = _king_safety(board, phase)

    full_white = _taper(mg, eg, phase) + mob + pawns + bp + ks
    if board.side_to_move == BLACK:
        return -full_white
    return full_white
