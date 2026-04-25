"""
ELO strength configuration.

Maps ELO rating (400-2400) to engine parameters for believable strength adjustment.

Implements:
- EloConfig dataclass with all strength parameters
- config_from_elo(elo) factory function
- Noise injection and move selection strategies
- Monotonic depth scaling

ELO Mapping Table:
==================
ELO  | Depth | Time Mult | Noise (cp) | Best Move Prob | Description
-----|-------|-----------|------------|----------------|------------------
400  |   1   |   0.10    |    300     |     0.30       | Beginner
600  |   2   |   0.20    |    250     |     0.40       | Novice
800  |   2   |   0.30    |    200     |     0.50       | Casual
1000 |   3   |   0.40    |    150     |     0.60       | Club player
1200 |   4   |   0.50    |    100     |     0.70       | Intermediate
1400 |   4   |   0.60    |     70     |     0.78       | Advanced
1600 |   5   |   0.70    |     45     |     0.85       | Strong club
1800 |   6   |   0.80    |     25     |     0.91       | Expert
2000 |   6   |   0.90    |     12     |     0.95       | Master
2200 |   7   |   0.95    |      5     |     0.98       | Strong master
2400  |   8   |   1.00    |      0     |     1.00       | Near-engine

Strategy:
---------
- Depth: Linear scaling from 1 to 8 (primary strength factor)
- Time: Linear scaling from 0.1x to 1.0x (affects node count)
- Noise: Quadratic decay (more mistakes at low ELO)
- Best move probability: Square-root curve (gradual improvement)
- Move selection: Weighted choice from top-3 when not choosing best

This creates believable play at all levels:
- Low ELO: shallow search + high noise + frequent suboptimal moves
- Mid ELO: moderate depth + some noise + occasional mistakes
- High ELO: deep search + minimal noise + rare mistakes
"""

import random
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class EloConfig:
    """
    ELO-based strength configuration.
    
    Attributes:
        elo_rating: Target ELO rating (400-2400)
        base_depth: Base search depth (1-8)
        time_multiplier: Time allocation factor (0.1-1.0)
        eval_noise: Evaluation noise in centipawns (0-300)
        best_move_probability: Probability of choosing best move (0.3-1.0)
    """
    elo_rating: int
    base_depth: int
    time_multiplier: float
    eval_noise: int
    best_move_probability: float
    
    def __post_init__(self):
        """Validate configuration."""
        assert 400 <= self.elo_rating <= 2400, f"ELO must be 400-2400, got {self.elo_rating}"
        assert 1 <= self.base_depth <= 8, f"Depth must be 1-8, got {self.base_depth}"
        assert 0.0 <= self.time_multiplier <= 1.0, f"Time multiplier must be 0-1, got {self.time_multiplier}"
        assert 0 <= self.eval_noise <= 300, f"Noise must be 0-300, got {self.eval_noise}"
        assert 0.0 <= self.best_move_probability <= 1.0, f"Best move prob must be 0-1, got {self.best_move_probability}"
    
    def add_noise_to_score(self, score: int, seed: Optional[int] = None) -> int:
        """
        Add random noise to evaluation score.
        
        Args:
            score: Original score in centipawns
            seed: Optional random seed for deterministic testing
        
        Returns:
            Score with noise added
        """
        if self.eval_noise == 0:
            return score
        
        if seed is not None:
            random.seed(seed)
        
        noise = random.randint(-self.eval_noise, self.eval_noise)
        return score + noise
    
    def select_move(self, moves_with_scores: List[Tuple], seed: Optional[int] = None) -> Optional:
        """
        Select move based on ELO configuration.
        
        Uses probabilistic selection:
        - With best_move_probability: choose best move
        - Otherwise: weighted choice from top-3 (best=3, second=2, third=1)
        
        Args:
            moves_with_scores: List of (move, score) tuples, sorted by score (best first)
            seed: Optional random seed for deterministic testing
        
        Returns:
            Selected move, or None if no moves available
        """
        if not moves_with_scores:
            return None
        
        if seed is not None:
            random.seed(seed)
        
        # Always choose best move with configured probability
        if random.random() < self.best_move_probability:
            return moves_with_scores[0][0]
        
        # Otherwise, choose from top 3 moves with weighted probability
        top_moves = moves_with_scores[:min(3, len(moves_with_scores))]
        
        # Weight by rank: best=3, second=2, third=1
        weights = [len(top_moves) - i for i in range(len(top_moves))]
        total_weight = sum(weights)
        
        rand = random.random() * total_weight
        cumulative = 0
        
        for i, weight in enumerate(weights):
            cumulative += weight
            if rand <= cumulative:
                return top_moves[i][0]
        
        # Fallback (should rarely happen)
        return top_moves[-1][0]
    
    def should_blunder_mate(self, is_forced_mate: bool, seed: Optional[int] = None) -> bool:
        """
        Determine if engine should blunder a forced mate.
        
        Never blunders forced mates (requirement from brief).
        
        Args:
            is_forced_mate: Whether position has forced mate
            seed: Optional random seed (unused, for API consistency)
        
        Returns:
            False (never blunder forced mates)
        """
        return False
    
    def __str__(self) -> str:
        """String representation."""
        return (f"EloConfig(rating={self.elo_rating}, depth={self.base_depth}, "
                f"noise={self.eval_noise}cp, best_prob={self.best_move_probability:.2f})")


def config_from_elo(elo: int) -> EloConfig:
    """
    Create EloConfig from ELO rating.
    
    Factory function that maps ELO rating to all engine parameters.
    
    Args:
        elo: ELO rating (400-2400)
    
    Returns:
        EloConfig with appropriate parameters
    """
    # Clamp to valid range
    elo = max(400, min(2400, elo))
    
    # Calculate parameters
    depth = _depth_for_elo(elo)
    time_mult = _time_multiplier_for_elo(elo)
    noise = _noise_for_elo(elo)
    best_prob = _best_move_prob_for_elo(elo)
    
    return EloConfig(
        elo_rating=elo,
        base_depth=depth,
        time_multiplier=time_mult,
        eval_noise=noise,
        best_move_probability=best_prob
    )


def _depth_for_elo(elo: int) -> int:
    """
    Calculate search depth for ELO rating.
    
    Linear mapping: 400 ELO -> depth 1, 2400 ELO -> depth 8
    
    Args:
        elo: ELO rating (400-2400)
    
    Returns:
        Search depth (1-8)
    """
    if elo <= 400:
        return 1
    elif elo >= 2400:
        return 8
    else:
        # Linear interpolation
        return int(1 + (elo - 400) * 7 / 2000)


def _time_multiplier_for_elo(elo: int) -> float:
    """
    Calculate time multiplier for ELO rating.
    
    Linear mapping: lower ELO = faster moves (less thinking time)
    
    Args:
        elo: ELO rating (400-2400)
    
    Returns:
        Time multiplier (0.1-1.0)
    """
    if elo <= 400:
        return 0.1
    elif elo >= 2400:
        return 1.0
    else:
        return 0.1 + (elo - 400) * 0.9 / 2000


def _noise_for_elo(elo: int) -> int:
    """
    Calculate evaluation noise for ELO rating.
    
    Quadratic decay: more noise at low ELO (exponential mistakes)
    
    Args:
        elo: ELO rating (400-2400)
    
    Returns:
        Noise in centipawns (0-300)
    """
    if elo <= 400:
        return 300
    elif elo >= 2400:
        return 0
    else:
        # Quadratic decay for more realistic mistake distribution
        normalized = (elo - 400) / 2000  # 0 to 1
        return int(300 * (1 - normalized) ** 2)


def _best_move_prob_for_elo(elo: int) -> float:
    """
    Calculate best-move probability for ELO rating.
    
    Square-root curve: gradual improvement in move selection
    
    Args:
        elo: ELO rating (400-2400)
    
    Returns:
        Probability of choosing best move (0.3-1.0)
    """
    if elo <= 400:
        return 0.3
    elif elo >= 2400:
        return 1.0
    else:
        # Square-root curve for gradual improvement
        normalized = (elo - 400) / 2000  # 0 to 1
        return 0.3 + 0.7 * (normalized ** 0.5)
