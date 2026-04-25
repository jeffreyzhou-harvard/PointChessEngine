"""ELO-to-search-parameter mapping.

The slider runs 400-2400 inclusive. We map it to a small bag of dials:

================  ===================  ========================================
Dial              Effect               Notes
================  ===================  ========================================
``max_depth``     Search depth         Higher = stronger
``movetime_ms``   Soft time budget     0 = no cap
``noise_cp``      Eval noise (cp)      Adds Gaussian-ish jitter to leaf scores
``blunder_pct``   % chance of picking  Picks 2nd-5th best instead of best move,
                  a sub-optimal move   weighted toward better candidates
``randomness``    Top-N candidate      How many top moves to consider when
                  pool size            blundering
================  ===================  ========================================

The mapping is *piecewise linear* so it's both predictable and easy to tune.
Weak settings choose plausible-but-suboptimal moves rather than truly random
ones, which keeps games playable and instructive.
"""

from __future__ import annotations

from dataclasses import dataclass


MIN_ELO = 400
MAX_ELO = 2400


@dataclass(frozen=True)
class StrengthSettings:
    elo: int
    max_depth: int
    movetime_ms: int
    noise_cp: int
    blunder_pct: float
    candidate_pool: int


def _clip(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _lerp(elo: int, e_lo: int, e_hi: int, v_lo: float, v_hi: float) -> float:
    if e_hi == e_lo:
        return v_lo
    t = (elo - e_lo) / (e_hi - e_lo)
    return v_lo + t * (v_hi - v_lo)


def settings_for_elo(elo: int) -> StrengthSettings:
    elo = _clip(int(elo), MIN_ELO, MAX_ELO)

    if elo < 800:                         # 400 - 800: rank beginner
        depth = 1 if elo < 600 else 2
        movetime = int(_lerp(elo, 400, 800, 300, 800))
        noise = int(_lerp(elo, 400, 800, 250, 120))
        blunder = _lerp(elo, 400, 800, 28.0, 14.0)
        pool = 5
    elif elo < 1200:                      # 800 - 1200: casual club
        depth = 2 if elo < 1000 else 3
        movetime = int(_lerp(elo, 800, 1200, 800, 1500))
        noise = int(_lerp(elo, 800, 1200, 120, 60))
        blunder = _lerp(elo, 800, 1200, 14.0, 6.0)
        pool = 4
    elif elo < 1600:                      # 1200 - 1600: solid club
        depth = 3 if elo < 1400 else 4
        movetime = int(_lerp(elo, 1200, 1600, 1500, 3000))
        noise = int(_lerp(elo, 1200, 1600, 60, 25))
        blunder = _lerp(elo, 1200, 1600, 6.0, 2.0)
        pool = 3
    elif elo < 2000:                      # 1600 - 2000: tournament
        depth = 4 if elo < 1800 else 5
        movetime = int(_lerp(elo, 1600, 2000, 3000, 5000))
        noise = int(_lerp(elo, 1600, 2000, 25, 10))
        blunder = _lerp(elo, 1600, 2000, 2.0, 0.5)
        pool = 2
    else:                                 # 2000 - 2400: maximum
        depth = 5 if elo < 2200 else 7
        movetime = int(_lerp(elo, 2000, 2400, 5000, 8000))
        noise = 0
        blunder = max(0.0, _lerp(elo, 2000, 2400, 0.5, 0.0))
        pool = 1

    return StrengthSettings(
        elo=elo,
        max_depth=depth,
        movetime_ms=movetime,
        noise_cp=noise,
        blunder_pct=blunder,
        candidate_pool=pool,
    )
