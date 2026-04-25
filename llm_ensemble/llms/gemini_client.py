"""Google Gemini voting client."""

from __future__ import annotations

import time
from typing import List

from .base import LLMClient, VoteResult, build_prompt, parse_move
from ..config import GEMINI_API_KEY, GEMINI_MODEL, LLM_TEMPERATURE


class GeminiClient(LLMClient):
    """Votes using Google Gemini 1.5 Pro."""

    name = "Gemini"

    def __init__(self) -> None:
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=GEMINI_API_KEY)
            self._model = genai.GenerativeModel(GEMINI_MODEL)
            self._genai = genai
            self._available = True
        except ImportError:
            self._model = None
            self._genai = None
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
                explanation="google-generativeai package not installed",
                raw_response="",
                success=False,
                latency_ms=0,
            )
        try:
            prompt = build_prompt(fen, candidates, side_to_move, move_number)
            generation_config = self._genai.types.GenerationConfig(
                temperature=LLM_TEMPERATURE,
                max_output_tokens=50,
            )
            response = self._model.generate_content(
                prompt,
                generation_config=generation_config,
            )
            raw = response.text.strip() if response.text else ""
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
