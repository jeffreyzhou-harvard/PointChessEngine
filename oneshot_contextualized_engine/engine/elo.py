"""ELO scaling.

Maps a target ELO into a `StrengthConfig` that the engine uses to weaken
itself in human-feeling ways. Inputs we modulate:

    max_depth         hard cap on iterative-deepening depth
    move_time_ms      time budget per move (when no time-control is given)
    skill_level       0..20 (Stockfish-style); influences eval noise + pick
    eval_noise_cp     gaussian noise added to final score, in centipawns
    blunder_prob      P(pick a non-best move from the move list)
    multipv           how many lines to consider for the skill-weighted pick
    use_book          opening book on/off

Mapping rationale (see docs/ELO.md):
  *  Depth grows roughly linearly from 1 ply at 400 ELO to ~9 ply at 2400.
  *  Time grows from ~50 ms to ~2000 ms in the same range.
  *  Eval noise *decreases* monotonically with ELO so weaker engines see
     positions hazily.
  *  Blunder probability decreases monotonically.
  *  The opening book is only enabled at >= 1400.

The mapping is data-driven: a tabulated list of (elo, config) anchors with
linear interpolation between them. Retuning is just editing the table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class StrengthConfig:
    elo: int
    max_depth: int
    move_time_ms: int
    skill_level: int
    eval_noise_cp: int
    blunder_prob: float
    multipv: int
    use_book: bool


# (elo, max_depth, move_time_ms, skill_level, eval_noise_cp, blunder_prob, multipv, use_book)
_ANCHORS: List[Tuple[int, int, int, int, int, float, int, bool]] = [
    ( 400,  1,   50,  0, 250, 0.45, 4, False),
    ( 700,  2,  100,  3, 180, 0.30, 4, False),
    (1000,  2,  200,  6, 120, 0.20, 4, False),
    (1300,  3,  350,  9,  70, 0.10, 3, False),
    (1500,  4,  500, 11,  45, 0.06, 3, True),
    (1700,  5,  700, 13,  25, 0.03, 2, True),
    (1900,  6, 1000, 15,  15, 0.01, 2, True),
    (2100,  7, 1300, 17,   8, 0.00, 1, True),
    (2300,  8, 1700, 19,   3, 0.00, 1, True),
    (2400,  9, 2000, 20,   0, 0.00, 1, True),
]


def _lerp(x: int, x0: int, x1: int, y0: float, y1: float) -> float:
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def config_from_elo(elo: int) -> StrengthConfig:
    elo = max(_ANCHORS[0][0], min(_ANCHORS[-1][0], int(elo)))

    # Find the bracketing anchors.
    for i in range(len(_ANCHORS) - 1):
        a = _ANCHORS[i]
        b = _ANCHORS[i + 1]
        if a[0] <= elo <= b[0]:
            depth = max(1, round(_lerp(elo, a[0], b[0], a[1], b[1])))
            move_time = max(20, round(_lerp(elo, a[0], b[0], a[2], b[2])))
            skill = max(0, min(20, round(_lerp(elo, a[0], b[0], a[3], b[3]))))
            noise = max(0, round(_lerp(elo, a[0], b[0], a[4], b[4])))
            blunder = max(0.0, _lerp(elo, a[0], b[0], a[5], b[5]))
            multipv = max(1, round(_lerp(elo, a[0], b[0], a[6], b[6])))
            use_book = b[7] if elo >= b[0] else a[7]
            return StrengthConfig(
                elo=elo,
                max_depth=depth,
                move_time_ms=move_time,
                skill_level=skill,
                eval_noise_cp=noise,
                blunder_prob=blunder,
                multipv=multipv,
                use_book=use_book,
            )

    # Fallback (shouldn't happen).
    a = _ANCHORS[-1]
    return StrengthConfig(elo=a[0], max_depth=a[1], move_time_ms=a[2],
                          skill_level=a[3], eval_noise_cp=a[4],
                          blunder_prob=a[5], multipv=a[6], use_book=a[7])


def config_from_skill(skill_level: int) -> StrengthConfig:
    """Convenience: convert a Stockfish-style 0..20 skill level to a config.

    We linearly map 0..20 onto the ELO range used by `config_from_elo`.
    """
    skill_level = max(0, min(20, int(skill_level)))
    elo_min, elo_max = _ANCHORS[0][0], _ANCHORS[-1][0]
    elo = round(elo_min + (elo_max - elo_min) * (skill_level / 20))
    return config_from_elo(elo)
