"""LLM client implementations.

Each client wraps one LLM provider's API and exposes a uniform
``vote(fen, candidates, side_to_move, move_number) -> VoteResult``
interface.
"""

from .base import LLMClient, VoteResult
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .gemini_client import GeminiClient
from .grok_client import GrokClient
from .deepseek_client import DeepSeekClient


def all_clients() -> list:
    """Instantiate all five LLM clients. Import errors are surfaced here."""
    return [
        OpenAIClient(),
        AnthropicClient(),
        GeminiClient(),
        GrokClient(),
        DeepSeekClient(),
    ]


__all__ = [
    "LLMClient",
    "VoteResult",
    "OpenAIClient",
    "AnthropicClient",
    "GeminiClient",
    "GrokClient",
    "DeepSeekClient",
    "all_clients",
]
