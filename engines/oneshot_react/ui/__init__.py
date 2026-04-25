"""Browser-based UI for human-vs-engine play."""

from .server import create_server, GameSession

__all__ = ["create_server", "GameSession"]
