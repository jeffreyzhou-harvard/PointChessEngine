"""LLM Ensemble configuration.

Set your API keys here (or via environment variables).
"""

import os
from pathlib import Path

# Load .env file if present (never committed to git)
try:
    from dotenv import load_dotenv
    _env = Path(__file__).parent / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass  # python-dotenv not installed; fall back to shell env vars

# ---------------------------------------------------------------------------
# API Keys — set in llm_ensemble/.env or as shell environment variables
# ---------------------------------------------------------------------------

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "PLACEHOLDER_OPENAI_API_KEY")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "PLACEHOLDER_ANTHROPIC_API_KEY")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "PLACEHOLDER_GEMINI_API_KEY")
GROK_API_KEY: str = os.getenv("GROK_API_KEY", "PLACEHOLDER_GROK_API_KEY")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "PLACEHOLDER_DEEPSEEK_API_KEY")

# ---------------------------------------------------------------------------
# Model names
# ---------------------------------------------------------------------------

OPENAI_MODEL: str = "gpt-4o"
ANTHROPIC_MODEL: str = "claude-opus-4-6"          # claude-sonnet-4-6 also works
GEMINI_MODEL: str = "gemini-1.5-pro"
GROK_MODEL: str = "grok-2-1212"
DEEPSEEK_MODEL: str = "deepseek-chat"

# ---------------------------------------------------------------------------
# API base URLs
# ---------------------------------------------------------------------------

GROK_BASE_URL: str = "https://api.x.ai/v1"
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

# ---------------------------------------------------------------------------
# Ensemble defaults
# ---------------------------------------------------------------------------

DEFAULT_ELO: int = 1500

# How long to wait for each LLM to respond (seconds)
VOTE_TIMEOUT_SECONDS: float = 45.0

# Number of candidate moves shown to the LLMs (overridden by ELO mapping)
DEFAULT_CANDIDATES: int = 5

# Maximum LLM tokens for the move response
MAX_RESPONSE_TOKENS: int = 50

# LLM temperature — low for deterministic move choice
LLM_TEMPERATURE: float = 0.1

# ---------------------------------------------------------------------------
# Voting methods
# ---------------------------------------------------------------------------

VOTING_METHOD_PLURALITY = "plurality"
VOTING_METHOD_SCORE_WEIGHTED = "score_weighted"
VOTING_METHOD_CONSENSUS = "consensus"

DEFAULT_VOTING_METHOD: str = VOTING_METHOD_PLURALITY
