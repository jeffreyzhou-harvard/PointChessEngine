"""Alpha-beta search with iterative deepening, quiescence, TT, killers, history.

Per design contract:
- alpha-beta within iterative deepening
- quiescence (captures + promotions only)
- Zobrist-keyed TT
- killer + history move ordering
- one-ply check extension (cap 2 per branch)
- NO null-move, NO LMR, NO aspiration windows
- accepts a stop_event: threading.Event for interruptible search
"""

from __future__ import annotations

import math
import random
import threading
import time
from typing import List, Optional, Tuple

from .board import (
    Board, Move, EMPTY, WHITE, BLACK,
    PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    F_CAPTURE, F_EP, F_PROMO, F_CASTLE,
    move_uci,
)
from .movegen import (
    generate_legal_moves, generate_pseudo_legal_moves,
    is_square_attacked, in_check,
)
from .evaluate import evaluate, MATERIAL
from .tt import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
from .strength import StrengthConfig, configure


INF = 10_000_000
MATE = 1_000_000  # mate scores above this threshold


def is_mate_score(s: int) -> bool:
    return abs(s) > MATE - 10000


# --- MVV-LVA scoring ------------------------------------------------------

# Victim values indexed by piece type
_VICTIM_VALUE = [0, 100, 320, 330, 500, 900, 20000]
_ATTACKER_VALUE = _VICTIM_VALUE


def _mvv_lva(board: Board, m: Move) -> int:
    if m.flags & F_EP:
        victim = PAWN
    elif m.flags & F_CAPTURE:
        victim = board.squares[m.to_sq] & 7
    else:
        victim = 0
    attacker = board.squares[m.from_sq] & 7
    base = _VICTIM_VALUE[victim] * 10 - _ATTACKER_VALUE[attacker]
    if m.promo:
        base += _VICTIM_VALUE[m.promo]
    return base


# --- Search state ---------------------------------------------------------

class SearchContext:
    __slots__ = (
        "board", "tt", "killers", "history",
        "stop_event", "deadline_ms", "start_time",
        "nodes", "stop_flag", "rng", "config",
        "best_root_move", "best_root_score",
    )

    def __init__(self, board: Board, tt: TranspositionTable,
                 stop_event: Optional[threading.Event],
                 hard_time_ms: int,
                 config: Optional[StrengthConfig] = None,
                 rng: Optional[random.Random] = None):
        self.board = board
        self.tt = tt
        # killers[ply] = [k1, k2]
        self.killers: List[List[Optional[Move]]] = [[None, None] for _ in range(128)]
        # history[from_sq][to_sq]
        self.history: List[List[int]] = [[0] * 64 for _ in range(64)]
        self.stop_event = stop_event
        self.start_time = time.monotonic()
        self.deadline_ms = hard_time_ms
        self.nodes = 0
        self.stop_flag = False
        self.rng = rng or random.Random()
        self.config = config
        self.best_root_move: Optional[Move] = None
        self.best_root_score: int = 0

    def time_up(self) -> bool:
        if self.stop_flag:
            return True
        if self.stop_event is not None and self.stop_event.is_set():
            self.stop_flag = True
            return True
        if self.deadline_ms is not None and self.deadline_ms > 0:
            elapsed_ms = (time.monotonic() - self.start_time) * 1000
            if elapsed_ms >= self.deadline_ms:
                self.stop_flag = True
                return True
        return False


# --- Move ordering --------------------------------------------------------

def _score_move(ctx: SearchContext, board: Board, m: Move,
                tt_move: Optional[Move], ply: int) -> int:
    if tt_move is not None and m == tt_move:
        return 10_000_000
    if (m.flags & F_CAPTURE) or m.promo:
        return 1_000_000 + _mvv_lva(board, m)
    # killers
    k = ctx.killers[ply] if ply < len(ctx.killers) else (None, None)
    if k[0] is not None and m == k[0]:
        return 900_000
    if k[1] is not None and m == k[1]:
        return 800_000
    return ctx.history[m.from_sq][m.to_sq]


def _order_moves(ctx: SearchContext, board: Board, moves: List[Move],
                 tt_move: Optional[Move], ply: int) -> List[Move]:
    return sorted(moves, key=lambda m: _score_move(ctx, board, m, tt_move, ply), reverse=True)


# --- Quiescence -----------------------------------------------------------

def quiescence(ctx: SearchContext, alpha: int, beta: int) -> int:
    ctx.nodes += 1
    if (ctx.nodes & 2047) == 0 and ctx.time_up():
        return 0

    board = ctx.board
    stand_pat = evaluate(board, alpha, beta)
    # Apply eval noise at leaves (search uses noisy values for exploration;
    # the root cutoff guard re-scores without noise).
    if ctx.config is not None and ctx.config.eval_noise_cp > 0:
        stand_pat += int(ctx.rng.gauss(0, ctx.config.eval_noise_cp))

    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    color = board.side_to_move
    pseudo = generate_pseudo_legal_moves(board, color)
    # captures + promotions only
    tactical = [m for m in pseudo if (m.flags & F_CAPTURE) or m.promo]
    tactical.sort(key=lambda m: _mvv_lva(board, m), reverse=True)

    opponent = 1 - color
    for m in tactical:
        # delta prune
        if m.flags & F_EP:
            captured_val = MATERIAL[1]
        elif m.flags & F_CAPTURE:
            captured_val = MATERIAL[board.squares[m.to_sq]]
        else:
            captured_val = 0
        if m.promo:
            captured_val += MATERIAL[m.promo + (8 if False else 0)]  # white index ok for value
        if stand_pat + captured_val + 200 < alpha:
            continue

        board.make_move(m)
        if is_square_attacked(board, board.king_sq[color], opponent):
            board.unmake_move()
            continue
        score = -quiescence(ctx, -beta, -alpha)
        board.unmake_move()
        if ctx.stop_flag:
            return 0
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


# --- Alpha-beta -----------------------------------------------------------

def alphabeta(ctx: SearchContext, depth: int, alpha: int, beta: int,
              ply: int, extensions_used: int = 0) -> int:
    ctx.nodes += 1
    if (ctx.nodes & 2047) == 0 and ctx.time_up():
        return 0

    board = ctx.board
    alpha_orig = alpha

    # Draw conditions: 50-move and threefold (cheap repetition check)
    if ply > 0:
        if board.is_fifty_move_draw() or board.has_insufficient_material():
            return 0
        if board.is_repetition(2):
            return 0

    # TT probe
    tt_entry = ctx.tt.probe(board.zobrist_key)
    tt_move = None
    if tt_entry is not None:
        ek, edepth, evalue, eflag, ebest = tt_entry
        if ek == board.zobrist_key:
            tt_move = ebest
            if ply > 0 and edepth >= depth:
                if eflag == TT_EXACT:
                    return evalue
                elif eflag == TT_LOWER and evalue >= beta:
                    return evalue
                elif eflag == TT_UPPER and evalue <= alpha:
                    return evalue

    # Check extension
    color = board.side_to_move
    in_chk = in_check(board, color)
    if in_chk and extensions_used < 2:
        depth += 1
        extensions_used += 1

    if depth <= 0:
        return quiescence(ctx, alpha, beta)

    moves = generate_legal_moves(board, color)
    if not moves:
        if in_chk:
            return -MATE + ply
        return 0  # stalemate

    moves = _order_moves(ctx, board, moves, tt_move, ply)

    best_move = None
    best_score = -INF

    for m in moves:
        board.make_move(m)
        score = -alphabeta(ctx, depth - 1, -beta, -alpha, ply + 1, extensions_used)
        board.unmake_move()

        if ctx.stop_flag:
            return 0

        if score > best_score:
            best_score = score
            best_move = m
        if score > alpha:
            alpha = score
        if alpha >= beta:
            # killer + history for quiet cutoff
            if not ((m.flags & F_CAPTURE) or m.promo):
                if ply < len(ctx.killers):
                    if ctx.killers[ply][0] != m:
                        ctx.killers[ply][1] = ctx.killers[ply][0]
                        ctx.killers[ply][0] = m
                ctx.history[m.from_sq][m.to_sq] += depth * depth
            break

    # store TT
    if best_score <= alpha_orig:
        flag = TT_UPPER
    elif best_score >= beta:
        flag = TT_LOWER
    else:
        flag = TT_EXACT
    ctx.tt.store(board.zobrist_key, depth, best_score, flag, best_move)

    return best_score


# --- Root search ----------------------------------------------------------

def _root_search(ctx: SearchContext, depth: int) -> List[Tuple[Move, int]]:
    """Search at root depth; return list of (move, score) for all legal moves
    in score-descending order."""
    board = ctx.board
    color = board.side_to_move
    moves = generate_legal_moves(board, color)
    if not moves:
        return []
    tt_entry = ctx.tt.probe(board.zobrist_key)
    tt_move = tt_entry[4] if tt_entry and tt_entry[0] == board.zobrist_key else None
    moves = _order_moves(ctx, board, moves, tt_move, 0)

    results: List[Tuple[Move, int]] = []
    alpha = -INF
    beta = INF
    best_score = -INF
    best_move = None

    for m in moves:
        board.make_move(m)
        score = -alphabeta(ctx, depth - 1, -beta, -alpha, 1, 0)
        board.unmake_move()
        if ctx.stop_flag:
            break
        results.append((m, score))
        if score > best_score:
            best_score = score
            best_move = m
        if score > alpha:
            alpha = score

    if not ctx.stop_flag and best_move is not None:
        ctx.best_root_move = best_move
        ctx.best_root_score = best_score
        ctx.tt.store(board.zobrist_key, depth, best_score, TT_EXACT, best_move)

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def iterative_deepening(
    board: Board,
    time_limit_ms: Optional[int] = None,
    max_depth: int = 64,
    stop_event: Optional[threading.Event] = None,
    tt: Optional[TranspositionTable] = None,
    config: Optional[StrengthConfig] = None,
    rng: Optional[random.Random] = None,
    info_callback=None,
) -> Tuple[Optional[Move], int, List[Tuple[Move, int]]]:
    """Run iterative deepening. Returns (best_move, score_cp, root_results).

    The returned `root_results` is the noise-aware result list from the deepest
    *completed* iteration. Strength sampling (top-K, softmax) is applied by the
    caller using `select_strength_move` or by `EngineCore`.
    """
    if tt is None:
        tt = TranspositionTable()
    hard_time = time_limit_ms if time_limit_ms is not None else 0
    ctx = SearchContext(board, tt, stop_event, hard_time, config=config, rng=rng)

    last_completed: List[Tuple[Move, int]] = []
    best_move: Optional[Move] = None
    best_score = 0

    # Root has at least one legal move? If not, return None.
    if not generate_legal_moves(board, board.side_to_move):
        return None, 0, []

    for depth in range(1, max_depth + 1):
        results = _root_search(ctx, depth)
        if ctx.stop_flag:
            break
        if not results:
            break
        last_completed = results
        best_move, best_score = results[0]
        if info_callback is not None:
            info_callback(depth, best_score, ctx.nodes,
                          (time.monotonic() - ctx.start_time) * 1000,
                          best_move)
        # If we found a forced mate, we can stop early.
        if is_mate_score(best_score):
            break
        # Soft-time check between iterations
        if config is not None and config.soft_time_ms:
            elapsed_ms = (time.monotonic() - ctx.start_time) * 1000
            if elapsed_ms >= config.soft_time_ms:
                break

    return best_move, best_score, last_completed


# --- Strength-aware root selection ---------------------------------------

def select_strength_move(
    board: Board,
    root_results: List[Tuple[Move, int]],
    config: StrengthConfig,
    rng: Optional[random.Random] = None,
) -> Optional[Move]:
    """Apply top-K + softmax sampling and guardrails per the contract."""
    if not root_results:
        return None
    if rng is None:
        rng = random.Random()

    # Hard guardrail #1: if any move is mate, play it.
    for m, s in root_results:
        if is_mate_score(s) and s > 0:
            return m

    if config.top_k <= 1 or not config.limit_strength:
        return root_results[0][0]

    best_score = root_results[0][1]
    cutoff = best_score - config.blunder_margin_cp
    candidates = [(m, s) for m, s in root_results[: config.top_k] if s >= cutoff]
    if not candidates:
        return root_results[0][0]
    if len(candidates) == 1:
        return candidates[0][0]

    # Softmax sampling
    temp = max(0.001, config.softmax_temp_cp)
    # Numerically stable softmax
    max_s = max(s for _, s in candidates)
    weights = []
    for _, s in candidates:
        weights.append(math.exp((s - max_s) / temp))
    total = sum(weights)
    if total <= 0:
        return candidates[0][0]
    r = rng.random() * total
    acc = 0.0
    for (m, _), w in zip(candidates, weights):
        acc += w
        if r <= acc:
            return m
    return candidates[-1][0]
