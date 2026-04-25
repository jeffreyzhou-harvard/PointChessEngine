"""ReAct-style reasoning trace for engine decisions.

The engine optionally records ``ReasoningStep`` entries while it searches and
selects a move. Each step is a Thought / Action / Observation triple, mirroring
the prompting pattern that drove the build itself. This lets users (and tests)
inspect *why* the engine made a particular move, not just *which* one.

The trace adds tiny overhead (a few list appends per move) and is opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ReasoningStep:
    thought: str
    action: str
    observation: str

    def render(self) -> str:
        return (
            f"Thought: {self.thought}\n"
            f"Action: {self.action}\n"
            f"Observation: {self.observation}"
        )


@dataclass
class ReasoningTrace:
    steps: List[ReasoningStep] = field(default_factory=list)
    final_move: Optional[str] = None
    final_score_cp: Optional[int] = None

    def add(self, thought: str, action: str, observation: str) -> None:
        self.steps.append(ReasoningStep(thought, action, observation))

    def render(self) -> str:
        out = [step.render() for step in self.steps]
        if self.final_move is not None:
            out.append(f"Decision: bestmove {self.final_move} ({self.final_score_cp}cp)")
        return "\n\n".join(out)
