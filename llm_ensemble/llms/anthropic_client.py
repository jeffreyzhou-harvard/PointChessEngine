"""Anthropic Claude voting client."""

from __future__ import annotations

import time
from typing import List

from .base import LLMClient, VoteResult, build_prompt, parse_move
from ..config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, MAX_RESPONSE_TOKENS, LLM_TEMPERATURE


class AnthropicClient(LLMClient):
    """Votes using Anthropic's Claude model."""

    name = "Claude"

    def __init__(self) -> None:
        try:
            import anthropic as _anthropic  # type: ignore
            self._client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
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
                explanation="anthropic package not installed",
                raw_response="",
                success=False,
                latency_ms=0,
            )
        try:
            prompt = build_prompt(fen, candidates, side_to_move, move_number)
            response = self._client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_RESPONSE_TOKENS,
                temperature=LLM_TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip() if response.content else ""
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
