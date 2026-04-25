"""ELO scaling configuration per design contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrengthConfig:
    elo: int
    max_depth: int
    soft_time_ms: int
    hard_time_ms: int
    eval_noise_cp: float
    top_k: int
    softmax_temp_cp: float
    blunder_margin_cp: int
    limit_strength: bool = True

    @property
    def t(self) -> float:
        return max(0.0, min(1.0, (self.elo - 400) / 2000.0))


def configure(elo: int, limit_strength: bool = True) -> StrengthConfig:
    elo = max(400, min(2400, int(elo)))
    t = (elo - 400) / 2000.0
    if t < 0:
        t = 0.0
    if t > 1:
        t = 1.0

    if not limit_strength:
        # Full strength regardless of slider.
        return StrengthConfig(
            elo=2400,
            max_depth=10,
            soft_time_ms=3000,
            hard_time_ms=5000,
            eval_noise_cp=0.0,
            top_k=1,
            softmax_temp_cp=1.0,
            blunder_margin_cp=300,
            limit_strength=False,
        )

    max_depth = max(1, round(1 + 9 * t))
    soft_time_ms = round(100 + 2900 * t)
    hard_time_ms = round(300 + 4700 * t)
    eval_noise_cp = max(0.0, 75 * (1 - t))
    top_k = max(1, round(4 - 3 * t))
    # Exponential decay from 80 to 1
    softmax_temp_cp = 80 * ((1.0 / 80.0) ** t)
    # Hard guardrail: 300 + 400*(1-t)
    blunder_margin_cp = round(300 + 400 * (1 - t))

    return StrengthConfig(
        elo=elo,
        max_depth=max_depth,
        soft_time_ms=soft_time_ms,
        hard_time_ms=hard_time_ms,
        eval_noise_cp=eval_noise_cp,
        top_k=top_k,
        softmax_temp_cp=softmax_temp_cp,
        blunder_margin_cp=blunder_margin_cp,
        limit_strength=True,
    )
