"""End-to-end orchestration: env -> council -> contract -> build."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from methodologies.debate.builder import BuildResult, run_build
from methodologies.debate.council import (
    Advisor,
    CouncilResult,
    default_advisors,
    render_design_contract,
    render_full_transcript,
    run_council,
)
from methodologies.debate.providers import PROVIDERS

DEFAULT_OUTPUT_DIR = "./engines/debate"


def default_brief() -> str:
    """Short tagline shown at the top of run logs."""
    return (
        "Build a complete pure-Python chess engine (UCI + ELO slider + "
        "playable UI + tests) by debating its design across multiple "
        "model families and letting Claude synthesise + build."
    )


@dataclass
class RunResult:
    council: CouncilResult
    build: BuildResult
    contract_path: Path
    transcript_path: Path


def _load_env() -> None:
    """Load .env, then bridge ANTHROPIC_KEY -> ANTHROPIC_API_KEY (legacy)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        alt = os.environ.get("ANTHROPIC_KEY")
        if alt:
            os.environ["ANTHROPIC_API_KEY"] = alt


def run(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    advisors: list[Advisor] | None = None,
    lead_provider: str = "anthropic",
    lead_model: str | None = None,
    skip_build: bool = False,
    max_build_iterations: int = 60,
    log: Callable[[str], None] | None = None,
) -> RunResult:
    _load_env()
    log = log or print

    log("[1/3] running council debate...")
    council = run_council(
        advisors=advisors,
        lead_provider=lead_provider,
        lead_model=lead_model,
        log=log,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    contract_md = render_design_contract(council)
    transcript_md = render_full_transcript(council)
    docs_dir = output_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    contract_path = docs_dir / "design_contract.md"
    transcript_path = docs_dir / "council_transcript.md"
    contract_path.write_text(contract_md, encoding="utf-8")
    transcript_path.write_text(transcript_md, encoding="utf-8")
    log(f"[2/3] design contract written to {contract_path}")

    if skip_build:
        log("[3/3] build phase SKIPPED")
        return RunResult(
            council=council,
            build=BuildResult(output_dir=output_dir, stop_reason="skipped"),
            contract_path=contract_path,
            transcript_path=transcript_path,
        )

    log(f"[3/3] running build phase (lead = {council.lead_label})...")
    build = run_build(
        design_contract=contract_md,
        output_dir=output_dir,
        model=lead_model or PROVIDERS[lead_provider].default_model,
        max_iterations=max_build_iterations,
        log=log,
    )
    log(
        f"build done: iterations={build.iterations} "
        f"tool_calls={build.tool_calls} "
        f"files_written={len(build.files_written)} "
        f"pytest_runs={len(build.pytest_runs)} "
        f"stop={build.stop_reason}"
    )

    return RunResult(
        council=council,
        build=build,
        contract_path=contract_path,
        transcript_path=transcript_path,
    )


def summarize(result: RunResult) -> str:
    lines: list[str] = []
    lines.append(f"output_dir:    {result.build.output_dir}")
    lines.append(f"contract:      {result.contract_path}")
    lines.append(f"transcript:    {result.transcript_path}")
    lines.append(f"advisors:      {', '.join(result.council.advisors_used)}")
    lines.append(f"lead:          {result.council.lead_label}")
    lines.append(f"topics:        {len(result.council.topics)}")
    lines.append(f"build_iters:   {result.build.iterations}")
    lines.append(f"tool_calls:    {result.build.tool_calls}")
    lines.append(f"files_written: {len(result.build.files_written)}")
    if result.build.pytest_runs:
        last = result.build.pytest_runs[-1]
        lines.append(f"last_pytest:   exit={last.get('returncode')}")
    return "\n".join(lines)
