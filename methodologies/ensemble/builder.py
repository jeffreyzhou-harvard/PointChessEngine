"""Lead-architect build phase: Claude tool-use loop, governed by the contract."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from methodologies.ensemble.prompts import BUILD_SYSTEM, build_user_message
from methodologies.ensemble.providers import PROVIDERS
from methodologies.ensemble.tools import TOOL_SCHEMAS, ToolRecorder, make_dispatch


@dataclass
class BuildResult:
    output_dir: Path
    iterations: int = 0
    tool_calls: int = 0
    files_written: list[tuple[str, str]] = field(default_factory=list)
    pytest_runs: list[dict] = field(default_factory=list)
    final_text: str = ""
    stop_reason: str = ""


def run_build(
    design_contract: str,
    output_dir: str | Path,
    *,
    model: str | None = None,
    max_iterations: int = 60,
    max_tokens_per_step: int = 8192,
    log: Callable[[str], None] | None = None,
) -> BuildResult:
    """Drive the Claude tool-use loop until the engine is built.

    The loop terminates when Claude returns ``stop_reason == "end_turn"``
    (no more tool calls) or when ``max_iterations`` is reached.
    """
    info = PROVIDERS["anthropic"]
    api_key = os.environ.get(info.env_key) or os.environ.get(info.env_key.replace("_API_KEY", "_KEY"))
    if not api_key:
        raise RuntimeError(f"missing env var {info.env_key} for the lead architect")
    model = model or info.default_model
    log = log or (lambda msg: None)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    output_dir = Path(output_dir)
    dispatch, recorder = make_dispatch(output_dir)

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_user_message(design_contract)},
    ]

    result = BuildResult(output_dir=output_dir)
    for it in range(max_iterations):
        result.iterations = it + 1
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens_per_step,
            system=BUILD_SYSTEM,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Append assistant turn verbatim so subsequent turns see context.
        assistant_blocks = [b.model_dump() for b in resp.content]
        messages.append({"role": "assistant", "content": assistant_blocks})

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        text_blocks = [b for b in resp.content if getattr(b, "type", None) == "text"]
        if text_blocks:
            preview = " | ".join(b.text.strip().splitlines()[0] for b in text_blocks if b.text.strip())[:160]
            if preview:
                log(f"  [step {it+1:02d}] {preview}")

        if not tool_uses:
            # No tools called: Claude has nothing more to do.
            result.final_text = "\n".join(b.text for b in text_blocks).strip()
            result.stop_reason = resp.stop_reason or "end_turn"
            break

        # Run all tool calls in this turn, then send a single user message
        # back containing tool_result blocks (Anthropic's required format).
        tool_results: list[dict[str, Any]] = []
        for tu in tool_uses:
            result.tool_calls += 1
            args = tu.input or {}
            output = dispatch(tu.name, args)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": output,
            })
            log(f"      tool {tu.name} -> {output.splitlines()[0][:120]}")
        messages.append({"role": "user", "content": tool_results})
    else:
        result.stop_reason = "max_iterations"
        log(f"  build halted: max_iterations={max_iterations} reached")

    result.files_written = list(recorder.writes)
    result.pytest_runs = list(recorder.pytest_runs)
    return result
