"""End-to-end orchestration: env -> ballot -> contract -> build."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from methodologies.ensemble.ballot import (
    EnsembleResult,
    Voter,
    default_voters,
    render_design_contract,
    render_full_transcript,
    run_ensemble,
)
from methodologies.ensemble.builder import BuildResult, run_build
from methodologies.ensemble.providers import PROVIDERS

DEFAULT_OUTPUT_DIR = "./engines/ensemble"


def default_brief() -> str:
    return (
        "Build a complete pure-Python chess engine (UCI + ELO slider + "
        "playable UI + tests) by VOTING on its design across multiple "
        "model families - no judge - and then having a single builder "
        "implement the contract."
    )


@dataclass
class RunResult:
    ensemble: EnsembleResult
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
    voters: list[Voter] | None = None,
    builder_provider: str = "anthropic",
    builder_model: str | None = None,
    skip_build: bool = False,
    max_build_iterations: int = 60,
    log: Callable[[str], None] | None = None,
) -> RunResult:
    _load_env()
    log = log or print

    log("[1/3] running ensemble vote...")
    ensemble = run_ensemble(voters=voters, log=log)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    contract_md = render_design_contract(ensemble)
    transcript_md = render_full_transcript(ensemble)
    docs_dir = output_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    contract_path = docs_dir / "design_contract.md"
    transcript_path = docs_dir / "ballot_transcript.md"
    contract_path.write_text(contract_md, encoding="utf-8")
    transcript_path.write_text(transcript_md, encoding="utf-8")
    log(f"[2/3] design contract written to {contract_path}")

    if skip_build:
        log("[3/3] build phase SKIPPED")
        return RunResult(
            ensemble=ensemble,
            build=BuildResult(output_dir=output_dir, stop_reason="skipped"),
            contract_path=contract_path,
            transcript_path=transcript_path,
        )

    builder_label = PROVIDERS[builder_provider].label
    log(f"[3/3] running build phase (builder = {builder_label})...")
    build = run_build(
        design_contract=contract_md,
        output_dir=output_dir,
        model=builder_model or PROVIDERS[builder_provider].default_model,
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
        ensemble=ensemble,
        build=build,
        contract_path=contract_path,
        transcript_path=transcript_path,
    )


def summarize(result: RunResult) -> str:
    lines: list[str] = []
    lines.append(f"output_dir:    {result.build.output_dir}")
    lines.append(f"contract:      {result.contract_path}")
    lines.append(f"transcript:    {result.transcript_path}")
    lines.append(f"voters:        {', '.join(result.ensemble.voters_used)}")
    lines.append(f"topics:        {len(result.ensemble.topics)}")
    winners = [f"{t.topic['id']}:{t.winner_label}" for t in result.ensemble.topics]
    lines.append(f"winners:       {', '.join(winners)}")
    lines.append(f"build_iters:   {result.build.iterations}")
    lines.append(f"tool_calls:    {result.build.tool_calls}")
    lines.append(f"files_written: {len(result.build.files_written)}")
    if result.build.pytest_runs:
        last = result.build.pytest_runs[-1]
        lines.append(f"last_pytest:   exit={last.get('returncode')}")
    return "\n".join(lines)
