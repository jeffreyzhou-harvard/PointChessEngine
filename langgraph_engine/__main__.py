"""CLI entry point: ``python -m langgraph_engine``.

Examples
--------

    # Run the orchestrator with defaults (claude-sonnet-4-5 -> ./langgraph_output)
    python -m langgraph_engine

    # Custom output directory and a stronger model with one rework pass
    python -m langgraph_engine --output ./out --model claude-opus-4-5 --revisions 1

    # Pass extra context for the Context Analyst to assess
    python -m langgraph_engine --context https://github.com/lichess-org/scalachess

    # Dry-run: build the graph but skip invocation (useful to confirm
    # the package + .env wiring before spending tokens)
    python -m langgraph_engine --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from langgraph_engine.runner import (
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_DIR,
    _load_env_key,
    default_brief,
    run,
    summarize,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m langgraph_engine",
        description="LangGraph multi-agent chess-engine builder.",
    )
    p.add_argument(
        "--output", default=DEFAULT_OUTPUT_DIR,
        help="Directory the agents are allowed to write (created if missing).",
    )
    p.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Anthropic model name (default: {DEFAULT_MODEL}).",
    )
    p.add_argument(
        "--revisions", type=int, default=1,
        help="Max integrator->specialist rework passes (default: 1).",
    )
    p.add_argument(
        "--context", action="append", default=[],
        help="Optional context entry for the Context Analyst (repeatable).",
    )
    p.add_argument(
        "--brief", default=None,
        help="Override the project brief (defaults to the chess-engine brief).",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-stage progress lines.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Set up env + graph but do NOT invoke any agents.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    _load_env_key()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write(
            "ERROR: no Anthropic API key found. Set ANTHROPIC_KEY in .env "
            "(or ANTHROPIC_API_KEY in your shell).\n"
        )
        return 2

    if args.dry_run:
        # Build the graph once to make sure imports + wiring are clean.
        from langgraph_engine import build_graph  # noqa: F401  (import-time check)
        from langgraph_engine.runner import _make_llm

        _make_llm(args.model)  # only validates the model name
        sys.stdout.write(
            f"[dry-run] env OK, model={args.model}, output={args.output}, "
            f"revisions={args.revisions}\n"
        )
        return 0

    sys.stdout.write(
        f"[run] model={args.model} output={args.output} "
        f"revisions={args.revisions} context_inputs={len(args.context)}\n"
    )
    state = run(
        brief=args.brief or default_brief(),
        context_inputs=args.context,
        output_dir=Path(args.output),
        model=args.model,
        max_revision_passes=args.revisions,
        print_progress=not args.quiet,
    )
    sys.stdout.write("\n=== orchestration complete ===\n")
    sys.stdout.write(summarize(state) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
