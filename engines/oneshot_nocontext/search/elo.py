"""ELO strength slider mapping.

Maps an ELO rating (400-2400) to engine parameters that simulate
different skill levels. The approach combines:

1. Search depth limit - Lower ELO = shallower search
2. Evaluation noise - Random noise added to evaluation scores
3. Blunder probability - Chance of picking a suboptimal move
4. Time limit - Maximum thinking time per move

How the mapping works:
---------------------
ELO 400-800   (Beginner):  depth 1-2, heavy noise (±200cp), 20-10% blunder rate
ELO 800-1200  (Club):      depth 2-3, moderate noise (±100cp), 10-5% blunder rate
ELO 1200-1600 (Intermediate): depth 3-4, light noise (±50cp), 5-2% blunder rate
ELO 1600-2000 (Advanced):  depth 4-5, minimal noise (±20cp), 2-0% blunder rate
ELO 2000-2400 (Expert):    depth 5-7, near-zero noise, 0% blunder rate

Blunders are "human-like": instead of picking a truly random move, the engine
picks from the 2nd-5th best moves, weighted by their evaluation. This prevents
absurd moves like hanging a queen for free.

The parameters interpolate linearly within each bracket for smooth transitions.
"""

import math
from typing import NamedTuple


class EloSettings(NamedTuple):
    """Engine parameters derived from an ELO target."""
    elo: int
    max_depth: int
    eval_noise: int         # centipawns of random noise added to evaluation
    blunder_chance: float   # probability (0-1) of picking a suboptimal move
    time_limit: float       # max seconds per move

    @staticmethod
    def from_elo(elo: int) -> 'EloSettings':
        """Create engine settings for a given ELO rating."""
        elo = max(400, min(2400, elo))

        # Depth mapping: 400->1, 800->2, 1200->3, 1600->4, 2000->5, 2400->7
        if elo <= 800:
            depth = 1 + (elo - 400) / 400
        elif elo <= 1600:
            depth = 2 + (elo - 800) / 400
        else:
            depth = 4 + (elo - 1600) * 3 / 800
        max_depth = max(1, int(round(depth)))

        # Noise mapping: 400->250, 1200->80, 2000->15, 2400->0
        if elo <= 1200:
            eval_noise = int(250 - (elo - 400) * 170 / 800)
        else:
            eval_noise = int(80 - (elo - 1200) * 80 / 1200)
        eval_noise = max(0, eval_noise)

        # Blunder chance: 400->0.25, 800->0.12, 1200->0.06, 1600->0.02, 2000->0.005, 2400->0
        if elo <= 1200:
            blunder_chance = 0.25 - (elo - 400) * 0.19 / 800
        elif elo <= 2000:
            blunder_chance = 0.06 - (elo - 1200) * 0.055 / 800
        else:
            blunder_chance = 0.005 - (elo - 2000) * 0.005 / 400
        blunder_chance = max(0.0, blunder_chance)

        # Time limit: 400->0.5s, 1200->2s, 2000->5s, 2400->10s
        if elo <= 1200:
            time_limit = 0.5 + (elo - 400) * 1.5 / 800
        else:
            time_limit = 2.0 + (elo - 1200) * 8.0 / 1200
        time_limit = min(10.0, time_limit)

        return EloSettings(
            elo=elo,
            max_depth=max_depth,
            eval_noise=eval_noise,
            blunder_chance=blunder_chance,
            time_limit=time_limit,
        )

    def describe(self) -> str:
        """Human-readable description of the settings."""
        return (f"ELO {self.elo}: depth={self.max_depth}, "
                f"noise=±{self.eval_noise}cp, "
                f"blunder={self.blunder_chance:.1%}, "
                f"time={self.time_limit:.1f}s")
