"""LLM Ensemble Chess Engine.

Five large-language-model chess advisors vote on each move.
The ensemble uses alpha-beta search to generate candidate moves,
presents them to all five LLMs in parallel, then aggregates their
votes to pick the final move.

LLMs used:
- GPT-4o (OpenAI)
- Claude (Anthropic)
- Gemini 1.5 Pro (Google)
- Grok-2 (xAI)
- DeepSeek Chat (DeepSeek)
"""

__version__ = "1.0.0"
