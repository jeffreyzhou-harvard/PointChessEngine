# ELO Strength Adjustment System

## Overview

The chess engine implements a comprehensive ELO-based strength adjustment system that allows it to play at different skill levels from beginner (400 ELO) to near-engine strength (2400 ELO). The system creates believable play at all levels by adjusting multiple parameters simultaneously.

## Architecture

The ELO system is implemented in `search/elo.py` and integrated into the main engine via `search/engine.py`.

### Key Components

1. **EloConfig** - Dataclass containing all strength parameters
2. **config_from_elo()** - Factory function to create configurations
3. **Engine integration** - Automatic application of ELO settings during search

## ELO Mapping Table

| ELO  | Depth | Time Mult | Noise (cp) | Best Move Prob | Description      |
|------|-------|-----------|------------|----------------|------------------|
| 400  | 1     | 0.10      | 300        | 0.30           | Beginner         |
| 600  | 2     | 0.20      | 250        | 0.40           | Novice           |
| 800  | 2     | 0.30      | 200        | 0.50           | Casual           |
| 1000 | 3     | 0.40      | 150        | 0.60           | Club player      |
| 1200 | 3     | 0.50      | 108        | 0.74           | Intermediate     |
| 1400 | 4     | 0.60      | 70         | 0.78           | Advanced         |
| 1600 | 5     | 0.70      | 45         | 0.85           | Strong club      |
| 1800 | 6     | 0.80      | 25         | 0.91           | Expert           |
| 2000 | 6     | 0.90      | 12         | 0.95           | Master           |
| 2200 | 7     | 0.95      | 5          | 0.98           | Strong master    |
| 2400 | 8     | 1.00      | 0          | 1.00           | Near-engine      |

## Parameters

### 1. Search Depth (base_depth)

**Range:** 1-8  
**Scaling:** Linear

The primary strength factor. Controls how many moves ahead the engine looks.

- **400 ELO:** Depth 1 (only considers immediate moves)
- **1200 ELO:** Depth 3 (typical club player)
- **2400 ELO:** Depth 8 (strong tactical vision)

**Formula:** `depth = 1 + (elo - 400) * 7 / 2000`

### 2. Time Multiplier (time_multiplier)

**Range:** 0.1-1.0  
**Scaling:** Linear

Controls how much time the engine uses for thinking. Lower ELO players make faster (less considered) moves.

- **400 ELO:** 0.1x time (very quick moves)
- **1200 ELO:** 0.5x time (moderate thinking)
- **2400 ELO:** 1.0x time (full thinking time)

**Formula:** `time_mult = 0.1 + (elo - 400) * 0.9 / 2000`

### 3. Evaluation Noise (eval_noise)

**Range:** 0-300 centipawns  
**Scaling:** Quadratic decay

Random noise added to position evaluations to simulate imperfect judgment.

- **400 ELO:** ±300cp (huge evaluation errors)
- **1200 ELO:** ±108cp (moderate errors)
- **2400 ELO:** 0cp (perfect evaluation)

**Formula:** `noise = 300 * (1 - normalized)²` where `normalized = (elo - 400) / 2000`

The quadratic decay creates more realistic mistake distribution - beginners make many large errors, while advanced players make occasional small errors.

### 4. Best Move Probability (best_move_probability)

**Range:** 0.3-1.0  
**Scaling:** Square-root curve

Probability of choosing the objectively best move vs. a suboptimal alternative.

- **400 ELO:** 30% (often chooses 2nd or 3rd best move)
- **1200 ELO:** 74% (usually finds good moves)
- **2400 ELO:** 100% (always chooses best move)

**Formula:** `prob = 0.3 + 0.7 * sqrt(normalized)` where `normalized = (elo - 400) / 2000`

When not choosing the best move, the engine uses weighted selection from the top 3 moves (weights: 3, 2, 1).

## Implementation Details

### Noise Injection

```python
def add_noise_to_score(self, score: int, seed: Optional[int] = None) -> int:
    if self.eval_noise == 0:
        return score
    noise = random.randint(-self.eval_noise, self.eval_noise)
    return score + noise
```

Noise is applied uniformly within the range `[-eval_noise, +eval_noise]`.

### Move Selection

```python
def select_move(self, moves_with_scores: List[Tuple], seed: Optional[int] = None):
    # Choose best move with configured probability
    if random.random() < self.best_move_probability:
        return moves_with_scores[0][0]
    
    # Otherwise, weighted choice from top 3
    top_moves = moves_with_scores[:3]
    weights = [3, 2, 1]  # Best, second, third
    return weighted_random_choice(top_moves, weights)
```

### Forced Mate Protection

**Critical requirement:** The engine NEVER blunders forced mates, regardless of ELO level.

```python
def should_blunder_mate(self, is_forced_mate: bool, seed: Optional[int] = None) -> bool:
    return False  # Never blunder forced mates
```

This is implemented in the engine by checking if the position has a mate score before applying move selection randomness.

## Usage

### Basic Usage

```python
from search.engine import Engine

# Create engine at specific ELO
engine = Engine(elo_rating=1500)

# Get best move
move = engine.get_best_move(game_state)
```

### Adjusting Strength

```python
# Change ELO dynamically
engine.set_elo(1800)

# Engine now plays at 1800 strength
move = engine.get_best_move(game_state)
```

### With Time Control

```python
# Get move with time limit (adjusted by ELO)
move = engine.get_best_move(game_state, time_ms=5000)

# At 400 ELO: uses 500ms (0.1x multiplier)
# At 2400 ELO: uses 5000ms (1.0x multiplier)
```

## Testing

The ELO system includes comprehensive tests in `tests/test_elo.py`:

- **Monotonic scaling:** All parameters scale correctly with ELO
- **Deterministic behavior:** Seeded random operations are reproducible
- **Forced mate handling:** Never blunders mates at any ELO
- **Noise injection:** Proper range and distribution
- **Move selection:** Correct probabilistic behavior

Run tests:
```bash
pytest tests/test_elo.py -v
```

## Design Rationale

### Why These Parameters?

1. **Depth** - Most important for tactical strength. Linear scaling provides smooth progression.

2. **Time** - Affects node count and search quality. Lower ELO players don't benefit from extra time as much.

3. **Noise** - Simulates evaluation errors. Quadratic decay because beginners make exponentially more mistakes.

4. **Move selection** - Simulates decision-making quality. Square-root curve provides gradual improvement.

### Why Quadratic Noise Decay?

Real chess players don't make mistakes uniformly. Beginners make many large blunders, while strong players make occasional small inaccuracies. The quadratic decay `(1-x)²` creates this realistic distribution:

- 400 ELO: 300cp noise (huge blunders)
- 800 ELO: 192cp noise (large mistakes)
- 1200 ELO: 108cp noise (moderate errors)
- 1600 ELO: 48cp noise (small inaccuracies)
- 2000 ELO: 12cp noise (tiny imperfections)
- 2400 ELO: 0cp noise (perfect)

### Why Square-Root Probability Curve?

The square-root curve `sqrt(x)` provides faster improvement at lower levels (where learning is rapid) and slower improvement at higher levels (where mastery is gradual):

- 400 ELO: 30% best move (beginner)
- 800 ELO: 51% best move (rapid improvement)
- 1200 ELO: 74% best move (good progress)
- 1600 ELO: 85% best move (strong play)
- 2000 ELO: 95% best move (near-perfect)
- 2400 ELO: 100% best move (perfect)

## Future Enhancements

Possible improvements to the ELO system:

1. **Opening book usage** - Higher ELO uses book more effectively
2. **Endgame tablebase** - Only available at high ELO
3. **Time management** - Better time allocation at higher ELO
4. **Blunder frequency** - Occasional large blunders at low ELO
5. **Positional understanding** - Adjust evaluation weights by ELO

## References

- ELO rating system: [Wikipedia](https://en.wikipedia.org/wiki/Elo_rating_system)
- Chess engine strength: Typical club player ~1200-1600, Expert ~1800-2000, Master ~2000-2200
- Centipawn values: Pawn=100, Knight/Bishop=300, Rook=500, Queen=900
