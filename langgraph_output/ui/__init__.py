"""
Browser-based user interface module.

This module implements a web-based interface for playing against the engine.

Features:
- Chessboard display with piece symbols
- Move input via click-to-move
- Game controls (new game, resign, side selection)
- ELO slider (400-2400)
- Move history display
- Game status display
- Promotion modal for pawn promotion

Usage:
    python -m ui.server
    
    Or programmatically:
    from ui import start_server
    start_server(port=8000)

Public API:
    - start_server: Start web server
    - GameSession: Game session management
"""

from .server import start_server
from .session import GameSession

__all__ = [
    'start_server',
    'GameSession',
]
