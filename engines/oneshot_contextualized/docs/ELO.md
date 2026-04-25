# ELO scaling

The user-facing strength control is a single integer ELO in
`[400, 2400]`. `engine.elo.config_from_elo(elo)` turns it into a
`StrengthConfig` that the rest of the engine reads:

```python
@dataclass
class StrengthConfig:
    elo: int
    max_depth: int        # iterative-deepening cap
    move_time_ms: int     # time budget per move when no clock is set
    skill_level: int      # 0..20, mostly informational
    eval_noise_cp: int    # gaussian noise sigma = noise/2 added per candidate
    blunder_prob: float   # P(uniform-random pick from MultiPV)
    multipv: int          # how many candidates we generate
    use_book: bool        # opening book on/off
```

## How weakening works

At runtime, `Engine.choose_move`:

1. **Book**. If `use_book` and the position is in our small built-in
   book, play a weighted-random book move and return.
2. **Search at MultiPV = N**. If we are below full strength, we ask the
   searcher for the top-N lines instead of just one. Generating more
   candidates is cheap: it's just sorting root scores from one full
   iteration.
3. **Pick with noise**. For each candidate, add gaussian noise with
   sigma = `eval_noise_cp / 2`. With probability `blunder_prob`, pick a
   uniform random candidate; otherwise pick the noisy-argmax.

This recipe makes weak play feel *plausibly human*. Most weak engines
randomly drop pieces (`P(blunder)` applied to *all* legal moves); ours
only ever picks from the top-N moves it found, so even at 400 ELO the
moves are usually defensible — just often not the *best*. The eval noise
makes it indecisive between near-equal moves, the way a beginner is.

## The mapping

The mapping is a list of anchor points with linear interpolation between
neighbors. Editing this table is the only thing you should need to
re-tune strength:

| ELO | depth | time(ms) | skill | noise(cp) | blunder | multipv | book |
|---|---|---|---|---|---|---|---|
| 400 | 1 | 50 | 0 | 250 | 0.45 | 4 | – |
| 700 | 2 | 100 | 3 | 180 | 0.30 | 4 | – |
| 1000 | 2 | 200 | 6 | 120 | 0.20 | 4 | – |
| 1300 | 3 | 350 | 9 | 70 | 0.10 | 3 | – |
| 1500 | 4 | 500 | 11 | 45 | 0.06 | 3 | ✓ |
| 1700 | 5 | 700 | 13 | 25 | 0.03 | 2 | ✓ |
| 1900 | 6 | 1000 | 15 | 15 | 0.01 | 2 | ✓ |
| 2100 | 7 | 1300 | 17 | 8 | 0.00 | 1 | ✓ |
| 2300 | 8 | 1700 | 19 | 3 | 0.00 | 1 | ✓ |
| 2400 | 9 | 2000 | 20 | 0 | 0.00 | 1 | ✓ |

At 2400 every dial is at its strongest setting, including `multipv = 1`
and `eval_noise_cp = 0`, so the engine plays its strongest line every
time and produces deterministic moves on a fixed input.

## UCI integration

Two UCI options control strength, mirroring Stockfish's conventions:

* `UCI_LimitStrength` (check, default false). When `true`, the engine
  reads `UCI_Elo` and weakens accordingly.
* `UCI_Elo` (spin, 400..2400, default 1500). The target ELO.
* `Skill Level` (spin, 0..20, default 20). A convenience that maps
  linearly to the same ELO range.

Setting `Skill Level` to anything below 20 implicitly turns
`UCI_LimitStrength` on, matching Stockfish behavior.
