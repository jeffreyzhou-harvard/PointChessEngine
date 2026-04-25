"""
Search module - chess engine search and evaluation.

Exports:
- Engine: Main engine interface
- SearchLimits: Search constraints
- SearchResult: Search result with analysis
- EloConfig: ELO-based strength configuration
- config_from_elo: Factory function for ELO configuration
- Evaluator: Position evaluator
- Searcher: Search algorithms
- TranspositionTable: Position cache
"""

from .engine import Engine
from .search import SearchLimits, SearchResult, Searcher
from .evaluation import Evaluator
from .transposition import TranspositionTable
from .elo import EloConfig, config_from_elo

__all__ = [
    'Engine',
    'SearchLimits',
    'SearchResult',
    'Searcher',
    'Evaluator',
    'TranspositionTable',
    'EloConfig',
    'config_from_elo'
]
