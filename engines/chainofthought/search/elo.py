"""ELO -> engine-config mapping.

A pure function. Both the UCI ``UCI_Elo`` setoption handler and the UI
slider call this, so a slider value at 1400 means the same thing in
either surface.

About the rating numbers
------------------------

The ELO range here (400..2400) is a **slider label**, NOT a calibrated
rating. We're picking parameter values that *feel* like the difference
between a beginner and a strong club player. With pure-Python search
we can't compete on speed against bullet-tested engines, so the
"strong" end of the slider is closer to a careful human than a true
2400 player.

Use these as approximate playing-strength targets:

  =====  ===================  ===============================
   ELO   Persona               How it plays
  =====  ===================  ===============================
   400   Total beginner        Sees one move ahead, blunders openly.
   800   Casual hobbyist       Sees the obvious, misses tactics.
  1200   Improving novice      Spots one-move tactics; long-term plans rare.
  1500   Default / club casual Plays solidly; occasional inaccuracy.
  1800   Competent club        Captures cleanly, rarely blunders.
  2100   Strong club           Calculates a few moves; near-optimal.
  2400   Engine maximum        No artificial weakening; full search.
  =====  ===================  ===============================

The mapping
-----------

Four knobs are derived from the ELO slider, all by linear
interpolation in ``t = (elo - MIN_ELO) / (MAX_ELO - MIN_ELO)``
(``t`` is in ``[0, 1]``):

  - **max_depth** (1..7): iterative-deepening cap when the caller
    didn't pass an explicit ``SearchLimits.depth``. Stronger ELO =
    deeper search.
  - **movetime_ms** (200..5000): per-move soft time budget when the
    caller didn't pass explicit time. Stronger ELO = thinks longer.
  - **eval_noise_cp** (200..0): symmetric uniform jitter added to
    each root move's score before the engine picks. Weaker ELO =
    larger jitter, which makes the engine occasionally prefer a
    less-good-but-not-crazy move.
  - **blunder_pct** (0.20..0.0): probability that, after sorting
    moves by their (jittered) scores, the engine picks one of the
    second/third-best instead of the absolute best. Weighted toward
    the better of those, so the result still looks like a human
    "I missed that" move rather than a random one.

How weakening is human-like (and where it isn't)
------------------------------------------------

Real weak players don't pick uniformly random legal moves -- they
play *plausible-looking* moves that are merely worse than the best.
Two mechanisms model this:

  1. **Bounded score noise.** A noise of 200 cp will reliably swap
     a 0 cp move for a +50 cp move (humanish) but won't make the
     engine drop a queen (a +900 cp swing won't be hidden by ±200).
  2. **Blunder = pick from top 3, weighted [3,2,1].** When the
     blunder roll fires, the engine still picks one of the moves it
     was already considering, with the best one most likely. That
     looks like "I saw the right move but talked myself out of it",
     which is recognisable.

This *will not* simulate things like:
  - opening-book ignorance (we have no book at all),
  - strategic confusion in long games,
  - time-pressure mistakes proportional to clock,
  - "fingerfehler" (missed coordinates).

That's fine; this stage's job is to make the slider deliver a
believable spread of skill, not to pass a Turing test.

Tuning strategy
---------------

If you want to retune these curves:

  1. Hold the *shape* fixed (linear in ``t``) and change only the
     anchor values. That keeps monotonicity guarantees that
     ``test_elo.py`` enforces.
  2. Validate against the standard sanity tests:
       - max ELO must produce ``eval_noise_cp == 0`` and
         ``blunder_pct == 0`` (otherwise the slider has no
         "play seriously" setting).
       - min ELO must produce strictly positive noise and blunder
         (otherwise the slider has no "weak" setting).
       - depth and movetime must be monotonically non-decreasing in
         ELO (a stronger player should never search less).
  3. Eyeball the band table in the README after retuning.

These checks live in ``tests/test_elo.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


MIN_ELO: Final[int] = 400
MAX_ELO: Final[int] = 2400
DEFAULT_ELO: Final[int] = 1500


@dataclass(frozen=True, slots=True)
class EloConfig:
    """Engine knobs derived from a single "playing-strength" ELO slider.

    All four fields are consumed by :class:`Engine`:

      - ``max_depth`` and ``movetime_ms`` act as **defaults** when
        the caller didn't pass an explicit ``SearchLimits.depth`` or
        time. UCI callers (and tests) that pass explicit limits
        override these.
      - ``eval_noise_cp`` and ``blunder_pct`` are **always applied**
        at root move selection, regardless of how limits were set.
        That way ``setoption UCI_Elo 800`` weakens the engine even
        when the caller passed ``go depth 30``.
    """

    elo: int
    max_depth: int            # iterative-deepening cap when none given
    movetime_ms: int          # per-move soft time budget when none given
    eval_noise_cp: int        # ± centipawn jitter on root scores
    blunder_pct: float        # 0..1 chance of picking 2nd/3rd best move


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def config_from_elo(elo: int) -> EloConfig:
    """Map a clamped ELO into an :class:`EloConfig`.

    Inputs outside ``[MIN_ELO, MAX_ELO]`` are clamped silently so
    callers (UCI, UI slider) never have to validate.
    """
    elo = _clamp(int(elo), MIN_ELO, MAX_ELO)

    span = MAX_ELO - MIN_ELO
    t = (elo - MIN_ELO) / span  # 0..1

    return EloConfig(
        elo=elo,
        max_depth=1 + int(round(6 * t)),                  # 1..7
        movetime_ms=200 + int(round(4800 * t)),           # 200..5000 ms
        eval_noise_cp=int(round(200 * (1 - t))),          # 200..0 cp
        blunder_pct=round(0.20 * (1 - t), 4),             # 0.20..0.0
    )
