"""ELO scaling per the contract.

ELO -> (max_depth, time_ms, top_k, temperature, blunder_prob)
piecewise-linear interpolation across anchors; move selection samples
from top-K by softmax-of-score/temperature, with optional blunders.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .board import Move


@dataclass
class StrengthParams:
    max_depth: int
    time_ms: int
    top_k: int
    temperature: float
    blunder_prob: float


# (elo, depth, time_ms, top_k, temp, blunder)
_ANCHORS: List[Tuple[int, int, int, int, float, float]] = [
    (400,  1,   50, 8, 2.0, 0.20),
    (800,  2,  100, 6, 1.2, 0.10),
    (1200, 3,  300, 4, 0.6, 0.03),
    (1600, 4,  800, 3, 0.3, 0.0),
    (2000, 5, 2000, 2, 0.1, 0.0),
    (2400, 7, 5000, 1, 0.0, 0.0),
]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def params_for_elo(elo: int) -> StrengthParams:
    if elo <= _ANCHORS[0][0]:
        _, d, tm, k, temp, blu = _ANCHORS[0]
        return StrengthParams(d, tm, k, temp, blu)
    if elo >= _ANCHORS[-1][0]:
        _, d, tm, k, temp, blu = _ANCHORS[-1]
        return StrengthParams(d, tm, k, temp, blu)
    # Find interval.
    for i in range(len(_ANCHORS) - 1):
        e0, d0, t0, k0, temp0, b0 = _ANCHORS[i]
        e1, d1, t1, k1, temp1, b1 = _ANCHORS[i + 1]
        if e0 <= elo <= e1:
            t = (elo - e0) / (e1 - e0)
            depth = int(round(_lerp(d0, d1, t)))
            time_ms = int(round(_lerp(t0, t1, t)))
            top_k = int(round(_lerp(k0, k1, t)))
            temperature = _lerp(temp0, temp1, t)
            blunder = _lerp(b0, b1, t)
            return StrengthParams(depth, time_ms, top_k, temperature, blunder)
    # unreachable
    raise AssertionError


def select_move(scored_moves: List[Tuple[Move, int]],
                params: StrengthParams,
                rng: Optional[random.Random] = None) -> Move:
    """Pick a move given (move, score) pairs and a strength profile.

    - top_k == 1: always returns the argmax.
    - else: softmax-samples among the top-K by score/temperature.
    - blunder_prob: with that probability, picks uniformly among the top-K
      excluding moves that drop eval by >300cp vs best.
    """
    if not scored_moves:
        raise ValueError("no scored moves")
    if rng is None:
        rng = random.Random()

    # Sort descending by score.
    ranked = sorted(scored_moves, key=lambda mv_s: -mv_s[1])
    if params.top_k <= 1 or len(ranked) == 1:
        return ranked[0][0]
    k = min(params.top_k, len(ranked))
    pool = ranked[:k]
    best_score = pool[0][1]

    # Blunder?
    if params.blunder_prob > 0 and rng.random() < params.blunder_prob:
        # Uniform among non-disastrous moves in pool.
        viable = [m for (m, s) in pool if (best_score - s) <= 300]
        if not viable:
            viable = [pool[0][0]]
        return rng.choice(viable)

    # Softmax sampling.
    if params.temperature <= 1e-9:
        return pool[0][0]
    # Numerical stability: subtract best_score; scale by 1/100 (centipawns to "logits").
    weights = []
    for _, s in pool:
        z = (s - best_score) / 100.0 / max(params.temperature, 1e-3)
        # clamp very-low to avoid math.exp underflow throwing.
        if z < -50: z = -50
        weights.append(math.exp(z))
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for (m, _), w in zip(pool, weights):
        acc += w
        if r <= acc:
            return m
    return pool[-1][0]
