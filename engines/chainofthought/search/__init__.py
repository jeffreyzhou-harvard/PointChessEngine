"""Search and evaluation.

Depends on ``core``. Does not depend on ``uci`` or ``ui``.
"""

from .engine import Engine, SearchLimits, SearchResult
from .elo import DEFAULT_ELO, EloConfig, MAX_ELO, MIN_ELO, config_from_elo
from .evaluation import evaluate, Weights, DEFAULT_WEIGHTS, MATE_SCORE

__all__ = [
    "Engine",
    "SearchLimits",
    "SearchResult",
    "EloConfig",
    "config_from_elo",
    "DEFAULT_ELO",
    "MIN_ELO",
    "MAX_ELO",
    "evaluate",
    "Weights",
    "DEFAULT_WEIGHTS",
    "MATE_SCORE",
]
