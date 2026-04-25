"""
Universal Chess Interface (UCI) protocol module.

This module implements the UCI protocol for chess engine communication.

Supported commands:
- uci: Identify engine
- isready: Synchronization
- ucinewgame: Reset game state
- position: Set position (FEN or startpos with moves)
- go: Start search
- stop: Halt search
- quit: Exit
- setoption: Set engine options (ELO, Hash)
- debug: Toggle debug mode

Public API:
    - UCIProtocol: Main protocol handler
    - run_uci: Run UCI protocol loop
"""

from .protocol import UCIProtocol, run_uci

__all__ = [
    'UCIProtocol',
    'run_uci',
]
