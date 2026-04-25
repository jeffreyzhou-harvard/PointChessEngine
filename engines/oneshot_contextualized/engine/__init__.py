"""Contextualized chess engine package.

Public surface:
    Engine      -- high-level facade used by both UCI and the web UI.
    Game        -- thin wrapper around chess.Board with history and PGN.
    config_from_elo, StrengthConfig
"""

from .engine import Engine
from .game import Game
from .elo import StrengthConfig, config_from_elo

__all__ = ["Engine", "Game", "StrengthConfig", "config_from_elo"]
