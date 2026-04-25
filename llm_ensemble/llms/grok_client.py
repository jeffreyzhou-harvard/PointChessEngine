"""xAI Grok voting client (OpenAI-compatible API)."""

from __future__ import annotations

import time
from typing import List

from .base import LLMClient, VoteResult, build_prompt, parse_move
from ..config import (
    GROK_API_KEY,
    GROK_MODEL,
    GROK_BASE_URL,
    MAX_RESPONSE_TOKENS,
    LLM_TEMPERATURE,
)


class GrokClient(LLMClient):
    """Votes using xAI's Grok model via OpenAI-compatible API."""

    name = "Grok"

    def __init__(self) -> None:
        try:
            from openai import OpenAI  # type: ignore
            self._client = OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL)
            self._available = True
        except ImportError:
            self._client = None
            self._available = False

    def vote(
        self,
        fen: str,
        candidates: List[str],
        side_to_move: str,
        move_number: int,
    ) -> VoteResult:
        start = time.monotonic()
        if not self._available:
            return VoteResult(
                llm_name=self.name,
                chosen_move=None,
                explanation="openai package not installed (needed for Grok)",
                raw_response="",
                success=False,
                latency_ms=0,
            )
        try:
            prompt = build_prompt(fen, candidates, side_to_move, move_number)
            response = self._client.chat.completions.create(
                model=GROK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=MAX_RESPONSE_TOKENS,
                temperature=LLM_TEMPERATURE,
            )
            raw = (response.choices[0].message.content or "").strip()
            move = parse_move(raw, candidates)
            latency_ms = int((time.monotonic() - start) * 1000)
            return VoteResult(
                llm_name=self.name,
                chosen_move=move,
                explanation=raw,
                raw_response=raw,
                success=move is not None,
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.monotonic() - start) * 1000)
            return VoteResult(
                llm_name=self.name,
                chosen_move=None,
                explanation=str(exc),
                raw_response=str(exc),
                success=False,
                latency_ms=latency_ms,
            )
